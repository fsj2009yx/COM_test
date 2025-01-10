import math
from PIL import Image
import io
import serial
import time
from tkinter import filedialog
from tqdm import tqdm


class FsmReceiver:
    def __init__(self, sers: serial.Serial):
        self.ser = sers  # serial实例化对象

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
            with tqdm(
                total=total, unit="B", unit_scale=True, desc="接收数据流"
            ) as pbar:
                with open("E:/python_Project/COM_test/test.jpg", "wb") as f:
                    bytes_saved = 0  # 已保存数据的字节数
                    while True:
                        if self.ser.in_waiting > 0:
                            byte_line = self.ser.readline()
                            # 读取到数据流结束的标志，结束循环
                            if byte_line == b"END_BYTES\n":
                                print("接收结束")
                                return True
                            # 写入数据
                            f.write(byte_line)
                            bytes_saved += len(byte_line)
                            # 更新进度条
                            pbar.update(len(byte_line))

    @property
    def is_open(self):
        return self.ser.is_open

    @property
    def name(self):
        return self.ser.name


class FsmSender:
    def __init__(self, sers: serial.Serial):
        # 初始化串口
        self.ser = sers

    def send_string(self, data: str):
        """
        发送字符串数据
        """
        print("开始发送字符串...")
        # 发送开始标志
        self.ser.write(b"BEGIN_STRING\n")
        time.sleep(0.1)  # 短暂等待，确保对端能识别标志

        # 发送字符串内容
        data += "\n"
        self.ser.write(data.encode("utf-8"))
        self.ser.flush()  # 确保数据立即发送

        self.ser.write(b"END_STRING\n")
        print("字符串发送完成")

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

        try:
            # 打开图片文件
            with Image.open(file_path) as img:
                image_stream = io.BytesIO()
                img.save(image_stream, format=img.format, optimize=True, quality=95)
                image_data = image_stream.getvalue()

            total_size = len(image_data)
            sent_bytes = 0
            chunk_size = 1024  # 每次发送1KB数据
            counter: int = 0
            chunk_num = math.ceil(total_size / chunk_size)  # 计算总分组数

            print(f"图片大小: {total_size} 字节,总分组数: {chunk_num}")

            loss_set = int(
                input(f"请输入丢失分组的序号 (为0或超过{chunk_num}时将不进行丢包):")
            )

            loss_chunk_num = self.loss(loss_set)

            print("开始发送图片...")
            # 发送开始标志
            self.ser.write(b"BEGIN_BYTES\n")
            time.sleep(0.1)

            # 发送总字节数
            self.ser.write(f"{total_size}\n".encode("utf-8"))
            time.sleep(0.1)

            # 按行发送数据
            time1 = time.time()
            while sent_bytes < total_size:
                chunk = image_data[sent_bytes : sent_bytes + chunk_size]
                sent_bytes += len(chunk)
                counter += 1
                print(f"发送分组: {counter},已发送 {sent_bytes}/{total_size} 字节")
                if loss_chunk_num == counter:
                    print(f"分组{counter}丢包")
                    continue
                self.ser.write(chunk)
                time.sleep(0.01)  # 避免串口缓存溢出

            # 发送结束
            self.ser.write(b"\nEND_BYTES\n")
            time2 = time.time()
            print(f"图片发送完成。发送用时: {time2-time1:.2f} 秒")

        except FileNotFoundError:
            print(f"文件 {file_path} 未找到")

    def loss(self, counter: int):  # 模拟传输中丢包的情况
        return counter

    @property
    def is_open(self):
        return self.ser.is_open

    @property
    def name(self):
        return self.ser.name
