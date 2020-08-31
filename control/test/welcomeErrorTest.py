import control.format
import socket

"""
该单元测试已停用
"""


def run():
    # Timeout
    cli = socket.socket()
    cli.connect(("127.0.0.1", 3000))
    cli.close()
    print(1)

    # 无法解析的信息
    cli = socket.socket()
    cli.connect(("127.0.0.1", 3000))
    cli.send(b"Hello")
    cli.close()
    print(2)

    # 错误的ID
    cli = socket.socket()
    cli.connect(("127.0.0.1", 3000))
    welcomeCmd = control.format.WelcomeCmd()
    welcomeCmd._drone = control.format.ObjectId.from_number(0x5f38a921b2e1fb5c98a89b98)
    welcomeCmd.ucBatteryH = 0x64
    welcomeCmd.ucBatteryL = 0x00
    welcomeCmd.nTimeStamp = 31
    cli.send(welcomeCmd.encode())
    cli.close()
    print(3)

    cli = socket.socket()
    cli.connect(("127.0.0.1", 3000))
    welcomeCmd = control.format.WelcomeCmd()
    welcomeCmd._drone = control.format.ObjectId.from_number(0x5f3f217deb05450df65cda10)
    welcomeCmd.ucBatteryH = 0x64
    welcomeCmd.ucBatteryL = 0x00
    welcomeCmd.nTimeStamp = 31
    cli.send(welcomeCmd.encode())
    print(cli.recv(1024))
    cli.close()


if __name__ == "__main__":
    run()
