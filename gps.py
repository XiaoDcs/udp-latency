#!/usr/bin/env python3
"""
无人机GPS数据记录脚本
将GPS数据保存到文件中，集成到UDP通信测试系统
"""

import rclpy
import time
import csv
import signal
import sys
import os
import getopt
from datetime import datetime
from typing import Dict, Any, Optional
from as2_python_api.drone_interface_gps import DroneInterfaceGPS

# 默认配置参数
DEFAULT_CONFIG = {
    "drone_id": "drone0",           # 无人机命名空间
    "log_path": "./logs",           # 日志保存路径
    "log_interval": 0.5,            # 记录间隔(秒)
    "running_time": 3600,           # 最长运行时间(秒)
    "use_sim_time": False,          # 是否使用仿真时间
    "verbose": True,                # 是否打印详细信息
}

class GPSLogger:
    """GPS数据记录器类，集成到UDP通信测试系统"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化GPS记录器
        
        Args:
            config: 配置参数字典
        """
        self.drone_id = config.get("drone_id", DEFAULT_CONFIG["drone_id"])
        self.log_path = config.get("log_path", DEFAULT_CONFIG["log_path"])
        self.log_interval = config.get("log_interval", DEFAULT_CONFIG["log_interval"])
        self.running_time = config.get("running_time", DEFAULT_CONFIG["running_time"])
        self.use_sim_time = config.get("use_sim_time", DEFAULT_CONFIG["use_sim_time"])
        self.verbose = config.get("verbose", DEFAULT_CONFIG["verbose"])
        
        self.running = True
        
        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        
        # 生成日志文件名（与UDP测试系统保持一致的命名格式）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self.log_path, f"gps_logger_{self.drone_id}_{timestamp}.csv")
        
        # 创建无人机接口
        if self.verbose:
            print(f"正在连接到无人机: {self.drone_id}...")
        
        try:
            self.drone = DroneInterfaceGPS(
                drone_id=self.drone_id, 
                verbose=False, 
                use_sim_time=self.use_sim_time
            )
        except Exception as e:
            print(f"连接无人机失败: {e}")
            sys.exit(1)
        
        # 初始化CSV文件
        self.init_csv_file()
        
        # 设置信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        
        if self.verbose:
            print(f"GPS记录器初始化完成")
            print(f"无人机ID: {self.drone_id}")
            print(f"记录间隔: {self.log_interval}秒")
            print(f"日志文件: {self.log_file}")
        
    def signal_handler(self, signum, frame):
        """处理Ctrl+C信号"""
        if self.verbose:
            print("\n正在停止GPS记录...")
        self.running = False
        
    def init_csv_file(self):
        """初始化CSV文件，写入表头（与UDP测试系统格式保持一致）"""
        try:
            with open(self.log_file, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                # 使用与原始文件一致的列名格式
                writer.writerow([
                    'timestamp',        # 时间戳（Unix时间戳）
                    'latitude',         # 纬度
                    'longitude',        # 经度
                    'altitude',         # 海拔高度
                    'local_x',          # 本地坐标X
                    'local_y',          # 本地坐标Y
                    'local_z',          # 本地坐标Z
                    'connected',        # 连接状态
                    'armed',            # 解锁状态
                    'offboard'          # Offboard模式状态
                ])
            if self.verbose:
                print(f"GPS数据将记录到: {self.log_file}")
        except Exception as e:
            print(f"创建CSV文件时出错: {e}")
            sys.exit(1)
            
    def log_gps_data(self):
        """记录GPS数据到文件（使用Unix时间戳格式）"""
        try:
            # 获取时间戳（使用Unix时间戳，与UDP测试系统保持一致）
            timestamp = time.time()
            
            # 获取GPS数据
            gps_pose = self.drone.gps.pose
            lat, lon, alt = gps_pose if gps_pose and len(gps_pose) == 3 else [0.0, 0.0, 0.0]
            
            # 获取本地位置
            local_pos = self.drone.position
            x, y, z = local_pos if local_pos and len(local_pos) == 3 else [0.0, 0.0, 0.0]
            
            # 获取无人机状态
            info = self.drone.info
            connected = info.get('connected', False)
            armed = info.get('armed', False)
            offboard = info.get('offboard', False)
            
            # 写入CSV文件
            with open(self.log_file, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    timestamp,                                  # Unix时间戳
                    lat, lon, alt,                             # GPS坐标
                    x, y, z,                                   # 本地坐标
                    connected, armed, offboard,                # 无人机状态
                ])
                
            # 显示当前数据（格式与UDP测试系统保持一致）
            if self.verbose:
                print(f"GPS logged at {timestamp:.6f}: "
                      f"GPS({lat:.6f}, {lon:.6f}, {alt:.2f}m) "
                      f"Local({x:.2f}, {y:.2f}, {z:.2f}m)")
            
        except Exception as e:
            print(f"记录GPS数据时出错: {e}")
    
    def run(self):
        """
        运行GPS数据记录
        """
        if self.verbose:
            print("GPS数据记录器已启动")
            print(f"最长运行时间: {self.running_time}秒")
            print("按 Ctrl+C 停止记录\n")
        
        # 计算结束时间
        end_time = time.time() + self.running_time
        
        while self.running and rclpy.ok() and time.time() < end_time:
            try:
                self.log_gps_data()
                time.sleep(self.log_interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"运行时错误: {e}")
                time.sleep(1.0)
                
        self.cleanup()
        
    def cleanup(self):
        """清理资源"""
        if self.verbose:
            print(f"\nGPS数据已保存到: {self.log_file}")
        try:
            self.drone.shutdown()
        except Exception as e:
            print(f"清理时出错: {e}")
        if self.verbose:
            print("GPS记录器已退出")


def parse_args() -> Dict[str, Any]:
    """
    解析命令行参数（与UDP测试系统保持一致的参数格式）
    Returns:
        包含配置参数的字典
    """
    config = DEFAULT_CONFIG.copy()
    
    try:
        opts, _ = getopt.getopt(
            sys.argv[1:],
            "hd:i:t:v",
            ["drone-id=", "log-path=", "interval=", "time=", "sim-time", "verbose=", "help"]
        )
        
        for opt, arg in opts:
            if opt in ("-h", "--help"):
                print("GPS数据记录器 - 无人机UDP通信测试系统")
                print("")
                print("使用方法: gps.py [选项]")
                print("")
                print("选项:")
                print("  -d, --drone-id=ID       无人机命名空间 (默认: drone0)")
                print("      --log-path=PATH     日志保存路径 (默认: ./logs)")
                print("  -i, --interval=SEC      记录间隔(秒) (默认: 1.0)")
                print("  -t, --time=SEC          最长运行时间(秒) (默认: 3600)")
                print("      --sim-time          使用仿真时间")
                print("  -v, --verbose=BOOL      详细输出 (默认: True)")
                print("  -h, --help              显示帮助信息")
                print("")
                print("示例:")
                print("  python3 gps.py --drone-id=drone0 --interval=0.5 --time=300")
                print("  python3 gps.py --log-path=./test_logs --sim-time")
                sys.exit()
            elif opt in ("-d", "--drone-id"):
                config["drone_id"] = arg
            elif opt == "--log-path":
                config["log_path"] = arg
            elif opt in ("-i", "--interval"):
                config["log_interval"] = float(arg)
            elif opt in ("-t", "--time"):
                config["running_time"] = int(arg)
            elif opt == "--sim-time":
                config["use_sim_time"] = True
            elif opt in ("-v", "--verbose"):
                config["verbose"] = arg.lower() in ("true", "yes", "1")
    
    except getopt.GetoptError as e:
        print(f"参数解析错误: {e}")
        print("使用 --help 查看帮助信息")
        sys.exit(2)
    
    return config


def main():
    """主函数"""
    # 解析命令行参数
    config = parse_args()
    
    # 初始化ROS 2
    rclpy.init()
    
    try:
        # 创建并运行GPS记录器
        logger = GPSLogger(config)
        logger.run()
        
    except Exception as e:
        print(f"启动GPS记录器时出错: {e}")
    finally:
        # 关闭ROS 2
        rclpy.shutdown()


if __name__ == '__main__':
    main()