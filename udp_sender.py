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
from typing import List, Dict, Any, Optional

from resilient_csv import ResilientCsvWriter

# 配置参数
DEFAULT_CONFIG = {
    "local_ip": "0.0.0.0",         # 本地IP地址
    "local_port": 20002,           # 本地端口
    "remote_ip": "192.168.104.2",  # 接收端IP地址
    "remote_port": 20001,          # 接收端端口
    "packet_size": 1000,           # 数据包大小(字节)
    "frequency": 10.0,             # 发送频率(Hz)
    "running_time": 60,            # 运行时间(秒)
    "verbose": True,               # 是否打印详细信息
    "log_path": "./logs",          # 日志保存路径
}

# 根据 errno 将常见的网络/套接字异常拆分，方便在运行时决定是否需要重建 socket
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

RECREATE_SOCKET_ERRNOS = {
    errno.EBADF,
    errno.ENOTCONN,
    errno.EPIPE,
    errno.EINVAL,
}

MAX_RETRY_SLEEP = 5.0
MIN_RETRY_SLEEP = 0.05

class UDPSender:
    """
    UDP发送端类，用于生成并发送UDP数据包，并记录发送日志。
    适用于无人机通信测试系统。
    """
    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化UDP发送端
        Args:
            config: 配置参数字典，包含IP地址、端口、发送频率等
        """
        self.local_ip = config.get("local_ip", DEFAULT_CONFIG["local_ip"])
        self.local_port = config.get("local_port", DEFAULT_CONFIG["local_port"])
        self.remote_ip = config.get("remote_ip", DEFAULT_CONFIG["remote_ip"])
        self.remote_port = config.get("remote_port", DEFAULT_CONFIG["remote_port"])
        self.packet_size = config.get("packet_size", DEFAULT_CONFIG["packet_size"])
        self.frequency = config.get("frequency", DEFAULT_CONFIG["frequency"])
        self.running_time = config.get("running_time", DEFAULT_CONFIG["running_time"])
        self.verbose = config.get("verbose", DEFAULT_CONFIG["verbose"])
        self.log_path = config.get("log_path", DEFAULT_CONFIG["log_path"])
        
        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        
        # 创建发送日志文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self.log_path, f"udp_sender_{timestamp}.csv")
        self._csv_log = ResilientCsvWriter(
            self.log_file,
            header=["seq_num", "timestamp", "send_done_timestamp", "packet_size"],
            flush_every=10,
            flush_interval_s=1.0,
            inode_check_every=50,
            inode_check_interval_s=1.0,
            retry_base_interval_s=5.0,
            retry_max_interval_s=60.0,
            verbose=self.verbose,
            label="UDP_SENDER",
        )
        self._csv_log.ensure_open()
        
        # 初始化序列号
        self.seq_num = 1
        
        # 创建UDP socket
        self._udp_socket: Optional[socket.socket] = None
        self._recreate_socket(initial=True)

        if self.verbose:
            print(f"UDP Sender initialized: {self.local_ip}:{self.local_port} -> {self.remote_ip}:{self.remote_port}")
            print(f"Packet size: {self.packet_size} bytes, Frequency: {self.frequency} Hz")
            print(f"Log file: {self.log_file}")
    
    def create_packet(self, send_time: float) -> bytes:
        """
        创建UDP数据包，使用调用方传入的发送时间戳，避免重复取时导致的记录不一致。
        Args:
            send_time: 计划发送该数据包时的时间戳(秒)
        Returns:
            包含序列号和时间戳的UDP数据包
        """
        # 使用struct来高效打包数据:
        # I: 4字节无符号整数(序列号)
        # d: 8字节双精度浮点数(时间戳)
        packet_header = struct.pack("!Id", self.seq_num, send_time)

        # 填充剩余空间，确保包大小符合要求
        remaining_size = max(0, self.packet_size - len(packet_header))
        packet = packet_header + b'\x00' * remaining_size

        return packet
    
    def send(self) -> None:
        """
        发送UDP数据包并记录日志
        """
        # 计算发送间隔
        send_interval = 1.0 / self.frequency
        
        # 计算结束时间
        end_time = time.time() + self.running_time
        
        try:
            if self.verbose:
                print("Starting UDP packet transmission...")
            
            while time.time() < end_time:
                # 发送开始时间
                start_loop = time.time()
                
                # 单次取时，作为包内时间戳和本地日志时间，避免双份时间记录产生偏差
                send_time = time.time()

                # 创建并发送数据包
                packet = self.create_packet(send_time)
                bytes_sent = self._send_packet_with_retry(packet, send_interval)
                if bytes_sent is None:
                    continue
                
                # 记录日志（失败时不影响发送流程）
                send_done_time = time.time()
                self._append_log_entry(self.seq_num, send_time, send_done_time, bytes_sent)
                
                # 打印发送信息
                if self.verbose:
                    print(f"Sent packet #{self.seq_num} at {send_time:.6f}, size: {bytes_sent} bytes")
                
                # 增加序列号
                self.seq_num += 1
                
                # 计算发送耗时，调整等待时间以保持频率
                elapsed = time.time() - start_loop
                sleep_time = max(0, send_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            if self.verbose:
                print(f"Transmission completed. Sent {self.seq_num-1} packets.")
                print(f"Log saved to {self.log_file}")
        
        except KeyboardInterrupt:
            print("\nTransmission interrupted by user.")
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
        seq: int,
        packet_timestamp: float,
        send_done_timestamp: float,
        packet_size: int,
    ) -> None:
        self._csv_log.write_row([seq, packet_timestamp, send_done_timestamp, packet_size])

    def _close_log_file(self) -> None:
        self._csv_log.close()

    def _retry_sleep(self, send_interval: float) -> float:
        """计算一次重试前需要休眠的时间，避免忙等"""
        return min(MAX_RETRY_SLEEP, max(MIN_RETRY_SLEEP, send_interval))

    def _send_packet_with_retry(self, packet: bytes, send_interval: float) -> Optional[int]:
        """发送单个数据包，遇到异常时根据类型自动恢复，并通过返回 None 让上层重试"""
        if self._udp_socket is None:
            self._recreate_socket()
            time.sleep(self._retry_sleep(send_interval))
            return None
        try:
            return self._udp_socket.sendto(packet, (self.remote_ip, self.remote_port))
        except OSError as exc:
            self._handle_socket_error(exc, send_interval)
            return None
        except Exception as exc:
            if self.verbose:
                print(f"Unexpected error while sending packet #{self.seq_num}: {exc}. Retrying...")
            time.sleep(self._retry_sleep(send_interval))
            return None

    def _handle_socket_error(self, exc: OSError, send_interval: float) -> None:
        """根据 errno 区分网络波动和真正的套接字异常，决定是否需要重建 socket"""
        err = exc.errno if isinstance(exc, OSError) else None
        if self.verbose:
            print(
                f"Socket error while sending packet #{self.seq_num}: {exc}"
                + (f" (errno={err})" if err is not None else "")
            )

        if err in RETRYABLE_NETWORK_ERRNOS:
            time.sleep(self._retry_sleep(send_interval))
            return

        if self.verbose and err in RECREATE_SOCKET_ERRNOS:
            print("Socket no longer valid, recreating descriptor...")

        # 对于无法恢复的错误，主动重建 socket 并持续尝试
        self._recreate_socket()
        time.sleep(self._retry_sleep(send_interval))

    def _recreate_socket(self, initial: bool = False) -> None:
        """关闭旧的 socket 并尽可能重新创建/绑定，直到成功"""
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
                self._udp_socket = sock
                if self.verbose and not initial:
                    print(f"Socket recreated: {self.local_ip}:{self.local_port} -> {self.remote_ip}:{self.remote_port}")
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
            "hi:p:r:o:s:f:t:v",
            ["local-ip=", "local-port=", "remote-ip=", "remote-port=", 
             "packet-size=", "frequency=", "time=", "verbose=", "log-path="]
        )
        
        for opt, arg in opts:
            if opt == '-h':
                print("Usage: udp_sender.py [options]")
                print("Options:")
                print("  -i, --local-ip=IP       Local IP address (default: 0.0.0.0)")
                print("  -p, --local-port=PORT   Local port (default: 20002)")
                print("  -r, --remote-ip=IP      Remote IP address (default: 192.168.104.2)")
                print("  -o, --remote-port=PORT  Remote port (default: 20001)")
                print("  -s, --packet-size=SIZE  Packet size in bytes (default: 1000)")
                print("  -f, --frequency=FREQ    Sending frequency in Hz (default: 10.0)")
                print("  -t, --time=TIME         Running time in seconds (default: 60)")
                print("  -v, --verbose=BOOL      Verbose output (default: True)")
                print("      --log-path=PATH     Log file path (default: ./logs)")
                sys.exit()
            elif opt in ("-i", "--local-ip"):
                config["local_ip"] = arg
            elif opt in ("-p", "--local-port"):
                config["local_port"] = int(arg)
            elif opt in ("-r", "--remote-ip"):
                config["remote_ip"] = arg
            elif opt in ("-o", "--remote-port"):
                config["remote_port"] = int(arg)
            elif opt in ("-s", "--packet-size"):
                config["packet_size"] = int(arg)
            elif opt in ("-f", "--frequency"):
                config["frequency"] = float(arg)
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
    
    # 创建并启动UDP发送端
    sender = UDPSender(config)
    sender.send()
