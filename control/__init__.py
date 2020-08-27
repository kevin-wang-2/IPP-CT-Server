import pymongo
from multiprocessing import Process
import struct

_config = {}


class ControlProcess(Process):
    def __init__(self, config, garage_id, drone_id, sock):
        super().__init__()
        global _config
        _config = config
        self.garage_id = garage_id
        self.drone_id = drone_id
        self.socket = sock
        self.socket_file = sock.make_file("rw")

        self.db_client = pymongo.MongoClient(_config["db"]["ip"], _config["db"]["port"])
        self.db_map = self.db_client[_config["db"]["db"]["map"]]
        self.db_map.authenticate(_config["db"]["user"], _config["db"]["pwd"])
        self.db_hardware = self.db_client[_config["db"]["db"]["hardware"]]
        self.db_hardware.authenticate(_config["db"]["user"], _config["db"]["pwd"])
        self.db_business = self.db_client[_config["db"]["db"]["business"]]
        self.db_business.authenticate(_config["db"]["user"], _config["db"]["pwd"])

        self.open = True

    def run(self):
        global _config
        while self.open:
            pass
        self.socket.close()
        self.db_client.close()
