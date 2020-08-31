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

    def generate_command(self, task, end=True):
        """
        生成并发送飞行指令
        :param dict task:
        :param bool end:
        :return: None
        """
        package = control.format.generate_package(control.format.PACKAGE_TASK_CMD,
                                                  ucChunked=0 if end else 1,
                                                  task=control.format.ObjectId.from_str(str(task["_id"])),
                                                  ucTaskType={
                                                      "idle": 0x00,
                                                      "load": 0x01,
                                                      "mission": 0x03,
                                                      "unload": 0x07
                                                  }[task["type"]],
                                                  nLen=len(task["waypoint"]) if "waypoint" in task else 0,
                                                  content=task["waypoint"] if "waypoint" in task else [])
        while self.sock_send(package) is None and self.parent.open:
            pass

    def parse_reply(self):
        """
        解析飞机回复
        :return:
        """
        try:
            reply = control.format.Package.read(self.parent.socket)
        except ConnectionResetError:
            self.reconnect()
            return None

        if reply.ucType == 0xfd:  # 退出状态
            if reply.ucReason == 0x00:
                logger.info("Drone %s shut down" % (self.parent.drone_id, ))
            else:
                logger.error("Drone %s emergency shut down" % (self.parent.drone_id, ))
            self.parent.stop()

        return reply

    def error_logic(self):
        logger.warning("Drone %s status error" % (self.parent.drone_id, ))
        self.state = "error"

    def reconnect(self):
        logger.warning("Drone %s disconnected" % (self.parent.drone_id, ))
        self.state = "disconnected"
        self.parent.stop()

    def run(self):
        while self.parent.open:
            # 1. 查询任务
            if self.cur_task is None or self.cur_task["type"] == "idle":
                tasks = self.parent.db_hardware["task"].find({
                    "type": {"$ne": "idle"},
                    "drone.$id": ObjectId(self.parent.drone_id),
                    "status": "pending"
                }).sort([
                    ("importance", pymongo.DESCENDING),
                    ("_id", pymongo.ASCENDING)
                ]).limit(2)
                try:
                    self.cur_task = tasks.next()
                except StopIteration:  # 库内无任务
                    self.next_task = None
                    if self.cur_task is None:  # 当前无任务，则当前任务为空闲
                        self.cur_task = {
                            "type": "idle",
                            "drone": DBRef("drone", ObjectId(self.parent.drone_id)),
                            "status": "ongoing",
                            "finish": 0
                        }
                        self.cur_task["_id"] = self.parent.db_hardware["task"].insert_one(self.cur_task).inserted_id
                else:
                    try:
                        self.next_task = tasks.next()
                    except StopIteration:  # 没有下一个任务，则下一个任务为空闲
                        self.next_task = {
                            "type": "idle",
                            "drone": DBRef("drone", ObjectId(self.parent.drone_id)),
                            "status": "ongoing",
                            "finish": 0
                        }
                        self.next_task["_id"] = self.parent.db_hardware["task"].insert_one(self.next_task).inserted_id
            elif self.next_task is None or self.next_task["type"] == "idle":  # 下一个任务不存在或为空闲，查看有没有新的任务
                tasks = self.parent.db_hardware["task"].find({
                    "_id": {"$ne": self.cur_task["_id"] if self.cur_task else {}},
                    "type": {"$ne": "idle"},
                    "drone.$id": ObjectId(self.parent.drone_id),
                    "status": "pending"
                }).sort([
                    ("importance", pymongo.DESCENDING),
                    ("_id", pymongo.ASCENDING)
                ]).limit(1)
                try:
                    self.next_task = tasks.next()
                except StopIteration:  # 没有其它任务
                    if self.next_task is None:  # 没有现存的空闲任务，创建一个作为下一个任务
                        self.next_task = {
                            "type": "idle",
                            "drone": DBRef("drone", ObjectId(self.parent.drone_id)),
                            "status": "ongoing",
                            "finish": 0
                        }
                        self.next_task["_id"] = self.parent.db_hardware["task"].insert_one(self.next_task).inserted_id

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
                "task": ObjectId(control.format.ObjectId.from_array(reply.task).to_string()),
                "coordinates": geography.epsg4326_to_epsg3857([reply.dPosX, reply.dPosY, reply.dPosZ]),
                "speed": [reply.dSpdX, reply.dSpdY, reply.dSpdZ],
                "battery": reply.ucBatteryH + reply.ucBatteryL / 256,
                "time": reply.nTimeStamp
            })

            # 5. 更新task状态
            if self.next_task is not None and ObjectId(control.format.ObjectId.from_array(reply.task).to_string()) == self.next_task["_id"]:
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
            elif ObjectId(control.format.ObjectId.from_array(reply.task).to_string()) == self.cur_task["_id"]:
                if self.cur_task["status"] != "ongoing":
                    self.parent.db_hardware["task"].update({
                        "_id": self.cur_task["_id"]
                    }, {
                        "$set": {
                            "status": "ongoing"
                        }
                    })
            else:
                self.error_logic()
