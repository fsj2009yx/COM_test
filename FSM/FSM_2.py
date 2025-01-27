from . import FSM_1
import threading
from .CRC import crc16xmodem
from typing import List, Tuple
import serial
import time
import pickle
from PIL import Image
import io
from tkinter import filedialog
import math

"""
发送端的FSM发送序列化为字节流的Data类的实例化对象，并在末尾添加CRC校验码,组成链路层帧
接收端的FSM接收字节流，解包得到Data类的实例化对象和CRC校验码,对Data类对象进一步解包得到实际数据和数据分片的序号
每一个Data类对象就是一个数据分组

使用SR协议，发送端维护一个发送窗口，接收端维护一个接收窗口
发送端使用threading模块创建一个线程，在发送帧的同时异步接收ACK
每收到一个ACK，发送窗口向后移动一个单位
如有一个分组的ACK丢失，在超时机制后重传该分组

超时重传实现:对每个已发送未ACK的分组创建一个Timer线程，定义线程任务:
如果在超时时间内没有收到该分组的ACK，重传该分组

端口转发:
假设COM1_send连接COM2_recv，COM_2_send连接COM_3_recv,COM_3_send连接COM_1_recv
从COM_1发送信息到COM_3:
以字符串为例:发送端先发送BEGIN_STRING标志,然后发送两行字符串,分别是目标端口和源端口，再发送数据
目标端口和源端口内容不能更改，接收到以后判断自己是否是目标端口，如果是，则将数据向上层交付，如果不是，则写入串口让下一跳接收
"""


# 数据基类:定义一个数据分组包含一个Data类对象和末尾的CRC校验码
class Data:
    def __init__(self, data: bytes, seq_num: int):
        self.__data = data
        self.__seq_num = seq_num  # 数据分片序号

    @property
    def data(self):
        return self.__data

    @property
    def seq_num(self):
        return self.__seq_num


class FSMReceiver(FSM_1.FsmReceiver):
    def __init__(self, sers: serial.Serial):
        super().__init__(sers)
        self.__window_size = 4  # 接收窗口的大小为4
        self.__window: List[Data] = []  # 接收窗口
        self.__crc = 0

        self.__seq_next = 1  # 期待接收的下一个分组的序号

    # 传入接收到的未校验数据
    def crc_check(self, data_nocheck: bytes) -> bool:
        # 计算CRC,与接收到的CRC校验码进行比较
        return crc16xmodem(data_nocheck) == self.__crc

    def recv(self):
        print("等待接收数据...")
        while True:
            if self.ser.in_waiting > 0:
                # 读取发送数据开始的信号并解码
                line = self.ser.readline()
                is_received: bool = self.__process_data(line)
                if is_received:
                    break
            time.sleep(0.1)

    def __process_data(self, arg: bytes) -> bool:
        print("开始接收...")
        if arg == b"BEGIN_STRING\n":
            print("识别到字符串")
            while True:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode("utf-8")
                    # 读取到数据流结束的标志，结束循环
                    if line == "END_STRING\n":
                        print("接收结束")
                        return True
                    print("接收到字符串: ", line)
                time.sleep(0.1)

        elif arg == b"BEGIN_BYTES\n":
            print("识别到数据流")
            while True:
                if self.ser.in_waiting > 0:
                    total = int(self.ser.readline().decode("utf-8"))
                    print("总字节数: ", total)
                    break
                time.sleep(0.1)

                # 开始接收数据流
            with open("E:/python_Project/COM_test/test.jpg", "wb") as f:
                bytes_saved = 0  # 已保存数据的字节数
                while True:
                    if self.ser.in_waiting > 0:

                        # 这里读取的是链路层帧,需要先解包
                        byte = self.ser.readline().decode().rstrip("\n")
                        # 如果读取到的是数据流结束的标志，结束循环
                        if byte == "END_BYTES":
                            print("接收结束")
                            return True

                        # 否则，byte是接收帧的长度
                        bytes_item = self.ser.read(int(byte))

                        chunk_nocheck, self.__crc = bytes_item[:-2], int.from_bytes(
                            bytes_item[-2:], "big"
                        )

                        print(f"获取到的crc校验码:{self.__crc}")

                        if self.crc_check(chunk_nocheck):
                            # 校验完成,将数据分组缓存到接收窗口
                            data: Data = pickle.loads(chunk_nocheck)
                            # 如果是期待接收的下一个分组，直接向上层交付
                            if data.seq_num == self.__seq_next:
                                print("接收到分组: ", data.seq_num)
                                f.write(data.data)
                                bytes_saved += len(data.data)
                                self.__seq_next += 1

                                # 发送ACK确认
                                self.ser.write(
                                    str(data.seq_num).encode("utf-8") + b"\n"
                                )
                                self.ser.flush()  # 确保数据立即发送
                                print("发送ACK: ", data.seq_num)

                            else:
                                if len(self.__window) < self.__window_size:
                                    print("未按序到达，缓存到接收窗口")
                                    # 如果不是期待接收的下一个分组，缓存到接收窗口
                                    self.__window.append(data)
                                    print(f"接收窗口长度: {len(self.__window)}")
                                    self.__window.sort(key=lambda x: x.seq_num)

                                    for item in self.__window:
                                        # 如果是期待接收的下一个分组，直接向上层交付
                                        if item.seq_num == self.__seq_next:
                                            f.write(item.data)
                                            bytes_saved += len(item.data)
                                            self.__seq_next += 1
                                        else:
                                            break

                                    # 发送ACK确认
                                    self.ser.write(
                                        str(data.seq_num).encode("utf-8") + b"\n"
                                    )
                                    self.ser.flush()  # 确保数据立即发送
                                    print("发送ACK: ", data.seq_num)

                                else:
                                    print(f"接收窗口已满,暂停发送ACK")

                        else:
                            print("数据校验失败")

                    time.sleep(0.1)


class FSMSender(FSM_1.FsmSender):
    def __init__(self, sers: serial.Serial):
        super().__init__(sers)
        self.__chunk_num = 0  # 数据分片的总数
        self.__window_size = 4  # 发送窗口的大小
        self.__ack = 0  # 接收到的ACK
        self.items: List[Tuple[bytes, bool]] = []

        self.front = self.back = 0  # 发送窗口的前沿和后沿

    def send_image(self):
        """
        发送图片文件
        """
        print("请选择要发送的图片文件:")

        # 打开文件选择对话框
        file_path = filedialog.askopenfilename(
            title="选择图片文件",
            filetypes=[
                ("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif"),
                ("所有文件", "*.*"),
            ],
        )

        # 检查是否选择了文件
        if file_path:
            print(f"选择的文件路径: {file_path}")
        else:
            print("未选择文件")
            return

        self.__process_data(file_path)

    # 定时器任务函数
    def timer(self, seq_num: int):
        time_start = time.time()
        while True:
            if self.items[seq_num - 1][1]:
                # 接收到ACK，结束循环
                return
            else:
                if time.time() - time_start > 5:
                    # 超时，重新发送
                    str1 = str(len(self.items[seq_num - 1][0])) + "\n"
                    self.ser.write(str1.encode("utf-8"))
                    self.ser.write(self.items[seq_num - 1][0])
                    self.ser.flush()
                    time_start = time.time()  # 重新计时

    # 接收ACK的任务函数
    def recvACK(self):
        while True:
            if self.ser.in_waiting > 0:
                line = self.ser.readline().decode("utf-8").rstrip("\n")
                # 将接收到的ACK标记为True
                self.items[int(line) - 1] = (self.items[int(line) - 1][0], True)
                print(f"接收到第{line}分组的ACK")
                # 读取到最后一个分组的ACK，结束循环
                if line == str(self.__chunk_num):
                    return

    # 对数据分片的封装
    def __process_data(self, file_path: str):
        try:
            # 打开图片文件
            with Image.open(file_path) as img:
                image_stream = io.BytesIO()
                img.save(image_stream, format=img.format, optimize=True, quality=95)
                image_data = image_stream.getvalue()

            total_size = len(image_data)
            datas_size = 1024  # 每个数据分片为512字节
            self.__chunk_num = math.ceil(total_size / datas_size)  # 计算总分组数

            # 更新总字节数为封装为帧后的总字节数
            total_size = 0

            # 存储分片的链路层帧(追加了CRC校验码),结构为二元组(帧，ACK确认)
            for i in range(self.__chunk_num):
                data_piece = image_data[
                    i * datas_size : (i + 1) * datas_size
                ]  # 每个数据分片
                chunk = pickle.dumps(Data(data_piece, i + 1))  # 数据分组
                crc = crc16xmodem(chunk)
                self.items.append((chunk + crc.to_bytes(2, "big"), False))
                print(f"第{i + 1}分组的CRC校验码: {crc}")
                total_size += len(chunk) + 2  # crc校验码的字节长度为2

            print(f"总文件大小: {total_size} 字节,总分组数: {self.__chunk_num}")

            loss_set = int(
                input(
                    f"请输入丢失分组的序号 (为0或超过{self.__chunk_num}时将不进行丢包):"
                )
            )

            loss_chunk_num = self.loss(loss_set)

            print("开始发送图片...")

            # 发送开始标志
            self.ser.write(b"BEGIN_BYTES\n")
            time.sleep(0.1)

            # 发送总字节数
            self.ser.write(f"{total_size}\n".encode("utf-8"))
            time.sleep(0.1)

            # 创建新线程异步接收ACK
            thread_recvACK = threading.Thread(target=self.recvACK)
            thread_recvACK.start()

            time1 = time.time()  # 计时总发送时间

            time_threads = []  # 管理超时定时器线程

            for i in range(self.__chunk_num):

                while self.front - self.back == self.__window_size:
                    # 发送窗口已满，暂停发送ACK
                    time.sleep(0.1)
                    if self.items[self.back][1]:
                        # 接收到期望的ACK,滑动窗口并继续发送
                        for j in range(self.back, self.front):
                            if self.items[j][1]:
                                self.back += 1
                            else:
                                break

                # 缓存到发送窗口
                self.front += 1

                if i != loss_chunk_num - 1:

                    # 发送数据分组
                    str1 = str(len(self.items[i][0])) + "\n"
                    self.ser.write(str1.encode("utf-8"))
                    print(f"发送第{i + 1}分组的长度: {len(self.items[i][0])}")
                    self.ser.write(self.items[i][0])
                    self.ser.flush()
                    time.sleep(0.1)

                else:
                    print(f"丢失分组{i + 1}")

                # 启动超时定时器
                time_thread = threading.Thread(target=self.timer, args=(i + 1,))
                time_thread.start()
                time_threads.append(time_thread)

                # 尝试移动发送窗口
                while self.back < self.front:
                    if self.items[self.back][1]:
                        self.back += 1
                    else:
                        break

            # 发送结束
            self.ser.write(b"END_BYTES\n")
            time2 = time.time()
            print(f"图片发送完成。发送用时: {time2 - time1:.2f} 秒")

        except FileNotFoundError:
            print(f"文件 {file_path} 未找到")
