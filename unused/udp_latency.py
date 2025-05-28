import socket
import time
import math
import csv
import sys
import getopt

from typing import List, Tuple, Union

# UDP数据包头大小：32字节(预留) + 4字节(包序号) + 8字节(时间戳)
HEADER_SIZE = 32 + 4 + 8


class Client:
    """
    UDP客户端类，用于发送测试数据包并记录发送时间
    """
    def __init__(
        self,
        local_ip: str = "0.0.0.0",      # 本地IP地址
        local_port: int = 20002,        # 本地端口
        remote_ip: str = "127.0.0.1",   # 远程服务器IP
        to_port: int = 20001,           # 远程服务器端口
    ) -> None:
        self.local_ip = local_ip
        self.local_port = local_port
        self.remote_ip = remote_ip
        self.to_port = to_port
        self.log: List[List[Union[int, float]]] = []  # 记录发送日志
        self.packet_index = 1  # 数据包序号

        # 创建UDP socket
        self._udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self._udp_socket.bind((self.local_ip, self.local_port))

    def synchronize(self, verbose: bool) -> None:
        """
        使用PTP(精确时间协议)同步客户端和服务器的时间
        Args:
            verbose: 是否打印详细信息
        """
        if verbose:
            print("|  ---------- Sychonizing Server & Client by PTP ------------  |")
        for _ in range(10):  # 进行10次同步
            # 发送同步请求
            t1 = time.time_ns()  # 记录发送时间
            time_bytes = t1.to_bytes(8, "big")
            index_bytes = (0).to_bytes(4, "big")
            msg = b"".join([b"\x00"] * 128)  # 填充数据
            msg = index_bytes + time_bytes + msg
            _send_nums = self._udp_socket.sendto(msg, (self.remote_ip, self.to_port))

            # 接收服务器响应
            msg, _ = self._udp_socket.recvfrom(128 + HEADER_SIZE)
            t2 = int.from_bytes(msg[4:12], "big")  # 服务器处理时间
            t2_p = time.time_ns()  # 接收响应时间
            time.sleep(0.05)

            # 发送确认消息
            index_bytes = (0).to_bytes(4, "big")
            time_bytes = t2_p.to_bytes(8, "big")
            msg = b""
            msg = index_bytes + time_bytes + msg
            _send_nums = self._udp_socket.sendto(msg, (self.remote_ip, self.to_port))
            time.sleep(1)

    def send(
        self,
        frequency: float,      # 发送频率(Hz)
        packet_size: int,      # 数据包大小(bytes)
        running_time: int,     # 运行时间(秒)
        verbose: bool,         # 是否打印详细信息
        sync: bool,           # 是否进行时间同步
        dyna: bool,           # 是否使用动态发送间隔
    ):
        """
        发送UDP测试数据包
        """
        if sync:
            self.synchronize(verbose)

        # 检查数据包大小是否合法
        if packet_size < HEADER_SIZE or packet_size > 1500:
            raise Exception("warning: packet size should be no larger than 1500 bytes.")

        # 准备数据包内容
        _payload_size = packet_size - HEADER_SIZE
        _fill = b"".join([b"\x00"] * (_payload_size))

        start_time = time.time_ns()
        total_packets = math.ceil(frequency * running_time)  # 计算总包数
        running_time = running_time * int(1e9)  # 转换为纳秒
        period = 1 / frequency  # 发送间隔

        while True:
            # 构造并发送数据包
            index_bytes = self.packet_index.to_bytes(4, "big")
            current_time = time.time_ns()
            time_bytes = current_time.to_bytes(8, "big")
            send_nums = self._udp_socket.sendto(
                index_bytes + time_bytes + _fill, (self.remote_ip, self.to_port)
            )
            self.log.append([self.packet_index, current_time, send_nums])

            # 检查是否达到运行时间或包数限制
            if (
                current_time - start_time
            ) > running_time or self.packet_index >= total_packets:
                break

            if verbose:
                print(
                    "|  Client: %d  |  Packet: %d  |  Time: %d  |  Data size: %d  |"
                    % (self.local_port, self.packet_index, current_time, send_nums)
                )
            self.packet_index += 1

            # 计算下一个包的发送时间
            if dyna:
                # 动态调整发送间隔，确保均匀分布
                prac_period = (
                    (running_time - (current_time - start_time))
                    / (total_packets - len(self.log))
                    * (len(self.log) / (frequency * (current_time - start_time + 1) * 1e-9))
                    * 1e-9
                )
                prac_period = period if prac_period > period else prac_period
            else:
                prac_period = period

            time.sleep(prac_period)

        # 发送结束信号
        self._udp_socket.sendto((0).to_bytes(4, "big"), (self.remote_ip, self.to_port))
        self._udp_socket.close()

    def __del__(self):
        """析构函数，确保socket正确关闭"""
        self._udp_socket.close()


class Server:
    """
    UDP服务器类，用于接收测试数据包并计算网络性能指标
    """
    def __init__(
        self,
        local_ip: str = "0.0.0.0",      # 本地IP地址
        local_port: int = 20001,        # 本地端口
        remote_ip: str = "127.0.0.1",   # 远程客户端IP
        to_port: int = 20002,           # 远程客户端端口
    ) -> None:
        self.local_ip = local_ip
        self.local_port = local_port
        self.remote_ip = remote_ip
        self.to_port = to_port
        self.log: List[List[Union[int, float]]] = []  # 记录接收日志

        self.offset: List[float] = []  # 时间偏移记录
        self.OFFSET = 0.0  # 最终采用的时间偏移值

        # 创建UDP socket
        self._udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self._udp_socket.bind((self.local_ip, self.local_port))

    def synchronize(self, verbose: bool):
        """
        与客户端进行时间同步
        Args:
            verbose: 是否打印详细信息
        """
        if verbose:
            print("|  ---------- Sychonizing Server & Client by PTP ------------  |")

        for i in range(10):  # 进行10次同步
            # 接收客户端同步请求
            msg, _ = self._udp_socket.recvfrom(128 + HEADER_SIZE)
            t1 = int.from_bytes(msg[4:12], "big")  # 客户端发送时间
            t1_p = time.time_ns()  # 服务器接收时间
            time.sleep(0.05)

            # 发送响应
            t2 = time.time_ns()  # 服务器发送时间
            index_bytes = (0).to_bytes(4, "big")
            time_bytes = t2.to_bytes(8, "big")
            msg = b"".join([b"\x00"] * 128)
            msg = index_bytes + time_bytes + msg
            send_nums = self._udp_socket.sendto(msg, (self.remote_ip, self.to_port))

            # 接收客户端确认
            msg, _ = self._udp_socket.recvfrom(1024)
            t2_p = int.from_bytes(msg[4:12], "big")  # 客户端接收时间

            # 计算时间偏移
            offset = round(((t1_p - t1 + t2 - t2_p) / 2) * 1e-9, 6)
            self.offset.append(offset)
            print("----- Offset at time %d second:  %f -----" % (i, offset))

        # 选择最小的时间偏移作为最终值
        abs_min = 1e9
        for v in self.offset:
            if abs(v) < abs_min:
                abs_min = abs(v)
                self.OFFSET = v

    def listen(self, buffer_size: int, verbose: bool, sync: bool):
        """
        监听并接收UDP测试数据包
        Args:
            buffer_size: 接收缓冲区大小
            verbose: 是否打印详细信息
            sync: 是否进行时间同步
        """
        if sync:
            self.synchronize(verbose)

        if verbose:
            print("|  ---------- Listen from Client %d ------------  |" % self.to_port)
        latency = 0.0
        while True:
            # 接收数据包
            msg, _ = self._udp_socket.recvfrom(buffer_size)
            recv_time = time.time_ns()
            packet_index = int.from_bytes(msg[:4], "big")
            send_time = int.from_bytes(msg[4:12], "big")
            
            # 计算延迟和抖动
            old_latency = latency
            latency = round(float(recv_time - send_time) * 1e-9 - float(self.OFFSET), 6)
            jitter = abs(latency - old_latency)
            recv_size = len(msg)

            # 检查是否收到结束信号
            if packet_index == 0:
                break

            # 记录接收信息
            self.log.append([packet_index, latency, jitter, recv_time, recv_size])

            if verbose:
                print(
                    "[  Server: %d  |  Packet: %6d  |  Latency: %f ｜ Jitter: %f |  Data size: %4d  ]"
                    % (self.local_port, packet_index, latency, jitter, recv_size)
                )

    def evaluate(self):
        """
        评估网络性能指标
        Returns:
            dict: 包含最大延迟、平均延迟、抖动和带宽的字典
        """
        # 提取延迟数据
        latency_list = [row[1] for row in self.log]
        latency_max = max(latency_list)
        latency_avg = sum(latency_list) / len(latency_list)
        
        # 计算标准差
        var = sum(pow(x - latency_avg, 2) for x in latency_list) / len(latency_list)
        latency_std = math.sqrt(var)
        
        # 计算抖动
        jitter = max(latency_list) - min(latency_list)
        
        # 计算总运行时间和带宽
        cycle = (self.log[-1][3] - self.log[0][3]) * 1e-9
        bandwidth = sum([x[4] + 32 for x in self.log]) / cycle
        
        # 计算丢包率
        packet_loss = (max([x[0] for x in self.log]) - len(latency_list)) / max(
            [x[0] for x in self.log]
        )

        # 打印评估结果
        print("| -------------  Summary  --------------- |")
        print("Total %d packets are received in %f seconds" % (len(self.log), cycle))
        print("Average latency: %f second" % latency_avg)
        print("Maximum latency: %f second" % latency_max)
        print("Std latency: %f second" % latency_std)
        print("bandwidth: %f Mbits" % (bandwidth * 8 / 1024 / 1024))
        print("Jitter (Latency Max - Min): %f second" % jitter)
        print("Packet loss: %f" % packet_loss)
        
        return {
            "latency_max": latency_max,
            "latency_avg": latency_avg,
            "jitter": jitter,
            "bandwidth": bandwidth,
        }

    def save(self, path):
        """
        将测试结果保存到CSV文件
        Args:
            path: 保存路径
        """
        with open(path, "w") as f:
            writer = csv.writer(f, delimiter=",")
            content = [["index", "latency", "jitter", "recv-time", "recv-size"]]
            writer.writerows(content + self.log)

    def __del__(self):
        """析构函数，确保socket正确关闭"""
        self._udp_socket.close()


if __name__ == "__main__":
    # 解析命令行参数
    try:
        _opts, _ = getopt.getopt(
            sys.argv[1:],
            "csf:n:t:b:m:",
            ["verbose=", "save=", "ip=", "port=", "sync=", "dyna="],
        )
        opts = dict(_opts)
        # 设置默认参数
        opts.setdefault("-f", "1")  # 默认频率1Hz
        opts.setdefault("-n", "1500")  # 默认包大小1500字节
        opts.setdefault("-t", "10")  # 默认运行时间10秒
        opts.setdefault("-b", "1500")  # 默认缓冲区大小1500字节
        opts.setdefault("--ip", "127.0.0.1")  # 默认IP地址
        opts.setdefault("--port", "20001")  # 默认端口
        opts.setdefault("--verbose", "True")  # 默认显示详细信息
        opts.setdefault("--save", "result.csv")  # 默认保存文件名
        opts.setdefault("--dyna", "True")  # 默认使用动态发送间隔
        opts.setdefault("--sync", "True")  # 默认进行时间同步

    except getopt.GetoptError:
        # 显示使用说明
        print(
            "For Client --> udp_latency.py -c -f/m <frequency / bandwidth> -m <bandwidth> -n <packet size> -t <running time> --ip <remote ip> --port <to port> --verbose <bool> --sync <bool>"
        )
        print(
            "For Server --> udp_latency.py -s -b <buffer size> --ip <remote ip> --port <local port> --verbose <bool> --sync <bool> --save <records saving path>"
        )
        sys.exit(2)

    # 根据参数启动客户端或服务器
    if "-c" in opts.keys():
        client = Client(remote_ip=opts["--ip"], to_port=int(opts["--port"]))
        _f: float
        if "-m" in opts:
            # 根据带宽计算发送频率
            _f = float(opts["-m"]) * 125000 / int(opts["-n"])
        elif opts["-f"] == "m":
            _f = math.inf
        else:
            _f = float(opts["-f"])
        client.send(
            float(_f),
            int(opts["-n"]),
            int(opts["-t"]),
            eval(opts["--verbose"]),
            sync=eval(opts["--sync"]),
            dyna=eval(opts["--dyna"]),
        )

    if "-s" in opts.keys():
        server = Server(remote_ip=opts["--ip"], local_port=int(opts["--port"]))
        server.listen(
            buffer_size=int(opts["-b"]),
            verbose=eval(opts["--verbose"]),
            sync=eval(opts["--sync"]),
        )
        server.evaluate()
        if "--save" in opts.keys():
            server.save(opts["--save"])
