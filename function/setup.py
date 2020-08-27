import pymongo
from bson.objectid import ObjectId
from bson.dbref import DBRef
import json
import socket


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
    2. 检查和无人机的通信
    3. 检查和数据库间通信
    - 登记
    - 更新硬件信息
    - 返回硬件编号
    :return:
    """
    config_file = open("./config/hardware_config.json", "r", encoding="utf-8")
    json_string = config_file.read()
    config = json.loads(json_string, encoding="utf-8")
    ip = get_host_ip()
    # TODO: 检查和无人机之间的通信

    try:
        client = pymongo.MongoClient(config["db"]["ip"], config["db"]["port"])
        db = client[config["db"]["db"]["hardware"]]
        db.authenticate(config["db"]["user"], config["db"]["pwd"])
    except Exception as e:
        print("Cannot open MongoDB client")
        return config, None

    col_garage = db["garage"]
    cur_garage = col_garage.find_one({"ip": ip})
    if cur_garage is None:
        garage_id = col_garage.insert_one({
            "ip": ip,
            "capacity": config["hardware"]["capacity"],
            "productCapacity": config["hardware"]["productCapacity"],
            "drones": [],  # 这两个信息让硬件平台来填
            "products": [],
            "center": DBRef("pinpoint", ObjectId(config["hardware"]["pinpoint"]), "map"),
            "description": config["hardware"]["description"]
        }).inserted_id
    else:
        garage_id = cur_garage["_id"]
    client.close()
    return config, garage_id

