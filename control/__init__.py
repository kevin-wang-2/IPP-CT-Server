import pymongo
from multiprocessing import Process
import control.format
from bson import ObjectId

_config = {}


class ControlProcess(Process):
    def __init__(self, config, garage_id, drone_id, sock):
        """
        :param dict config:
        :param str garage_id:
        :param str drone_id:
        :param socket.socket sock:
        """
        super().__init__()
        global _config
        _config = config
        self.garage_id = garage_id
        self.drone_id = drone_id
        self.socket = sock
        self.socket_file = sock.makefile("rb+")

        self.db_client = pymongo.MongoClient(_config["db"]["ip"], _config["db"]["port"])
        self.db_map = self.db_client[_config["db"]["db"]["map"]]
        self.db_map.authenticate(_config["db"]["user"], _config["db"]["pwd"])
        self.db_hardware = self.db_client[_config["db"]["db"]["hardware"]]
        self.db_hardware.authenticate(_config["db"]["user"], _config["db"]["pwd"])
        self.db_business = self.db_client[_config["db"]["db"]["business"]]
        self.db_business.authenticate(_config["db"]["user"], _config["db"]["pwd"])

        self.open = True

    def stop(self):
        self.open = False
        self.terminate()

    def run(self):
        global _config
        while self.open:
            # 1. 查询任务
            tasks = self.db_hardware["task"].find({
                "type": {"$ne": "idle"},
                "drone.$id": ObjectId(self.drone_id),
                "$or": [
                    {"status": "pending"},
                    {"status": "ongoing"}]
            }).sort([
                ("importance", pymongo.DESCENDING),
                ("_id", pymongo.ASCENDING)
            ]).limit(2)
            try:
                cur_task = tasks.next()
            except StopIteration as e:  # 库内没有任务，添加idle任务
                cur_task = {
                    "type": "idle",
                    "status": "ongoing",
                    "finish": 0
                }
                cur_task["_id"] = self.db_hardware["task"].insert_one(cur_task).inserted_id

            try:
                next_task = tasks.next()
            except StopIteration as e:
                next_task = None

            # 2. 格式化并发送任务
            command = control.format.TaskCmd()

            # 2.1 当前指令
            command.ucEnd = next_task is None
            command._drone = control.format.ObjectId.from_str(self.drone_id)
            command._task = control.format.ObjectId.from_str(str(cur_task["_id"]))
            command.ucTaskType = {
                "idle": 0x00,
                "load": 0x01,
                "mission": 0x03,
                "unload": 0x07
            }[cur_task["type"]]
            command.nLen = len(cur_task["waypoint"]) if "waypoint" in cur_task else 0
            self.socket_file.write(command.encode())
            if "waypoint" in cur_task:
                self.socket_file.write(control.format.encode_double_array(cur_task["waypoint"], 2))

            # 2.2 下一指令
            if next_task is not None:
                command.ucEnd = 0
                command._task = control.format.ObjectId.from_str(str(next_task["_id"]))
                command.ucTaskType = {
                    "idle": 0x00,
                    "load": 0x01,
                    "mission": 0x03,
                    "unload": 0x07
                }[next_task["type"]]
                command.nLen = len(next_task["waypoint"]) if "waypoint" in next_task else 0
                self.socket_file.write(command.encode())
                if "waypoint" in next_task:
                    self.socket_file.write(control.format.encode_double_array(next_task["waypoint"], 2))

            # 3. 解析回复
            buffer = self.socket_file.read(1024)
            try:
                reply = control.format.ReplyCmd.decode(buffer)
            except control.format.ValidationError as e:
                continue
            if reply.ucType == 0xfc:  # 退出状态
                self.open = False

            # 4. 写入status状态
            self.db_hardware["status"].insert_one({
                "drone": ObjectId(self.drone_id),
                "task": ObjectId(control.format.ObjectId.from_array(reply._task).to_string()),
                "coordinates": [reply.dPos[0], reply.dPos[1], reply.dPos[2]],
                "speed": [reply.dSpd[0], reply.dSpd[1], reply.dSpd[2]],
                "battery": reply.ucBatteryH + reply.ucBatteryLow / 256,
                "time": reply.nTimeStamp
            })

            # 5. 更新task状态
            if ObjectId(control.format.ObjectId.from_array(reply._task).to_string()) != cur_task["_id"]:
                self.db_hardware["task"].update({
                    "_id": cur_task["_id"]
                }, {
                    "$set": {
                        "status": "finished"
                    }
                })
                self.db_hardware["task"].update({
                    "_id": next_task["_id"]
                }, {
                    "$set": {
                        "status": "ongoing"
                    }
                })

        self.socket.close()
        self.db_client.close()
