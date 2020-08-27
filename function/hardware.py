import json

_config = {}


class Hardware:
    center = ()

    def __init__(self, config):
        """
        机库硬件自检流程
        """
        global _config
        _config = config
        if _config["hardware"]["env"] == "none": # 无实际硬件
            self.center = tuple(_config["hardware"]["center"])
