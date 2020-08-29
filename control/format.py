from ctypes import *
import struct


class ValidationError(Exception):
    pass


class ObjectId(c_uint8 * 12):
    @classmethod
    def from_number(cls, num):
        components = []
        for i in range(0, 12):
            components.insert(0, (num >> (i * 8)) & 0xff)
        return ObjectId(*components)

    @classmethod
    def from_array(cls, arr):
        return ObjectId(*arr)

    @classmethod
    def from_str(cls, s):
        return cls.from_number(int(s, 16))

    def to_number(self):
        result = 0
        for i in range(0, 12):
            result <<= 8
            result += self[i]
        return result

    def to_string(self):
        return hex(self.to_number())[2:]


class BigEndianEncoding(BigEndianStructure):
    _pack_ = 1
    _validation_ = None

    def encode(self):
        if self._validation_ is not None:
            self.__setattr__(self._validation_, 0)
            partial = sum(i[0] for i in struct.iter_unpack(">B", string_at(addressof(self), sizeof(self))))
            self.__setattr__(self._validation_, (~(partial & 0x7f) + 1) & 0x7f)
        return string_at(addressof(self), sizeof(self))

    @classmethod
    def decode(cls, data):
        self = cls()
        memmove(addressof(self), data, sizeof(self))
        if self._validation_ is not None and sum(i[0] for i in struct.iter_unpack(">B", data)) & 0x7f != 0:
            raise ValidationError
        return self


class PackageHead(BigEndianEncoding):
    _fields_ = [
        ("ucBegin", c_uint8),
        ("ucType", c_uint8),
        ("ucChunked", c_uint8),
        ("", c_uint8),
        ("nPackLen", c_uint32)
    ]

    def __init__(self):
        super(PackageHead, self).__init__()
        self.ucBegin = 0x00


class PackageTail(BigEndianEncoding):
    _fields_ = [
        ("ucValidation", c_uint8),
        ("", c_uint8),
        ("", c_uint8),
        ("ucEnd", c_uint8)
    ]

    def __init__(self):
        super(PackageTail, self).__init__()
        self.ucEnd = 0x01


class WelcomeCmdBody(BigEndianEncoding):
    _fields_ = [
        ("controller", ObjectId),
        ("ucReconnect", c_uint8),
        ("", c_uint8 * 3)
    ]


class TaskCmdBody(BigEndianEncoding):
    _fields_ = [
        ("task", ObjectId),
        ("ucTaskType", c_uint8),
        ("", c_uint8),
        ("nLen", c_ushort)
    ]


class WelcomeMsgBody(BigEndianEncoding):
    _fields_ = [
        ("drone", ObjectId),
        ("ucBatteryH", c_uint8),
        ("ucBatteryL", c_uint8),
        ("", c_uint8 * 2),
        ("ucTimeStamp", c_uint32)
    ]


class StatusMsgBody(BigEndianEncoding):
    _fields_ = [
        ("task", ObjectId),
        ("dPosX", c_double),
        ("dPosY", c_double),
        ("dPosZ", c_double),
        ("dSpdX", c_double),
        ("dSpdY", c_double),
        ("dSpdZ", c_double),
        ("ucBatteryH", c_uint8),
        ("ucBatteryL", c_uint8),
        ("", c_uint8 * 2),
        ("nTimeStamp", c_uint32)
    ]


class ExitMsgBody(BigEndianEncoding):
    _fields_ = [
        ("ucReason", c_uint8),
        ("", c_uint8 * 3)
    ]


PACKAGE_WELCOME_CMD = 0x00
PACKAGE_TASK_CMD = 0x01
PACKAGE_RESET_CMD = 0x02
PACKAGE_WELCOME_MSG = 0xff
PACKAGE_STATUS_MSG = 0xfe
PACKAGE_EXIT_MSG = 0xfd
body_table = {
    PACKAGE_WELCOME_CMD: WelcomeCmdBody,
    PACKAGE_TASK_CMD: TaskCmdBody,
    PACKAGE_WELCOME_MSG: WelcomeMsgBody,
    PACKAGE_STATUS_MSG: StatusMsgBody,
    PACKAGE_EXIT_MSG: ExitMsgBody
}
size_table = {
    PACKAGE_WELCOME_CMD: WelcomeCmdBody,
    PACKAGE_TASK_CMD: TaskCmdBody,
    PACKAGE_WELCOME_MSG: WelcomeMsgBody,
    PACKAGE_STATUS_MSG: StatusMsgBody,
    PACKAGE_EXIT_MSG: ExitMsgBody
}


class Package:
    _head = PackageHead()
    _body = {}
    _extra = []
    _tail = PackageTail()

    def __init__(self, package_type=0):
        self._head.ucType = package_type
        self._type = package_type
        if package_type in body_table:
            self._body = body_table[package_type]()

    @property
    def type(self):
        return self._type

    def __getattr__(self, item):
        if item == "content":
            return self._extra
        elif hasattr(self._body, item):
            return eval("self._body." + item)
        elif hasattr(self._head, item):
            return eval("self._head." + item)
        return eval("self._tail." + item)

    def __setattr__(self, key, value):
        if key == "content":
            self._extra = value
        elif hasattr(self._body, key):
            self._body.__setattr__(key, value)
        elif hasattr(self._head, key):
            self._head.__setattr__(key, value)
        elif hasattr(self._tail, key):
            self._tail.__setattr__(key, value)
        else:
            object.__setattr__(self, key, value)

    def encode(self):
        self._tail.ucValidation = 0
        self._head.nPackLen = sizeof(self._head) + \
                              sizeof(self._body) + \
                              sum([len(i) for i in self._extra]) * 8 + \
                              sizeof(self._tail)
        temp = self._head.encode() + (self._body.encode() if self._body else b"") + \
               (encode_double_array(self._extra, 2) if len(self._extra) else b"") + \
               self._tail.encode()
        partial = sum(i[0] for i in struct.iter_unpack(">B", temp))
        self._tail.ucValidation = (~(partial & 0x7f) + 1) & 0x7f
        tt = self._head.encode() + (self._body.encode() if self._body else b"") + \
               (encode_double_array(self._extra, 2) if len(self._extra) else b"") + \
               self._tail.encode()
        return self._head.encode() + (self._body.encode() if self._body else b"") + \
               (encode_double_array(self._extra, 2) if len(self._extra) else b"") + \
               self._tail.encode()

    @classmethod
    def read(cls, sock):
        """
        :param socket.socket sock:
        :return:
        """
        self = cls()
        full_text = b""
        header = sock.recv(8)
        full_text += header
        self._head = PackageHead.decode(header)
        if self._head.ucBegin != 0:
            raise ValidationError
        if self._head.ucType in body_table:
            body = sock.recv(self._head.nPackLen - 12)
            full_text += body
            self._body = body_table[self._head.ucType].decode(body)
            if self._head.ucType == 0x01:
                self._extra = decode_position_array(body[16:])
        tail = sock.recv(4)
        full_text += tail
        self._tail = PackageTail.decode(tail)
        if sum(i[0] for i in struct.iter_unpack(">B", full_text)) & 0x7f != 0:
            raise ValidationError
        if self._tail.ucEnd != 0x01:
            raise ValidationError
        return self


def encode_double_array(arr, dimension=1):
    if dimension == 1:
        return struct.pack(">" + str(len(arr)) + "d", *arr)
    else:
        result = b""
        for i in arr:
            result += encode_double_array(i, dimension - 1)
        return result


def decode_position_array(buffer):
    return [
        item for item in struct.iter_unpack(">ddd", buffer)
    ]


def generate_package(package_type, **kwargs):
    pack = Package(package_type)
    for key in kwargs:
        pack.__setattr__(key, kwargs[key])
    return pack.encode()


if __name__ == "__main__":
    cmd = Package(PACKAGE_WELCOME_CMD)
    cmd.controller = ObjectId.from_number(0x5f38a917b2e1fb5c98a89b97)
    cmd.ucReconnect = 0x1
    print(cmd.encode())
