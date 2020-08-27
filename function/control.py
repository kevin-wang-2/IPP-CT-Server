import pymongo
from bson.objectid import ObjectId
import socket
import threading
import control
import control.format

global _config


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
        control_socket.bind(("0.0.0.0", _config["control"]["port"]))
        control_socket.listen(_config["control"]["capacity"])

        class Listener(threading.Thread):
            def run(child):
                global _config
                while not self.terminate:
                    client, addr = control_socket.accept()
                    try:
                        welcome = client.recv(1024)
                    except TimeoutError as e:
                        continue

                    try:
                        welcome_msg = control.format.WelcomeCmd.decode(welcome)
                    except control.format.ValidationError as e:
                        client.close()
                        continue

                    if welcome_msg.ucType != 1:
                        client.close()
                        continue

                    if control.format.ObjectId.from_array(welcome).to_string() in _config["control"]["drones"]:
                        control.ControlProcess(_config, self.garage_id, welcome, client)
                    else:
                        client.close()

        Listener().start()
