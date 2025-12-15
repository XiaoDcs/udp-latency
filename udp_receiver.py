#!/usr/bin/env python3
import socket
import time
import json
import sys
import getopt
import struct
import os
import errno
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from resilient_csv import ResilientCsvWriter

# 配置参数
DEFAULT_CONFIG = {
    "local_ip": "0.0.0.0",         # 本地IP地址
    "local_port": 20001,           # 本地端口
    "buffer_size": 1500,           # 接收缓冲区大小
    "running_time": 3600,          # 最长运行时间(秒)，默认1小时
    "verbose": True,               # 是否打印详细信息
    "log_path": "./logs",          # 日志保存路径
}

# 常见可恢复的网络异常码，出现时仅重试
RETRYABLE_NETWORK_ERRNOS = {
    errno.EAGAIN,
    errno.EWOULDBLOCK,
    errno.EINTR,
    errno.ENETUNREACH,
    errno.EHOSTUNREACH,
    errno.EHOSTDOWN,
    errno.ENETDOWN,
    errno.ENETRESET,
    errno.ECONNRESET,
    errno.ECONNREFUSED,
    errno.ENOBUFS,
}

# 套接字已失效时需要重建
RECREATE_SOCKET_ERRNOS = {
    errno.EBADF,
    errno.ENOTCONN,
    errno.EPIPE,
    errno.EINVAL,
}

DEFAULT_SOCKET_TIMEOUT = 1.0
MAX_RETRY_SLEEP = 5.0
MIN_RETRY_SLEEP = 0.05
DEFAULT_RETRY_INTERVAL = 0.5

class UDPReceiver:
    """
    UDP接收端类，用于接收UDP数据包，计算延迟和丢包率，并记录接收日志。
    适用于无人机通信测试系统。
    """
    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化UDP接收端
        Args:
            config: 配置参数字典，包含IP地址、端口等
        """
        self.local_ip = config.get("local_ip", DEFAULT_CONFIG["local_ip"])
        self.local_port = config.get("local_port", DEFAULT_CONFIG["local_port"])
        self.buffer_size = config.get("buffer_size", DEFAULT_CONFIG["buffer_size"])
        self.running_time = config.get("running_time", DEFAULT_CONFIG["running_time"])
        self.verbose = config.get("verbose", DEFAULT_CONFIG["verbose"])
        self.log_path = config.get("log_path", DEFAULT_CONFIG["log_path"])
        
        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        
        # 创建接收日志文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self.log_path, f"udp_receiver_{timestamp}.csv")
        self._csv_log = ResilientCsvWriter(
            self.log_file,
            header=[
                "seq_num",
                "send_timestamp",
                "recv_timestamp",
                "delay",
                "src_ip",
                "src_port",
                "packet_size",
            ],
            flush_every=10,
            flush_interval_s=1.0,
            inode_check_every=50,
            inode_check_interval_s=1.0,
            retry_base_interval_s=5.0,
            retry_max_interval_s=60.0,
            verbose=self.verbose,
            label="UDP_RECEIVER",
        )
        self._csv_log.ensure_open()
        
        # 记录最近收到的序列号，用于检测丢包
        self.last_seq_num = 0
        self.packets_received = 0
        self.packets_lost = 0
        self._retry_base_interval = DEFAULT_RETRY_INTERVAL
        
        # 创建UDP socket
        self._udp_socket = None
        self._recreate_socket(initial=True)
        
        if self.verbose:
            print(f"UDP Receiver initialized: {self.local_ip}:{self.local_port}")
            print(f"Buffer size: {self.buffer_size} bytes")
            print(f"Log file: {self.log_file}")
    
    def parse_packet(self, data: bytes) -> Tuple[int, float]:
        """
        解析UDP数据包
        Args:
            data: 收到的UDP数据包
        Returns:
            (序列号, 发送时间戳)
        """
        # 检查数据包长度是否足够
        if len(data) < 12:  # 4(seq) + 8(timestamp)
            return 0, 0.0
        
        # 使用struct解包数据:
        # I: 4字节无符号整数(序列号)
        # d: 8字节双精度浮点数(时间戳)
        seq_num, send_time = struct.unpack("!Id", data[:12])
        
        return seq_num, send_time
    
    def calculate_packet_loss(self, seq_num: int) -> int:
        """
        计算丢包数量
        Args:
            seq_num: 当前收到的序列号
        Returns:
            丢失的包数量
        """
        if self.last_seq_num == 0:
            self.last_seq_num = seq_num
            return 0
        
        # 如果序列号连续，没有丢包
        if seq_num == self.last_seq_num + 1:
            self.last_seq_num = seq_num
            return 0
        
        # 如果序列号不连续，计算丢包数
        lost_packets = seq_num - self.last_seq_num - 1
        self.last_seq_num = seq_num
        return max(0, lost_packets)
    
    def listen(self) -> None:
        """
        监听并接收UDP数据包，计算延迟和丢包率
        """
        start_time = time.time()
        end_time = start_time + self.running_time
        
        try:
            if self.verbose:
                print("Starting UDP packet reception...")
            
            while time.time() < end_time:
                packet = self._recv_packet_with_retry()
                if packet is None:
                    continue

                data, addr, recv_time = packet

                try:
                    # 解析数据包
                    seq_num, send_time = self.parse_packet(data)

                    # 跳过无效数据包
                    if seq_num == 0:
                        continue

                    # 计算延迟(秒)
                    delay = recv_time - send_time

                    # 检查丢包
                    lost_packets = self.calculate_packet_loss(seq_num)
                    if lost_packets > 0:
                        self.packets_lost += lost_packets
                        if self.verbose:
                            print(f"Detected {lost_packets} lost packets before #{seq_num}")

                    # 增加已接收数据包计数
                    self.packets_received += 1

                    # 记录日志（失败不影响循环）
                    self._append_log_entry(
                        seq_num,
                        send_time,
                        recv_time,
                        delay,
                        addr,
                        len(data),
                    )

                    # 打印接收信息
                    if self.verbose:
                        print(
                            f"Received packet #{seq_num} from {addr[0]}:{addr[1]}, delay: {delay:.6f}s"
                        )

                except Exception as exc:
                    if self.verbose:
                        print(
                            f"Error processing packet from {addr[0]}:{addr[1]}: {exc}. Packet skipped."
                        )
                    continue

            # 计算总丢包率
            total_expected = self.packets_received + self.packets_lost
            packet_loss_rate = 0 if total_expected == 0 else (self.packets_lost / total_expected) * 100
            
            # 打印统计数据（不记录到日志）
            if self.verbose:
                print(f"Reception completed. Received {self.packets_received} packets.")
                print(f"Detected {self.packets_lost} lost packets.")
                print(f"Packet loss rate: {packet_loss_rate:.2f}%")
                print(f"Log saved to {self.log_file}")
        
        except KeyboardInterrupt:
            print("\nReception interrupted by user.")
        finally:
            if self._udp_socket:
                self._udp_socket.close()
            self._close_log_file()

    def __del__(self):
        """析构函数，确保socket正确关闭"""
        try:
            if self._udp_socket:
                self._udp_socket.close()
        except:
            pass
        self._close_log_file()

    def _append_log_entry(
        self,
        seq_num: int,
        send_time: float,
        recv_time: float,
        delay: float,
        addr: Tuple[str, int],
        packet_size: int,
    ) -> None:
        self._csv_log.write_row(
            [
                seq_num,
                send_time,
                recv_time,
                delay,
                addr[0],
                addr[1],
                packet_size,
            ]
        )

    def _close_log_file(self) -> None:
        self._csv_log.close()

    def _retry_sleep(self) -> float:
        return min(MAX_RETRY_SLEEP, max(MIN_RETRY_SLEEP, self._retry_base_interval))

    def _recv_packet_with_retry(self) -> Optional[Tuple[bytes, Tuple[str, int], float]]:
        if self._udp_socket is None:
            self._recreate_socket()
            time.sleep(self._retry_sleep())
            return None
        try:
            data, addr = self._udp_socket.recvfrom(self.buffer_size)
            return data, addr, time.time()
        except socket.timeout:
            # 用于周期性检查退出条件
            return None
        except OSError as exc:
            self._handle_socket_error(exc)
            return None
        except Exception as exc:
            if self.verbose:
                print(f"Unexpected error while receiving UDP packet: {exc}. Retrying...")
            time.sleep(self._retry_sleep())
            return None

    def _handle_socket_error(self, exc: OSError) -> None:
        err = exc.errno if isinstance(exc, OSError) else None
        if self.verbose:
            print(
                f"Socket error while receiving UDP packet: {exc}"
                + (f" (errno={err})" if err is not None else "")
            )

        if err in RETRYABLE_NETWORK_ERRNOS:
            time.sleep(self._retry_sleep())
            return

        if self.verbose and err in RECREATE_SOCKET_ERRNOS:
            print("Socket no longer valid, recreating descriptor...")

        self._recreate_socket()
        time.sleep(self._retry_sleep())

    def _recreate_socket(self, initial: bool = False) -> None:
        if self._udp_socket is not None:
            try:
                self._udp_socket.close()
            except OSError:
                pass

        while True:
            try:
                sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((self.local_ip, self.local_port))
                sock.settimeout(DEFAULT_SOCKET_TIMEOUT)
                self._udp_socket = sock
                if self.verbose and not initial:
                    print(
                        f"Socket recreated: {self.local_ip}:{self.local_port} waiting for packets"
                    )
                return
            except OSError as exc:
                if self.verbose:
                    print(f"Failed to create/bind UDP socket: {exc}. Retrying in 1s...")
                time.sleep(1.0)


def parse_args() -> Dict[str, Any]:
    """
    解析命令行参数
    Returns:
        包含配置参数的字典
    """
    config = DEFAULT_CONFIG.copy()
    
    try:
        opts, _ = getopt.getopt(
            sys.argv[1:],
            "hi:p:b:t:v",
            ["local-ip=", "local-port=", "buffer-size=", "time=", "verbose=", "log-path="]
        )
        
        for opt, arg in opts:
            if opt == '-h':
                print("Usage: udp_receiver.py [options]")
                print("Options:")
                print("  -i, --local-ip=IP       Local IP address (default: 0.0.0.0)")
                print("  -p, --local-port=PORT   Local port (default: 20001)")
                print("  -b, --buffer-size=SIZE  Buffer size in bytes (default: 1500)")
                print("  -t, --time=TIME         Maximum running time in seconds (default: 3600)")
                print("  -v, --verbose=BOOL      Verbose output (default: True)")
                print("      --log-path=PATH     Log file path (default: ./logs)")
                sys.exit()
            elif opt in ("-i", "--local-ip"):
                config["local_ip"] = arg
            elif opt in ("-p", "--local-port"):
                config["local_port"] = int(arg)
            elif opt in ("-b", "--buffer-size"):
                config["buffer_size"] = int(arg)
            elif opt in ("-t", "--time"):
                config["running_time"] = int(arg)
            elif opt in ("-v", "--verbose"):
                config["verbose"] = arg.lower() in ("true", "yes", "1")
            elif opt == "--log-path":
                config["log_path"] = arg
    
    except getopt.GetoptError:
        print("Error parsing arguments. Use -h for help.")
        sys.exit(2)
    
    return config


if __name__ == "__main__":
    # 解析命令行参数
    config = parse_args()
    
    # 创建并启动UDP接收端
    receiver = UDPReceiver(config)
    receiver.listen()
