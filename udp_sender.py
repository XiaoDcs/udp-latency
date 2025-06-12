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
from typing import List, Dict, Any, Optional

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
    "network_retry_delay": 1.0,    # 网络错误重试延迟(秒)
    "log_network_errors": True,    # 是否记录网络错误到日志
}

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
        self.network_retry_delay = config.get("network_retry_delay", DEFAULT_CONFIG["network_retry_delay"])
        self.log_network_errors = config.get("log_network_errors", DEFAULT_CONFIG["log_network_errors"])
        
        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        
        # 创建发送日志文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self.log_path, f"udp_sender_{timestamp}.csv")
        
        # 初始化日志
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["seq_num", "timestamp", "packet_size_or_error"])
        
        # 初始化序列号
        self.seq_num = 1
        
        # 统计信息
        self.successful_sends = 0
        self.network_errors = 0
        
        # 创建UDP socket
        self._udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self._udp_socket.bind((self.local_ip, self.local_port))
        
        if self.verbose:
            print(f"UDP Sender initialized: {self.local_ip}:{self.local_port} -> {self.remote_ip}:{self.remote_port}")
            print(f"Packet size: {self.packet_size} bytes, Frequency: {self.frequency} Hz")
            print(f"Log file: {self.log_file}")
    
    def create_packet(self) -> bytes:
        """
        创建UDP数据包
        Returns:
            包含序列号和时间戳的UDP数据包
        """
        # 获取当前时间戳(秒)
        current_time = time.time()
        
        # 创建数据包内容
        # 使用struct来高效打包数据:
        # I: 4字节无符号整数(序列号)
        # d: 8字节双精度浮点数(时间戳)
        packet_header = struct.pack("!Id", self.seq_num, current_time)
        
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
                
                try:
                    # 创建并发送数据包
                    packet = self.create_packet()
                    bytes_sent = self._udp_socket.sendto(packet, (self.remote_ip, self.remote_port))
                    
                    # 获取当前时间戳和无人机状态
                    send_time = time.time()
                    
                    # 记录日志
                    with open(self.log_file, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([self.seq_num, send_time, bytes_sent])
                    
                    # 打印发送信息
                    if self.verbose:
                        print(f"Sent packet #{self.seq_num} at {send_time:.6f}, size: {bytes_sent} bytes")
                    
                    # 增加序列号
                    self.seq_num += 1
                    
                    # 统计成功发送
                    self.successful_sends += 1
                    
                except OSError as e:
                    # 处理网络相关错误（如Network is unreachable）
                    error_time = time.time()
                    error_msg = f"Network error for packet #{self.seq_num}: {e}"
                    
                    if self.verbose:
                        print(f"⚠️  {error_msg}")
                    
                    # 记录网络错误到日志（如果启用）
                    if self.log_network_errors:
                        with open(self.log_file, 'a', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow([self.seq_num, error_time, f"ERROR: {e}"])
                    
                    # 增加序列号（即使发送失败也要继续计数）
                    self.seq_num += 1
                    
                    # 统计网络错误
                    self.network_errors += 1
                    
                    # 网络错误时等待一段时间再重试
                    if self.verbose:
                        print(f"⏳ Waiting {self.network_retry_delay}s before retry...")
                    time.sleep(self.network_retry_delay)
                    continue
                
                # 计算发送耗时，调整等待时间以保持频率
                elapsed = time.time() - start_loop
                sleep_time = max(0, send_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            if self.verbose:
                total_attempts = self.seq_num - 1
                success_rate = (self.successful_sends / total_attempts * 100) if total_attempts > 0 else 0
                print(f"\n📊 Transmission completed!")
                print(f"   Total attempts: {total_attempts}")
                print(f"   Successful sends: {self.successful_sends}")
                print(f"   Network errors: {self.network_errors}")
                print(f"   Success rate: {success_rate:.1f}%")
                print(f"   Log saved to {self.log_file}")
        
        except KeyboardInterrupt:
            if self.verbose:
                total_attempts = self.seq_num - 1
                success_rate = (self.successful_sends / total_attempts * 100) if total_attempts > 0 else 0
                print(f"\n⚡ Transmission interrupted by user!")
                print(f"   Total attempts: {total_attempts}")
                print(f"   Successful sends: {self.successful_sends}")
                print(f"   Network errors: {self.network_errors}")
                print(f"   Success rate: {success_rate:.1f}%")
                print(f"   Log saved to {self.log_file}")
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