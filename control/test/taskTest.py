import control.format
import socket
import pymongo
import time
from bson import ObjectId, DBRef


def get_task(cli):
    task_list = []
    while True:
        task = control.format.Package.read(cli)
        task_list.append(task)
        if task.ucChunked == 0:
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

    welcome = control.format.Package.read(cli)
    print(
        control.format.ObjectId.from_array(welcome.controller).to_string(),
        welcome.ucReconnect
    )

    cli.send(control.format.generate_package(control.format.PACKAGE_WELCOME_MSG,
                                             drone=control.format.ObjectId.from_number(0x5f3f217deb05450df65cda10),
                                             ucBatteryH=0x64,
                                             ucBatteryL=0x00,
                                             nTimeStamp=int(time.time())))
    pos = []
    while True:
        tasks = get_task(cli)
        for task in tasks:
            print(task.ucTaskType)
            if task.nLen > 0:
                print(task.content)

        if tasks[0].ucTaskType == 0x03:
            pos = tasks[0].content[-1]

        cli.send(control.format.generate_package(control.format.PACKAGE_STATUS_MSG,
                                                 task=control.format.ObjectId.from_array(tasks[-1].task),
                                                 dPosX=pos[0],
                                                 dPosY=pos[1],
                                                 dPosZ=pos[2],
                                                 ucBatteryL=0,
                                                 ucBatteryH=0x64,
                                                 nTimeStamp=int(time.time())))
        time.sleep(1)


if __name__ == "__main__":
    run()
