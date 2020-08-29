import pymongo
from multiprocessing import Process
import socket
import threading
import control.format
import control.ControlStateMachine
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

_config = {}


class Control:
    def __init__(self, config, garage_id):
        global _config
        _config = config
        self.garage_id = garage_id
        self.terminate = False

    def run(self):
        global _config
        control_socket = socket.socket()
        control_socket.settimeout(10)
        control_socket.setblocking(False)
        control_socket.bind(("0.0.0.0", _config["control"]["port"]))
        control_socket.listen(_config["control"]["capacity"])

        def listen():
            while not self.terminate:
                yield
                try:
                    client, addr = control_socket.accept()
                except (socket.timeout, BlockingIOError) as e:
                    continue

                yield
                get_welcomed = False
                while not get_welcomed:
                    try:
                        welcome_msg = control.format.Package.read(client)
                        get_welcomed = True
                    except BlockingIOError as e:
                        continue
                    except socket.timeout as e:
                        client.close()
                        logger.warning("%s:%d - Time out" % (addr[0], addr[1]))
                        break
                    except control.format.ValidationError as e:
                        logger.warning("%s:%d - Validation Error" % (addr[0], addr[1]))
                        client.close()
                        break
                if not get_welcomed:
                    continue

                if welcome_msg.ucType != 0xff:
                    logger.warning("%s:%d Validation Error" % (addr[0], addr[1]))
                    client.close()
                    continue

                if control.format.ObjectId.from_array(welcome_msg.drone).to_string() in _config["control"]["drones"]:
                    process = ControlProcess(config, self.garage_id,
                                             control.format.ObjectId.from_array(welcome_msg.drone).to_string(), client)
                    process.start()
                else:
                    logger.warning("%s:%d - %s Not in drone list" % (addr[0], addr[1],
                                                                     control.format.ObjectId.from_array(welcome_msg.drone).to_string()))
                    client.close()

        return listen()


class ControlProcess(Process):
    db_client = None
    db_map = None
    db_hardware = None
    db_business = None

    def __init__(self, config, garage_id, drone_id, sock):
        """
        :param str garage_id:
        :param str drone_id:
        :param socket.socket sock:
        """
        super().__init__()
        self.garage_id = garage_id
        self.drone_id = drone_id
        self.socket = sock

        self.config = config

        self.open = True

    def stop(self):
        logger.info("Control process for drone %s exited" % (self.drone_id,))
        self.open = False
        self.close()

    def run(self):
        global _config
        _config = self.config
        self.db_client = pymongo.MongoClient(_config["db"]["ip"], _config["db"]["port"])
        self.db_map = self.db_client[_config["db"]["db"]["map"]]
        self.db_map.authenticate(_config["db"]["user"], _config["db"]["pwd"])
        self.db_hardware = self.db_client[_config["db"]["db"]["hardware"]]
        self.db_hardware.authenticate(_config["db"]["user"], _config["db"]["pwd"])
        self.db_business = self.db_client[_config["db"]["db"]["business"]]
        self.db_business.authenticate(_config["db"]["user"], _config["db"]["pwd"])

        logger.info("Control process for drone %s started" % (self.drone_id,))
        state_machine = control.ControlStateMachine.ControlStateMachine(self)
        state_machine.run()

        self.socket.close()
        self.db_client.close()


if __name__ == "__main__":  # 单元测试
    import control.test
    import json

    config_file = open("../config/hardware_config.json", "r", encoding="utf-8")
    json_string = config_file.read()
    config = json.loads(json_string, encoding="utf-8")
    cor = Control(config, "5f473c56b027140c197d7d08").run()
    for i in cor:
        pass
