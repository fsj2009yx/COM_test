import serial
import sys
from FSM import FSM_2, FSM_1


def main():
    if len(sys.argv) != 2:
        print("用法: python script.py <-1 或 -2>")
        exit(1)

    mode = sys.argv[1]

    try:
        ser = serial.Serial("COM8", 9600)
    except serial.SerialException as e:
        print(f"无法打开串口: {e}")
        exit(1)

    if not ser.is_open:
        print("串口未打开")
        exit(1)

    print(ser.name + " 打开成功")

    if mode == "-1":
        fsmSender = FSM_1.FsmSender(ser)
        fsmReceiver = FSM_1.FsmReceiver(ser)
    elif mode == "-2":
        fsmSender = FSM_2.FSMSender(ser)
        fsmReceiver = FSM_2.FSMReceiver(ser)
    else:
        print("无效的参数, 请使用 -1 或 -2")
        exit(1)

    while True:
        print("选择操作:")
        print("1. 发送字符串")
        print("2. 发送图片")
        print("3. 接收数据")
        print("4. 退出")
        try:
            choose = int(input())
        except ValueError:
            print("请输入有效的数字")
            continue

        if choose == 1:
            data = input("请输入要发送的字符串: ")
            fsmSender.send_string(data)

        elif choose == 2:
            fsmSender.send_image()

        elif choose == 3:
            fsmReceiver.recv()

        elif choose == 4:
            print("退出程序")
            ser.close()
            exit(0)

        else:
            print("选择错误")


if __name__ == "__main__":
    main()
