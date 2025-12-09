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
import math
from datetime import datetime
from functools import partial
from typing import Dict, Any, Optional, List

from geometry_msgs.msg import Vector3Stamped, AccelStamped, TwistStamped, QuaternionStamped
from sensor_msgs.msg import NavSatFix, MagneticField, Joy
from std_msgs.msg import Float32, Bool, UInt8, UInt16
from psdk_interfaces.msg import (
    PositionFused,
    GPSDetails,
    RCConnectionStatus,
    RelativeObstacleInfo,
    EscData,
    SingleBatteryInfo,
    FlightStatus,
    FlightAnomaly,
    DisplayMode,
    ControlMode,
    HmsInfoTable,
    RTKYaw,
)
from rclpy.qos import qos_profile_sensor_data

from as2_python_api.drone_interface_gps import DroneInterfaceGPS

# Monkey patch: ensure as2_python_api's GpsModule implements __call__ at runtime.
try:
    from as2_python_api.modules.gps_module import GpsModule
except Exception:
    GpsModule = None
else:
    if '__call__' not in GpsModule.__dict__:
        def _gps_module_call(self, *args, **kwargs):
            return True

        setattr(GpsModule, '__call__', _gps_module_call)
        abstract_methods = getattr(GpsModule, '__abstractmethods__', set())
        if '__call__' in abstract_methods:
            remaining = set(abstract_methods)
            remaining.discard('__call__')
            GpsModule.__abstractmethods__ = frozenset(remaining)

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
        self.extra_data: Dict[str, Any] = {}
        self.subscriptions: List[Any] = []
        
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

        self.setup_additional_subscribers()
        
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
                    'timestamp', 'latitude', 'longitude', 'altitude',
                    'local_x', 'local_y', 'local_z',
                    'connected', 'armed', 'offboard',
                    'linear_vx', 'linear_vy', 'linear_vz',
                    'angular_vx', 'angular_vy', 'angular_vz',
                    'roll', 'pitch', 'yaw',
                    'psdk_vel_x', 'psdk_vel_y', 'psdk_vel_z',
                    'psdk_acc_ground_x', 'psdk_acc_ground_y', 'psdk_acc_ground_z',
                    'psdk_acc_body_raw_x', 'psdk_acc_body_raw_y', 'psdk_acc_body_raw_z',
                    'psdk_acc_body_fused_x', 'psdk_acc_body_fused_y', 'psdk_acc_body_fused_z',
                    'psdk_ang_rate_body_x', 'psdk_ang_rate_body_y', 'psdk_ang_rate_body_z',
                    'psdk_att_qx', 'psdk_att_qy', 'psdk_att_qz', 'psdk_att_qw',
                    'height_above_ground', 'altitude_barometric', 'altitude_sea_level',
                    'position_fused_x', 'position_fused_y', 'position_fused_z',
                    'position_fused_health_x', 'position_fused_health_y', 'position_fused_health_z',
                    'mag_field_x', 'mag_field_y', 'mag_field_z',
                    'gps_nav_lat', 'gps_nav_lon', 'gps_nav_alt',
                    'gps_nav_vel_x', 'gps_nav_vel_y', 'gps_nav_vel_z',
                    'gps_fix_state', 'gps_horizontal_dop', 'gps_position_dop',
                    'gps_vertical_accuracy', 'gps_horizontal_accuracy', 'gps_speed_accuracy',
                    'gps_satellites_gps', 'gps_satellites_glonass', 'gps_satellites_total', 'gps_counter',
                    'gps_signal_level',
                    'home_point_lat', 'home_point_lon', 'home_point_alt', 'home_point_status', 'home_point_altitude',
                    'rtk_lat', 'rtk_lon', 'rtk_alt',
                    'rtk_vel_x', 'rtk_vel_y', 'rtk_vel_z',
                    'rtk_connection_status', 'rtk_yaw',
                    'platform_state', 'platform_yaw_mode', 'platform_control_mode', 'platform_reference_frame',
                    'display_mode', 'psdk_control_mode', 'psdk_device_mode', 'psdk_control_auth',
                    'flight_status', 'flight_anomaly_flags',
                    'rc_axis_0', 'rc_axis_1', 'rc_axis_2', 'rc_axis_3',
                    'rc_button_0', 'rc_button_1',
                    'rc_air_connection', 'rc_ground_connection', 'rc_app_connection', 'rc_link_disconnected',
                    'battery1_voltage', 'battery1_current', 'battery1_capacity_remain', 'battery1_capacity_pct', 'battery1_temperature',
                    'battery2_voltage', 'battery2_current', 'battery2_capacity_remain', 'battery2_capacity_pct', 'battery2_temperature',
                    'esc_avg_current', 'esc_avg_voltage', 'esc_avg_temperature', 'esc_max_temperature',
                    'relative_obstacle_up', 'relative_obstacle_down', 'relative_obstacle_front',
                    'relative_obstacle_back', 'relative_obstacle_left', 'relative_obstacle_right',
                    'relative_obstacle_up_health', 'relative_obstacle_down_health', 'relative_obstacle_front_health',
                    'relative_obstacle_back_health', 'relative_obstacle_left_health', 'relative_obstacle_right_health',
                    'hms_error_summary'
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
            
            # 获取线速度 / 姿态
            speed = self.drone.speed or [math.nan, math.nan, math.nan]
            roll_pitch_yaw = self.drone.orientation or [math.nan, math.nan, math.nan]
            angular_speed = self._vector_or_nan('angular_rate_ground')

            psdk_vel = self._vector_or_nan('psdk_velocity')
            acc_ground = self._vector_or_nan('acc_ground')
            acc_body_raw = self._vector_or_nan('acc_body_raw')
            acc_body_fused = self._vector_or_nan('acc_body_fused')
            ang_rate_body = self._vector_or_nan('ang_rate_body')
            att_quat = self._vector_or_nan('att_quat', length=4)
            height_agl = self.extra_data.get('height_agl', math.nan)
            altitude_barometric = self.extra_data.get('altitude_barometric', math.nan)
            altitude_sea_level = self.extra_data.get('altitude_sea_level', math.nan)
            pos_fused = self._vector_or_nan('position_fused')
            pos_health = self._vector_or_nan('position_fused_health')
            mag_field = self._vector_or_nan('magnetic_field')
            gps_nav = self._vector_or_nan('gps_position')
            gps_nav_vel = self._vector_or_nan('gps_velocity')
            gps_details = self.extra_data.get('gps_details', {})
            gps_fix_state = gps_details.get('fix_state', math.nan)
            gps_horizontal_dop = gps_details.get('horizontal_dop', math.nan)
            gps_position_dop = gps_details.get('position_dop', math.nan)
            gps_vertical_accuracy = gps_details.get('vertical_accuracy', math.nan)
            gps_horizontal_accuracy = gps_details.get('horizontal_accuracy', math.nan)
            gps_speed_accuracy = gps_details.get('speed_accuracy', math.nan)
            gps_sat_gps = gps_details.get('num_gps', math.nan)
            gps_sat_glonass = gps_details.get('num_glonass', math.nan)
            gps_sat_total = gps_details.get('num_total', math.nan)
            gps_counter = gps_details.get('gps_counter', math.nan)
            gps_signal_level = self.extra_data.get('gps_signal_level', math.nan)
            home_point = self._vector_or_nan('home_point')
            home_point_status = self.extra_data.get('home_point_status', math.nan)
            home_point_altitude = self.extra_data.get('home_point_altitude', math.nan)
            rtk_pos = self._vector_or_nan('rtk_position')
            rtk_vel = self._vector_or_nan('rtk_velocity')
            rtk_connection = self.extra_data.get('rtk_connection_status', math.nan)
            rtk_yaw = self.extra_data.get('rtk_yaw', math.nan)
            platform_state = info.get('state', None)
            platform_yaw_mode = info.get('yaw_mode', None)
            platform_control_mode = info.get('control_mode', None)
            platform_reference_frame = info.get('reference_frame', None)
            display_mode = self.extra_data.get('display_mode', math.nan)
            psdk_control_info = self.extra_data.get('psdk_control', {})
            psdk_control_mode = psdk_control_info.get('control_mode', math.nan)
            psdk_device_mode = psdk_control_info.get('device_mode', math.nan)
            psdk_control_auth = psdk_control_info.get('control_auth', math.nan)
            flight_status = self.extra_data.get('flight_status', math.nan)
            flight_anomaly_flags = self.extra_data.get('flight_anomaly_flags', '')
            rc_axes = self._list_with_length('rc_axes', 4)
            rc_buttons = self._list_with_length('rc_buttons', 2)
            rc_link = self.extra_data.get('rc_link', {})
            battery1 = self.extra_data.get('battery1', {})
            battery2 = self.extra_data.get('battery2', {})
            esc_stats = self.extra_data.get('esc_stats', {})
            rel_obs = self.extra_data.get('relative_obstacle', {})
            hms_summary = self.extra_data.get('hms_error_summary', '')

            # 写入CSV文件
            with open(self.log_file, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    timestamp,
                    lat, lon, alt,
                    x, y, z,
                    connected, armed, offboard,
                    speed[0], speed[1], speed[2],
                    angular_speed[0], angular_speed[1], angular_speed[2],
                    roll_pitch_yaw[0], roll_pitch_yaw[1], roll_pitch_yaw[2],
                    psdk_vel[0], psdk_vel[1], psdk_vel[2],
                    acc_ground[0], acc_ground[1], acc_ground[2],
                    acc_body_raw[0], acc_body_raw[1], acc_body_raw[2],
                    acc_body_fused[0], acc_body_fused[1], acc_body_fused[2],
                    ang_rate_body[0], ang_rate_body[1], ang_rate_body[2],
                    att_quat[0], att_quat[1], att_quat[2], att_quat[3],
                    height_agl, altitude_barometric, altitude_sea_level,
                    pos_fused[0], pos_fused[1], pos_fused[2],
                    pos_health[0], pos_health[1], pos_health[2],
                    mag_field[0], mag_field[1], mag_field[2],
                    gps_nav[0], gps_nav[1], gps_nav[2],
                    gps_nav_vel[0], gps_nav_vel[1], gps_nav_vel[2],
                    gps_fix_state, gps_horizontal_dop, gps_position_dop,
                    gps_vertical_accuracy, gps_horizontal_accuracy, gps_speed_accuracy,
                    gps_sat_gps, gps_sat_glonass, gps_sat_total, gps_counter,
                    gps_signal_level,
                    home_point[0], home_point[1], home_point[2], home_point_status, home_point_altitude,
                    rtk_pos[0], rtk_pos[1], rtk_pos[2],
                    rtk_vel[0], rtk_vel[1], rtk_vel[2],
                    rtk_connection, rtk_yaw,
                    platform_state, platform_yaw_mode, platform_control_mode, platform_reference_frame,
                    display_mode, psdk_control_mode, psdk_device_mode, psdk_control_auth,
                    flight_status, flight_anomaly_flags,
                    rc_axes[0], rc_axes[1], rc_axes[2], rc_axes[3],
                    rc_buttons[0], rc_buttons[1],
                    rc_link.get('air', math.nan), rc_link.get('ground', math.nan), rc_link.get('app', math.nan), rc_link.get('disconnected', math.nan),
                    battery1.get('voltage', math.nan), battery1.get('current', math.nan),
                    battery1.get('capacity_remain', math.nan), battery1.get('capacity_pct', math.nan),
                    battery1.get('temperature', math.nan),
                    battery2.get('voltage', math.nan), battery2.get('current', math.nan),
                    battery2.get('capacity_remain', math.nan), battery2.get('capacity_pct', math.nan),
                    battery2.get('temperature', math.nan),
                    esc_stats.get('avg_current', math.nan), esc_stats.get('avg_voltage', math.nan),
                    esc_stats.get('avg_temperature', math.nan), esc_stats.get('max_temperature', math.nan),
                    rel_obs.get('up', math.nan), rel_obs.get('down', math.nan), rel_obs.get('front', math.nan),
                    rel_obs.get('back', math.nan), rel_obs.get('left', math.nan), rel_obs.get('right', math.nan),
                    rel_obs.get('up_health', math.nan), rel_obs.get('down_health', math.nan),
                    rel_obs.get('front_health', math.nan), rel_obs.get('back_health', math.nan),
                    rel_obs.get('left_health', math.nan), rel_obs.get('right_health', math.nan),
                    hms_summary,
                ])
                
            # 显示当前数据（格式与UDP测试系统保持一致）
            if self.verbose:
                print(f"GPS logged at {timestamp:.6f}: "
                      f"GPS({lat:.6f}, {lon:.6f}, {alt:.2f}m) "
                      f"Local({x:.2f}, {y:.2f}, {z:.2f}m)")
            
        except Exception as e:
            print(f"记录GPS数据时出错: {e}")
    
    def _vector_or_nan(self, key: str, length: int = 3) -> List[float]:
        values = [math.nan] * length
        data = self.extra_data.get(key)
        if isinstance(data, (list, tuple)):
            for idx in range(min(length, len(data))):
                values[idx] = data[idx]
        return values

    def _list_with_length(self, key: str, length: int) -> List[float]:
        return self._vector_or_nan(key, length)
    
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
            for sub in self.subscriptions:
                try:
                    self.drone.destroy_subscription(sub)
                except Exception:
                    pass
            self.subscriptions.clear()
            self.drone.shutdown()
        except Exception as e:
            print(f"清理时出错: {e}")
        if self.verbose:
            print("GPS记录器已退出")

    def setup_additional_subscribers(self):
        """订阅额外话题以获取更多状态"""
        sensor_qos = qos_profile_sensor_data
        status_qos = 10

        def add_sub(msg_type, topic, callback, qos):
            try:
                sub = self.drone.create_subscription(msg_type, topic, callback, qos)
                self.subscriptions.append(sub)
            except Exception as e:
                if self.verbose:
                    print(f"创建订阅 {topic} 失败: {e}")

        add_sub(Vector3Stamped, 'psdk_ros2/angular_rate_ground_fused', self._angular_rate_ground_callback, sensor_qos)
        add_sub(Vector3Stamped, 'psdk_ros2/velocity_ground_fused', self._velocity_ground_callback, sensor_qos)
        add_sub(AccelStamped, 'psdk_ros2/acceleration_ground_fused', self._acc_ground_callback, sensor_qos)
        add_sub(AccelStamped, 'psdk_ros2/acceleration_body_raw', self._acc_body_raw_callback, sensor_qos)
        add_sub(AccelStamped, 'psdk_ros2/acceleration_body_fused', self._acc_body_fused_callback, sensor_qos)
        add_sub(Vector3Stamped, 'psdk_ros2/angular_rate_body_raw', self._ang_rate_body_callback, sensor_qos)
        add_sub(QuaternionStamped, 'psdk_ros2/attitude', self._attitude_callback, sensor_qos)
        add_sub(PositionFused, 'psdk_ros2/position_fused', self._position_fused_callback, sensor_qos)
        add_sub(MagneticField, 'psdk_ros2/magnetic_field', self._mag_field_callback, sensor_qos)
        add_sub(Float32, 'psdk_ros2/height_above_ground', self._height_callback, sensor_qos)
        add_sub(Float32, 'psdk_ros2/altitude_barometric', self._altitude_barometric_callback, sensor_qos)
        add_sub(Float32, 'psdk_ros2/altitude_sea_level', self._altitude_sea_level_callback, sensor_qos)
        add_sub(NavSatFix, 'psdk_ros2/gps_position', self._gps_position_callback, sensor_qos)
        add_sub(TwistStamped, 'psdk_ros2/gps_velocity', self._gps_velocity_callback, sensor_qos)
        add_sub(GPSDetails, 'psdk_ros2/gps_details', self._gps_details_callback, sensor_qos)
        add_sub(UInt8, 'psdk_ros2/gps_signal_level', self._gps_signal_callback, status_qos)
        add_sub(NavSatFix, 'psdk_ros2/home_point', self._home_point_callback, sensor_qos)
        add_sub(Bool, 'psdk_ros2/home_point_status', self._home_point_status_callback, status_qos)
        add_sub(Float32, 'psdk_ros2/home_point_altitude', self._home_point_altitude_callback, status_qos)
        add_sub(NavSatFix, 'psdk_ros2/rtk_position', self._rtk_position_callback, sensor_qos)
        add_sub(TwistStamped, 'psdk_ros2/rtk_velocity', self._rtk_velocity_callback, sensor_qos)
        add_sub(UInt16, 'psdk_ros2/rtk_connection_status', self._rtk_connection_callback, status_qos)
        add_sub(RTKYaw, 'psdk_ros2/rtk_yaw', self._rtk_yaw_callback, status_qos)
        add_sub(DisplayMode, 'psdk_ros2/display_mode', self._display_mode_callback, status_qos)
        add_sub(ControlMode, 'psdk_ros2/control_mode', self._control_mode_callback, status_qos)
        add_sub(FlightStatus, 'psdk_ros2/flight_status', self._flight_status_callback, status_qos)
        add_sub(FlightAnomaly, 'psdk_ros2/flight_anomaly', self._flight_anomaly_callback, status_qos)
        add_sub(Joy, 'psdk_ros2/rc', self._rc_callback, sensor_qos)
        add_sub(RCConnectionStatus, 'psdk_ros2/rc_connection_status', self._rc_status_callback, status_qos)
        add_sub(SingleBatteryInfo, 'psdk_ros2/single_battery_index1', partial(self._battery_callback, idx='battery1'), status_qos)
        add_sub(SingleBatteryInfo, 'psdk_ros2/single_battery_index2', partial(self._battery_callback, idx='battery2'), status_qos)
        add_sub(EscData, 'psdk_ros2/esc_data', self._esc_callback, status_qos)
        add_sub(RelativeObstacleInfo, 'psdk_ros2/relative_obstacle_info', self._relative_obstacle_callback, status_qos)
        add_sub(HmsInfoTable, 'psdk_ros2/hms_info_table', self._hms_table_callback, status_qos)

    def _angular_rate_ground_callback(self, msg: Vector3Stamped):
        self.extra_data['angular_rate_ground'] = [msg.vector.x, msg.vector.y, msg.vector.z]

    def _velocity_ground_callback(self, msg: Vector3Stamped):
        self.extra_data['psdk_velocity'] = [msg.vector.x, msg.vector.y, msg.vector.z]

    def _acc_ground_callback(self, msg: AccelStamped):
        self.extra_data['acc_ground'] = [msg.accel.linear.x, msg.accel.linear.y, msg.accel.linear.z]

    def _acc_body_raw_callback(self, msg: AccelStamped):
        self.extra_data['acc_body_raw'] = [msg.accel.linear.x, msg.accel.linear.y, msg.accel.linear.z]

    def _acc_body_fused_callback(self, msg: AccelStamped):
        self.extra_data['acc_body_fused'] = [msg.accel.linear.x, msg.accel.linear.y, msg.accel.linear.z]

    def _ang_rate_body_callback(self, msg: Vector3Stamped):
        self.extra_data['ang_rate_body'] = [msg.vector.x, msg.vector.y, msg.vector.z]

    def _attitude_callback(self, msg: QuaternionStamped):
        self.extra_data['att_quat'] = [msg.quaternion.x, msg.quaternion.y, msg.quaternion.z, msg.quaternion.w]

    def _position_fused_callback(self, msg: PositionFused):
        self.extra_data['position_fused'] = [msg.position.x, msg.position.y, msg.position.z]
        self.extra_data['position_fused_health'] = [msg.x_health, msg.y_health, msg.z_health]

    def _mag_field_callback(self, msg: MagneticField):
        self.extra_data['magnetic_field'] = [msg.magnetic_field.x, msg.magnetic_field.y, msg.magnetic_field.z]

    def _height_callback(self, msg: Float32):
        self.extra_data['height_agl'] = msg.data

    def _altitude_barometric_callback(self, msg: Float32):
        self.extra_data['altitude_barometric'] = msg.data

    def _altitude_sea_level_callback(self, msg: Float32):
        self.extra_data['altitude_sea_level'] = msg.data

    def _gps_position_callback(self, msg: NavSatFix):
        self.extra_data['gps_position'] = [msg.latitude, msg.longitude, msg.altitude]

    def _gps_velocity_callback(self, msg: TwistStamped):
        self.extra_data['gps_velocity'] = [msg.twist.linear.x, msg.twist.linear.y, msg.twist.linear.z]

    def _gps_details_callback(self, msg: GPSDetails):
        self.extra_data['gps_details'] = {
            'horizontal_dop': msg.horizontal_dop,
            'position_dop': msg.position_dop,
            'fix_state': msg.fix_state,
            'vertical_accuracy': msg.vertical_accuracy,
            'horizontal_accuracy': msg.horizontal_accuracy,
            'speed_accuracy': msg.speed_accuracy,
            'num_gps': msg.num_gps_satellites_used,
            'num_glonass': msg.num_glonass_satellites_used,
            'num_total': msg.num_total_satellites_used,
            'gps_counter': msg.gps_counter,
        }

    def _gps_signal_callback(self, msg: UInt8):
        self.extra_data['gps_signal_level'] = msg.data

    def _home_point_callback(self, msg: NavSatFix):
        self.extra_data['home_point'] = [msg.latitude, msg.longitude, msg.altitude]

    def _home_point_status_callback(self, msg: Bool):
        self.extra_data['home_point_status'] = bool(msg.data)

    def _home_point_altitude_callback(self, msg: Float32):
        self.extra_data['home_point_altitude'] = msg.data

    def _rtk_position_callback(self, msg: NavSatFix):
        self.extra_data['rtk_position'] = [msg.latitude, msg.longitude, msg.altitude]

    def _rtk_velocity_callback(self, msg: TwistStamped):
        self.extra_data['rtk_velocity'] = [msg.twist.linear.x, msg.twist.linear.y, msg.twist.linear.z]

    def _rtk_connection_callback(self, msg: UInt16):
        self.extra_data['rtk_connection_status'] = msg.data

    def _rtk_yaw_callback(self, msg: RTKYaw):
        self.extra_data['rtk_yaw'] = msg.yaw

    def _display_mode_callback(self, msg: DisplayMode):
        self.extra_data['display_mode'] = msg.display_mode

    def _control_mode_callback(self, msg: ControlMode):
        self.extra_data['psdk_control'] = {
            'control_mode': msg.control_mode,
            'device_mode': msg.device_mode,
            'control_auth': msg.control_auth,
        }

    def _flight_status_callback(self, msg: FlightStatus):
        self.extra_data['flight_status'] = msg.flight_status

    def _flight_anomaly_callback(self, msg: FlightAnomaly):
        flags = []
        for field in [
            'impact_in_air', 'random_fly', 'height_ctrl_fail', 'roll_pitch_ctrl_fail',
            'yaw_ctrl_fail', 'aircraft_is_falling', 'strong_wind_level1', 'strong_wind_level2',
            'compass_installation_error', 'imu_installation_error', 'esc_temperature_high',
            'at_least_one_esc_disconnected', 'gps_yaw_error'
        ]:
            if getattr(msg, field, 0):
                flags.append(field)
        self.extra_data['flight_anomaly_flags'] = '|'.join(flags) if flags else 'none'

    def _rc_callback(self, msg: Joy):
        axes = list(msg.axes)
        buttons = list(msg.buttons)
        self.extra_data['rc_axes'] = axes
        self.extra_data['rc_buttons'] = buttons

    def _rc_status_callback(self, msg: RCConnectionStatus):
        self.extra_data['rc_link'] = {
            'air': msg.air_connection,
            'ground': msg.ground_connection,
            'app': msg.app_connection,
            'disconnected': msg.air_or_ground_disconnected,
        }

    def _battery_callback(self, msg: SingleBatteryInfo, idx: str):
        self.extra_data[idx] = {
            'voltage': msg.voltage,
            'current': msg.current,
            'capacity_remain': msg.capacity_remain,
            'capacity_pct': msg.capacity_percentage,
            'temperature': msg.temperature,
        }

    def _esc_callback(self, msg: EscData):
        if not msg.esc:
            return
        currents = [entry.current for entry in msg.esc]
        voltages = [entry.voltage for entry in msg.esc]
        temperatures = [entry.temperature for entry in msg.esc]
        self.extra_data['esc_stats'] = {
            'avg_current': sum(currents) / len(currents) if currents else math.nan,
            'avg_voltage': sum(voltages) / len(voltages) if voltages else math.nan,
            'avg_temperature': sum(temperatures) / len(temperatures) if temperatures else math.nan,
            'max_temperature': max(temperatures) if temperatures else math.nan,
        }

    def _relative_obstacle_callback(self, msg: RelativeObstacleInfo):
        self.extra_data['relative_obstacle'] = {
            'up': msg.up,
            'down': msg.down,
            'front': msg.front,
            'back': msg.back,
            'left': msg.left,
            'right': msg.right,
            'up_health': msg.up_health,
            'down_health': msg.down_health,
            'front_health': msg.front_health,
            'back_health': msg.back_health,
            'left_health': msg.left_health,
            'right_health': msg.right_health,
        }

    def _hms_table_callback(self, msg: HmsInfoTable):
        summaries = []
        for entry in msg.table:
            if entry.error_code:
                summaries.append(f"{entry.error_code}:{entry.error_level}")
        self.extra_data['hms_error_summary'] = ';'.join(summaries) if summaries else ''


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
