#!/usr/bin/env python3
"""
Nexfi通信模块状态记录器
集成到UDP通信测试系统，记录通信模块状态信息
支持CSV格式日志记录，与GPS和UDP测试系统保持一致
"""

import requests
import uuid
import json
import time
import csv
import signal
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 默认配置参数
DEFAULT_CONFIG = {
    "nexfi_ip": "192.168.104.1",    # Nexfi设备IP地址
    "username": "root",              # 登录用户名
    "password": "nexfi",             # 登录密码
    "log_path": "./logs",            # 日志保存路径
    "log_interval": 0.5,             # 记录间隔(秒)
    "running_time": 3600,            # 最长运行时间(秒)
    "verbose": True,                 # 是否打印详细信息
    "device_name": "adhoc0",         # 网络设备名称
}


class NexfiClient:
    """Nexfi通信模块客户端类"""
    
    def __init__(self, api_url: str = "192.168.104.1", username: str = "root", password: str = "nexfi"):
        """
        初始化Nexfi客户端
        
        Args:
            api_url (str): Nexfi设备的IP地址，默认为192.168.104.1
            username (str): 登录用户名，默认为root
            password (str): 登录密码，默认为nexfi
        """
        self.api_url = f"http://{api_url}/ubus"
        self.username = username
        self.password = password
        self.session = None
        self._login()
    
    def _login(self) -> None:
        """登录并获取会话ID"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call",
            "params": [
                "00000000000000000000000000000000",
                "session",
                "login",
                {"username": self.username, "password": self.password},
            ],
        }
        
        try:
            response = requests.post(self.api_url, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if "result" in result and len(result["result"]) > 1:
                    self.session = result["result"][1]["ubus_rpc_session"]
                    logger.info("Successfully logged in to Nexfi device")
                else:
                    raise Exception("Invalid login response format")
            else:
                raise Exception(f"Login failed with status code {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during login: {e}")
            raise Exception("Failed to create session due to network error")
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Invalid response format during login: {e}")
            raise Exception("Failed to create session due to invalid response")
        except Exception as e:
            logger.error(f"Failed to login: {e}")
            raise Exception("Failed to create session")
    
    def _make_request(self, service: str, method: str, params: Dict = None, max_retries: int = 3) -> Dict:
        """
        发送API请求的通用方法
        
        Args:
            service (str): 服务名称
            method (str): 方法名称
            params (Dict): 参数字典
            max_retries (int): 最大重试次数
            
        Returns:
            Dict: API响应结果
        """
        if params is None:
            params = {}
            
        for i in range(max_retries):
            request_id = str(uuid.uuid4())
            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "call",
                "params": [self.session, service, method, params],
            }
            
            try:
                response = requests.post(self.api_url, json=payload, timeout=5)
                
                if response.status_code != 200:
                    if i == max_retries - 1:
                        logger.warning(f"Request failed with status code {response.status_code}")
                    continue
                    
                result = response.json()
                
                if result.get("id") != request_id:
                    if i == max_retries - 1:
                        logger.warning(f"Request ID mismatch")
                    continue
                
                # 检查响应格式
                if "result" in result and len(result["result"]) > 1:
                    return result["result"][1]
                else:
                    if i == max_retries - 1:
                        logger.warning(f"Invalid response format from {service}.{method}")
                    continue
                    
            except requests.exceptions.RequestException as e:
                if i == max_retries - 1:
                    logger.warning(f"Request failed: {e}")
                continue
            except (KeyError, IndexError, TypeError, ValueError) as e:
                if i == max_retries - 1:
                    logger.warning(f"Invalid response format: {e}")
                continue
        
        # 返回空字典而不是抛出异常，保证记录器继续运行
        return {}
    
    def get_system_status(self) -> Dict:
        """获取系统状态"""
        return self._make_request("nexfi.system", "status")
    
    def get_mesh_info(self) -> Dict:
        """获取Nexfi Mesh信息"""
        return self._make_request("nexfi.mesh", "status")
    
    def get_connected_nodes(self, device: str = "adhoc0") -> List[Dict]:
        """获取已连接站点列表"""
        result = self._make_request("nexfi.mesh", "sites", {"device": device})
        return result.get("results", [])
    
    def get_network_topology(self) -> List[Dict]:
        """获取网络拓扑"""
        result = self._make_request("nexfi.mesh", "vis")
        return result.get("vis", [])


class NexfiStatusLogger:
    """Nexfi通信状态记录器类，集成到UDP通信测试系统"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化Nexfi状态记录器
        
        Args:
            config: 配置参数字典
        """
        self.nexfi_ip = config.get("nexfi_ip", DEFAULT_CONFIG["nexfi_ip"])
        self.username = config.get("username", DEFAULT_CONFIG["username"])
        self.password = config.get("password", DEFAULT_CONFIG["password"])
        self.log_path = config.get("log_path", DEFAULT_CONFIG["log_path"])
        self.log_interval = config.get("log_interval", DEFAULT_CONFIG["log_interval"])
        self.running_time = config.get("running_time", DEFAULT_CONFIG["running_time"])
        self.verbose = config.get("verbose", DEFAULT_CONFIG["verbose"])
        self.device_name = config.get("device_name", DEFAULT_CONFIG["device_name"])
        
        self.running = True
        
        self.typology_path = os.path.join(self.log_path, "typology/")
        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        # 创建目录保存网络拓扑信息
        os.makedirs(self.typology_path, exist_ok=True)
        # 生成日志文件名（与UDP测试系统保持一致的命名格式）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self.log_path, f"nexfi_status_{timestamp}.csv")
        
        # 创建Nexfi客户端
        if self.verbose:
            print(f"正在连接到Nexfi设备: {self.nexfi_ip}...")
        
        try:
            self.client = NexfiClient(self.nexfi_ip, self.username, self.password)
        except Exception as e:
            print(f"连接Nexfi设备失败: {e}")
            print("将使用模拟数据继续运行...")
            self.client = None
        
        # 初始化CSV文件
        self.init_csv_file()
        
        # 设置信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        
        if self.verbose:
            print(f"Nexfi状态记录器初始化完成")
            print(f"设备IP: {self.nexfi_ip}")
            print(f"记录间隔: {self.log_interval}秒")
            print(f"日志文件: {self.log_file}")
    
    def signal_handler(self, signum, frame):
        """处理Ctrl+C信号"""
        if self.verbose:
            print("\n正在停止Nexfi状态记录...")
        self.running = False
    
    def init_csv_file(self):
        """初始化CSV文件，写入表头（与UDP测试系统格式保持一致）"""
        try:
            with open(self.log_file, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                # 使用与UDP测试系统一致的列名格式
                writer.writerow([
                    'timestamp',           # 时间戳（Unix时间戳）
                    'mesh_enabled',        # Mesh是否启用
                    'channel',             # 信道号
                    'frequency_band',      # 频宽(MHz)
                    'tx_power',            # 发射功率(dBm)
                    'work_mode',           # 工作模式
                    'node_id',             # 节点ID
                    'connected_nodes',     # 连接的节点数量
                    'avg_rssi',            # 平均信号强度
                    'avg_snr',             # 平均信噪比
                    'throughput',          # 吞吐量(Mbps)
                    'cpu_usage',           # CPU使用率
                    'memory_usage',        # 内存使用率
                    'uptime',              # 运行时间
                    'firmware_version',    # 固件版本
                    'topology_nodes',      # 拓扑中的节点数
                    'link_quality',        # 平均链路质量
                ])
            if self.verbose:
                print(f"Nexfi状态数据将记录到: {self.log_file}")
        except Exception as e:
            print(f"创建CSV文件时出错: {e}")
            sys.exit(1)
    
    def get_mock_data(self) -> Dict[str, Any]:
        """获取模拟数据（当无法连接到Nexfi设备时使用）"""
        # 模拟拓扑数据
        mock_topology = [
            {
                "id": "1",
                "neighbors": [
                    {
                        "id": "2",
                        "metric": 180.0,
                        "quality": "good"
                    }
                ]
            },
            {
                "id": "2", 
                "neighbors": [
                    {
                        "id": "1",
                        "metric": 175.0,
                        "quality": "good"
                    }
                ]
            }
        ]
        
        return {
            'mesh_enabled': True,
            'channel': '149',
            'frequency_band': '20',
            'tx_power': '20',
            'work_mode': 'adhoc',
            'node_id': '1',
            'connected_nodes': 1,
            'avg_rssi': -65.0,
            'avg_snr': 25.0,
            'throughput': '50.5',
            'cpu_usage': '15%',
            'memory_usage': '45%',
            'uptime': '2h 30m',
            'firmware_version': 'v1.0.0',
            'topology_nodes': 2,
            'link_quality': 180.0,
            'typology': mock_topology
        }
    
    def process_nexfi_data(self) -> Dict[str, Any]:
        """处理Nexfi数据，提取关键指标"""
        if not self.client:
            return self.get_mock_data()
        
        try:
            # 获取各种状态信息
            system_status = self.client.get_system_status()
            mesh_info = self.client.get_mesh_info()
            connected_nodes = self.client.get_connected_nodes(self.device_name)
            topology = self.client.get_network_topology()
            
            #TODO: 逻辑错误，不能使用所有节点的snr和rssi计算平均，只能
            # 处理连接节点的信号质量
            rssi_values = []
            snr_values = []
            nodeinfo_list = []
            for node in connected_nodes:
                try:
                    name = node.get('name', 'unknown')
                    rssi = float(node.get('rssi', 0))
                    snr = float(node.get('snr', 0))
                    nodeinfo_list.append({'name': name, 'rssi': rssi, 'snr': snr})
                    if rssi != 0:
                        rssi_values.append(rssi)
                    if snr != 0:
                        snr_values.append(snr)
                except (ValueError, TypeError):
                    continue
            
            avg_rssi = sum(rssi_values) / len(rssi_values) if rssi_values else 0.0
            avg_snr = sum(snr_values) / len(snr_values) if snr_values else 0.0
            
            # 处理拓扑信息，计算平均链路质量
            link_qualities = []
            for node in topology:
                neighbors = node.get('neighbors', [])
                for neighbor in neighbors:
                    try:
                        metric = float(neighbor.get('metric', 0))
                        if metric > 0:
                            link_qualities.append(metric)
                    except (ValueError, TypeError):
                        continue
            
            avg_link_quality = sum(link_qualities) / len(link_qualities) if link_qualities else 0.0
            
            return {
                'mesh_enabled': mesh_info.get('disabled', '1') == '0',
                'channel': mesh_info.get('channel', 'N/A'),
                'frequency_band': mesh_info.get('chanbw', 'N/A'),
                'tx_power': mesh_info.get('txpower', 'N/A'),
                'work_mode': mesh_info.get('mode', 'N/A'),
                'node_id': mesh_info.get('nodeid', 'N/A'),
                'connected_nodes': len(connected_nodes),
                'avg_rssi': avg_rssi,
                'avg_snr': avg_snr,
                'throughput': system_status.get('throughput', 'N/A'),
                'cpu_usage': system_status.get('cpu', 'N/A'),
                'memory_usage': system_status.get('memory', 'N/A'),
                'uptime': system_status.get('uptime', 'N/A'),
                'firmware_version': system_status.get('firmware', 'N/A'),
                'topology_nodes': len(topology),
                'link_quality': avg_link_quality,
                'nodeinfo_list': nodeinfo_list
                'typology':topology
            }
            
        except Exception as e:
            if self.verbose:
                print(f"获取Nexfi数据时出错: {e}")
            return self.get_mock_data()
    
    def log_nexfi_status(self):
        """记录Nexfi状态数据到文件（使用Unix时间戳格式）"""
        try:
            # 获取时间戳（使用Unix时间戳，与UDP测试系统保持一致）
            timestamp = time.time()
            
            # 获取处理后的Nexfi数据
            data = self.process_nexfi_data()
            
            # 写入CSV文件
            with open(self.log_file, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    timestamp,                          # Unix时间戳
                    data['mesh_enabled'],               # Mesh启用状态
                    data['channel'],                    # 信道
                    data['frequency_band'],             # 频宽
                    data['tx_power'],                   # 发射功率
                    data['work_mode'],                  # 工作模式
                    data['node_id'],                    # 节点ID
                    data['connected_nodes'],            # 连接节点数
                    data['avg_rssi'],                   # 平均RSSI
                    data['avg_snr'],                    # 平均SNR
                    data['throughput'],                 # 吞吐量
                    data['cpu_usage'],                  # CPU使用率
                    data['memory_usage'],               # 内存使用率
                    data['uptime'],                     # 运行时间
                    data['firmware_version'],           # 固件版本
                    data['topology_nodes'],             # 拓扑节点数
                    data['link_quality'],               # 链路质量
                    data['nodeinfo_list']                # 节点信息列表
                ])
            
            # 写拓扑数据到json文件
            if 'typology' in data and data['typology']:
                # 将timestamp转换为易读的年月日-时分秒格式
                readable_time = datetime.fromtimestamp(timestamp).strftime("%Y%m%d-%H%M%S")
                typology_filename = f"typology_{readable_time}.json"
                typology_filepath = os.path.join(self.typology_path, typology_filename)
                
                try:
                    typology_data = {
                        "timestamp": timestamp,
                        "datetime": datetime.fromtimestamp(timestamp).isoformat(),
                        "readable_time": readable_time,
                        "node_id": data['node_id'],
                        "typology": data['typology']
                    }
                    
                    with open(typology_filepath, 'w', encoding='utf-8') as f:
                        json.dump(typology_data, f, ensure_ascii=False, indent=2)
                    
                    if self.verbose:
                        print(f"拓扑数据已保存到: {typology_filepath}")
                        
                except Exception as e:
                    if self.verbose:
                        print(f"保存拓扑数据时出错: {e}")
            
            # 从data中移除typology，避免在CSV中显示
            data.pop('typology', None) 
            
            # 显示当前数据（格式与UDP测试系统保持一致）
            if self.verbose:
                print(f"Nexfi logged at {timestamp:.6f}: "
                      f"Nodes: {data['connected_nodes']}, "
                      f"RSSI: {data['avg_rssi']:.1f}dBm, "
                      f"SNR: {data['avg_snr']:.1f}dB, "
                      f"Throughput: {data['throughput']}")
                
        except Exception as e:
            print(f"记录Nexfi状态数据时出错: {e}")
    
    def run(self):
        """运行Nexfi状态数据记录"""
        if self.verbose:
            print("Nexfi状态记录器已启动")
            print(f"最长运行时间: {self.running_time}秒")
            print("按 Ctrl+C 停止记录\n")
        
        # 计算结束时间
        end_time = time.time() + self.running_time
        
        while self.running and time.time() < end_time:
            try:
                self.log_nexfi_status()
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
            print(f"\nNexfi状态记录已停止")
            print(f"日志文件已保存: {self.log_file}")


def parse_args() -> Dict[str, Any]:
    """解析命令行参数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Nexfi通信状态记录器')
    parser.add_argument('--nexfi-ip', default=DEFAULT_CONFIG["nexfi_ip"], 
                       help=f'Nexfi设备IP地址 (默认: {DEFAULT_CONFIG["nexfi_ip"]})')
    parser.add_argument('--username', default=DEFAULT_CONFIG["username"],
                       help=f'登录用户名 (默认: {DEFAULT_CONFIG["username"]})')
    parser.add_argument('--password', default=DEFAULT_CONFIG["password"],
                       help=f'登录密码 (默认: {DEFAULT_CONFIG["password"]})')
    parser.add_argument('--log-path', default=DEFAULT_CONFIG["log_path"],
                       help=f'日志保存路径 (默认: {DEFAULT_CONFIG["log_path"]})')
    parser.add_argument('--interval', type=float, default=DEFAULT_CONFIG["log_interval"],
                       help=f'记录间隔(秒) (默认: {DEFAULT_CONFIG["log_interval"]})')
    parser.add_argument('--time', type=int, default=DEFAULT_CONFIG["running_time"],
                       help=f'运行时间(秒) (默认: {DEFAULT_CONFIG["running_time"]})')
    parser.add_argument('--device', default=DEFAULT_CONFIG["device_name"],
                       help=f'网络设备名称 (默认: {DEFAULT_CONFIG["device_name"]})')
    parser.add_argument('--verbose', type=str, default='true',
                       help='是否显示详细信息 (true/false)')
    parser.add_argument('--monitor', type=int, help='监控模式，指定刷新间隔（秒）')
    parser.add_argument('--save', action='store_true', help='保存信息到JSON文件')
    parser.add_argument('--output', help='输出文件名')
    
    args = parser.parse_args()
    
    # 转换配置
    config = {
        "nexfi_ip": args.nexfi_ip,
        "username": args.username,
        "password": args.password,
        "log_path": args.log_path,
        "log_interval": args.interval,
        "running_time": args.time,
        "device_name": args.device,
        "verbose": args.verbose.lower() == 'true',
    }
    
    return config, args


def main():
    """主函数"""
    try:
        config, args = parse_args()
        
        if args.monitor:
            # 监控模式 - 使用原有的显示功能
            client = NexfiClient(config["nexfi_ip"], config["username"], config["password"])
            print(f"开始监控模式，刷新间隔: {args.monitor}秒")
            print("按 Ctrl+C 退出")
            try:
                while True:
                    # 简化的状态显示
                    system_status = client.get_system_status()
                    mesh_info = client.get_mesh_info()
                    connected_nodes = client.get_connected_nodes()
                    
                    print(f"\n=== {datetime.now().strftime('%H:%M:%S')} ===")
                    print(f"Mesh状态: {'启用' if mesh_info.get('disabled') == '0' else '禁用'}")
                    print(f"连接节点: {len(connected_nodes)}个")
                    print(f"吞吐量: {system_status.get('throughput', 'N/A')} Mbps")
                    print(f"CPU: {system_status.get('cpu', 'N/A')}")
                    
                    time.sleep(args.monitor)
            except KeyboardInterrupt:
                print("\n监控已停止")
        
        elif args.save:
            # 保存模式 - 保存当前状态到JSON
            client = NexfiClient(config["nexfi_ip"], config["username"], config["password"])
            data = {
                "timestamp": datetime.now().isoformat(),
                "system_status": client.get_system_status(),
                "mesh_info": client.get_mesh_info(),
                "connected_nodes": client.get_connected_nodes(),
                "network_topology": client.get_network_topology()
            }
            
            filename = args.output or f"nexfi_info_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"信息已保存到: {filename}")
        
        else:
            # 记录模式 - 持续记录状态到CSV
            logger_instance = NexfiStatusLogger(config)
            logger_instance.run()
            
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())