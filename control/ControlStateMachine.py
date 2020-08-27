import control.format
import pymongo
from bson import ObjectId


class ControlStateMachine:
    def __init__(self, parent):
        """
        :param control.ControlProcess parent:
        """
        self.parent = parent
        self.state = "idle"

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
        self.parent.socket_file.write(command.encode())
        if "waypoint" in task:
            self.parent.socket_file.write(control.format.encode_double_array(task["waypoint"], 2))

    def parse_reply(self):
        """
        解析飞机回复
        :return:
        """
        buffer = self.parent.socket_file.read(1024)
        try:
            reply = control.format.ReplyCmd.decode(buffer)
        except control.format.ValidationError as e:
            return None
        if reply.ucType == 0xfc:  # 退出状态
            self.parent.close()
        else:
            coordinates_epsg_4326 = [reply.dPos[0], reply.dPos[1], reply.dPos[2]]
        return reply

    def error_logic(self):
        self.state = "error"

    def run(self):
        while self.parent.open:
            # 1. 查询任务
            tasks = self.parent.db_hardware["task"].find({
                "type": {"$ne": "idle"},
                "drone.$id": ObjectId(self.parent.drone_id),
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
                cur_task["_id"] = self.parent.db_hardware["task"].insert_one(cur_task).inserted_id

            try:
                next_task = tasks.next()
            except StopIteration as e:
                next_task = None

            # 2. 格式化并发送任务

            # 2.1 当前指令
            self.generate_command(cur_task, next_task is None)

            # 2.2 下一指令
            if next_task is not None:
                self.generate_command(next_task)

            # 3. 解析回复
            reply = self.parse_reply()
            if reply is None:
                self.error_logic()
                continue
            elif not self.parent.open:
                break

            # 4. 写入status状态
            self.parent.db_hardware["status"].insert_one({
                "drone": ObjectId(self.parent.drone_id),
                "task": ObjectId(control.format.ObjectId.from_array(reply._task).to_string()),
                "coordinates": [reply.dPos[0], reply.dPos[1], reply.dPos[2]],
                "speed": [reply.dSpd[0], reply.dSpd[1], reply.dSpd[2]],
                "battery": reply.ucBatteryH + reply.ucBatteryLow / 256,
                "time": reply.nTimeStamp
            })

            # 5. 更新task状态
            if ObjectId(control.format.ObjectId.from_array(reply._task).to_string()) != cur_task["_id"]:
                self.parent.db_hardware["task"].update({
                    "_id": cur_task["_id"]
                }, {
                    "$set": {
                        "status": "finished"
                    }
                })
                self.parent.db_hardware["task"].update({
                    "_id": next_task["_id"]
                }, {
                    "$set": {
                        "status": "ongoing"
                    }
                })
