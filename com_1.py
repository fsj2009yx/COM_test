import serial

from FSM import FSM_2

if __name__ == "__main__":
    ser = serial.Serial("COM9", 9600)

    fsmSender = FSM_2.FSMSender(ser)
    fsmReceiver = FSM_2.FSMReceiver(ser)

    if not ser.is_open:
        print("串口未打开")
        exit(1)
    else:
        print(ser.name + " 打开成功")
        while True:
            print("选择操作:")
            print("1. 发送字符串")
            print("2. 发送图片")
            print("3. 接收数据")
            print("4. 退出")
            choose = int(input())

            if choose == 1:
                data = input("请输入要发送的字符串: ")
                fsmSender.send_string(data)

            elif choose == 2:
                fsmSender.send_image()

            elif choose == 3:
                fsmReceiver.recv()

            elif choose == 4:
                exit(0)
            else:
                print("选择错误")
