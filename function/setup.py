import pymongo
from bson.objectid import ObjectId
from bson.dbref import DBRef
import json
import socket
import function.hardware
import control


def get_host_ip():
    """
    查询本机ip地址
    :return:
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()

    return ip


def setup():
    """
    - 读取config
    - 自检
    1. 获取本机IP
    2. 检查和数据库间通信
    3. 初始化硬件
    - 更新硬件信息
    - 初始化控制服务器
    :return:
    """
    # 读取config
    config_file = open("./config/hardware_config.json", "r", encoding="utf-8")
    json_string = config_file.read()
    config = json.loads(json_string, encoding="utf-8")

    # 自检
    # 1.
    ip = get_host_ip()

    # 2.
    try:
        client = pymongo.MongoClient(config["db"]["ip"], config["db"]["port"])
        db = client[config["db"]["db"]["hardware"]]
        db.authenticate(config["db"]["user"], config["db"]["pwd"])
    except Exception as e:
        print("Cannot open MongoDB client")
        raise e

    # 3.
    try:
        hardware = function.hardware.Hardware(config)
    except Exception as e:
        print("Fail to initialize hardware")
        raise e

    # 更新硬件信息
    col_garage = db["garage"]
    cur_garage = col_garage.find_one({"ip": ip})
    if cur_garage is None:
        """
        新机库流程
        0. 连接map数据库
        1. 查询机库位置是否存在pinpoint
           - 更新pinpoint
        3. 新建机库
        """
        # 0.
        map_db = client["map"]
        map_db.authenticate(config["db"]["user"], config["db"]["pwd"])
        col_pinpoint = map_db["pinpoint"]

        # 1.
        pinpoint = col_pinpoint.find_one({"coordinate": hardware.center})
        if pinpoint is None:
            pinpoint_id = col_pinpoint.insert_one({
                "coordinate": hardware.center,
                "type": "terminal",
                "new": True
            }).inserted_id
        else:
            pinpoint_id = pinpoint["_id"]

        garage_id = col_garage.insert_one({
            "ip": ip,
            "capacity": config["hardware"]["capacity"],
            "productCapacity": config["hardware"]["productCapacity"],
            "drones": [],  # 这两个信息让硬件平台来填
            "products": [],
            "center": DBRef("pinpoint", ObjectId(pinpoint_id), "map"),
            "description": config["hardware"]["description"]
        }).inserted_id
    else:
        garage_id = cur_garage["_id"]
    client.close()

    # 初始化控制服务器
    try:
        control_instance = control.Control(config, garage_id)
    except Exception as e:
        print("Fail to initialize Control Tower")
        raise e

    return config, hardware, control_instance
