#!/usr/bin/env python3
import time
import csv
import os
import sys
import getopt
import threading
from datetime import datetime
from typing import Dict, Any, Optional

# 配置参数
DEFAULT_CONFIG = {
    "log_interval": 1.0,        # 记录间隔(秒)
    "running_time": 3600,       # 最长运行时间(秒)，默认1小时
    "verbose": True,            # 是否打印详细信息
    "log_path": "./logs",       # 日志保存路径
}

class GPSLogger:
    """
    GPS数据记录器，用于记录无人机的GPS位置信息。
    注意：这是一个占位实现，实际使用时需要与无人机的GPS系统集成。
    """
    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化GPS记录器
        Args:
            config: 配置参数字典
        """
        self.log_interval = config.get("log_interval", DEFAULT_CONFIG["log_interval"])
        self.running_time = config.get("running_time", DEFAULT_CONFIG["running_time"])
        self.verbose = config.get("verbose", DEFAULT_CONFIG["verbose"])
        self.log_path = config.get("log_path", DEFAULT_CONFIG["log_path"])
        
        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        
        # 创建GPS日志文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self.log_path, f"gps_log_{timestamp}.csv")
        
        # 初始化日志
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "latitude", "longitude", "altitude", "speed", "heading"])
        
        # 停止标志
        self.stop_flag = threading.Event()
        
        if self.verbose:
            print(f"GPS Logger initialized")
            print(f"Log interval: {self.log_interval} seconds")
            print(f"Log file: {self.log_file}")
    
    def get_gps_data(self) -> Dict[str, Any]:
        """
        获取GPS数据
        注意：这是一个占位函数，实际实现需要与无人机系统集成
        Returns:
            包含GPS数据的字典
        """
        # 这里应该是从GPS硬件获取位置数据的代码
        # 实际实现时需要根据具体的硬件接口进行开发
        
        # 模拟GPS数据
        return {
            "latitude": 40.7128,  # 模拟纬度
            "longitude": -74.0060,  # 模拟经度
            "altitude": 100.0,  # 模拟高度(米)
            "speed": 5.0,  # 模拟速度(米/秒)
            "heading": 90.0,  # 模拟航向(度)
        }
    
    def log_gps_data(self) -> None:
        """
        记录GPS数据到日志文件
        """
        # 获取当前时间和GPS数据
        current_time = time.time()
        gps_data = self.get_gps_data()
        
        # 记录到日志
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                current_time,
                gps_data.get("latitude", 0.0),
                gps_data.get("longitude", 0.0),
                gps_data.get("altitude", 0.0),
                gps_data.get("speed", 0.0),
                gps_data.get("heading", 0.0)
            ])
        
        # 打印信息
        if self.verbose:
            print(f"Logged GPS data at {current_time:.6f}: " + 
                  f"lat={gps_data.get('latitude', 0.0):.6f}, " + 
                  f"lon={gps_data.get('longitude', 0.0):.6f}, " + 
                  f"alt={gps_data.get('altitude', 0.0):.1f}m")
    
    def run(self) -> None:
        """
        运行GPS记录器
        """
        start_time = time.time()
        end_time = start_time + self.running_time
        
        try:
            if self.verbose:
                print("Starting GPS logging...")
            
            while time.time() < end_time and not self.stop_flag.is_set():
                loop_start = time.time()
                
                # 记录GPS数据
                self.log_gps_data()
                
                # 计算等待时间，确保日志间隔准确
                elapsed = time.time() - loop_start
                sleep_time = max(0, self.log_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            if self.verbose:
                print(f"GPS logging completed.")
                print(f"Log saved to {self.log_file}")
        
        except KeyboardInterrupt:
            print("\nGPS logging interrupted by user.")
        finally:
            self.stop_flag.set()
    
    def stop(self) -> None:
        """
        停止GPS记录器
        """
        self.stop_flag.set()


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
            "hi:t:v",
            ["interval=", "time=", "verbose=", "log-path="]
        )
        
        for opt, arg in opts:
            if opt == '-h':
                print("Usage: gps_logger.py [options]")
                print("Options:")
                print("  -i, --interval=INTERVAL  Log interval in seconds (default: 1.0)")
                print("  -t, --time=TIME          Maximum running time in seconds (default: 3600)")
                print("  -v, --verbose=BOOL       Verbose output (default: True)")
                print("      --log-path=PATH      Log file path (default: ./logs)")
                sys.exit()
            elif opt in ("-i", "--interval"):
                config["log_interval"] = float(arg)
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
    
    # 创建并启动GPS记录器
    logger = GPSLogger(config)
    logger.run() 