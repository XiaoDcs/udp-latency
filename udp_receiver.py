#!/usr/bin/env python3
import socket
import time
import json
import csv
import sys
import getopt
import struct
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# 配置参数
DEFAULT_CONFIG = {
    "local_ip": "0.0.0.0",         # 本地IP地址
    "local_port": 20001,           # 本地端口
    "buffer_size": 1500,           # 接收缓冲区大小
    "running_time": 3600,          # 最长运行时间(秒)，默认1小时
    "verbose": True,               # 是否打印详细信息
    "log_path": "./logs",          # 日志保存路径
}

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
        
        # 初始化日志
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["seq_num", "send_timestamp", "recv_timestamp", "delay", "src_ip", "src_port", "packet_size"])
        
        # 记录最近收到的序列号，用于检测丢包
        self.last_seq_num = 0
        self.packets_received = 0
        self.packets_lost = 0
        
        # 创建UDP socket
        self._udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self._udp_socket.bind((self.local_ip, self.local_port))
        
        # 设置超时，以便定期检查是否应该停止
        self._udp_socket.settimeout(1.0)
        
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
                try:
                    # 接收数据包
                    data, addr = self._udp_socket.recvfrom(self.buffer_size)
                    recv_time = time.time()
                    
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
                    
                    # 记录日志
                    with open(self.log_file, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            seq_num, send_time, recv_time, delay,
                            addr[0], addr[1], len(data)
                        ])
                    
                    # 打印接收信息
                    if self.verbose:
                        print(f"Received packet #{seq_num} from {addr[0]}:{addr[1]}, delay: {delay:.6f}s")
                
                except socket.timeout:
                    # 超时只是为了定期检查是否应该退出循环
                    continue
                except Exception as e:
                    print(f"Error receiving packet: {e}")
            
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
            self._udp_socket.close()
    
    def __del__(self):
        """析构函数，确保socket正确关闭"""
        try:
            self._udp_socket.close()
        except:
            pass


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