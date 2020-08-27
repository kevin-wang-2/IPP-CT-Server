import pymongo
from bson.objectid import ObjectId
import socket


def pre(config, garage_id, drone_id):
    client = pymongo.MongoClient(config["db"]["ip"], config["db"]["port"])
    db = client[config["db"]["db"]["hardware"]]
    db.authenticate(config["db"]["user"], config["db"]["pwd"])
    col_drone = db["drone"]
    drone_result = col_drone.find_one({"_id": ObjectId(drone_id)})
    assert drone_result is not None
    assert drone_result["controller"] == ObjectId(garage_id)
    sock = socket.socket()
    sock.connect((drone_result["ip"], config["hardware"]["drone_port"]))
    return sock


def run(config, garage_id, drone_id):
    sock = pre(config, garage_id, drone_id)
    welcome_msg = sock.recv(1024)
