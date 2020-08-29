import control.format
import socket
import pymongo
import time
from bson import ObjectId, DBRef


def get_task(cli):
    task_list = []
    while True:
        task_data = cli.recv(36)
        task = control.format.TaskCmd.decode(task_data)
        print(
            task.ucType,
            task.ucEnd,
            control.format.ObjectId.from_array(task._drone).to_string(),
            control.format.ObjectId.from_array(task._task).to_string(),
            task.ucTaskType,
            task.nLen
        )
        if task.nLen:
            task_content = cli.recv(task.nLen * 24)
            task.content = control.format.decode_position_array(task_content)
        task_list.append(task)
        if task.ucEnd == 1:
            break
    return task_list


def run():
    db_client = pymongo.MongoClient("127.0.0.1", 27017)
    db_hardware = db_client["hardware"]
    db_hardware.authenticate("admin", "12345678")
    db_hardware["task"].insert_many([{
        "type": "mission",
        "drone": DBRef("drone", ObjectId("5f3f217deb05450df65cda10")),
        "waypoint": [
            [1, 2, 3],
            [4, 5, 6]
        ],
        "status": "pending"
    }, {
        "type": "mission",
        "drone": DBRef("drone", ObjectId("5f3f217deb05450df65cda10")),
        "waypoint": [
            [4, 5, 6],
            [7, 8, 9]
        ],
        "status": "pending"
    }])
    db_client.close()

    cli = socket.socket()
    cli.connect(("127.0.0.1", 3000))
    welcome_cmd = control.format.WelcomeCmd()
    welcome_cmd._drone = control.format.ObjectId.from_number(0x5f3f217deb05450df65cda10)
    welcome_cmd.ucBatteryH = 0x64
    welcome_cmd.ucBatteryL = 0x00
    welcome_cmd.nTimeStamp = 31
    cli.send(welcome_cmd.encode())
    pos = []
    while True:
        tasks = get_task(cli)
        for task in tasks:
            if task.nLen > 0:
                print(task.content)

        reply = control.format.ReplyCmd()
        reply._drone = control.format.ObjectId.from_number(0x5f3f217deb05450df65cda10)
        reply._task = control.format.ObjectId.from_array(tasks[-1]._task)
        if tasks[0].nLen > 0:
            pos = tasks[0].content[-1]
        reply.dPos[0] = pos[0]
        reply.dPos[1] = pos[1]
        reply.dPos[2] = pos[2]
        reply.ucBatteryL = 0
        reply.ucBatteryH = 0x64
        reply.nTimeStamp = int(time.time())
        cli.send(reply.encode())
        time.sleep(1)

    exit_cmd = control.format.ReplyCmd()
    exit_cmd.ucType = 0xfc
    exit_cmd._drone = control.format.ObjectId.from_number(0x5f3f217deb05450df65cda10)
    cli.send(exit_cmd.encode())
    cli.close()


if __name__ == "__main__":
    run()
