import pymongo
from bson.objectid import ObjectId
import socket

global _config


class Control:
    def __init__(self, config, garage_id):
        global _config
        _config = config
        self.garage_id = garage_id
