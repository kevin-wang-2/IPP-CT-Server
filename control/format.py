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
    _validation_ = None

    def encode(self):
        if self._validation_ is not None:
            total = 0
            for key in self._fields_:
                if key[0] == self._validation_ or key[0] == "":
                    continue
                val = eval("self." + key[0])
                if type(val) == c_uint8 * 12:
                    total += sum(val)
                elif hasattr(val, "__getitem__"):
                    total += int(sum(val))
                else:
                    total += val
            self.__setattr__(self._validation_, (~(total & 0x7f) + 1) & 0x7f)
        return string_at(addressof(self), sizeof(self))

    @classmethod
    def decode(cls, data):
        self = cls()
        memmove(addressof(self), data, sizeof(self))
        if self._validation_ is not None:
            total = 0
            for key in self._fields_:
                if key[0] == "":
                    continue
                val = eval("self." + key[0])
                if type(val) == c_uint8 * 12:
                    total += sum(val)
                elif hasattr(val, "__getitem__"):
                    total += int(sum(val))
                else:
                    total += val
            if total & 0x7f != 0:
                raise ValidationError
        return self


def create_structure(fields, init=None, verification=None):
    if init is None:
        init = {}

    class S(BigEndianEncoding):
        _pack_ = 1
        _fields_ = fields
        _validation_ = verification

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            for key in init.keys():
                self.__setattr__(key, init[key])

    return S


def encode_double_array(arr, dimension=1):
    if dimension == 1:
        return struct.pack(">" + str(len(arr)) + "d", *arr)
    else:
        result = b""
        for i in arr:
            result += encode_double_array(i, dimension - 1)
        return result


WelcomeCmd = create_structure([
    ("ucType", c_uint8),
    ("", c_uint8 * 3),
    ("_drone", ObjectId),
    ("ucBatteryH", c_uint8),
    ("ucBatteryL", c_uint8),
    ("", c_uint16),
    ("nTimeStamp", c_uint32),
    ("nValidation", c_uint32)
], {
    "ucType": 0xff
},
    "nValidation")

TaskCmd = create_structure([
    ("ucType", c_uint8),
    ("ucEnd", c_uint8),
    ("", c_uint8 * 2),
    ("_drone", ObjectId),
    ("_task", ObjectId),
    ("ucTaskType", c_uint8),
    ("reserved", c_uint8),
    ("nLen", c_short),
    ("nValidation", c_uint32)
], {
    "ucType": 0
},
    "nValidation")

ReplyCmd = create_structure([
    ("ucType", c_uint8),
    ("", c_uint8 * 3),
    ("_drone", ObjectId),
    ("_task", ObjectId),
    ("dPos", c_double * 3),
    ("dSpd", c_double * 3),
    ("ucBatteryH", c_uint8),
    ("ucBatteryL", c_uint8),
    ("", c_uint8 * 2),
    ("ucTimeStamp", c_uint32),
    ("nValidation", c_uint32)
], {
    "ucType": 0xfe
},
    "nValidation")

if __name__ == "__main__":
    welcomeCmd = WelcomeCmd()
    welcomeCmd._drone = ObjectId.from_number(0x5f38a921b2e1fb5c98a89b98)
    welcomeCmd.ucBatteryH = 0x64
    welcomeCmd.ucBatteryL = 0x00
    welcomeCmd.nTimeStamp = 31
    print(welcomeCmd.encode())
    print(hex(ObjectId.from_array(welcomeCmd.decode(welcomeCmd.encode())._drone).to_number()))
    print(encode_double_array([[1, 2, 3], [4, 5, 6]], 2))
