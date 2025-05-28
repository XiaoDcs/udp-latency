#!/usr/bin/env python3
"""
无人机GPS数据记录脚本
将GPS数据保存到文件中
"""

import rclpy
import time
import csv
import signal
import sys
from datetime import datetime
from as2_python_api.drone_interface_gps import DroneInterfaceGPS


class GPSLogger:
    """GPS数据记录器类"""
    
    def __init__(self, drone_id='drone0', log_file=None, use_sim_time=False):
        """
        初始化GPS记录器
        
        Args:
            drone_id (str): 无人机命名空间
            log_file (str): 日志文件路径，默认自动生成
            use_sim_time (bool): 是否使用仿真时间
        """
        self.drone_id = drone_id
        self.running = True
        
        # 生成日志文件名
        if log_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file = f"gps_log_{drone_id}_{timestamp}.csv"
        else:
            self.log_file = log_file
            
        # 创建无人机接口
        print(f"正在连接到无人机: {drone_id}...")
        self.drone = DroneInterfaceGPS(
            drone_id=drone_id, 
            verbose=False, 
            use_sim_time=use_sim_time
        )
        
        # 初始化CSV文件
        self.init_csv_file()
        
        # 设置信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        """处理Ctrl+C信号"""
        print("\n正在停止GPS记录...")
        self.running = False
        
    def init_csv_file(self):
        """初始化CSV文件，写入表头"""
        try:
            with open(self.log_file, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    'timestamp', 'latitude', 'longitude', 'altitude',
                    'local_x', 'local_y', 'local_z',
                    'connected', 'armed', 'offboard'
                ])
            print(f"GPS数据将记录到: {self.log_file}")
        except Exception as e:
            print(f"创建CSV文件时出错: {e}")
            sys.exit(1)
            
    def log_gps_data(self):
        """记录GPS数据到文件"""
        try:
            # 获取时间戳
            timestamp = datetime.now().isoformat()
            
            # 获取GPS数据
            gps_pose = self.drone.gps.pose
            lat, lon, alt = gps_pose if gps_pose and len(gps_pose) == 3 else [0, 0, 0]
            
            # 获取本地位置
            local_pos = self.drone.position
            x, y, z = local_pos if local_pos and len(local_pos) == 3 else [0, 0, 0]
            
            # 获取无人机状态
            info = self.drone.info
            connected = info.get('connected', False)
            armed = info.get('armed', False)
            offboard = info.get('offboard', False)
            
            # 写入CSV文件
            with open(self.log_file, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    timestamp, lat, lon, alt,
                    x, y, z,
                    connected, armed, offboard
                ])
                
            # 显示当前数据
            print(f"{timestamp}: GPS({lat:.6f}, {lon:.6f}, {alt:.2f}m) "
                  f"Local({x:.2f}, {y:.2f}, {z:.2f}m)")
            
        except Exception as e:
            print(f"记录GPS数据时出错: {e}")
    
    def run(self, log_interval=0.02):
        """
        运行GPS数据记录
        
        Args:
            log_interval (float): 记录间隔（秒）
        """
        print("GPS数据记录器已启动")
        print(f"记录间隔: {log_interval}秒")
        print("按 Ctrl+C 停止记录\n")
        
        while self.running and rclpy.ok():
            try:
                self.log_gps_data()
                time.sleep(log_interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"运行时错误: {e}")
                time.sleep(1.0)
                
        self.cleanup()
        
    def cleanup(self):
        """清理资源"""
        print(f"\nGPS数据已保存到: {self.log_file}")
        try:
            self.drone.shutdown()
        except Exception as e:
            print(f"清理时出错: {e}")
        print("GPS记录器已退出")


def main():
    """主函数"""
    # 初始化ROS 2
    rclpy.init()
    
    try:
        # 创建并运行GPS记录器
        logger = GPSLogger(drone_id='drone0', use_sim_time=False)
        logger.run(log_interval=1.0)  # 每秒记录一次
        
    except Exception as e:
        print(f"启动GPS记录器时出错: {e}")
    finally:
        # 关闭ROS 2
        rclpy.shutdown()


if __name__ == '__main__':
    main()