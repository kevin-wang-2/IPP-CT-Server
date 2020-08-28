import control.format
import pymongo
import socket
from bson import ObjectId, DBRef
import geography
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ControlStateMachine:
    def __init__(self, parent):
        """
        :param control.ControlProcess parent:
        """
        self.parent = parent
        self.state = "idle"
        self.cur_task = None
        self.next_task = None

    def sock_send(self, msg):
        try:
            return self.parent.socket.send(msg)
        except (ConnectionAbortedError, ConnectionResetError, socket.timeout) as e:
            self.reconnect()
            return None

    def sock_recv(self):
        try:
            return self.parent.socket.recv(1024)
        except (ConnectionAbortedError, ConnectionResetError, socket.timeout) as e:
            self.reconnect()
            return None

    def generate_command(self, task, end=False):
        """
        生成并发送飞行指令
        :param dict task:
        :param bool end:
        :return: None
        """
        command = control.format.TaskCmd()
        command.ucEnd = end
        command._drone = control.format.ObjectId.from_str(self.parent.drone_id)
        command._task = control.format.ObjectId.from_str(str(task["_id"]))
        command.ucTaskType = {
            "idle": 0x00,
            "load": 0x01,
            "mission": 0x03,
            "unload": 0x07
        }[task["type"]]
        command.nLen = len(task["waypoint"]) if "waypoint" in task else 0
        while self.sock_send(command.encode()) is None and self.parent.open:
            pass
        if "waypoint" in task:
            while self.sock_send(control.format.encode_double_array(task["waypoint"], 2)) is None and self.parent.open:
                pass

    def parse_reply(self):
        """
        解析飞机回复
        :return:
        """
        buffer = self.sock_recv()
        if buffer is None:
            return None

        try:
            reply = control.format.ReplyCmd.decode(buffer)
        except control.format.ValidationError as e:
            self.error_logic()
            return None

        if reply.ucType == 0xfc:  # 退出状态
            self.parent.stop()

        return reply

    def error_logic(self):
        self.state = "error"

    def reconnect(self):
        logger.warning("disconnected")
        self.state = "disconnected"
        self.parent.stop()

    def run(self):
        while self.parent.open:
            # 1. 查询任务
            if self.next_task is None:
                tasks = self.parent.db_hardware["task"].find({
                    "_id": {"$ne": self.cur_task["_id"]} if self.cur_task else {},
                    "type": {"$ne": "idle"},
                    "drone.$id": ObjectId(self.parent.drone_id),
                    "status": "pending"
                }).sort([
                    ("importance", pymongo.DESCENDING),
                    ("_id", pymongo.ASCENDING)
                ]).limit(1)
                try:
                    self.next_task = tasks.next()
                except StopIteration as e:
                    self.next_task = None
                if self.cur_task is None:
                    if self.next_task is None:
                        self.cur_task = {
                            "type": "idle",
                            "drone": DBRef("drone", ObjectId(self.parent.drone_id)),
                            "status": "ongoing",
                            "finish": 0
                        }
                        self.cur_task["_id"] = self.parent.db_hardware["task"].insert_one(self.cur_task).inserted_id
                    else:
                        self.cur_task = self.next_task
                        self.next_task = None
                elif self.cur_task["type"] == "idle" and self.next_task is not None:
                    self.cur_task = self.next_task
                    tasks = self.parent.db_hardware["task"].find({
                        "_id": {"$ne": self.cur_task["_id"]},
                        "type": {"$ne": "idle"},
                        "drone.$id": ObjectId(self.parent.drone_id),
                        "status": "pending"
                    }).sort([
                        ("importance", pymongo.DESCENDING),
                        ("_id", pymongo.ASCENDING)
                    ]).skip(1).limit(1)
                    try:
                        self.next_task = tasks.next()
                    except StopIteration as e:
                        self.next_task = None

            # 2. 格式化并发送任务

            # 2.1 当前指令
            self.generate_command(self.cur_task, self.next_task is None)

            # 2.2 下一指令
            if self.next_task is not None:
                self.generate_command(self.next_task)

            # 3. 解析回复
            reply = self.parse_reply()
            if reply is None:
                continue
            elif not self.parent.open:
                break

            # 4. 写入status状态
            self.parent.db_hardware["status"].insert_one({
                "drone": ObjectId(self.parent.drone_id),
                "task": ObjectId(control.format.ObjectId.from_array(reply._task).to_string()),
                "coordinates": geography.epsg4326_to_epsg3857([reply.dPos[0], reply.dPos[1], reply.dPos[2]]),
                "speed": [reply.dSpd[0], reply.dSpd[1], reply.dSpd[2]],
                "battery": reply.ucBatteryH + reply.ucBatteryL / 256,
                "time": reply.nTimeStamp
            })

            # 5. 更新task状态
            if ObjectId(control.format.ObjectId.from_array(reply._task).to_string()) == self.next_task["_id"]:
                self.parent.db_hardware["task"].update({
                    "_id": self.cur_task["_id"]
                }, {
                    "$set": {
                        "status": "finished"
                    }
                })
                self.parent.db_hardware["task"].update({
                    "_id": self.next_task["_id"]
                }, {
                    "$set": {
                        "status": "ongoing"
                    }
                })
                self.state = self.next_task["type"]
                self.cur_task = self.next_task
                self.next_task = None
