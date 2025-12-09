#!/usr/bin/env python3
"""
Nexfi通信模块状态记录器
集成到UDP通信测试系统，记录通信模块状态信息
支持CSV格式日志记录，与GPS和UDP测试系统保持一致
"""

import argparse
import requests
import uuid
import json
import time
import csv
import signal
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 默认配置参数
DEFAULT_CONFIG = {
    "nexfi_ip": "192.168.104.12",    # Nexfi设备IP地址
    "username": "root",              # 登录用户名
    "password": "nexfi",             # 登录密码
    "log_path": "./logs",            # 日志保存路径
    "log_interval": 0.5,             # 记录间隔(秒)
    "running_time": 3600,            # 最长运行时间(秒)
    "verbose": True,                 # 是否打印详细信息
    "device_name": "adhoc0",         # 网络设备名称
    "bat_interface": "bat0",        # batman-adv接口
}


class NexfiClient:
    """Nexfi通信模块客户端类"""
    
    def __init__(
        self,
        api_url: str = "192.168.104.1",
        username: str = "root",
        password: str = "nexfi",
        device_name: str = "adhoc0",
        bat_interface: str = "bat0",
    ):
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
        self.device_name = device_name
        self.bat_interface = bat_interface
        self._login()
    
    def _candidate_devices(self) -> List[str]:
        candidates = [self.device_name, "mesh0", "adhoc0", "wlan0"]
        seen = set()
        ordered = []
        for dev in candidates:
            if dev and dev not in seen:
                seen.add(dev)
                ordered.append(dev)
        return ordered

    @staticmethod
    def _is_error_response(result: Optional[Dict[str, Any]]) -> bool:
        return isinstance(result, dict) and "__error__" in result
    
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
    
    def _normalize_response_payload(self, payload: Any) -> Any:
        """Handle Nexfi firmwares that wrap JSON data inside stdout strings."""
        if not isinstance(payload, dict):
            return payload

        stdout_content = payload.get("stdout")
        if isinstance(stdout_content, str):
            stripped = stdout_content.strip()
            if stripped:
                try:
                    parsed = json.loads(stripped)
                    combined = dict(payload)
                    if isinstance(parsed, dict):
                        combined.update(parsed)
                    combined["stdout_parsed"] = parsed
                    return combined
                except json.JSONDecodeError:
                    logger.debug("Failed to parse stdout JSON snippet: %s", stripped[:120])
        return payload
    
    def _parse_json_string(self, raw: str) -> Optional[Any]:
        if not isinstance(raw, str):
            return None
        stripped = raw.strip()
        if not stripped:
            return None
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            logger.debug("Failed to decode JSON string: %s", stripped[:120])
            return None

    def _extract_result_payload(self, response_json: Dict[str, Any]) -> Optional[Any]:
        if "error" in response_json:
            return {"__error__": response_json["error"]}

        payload = response_json.get("result")
        if payload is None:
            return None

        if isinstance(payload, list):
            # ubus responses often look like [0, { ... }] ; iterate反向可直接拿到字典
            for item in reversed(payload):
                if isinstance(item, dict):
                    return self._normalize_response_payload(item)
                if isinstance(item, str):
                    parsed = self._parse_json_string(item)
                    if parsed is not None:
                        return parsed if isinstance(parsed, dict) else {"data": parsed}
            return None

        if isinstance(payload, dict):
            return self._normalize_response_payload(payload)

        if isinstance(payload, str):
            parsed = self._parse_json_string(payload)
            if parsed is not None:
                return parsed if isinstance(parsed, dict) else {"data": parsed}

        return None

    def _call_file_exec(self, command: str, params: Optional[List[str]] = None, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        payload = {
            "command": command,
            "params": params or [],
            "env": env or {},
        }
        return self._make_request("file", "exec", payload)

    def _get_system_status_fallback(self) -> Dict[str, Any]:
        system_info = self._make_request("system", "info")
        board_info = self._make_request("system", "board")

        if self._is_error_response(system_info):
            system_info = {}
        if self._is_error_response(board_info):
            board_info = {}

        load_avg = system_info.get("load", [])
        def _format_load(value):
            try:
                return round((float(value) / 65535.0), 3)
            except (TypeError, ValueError):
                return None

        load1 = _format_load(load_avg[0]) if len(load_avg) > 0 else None
        load5 = _format_load(load_avg[1]) if len(load_avg) > 1 else None
        load15 = _format_load(load_avg[2]) if len(load_avg) > 2 else None
        cpu_usage = f"{(load1 or 0) * 100:.1f}%" if load1 is not None else "N/A"

        memory = system_info.get("memory", {})
        memory_usage = "N/A"
        total_mem = memory.get("total")
        free_mem = memory.get("free")
        if total_mem:
            used = total_mem - (free_mem or 0)
            memory_usage = f"{(used / total_mem) * 100:.1f}%"

        uptime_seconds = system_info.get("uptime")
        uptime = f"{uptime_seconds}s" if uptime_seconds is not None else "N/A"

        release = board_info.get("release", {})
        firmware_version = release.get("description") or release.get("version") or board_info.get("kernel", "N/A")

        return {
            "throughput": "N/A",
            "cpu": cpu_usage,
            "memory": memory_usage,
            "uptime": uptime,
            "firmware": firmware_version,
            "load1": load1,
            "load5": load5,
            "load15": load15,
            "mem_total": total_mem,
            "mem_free": free_mem,
            "mem_cached": memory.get("cached"),
        }

    def _get_mesh_info_fallback(self) -> Dict[str, Any]:
        wifi_info: Optional[Dict[str, Any]] = None
        device_used = None
        for dev in self._candidate_devices():
            response = self._make_request("iwinfo", "info", {"device": dev})
            if response and not self._is_error_response(response):
                wifi_info = response
                device_used = dev
                break

        if not wifi_info:
            return {}

        interface_name = self.bat_interface or "bat0"
        network_info = self._make_request(f"network.interface.{interface_name}", "status")
        if self._is_error_response(network_info):
            network_info = {}

        disabled_flag = '0'
        if isinstance(network_info, dict) and not network_info.get('up', True):
            disabled_flag = '1'

        def _collect_addresses(items, key):
            if not isinstance(items, list):
                return []
            addresses = []
            for entry in items:
                addr = entry.get(key)
                if addr:
                    addresses.append(addr)
            return addresses

        ipv4_list = _collect_addresses(network_info.get('ipv4-address'), 'address')
        ipv6_list = _collect_addresses(network_info.get('ipv6-address'), 'address')

        return {
            "mode": wifi_info.get("mode"),
            "channel": wifi_info.get("channel"),
            "chanbw": wifi_info.get("htmode"),
            "txpower": wifi_info.get("txpower"),
            "nodeid": wifi_info.get("bssid"),
            "primary": wifi_info.get("bssid"),
            "device": device_used,
            "disabled": disabled_flag,
            "quality": wifi_info.get("quality"),
            "quality_max": wifi_info.get("quality_max"),
            "noise": wifi_info.get("noise"),
            "bitrate": wifi_info.get("bitrate"),
            "channel_width": wifi_info.get("htmode"),
            "bat_ipv4": ','.join(ipv4_list) if ipv4_list else None,
            "bat_ipv6": ','.join(ipv6_list) if ipv6_list else None,
        }

    def _format_assoc_entry(self, entry: Dict[str, Any], device: str) -> Dict[str, Any]:
        signal = entry.get("signal")
        noise = entry.get("noise")
        snr = None
        if isinstance(signal, (int, float)) and isinstance(noise, (int, float)):
            snr = signal - noise
        return {
            "primary": entry.get("mac", "").lower(),
            "rssi": signal,
            "snr": snr,
            "device": device,
            "raw": entry,
        }

    def _get_connected_nodes_fallback(self) -> List[Dict[str, Any]]:
        for dev in self._candidate_devices():
            response = self._make_request("iwinfo", "assoclist", {"device": dev})
            if not response or self._is_error_response(response):
                continue
            result_list = response.get("results")
            if isinstance(result_list, list) and result_list:
                return [self._format_assoc_entry(entry, dev) for entry in result_list]
        return []

    def _get_network_topology_fallback(self) -> List[Dict[str, Any]]:
        response = self._call_file_exec("/usr/sbin/batadv-vis", ["-f", "jsondoc"])
        if not response or self._is_error_response(response):
            return []

        if isinstance(response.get("vis"), list):
            return response.get("vis", [])

        stdout_parsed = response.get("stdout_parsed")
        if isinstance(stdout_parsed, dict) and isinstance(stdout_parsed.get("vis"), list):
            return stdout_parsed.get("vis", [])
        return []

    def _make_request(
        self,
        service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        发送API请求的通用方法
        
        Args:
            service (str): 服务名称
            method (str): 方法名称
            params (Optional[Dict[str, Any]]): 参数字典
            max_retries (int): 最大重试次数
            
        Returns:
            Dict[str, Any]: API响应结果
        """
        params_dict: Dict[str, Any] = params if params is not None else {}
            
        for i in range(max_retries):
            request_id = str(uuid.uuid4())
            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "call",
                "params": [self.session, service, method, params_dict],
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
                payload = self._extract_result_payload(result)
                if payload is not None:
                    return payload
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
        result = self._make_request("nexfi.system", "status")
        if result and not self._is_error_response(result):
            return result
        return self._get_system_status_fallback()
    
    def get_mesh_info(self) -> Dict:
        """获取Nexfi Mesh信息"""
        result = self._make_request("nexfi.mesh", "status")
        if result and not self._is_error_response(result):
            return result
        return self._get_mesh_info_fallback()
    
    def get_connected_nodes(self, device: str = "adhoc0") -> List[Dict]:
        """获取已连接站点列表"""
        result = self._make_request("nexfi.mesh", "sites", {"device": device})
        candidates: List[Dict[str, Any]] = []
        if isinstance(result, list):
            candidates = result
        elif isinstance(result, dict) and not self._is_error_response(result):
            for key in ("results", "sites", "nodes", "data"):
                value = result.get(key)
                if isinstance(value, list):
                    candidates = value
                    break

        if candidates:
            return candidates
        return self._get_connected_nodes_fallback()

    def get_network_topology(self) -> List[Dict]:
        """获取网络拓扑"""
        result = self._make_request("nexfi.mesh", "vis")
        if isinstance(result, list):
            return result

        if isinstance(result, dict) and not self._is_error_response(result):
            if isinstance(result.get("vis"), list):
                return result.get("vis", [])
            data_value = result.get("data")
            if isinstance(data_value, dict) and isinstance(data_value.get("vis"), list):
                return data_value.get("vis", [])
        return self._get_network_topology_fallback()


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
        self.bat_interface = config.get("bat_interface", DEFAULT_CONFIG["bat_interface"])
        
        self.running = True
        
        self.typology_path = os.path.join(self.log_path, "typology/")
        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        # 创建目录保存网络拓扑信息
        os.makedirs(self.typology_path, exist_ok=True)
        # 生成日志文件名（与UDP测试系统保持一致的命名格式）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self.log_path, f"nexfi_status_{timestamp}.csv")
        self.topology_edges_file = os.path.join(self.typology_path, f"typology_edges_{timestamp}.csv")
        self.topology_edges_initialized = False
        self.topology_edges_disabled = False
        
        # 创建Nexfi客户端
        if self.verbose:
            print(f"正在连接到Nexfi设备: {self.nexfi_ip}...")
        
        try:
            self.client = NexfiClient(
                self.nexfi_ip,
                self.username,
                self.password,
                device_name=self.device_name,
                bat_interface=self.bat_interface,
            )
        except Exception as e:
            print(f"连接Nexfi设备失败: {e}")
            print("将使用模拟数据继续运行...")
            self.client = None
        
        # 初始化CSV文件
        self.init_csv_file()
        self.init_topology_edges_file()
        
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
                    'node_ip',             # 节点IP
                    'wifi_quality',        # Wi-Fi质量
                    'wifi_quality_max',    # Wi-Fi质量上限
                    'wifi_noise',          # 噪声
                    'wifi_bitrate',        # 速率
                    'wifi_mode',           # Wi-Fi模式
                    'channel_width',       # 信道宽度
                    'connected_nodes',     # 连接的节点数量
                    'connected_node_id',   # 连接的节点ID
                    'connected_node_mac',  # 连接的节点MAC
                    'connected_node_ip',   # 连接的节点IP
                    'rssi',                # 平均信号强度(dBm)
                    'snr',                 # 信噪比
                    'topology_snr',        # 拓扑中的信噪比
                    'link_metric',         # 拓扑metric
                    'tx_rate',             # 拓扑速率
                    'last_seen',           # 最后可达
                    'thr',                 # 节点吞吐估计
                    'tx_packets',          # 发送包数
                    'tx_bytes',            # 发送字节
                    'tx_retries',          # 重传次数
                    'rx_packets',          # 接收包数
                    'rx_bytes',            # 接收字节
                    'rx_drop_misc',        # 接收丢弃
                    'mesh_plink',          # Mesh链路状态
                    'mesh_llid',           # Mesh LLID
                    'mesh_plid',           # Mesh PLID
                    'mesh_local_ps',       # 本地省电状态
                    'mesh_peer_ps',        # 对端省电状态
                    'mesh_non_peer_ps',    # 非对端省电状态
                    'throughput',          # 吞吐量(Mbps)
                    'cpu_usage',           # CPU使用率
                    'memory_usage',        # 内存使用率
                    'load1',               # 1分钟负载
                    'load5',               # 5分钟负载
                    'load15',              # 15分钟负载
                    'mem_total',           # 内存总量
                    'mem_free',            # 内存空闲
                    'mem_cached',          # 缓存
                    'bat_ipv4',            # bat接口IPv4
                    'bat_ipv6',            # bat接口IPv6
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

    def init_topology_edges_file(self):
        """初始化拓扑边CSV文件"""
        if self.topology_edges_disabled:
            return
        try:
            with open(self.topology_edges_file, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    'timestamp',
                    'router_mac',
                    'router_ip',
                    'router_nodeid',
                    'neighbor_mac',
                    'neighbor_ip',
                    'neighbor_nodeid',
                    'metric',
                    'tx_rate',
                    'snr',
                    'last_seen'
                ])
            self.topology_edges_initialized = True
        except Exception as e:
            print(f"创建拓扑边CSV文件时出错: {e}")
            self.topology_edges_initialized = False
            self.topology_edges_disabled = True
    
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
        
        mock_nodes = [
            {
                'macaddr': 'b8:8e:df:01:e7:d5',
                'rssi': -65.0,
                'snr': 25.0,
                'nodeid': '2',
                'ipaddr': '192.168.104.9',
                'link_metric': 185.0,
                'tx_rate': 24.0,
                'topology_snr': 30.0,
                'last_seen': '0'
            }
        ]

        return {
            'mesh_enabled': True,
            'channel': '149',
            'frequency_band': '20',
            'tx_power': '20',
            'work_mode': 'adhoc',
            'node_id': '1',
            'node_ip': '192.168.104.12',
            'connected_nodes': len(mock_nodes),
            'avg_rssi': -65.0,
            'avg_snr': 25.0,
            'throughput': '50.5',
            'cpu_usage': '15%',
            'memory_usage': '45%',
            'uptime': '2h 30m',
            'firmware_version': 'v1.0.0',
            'topology_nodes': 2,
            'link_quality': 180.0,
            'typology': mock_topology,
            'nodeinfo_list': mock_nodes
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
            topology_by_mac: Dict[str, Dict[str, Any]] = {}
            for topo_node in topology:
                primary_value = topo_node.get('primary')
                if not primary_value:
                    continue
                topology_by_mac[str(primary_value).lower()] = topo_node
            
            #TODO: connected_nodes中的node字典中没有nodeid字段，需要根据实际情况调整，
            #      nodeid需要从其他地方获取，例如拓扑结构中
            # 处理连接节点的信号质量
            self_id_value = mesh_info.get('nodeid') or mesh_info.get('primary') or mesh_info.get('node_mac') or mesh_info.get('device')
            self_id = str(self_id_value).lower() if self_id_value else 'n/a'
            self_entry = topology_by_mac.get(self_id)
            node_ip = (self_entry or {}).get('ipaddr') or mesh_info.get('ipaddr') or 'N/A'
            neighbors_data = self_entry.get('neighbors', []) if self_entry else []
            nodeinfo_list = []
            throughput_samples = []
            for node in connected_nodes:      # 这里只提供了mac地址和snr，rssi的对应关系
                if not isinstance(node, dict):
                    continue
                try:
                    primary_value = node.get('primary') or node.get('mac') or 'N/A'
                    macaddr = str(primary_value).lower()
                    rssi_raw = node.get('rssi', 0)
                    snr_raw = node.get('snr', 0)
                    rssi = float(rssi_raw) if rssi_raw is not None else 0.0
                    snr = float(snr_raw) if snr_raw is not None else 0.0
                    raw_source = node.get('raw')
                    raw_assoc: Dict[str, Any]
                    if isinstance(raw_source, dict):
                        raw_assoc = raw_source
                    else:
                        raw_assoc = node
                    node_entry = {
                        'macaddr': macaddr,
                        'rssi': rssi,
                        'snr': snr,
                        'raw': raw_assoc,
                        'thr': raw_assoc.get('thr'),
                        'mesh_plink': raw_assoc.get('mesh plink'),
                        'mesh_llid': raw_assoc.get('mesh llid'),
                        'mesh_plid': raw_assoc.get('mesh plid'),
                        'mesh_local_ps': raw_assoc.get('mesh local PS'),
                        'mesh_peer_ps': raw_assoc.get('mesh peer PS'),
                        'mesh_non_peer_ps': raw_assoc.get('mesh non-peer PS'),
                    }
                    nodeinfo_list.append(node_entry)
                    raw_info_candidate = node_entry.get('raw')
                    raw_info: Dict[str, Any] = raw_info_candidate if isinstance(raw_info_candidate, dict) else {}
                    thr_value = raw_info.get('thr')
                    if isinstance(thr_value, (int, float)):
                        throughput_samples.append(thr_value / 1000.0)

                    tx_candidate = raw_info.get('tx')
                    tx_info: Dict[str, Any] = tx_candidate if isinstance(tx_candidate, dict) else {}
                    rx_candidate = raw_info.get('rx')
                    rx_info: Dict[str, Any] = rx_candidate if isinstance(rx_candidate, dict) else {}
                    node_entry['tx_packets'] = tx_info.get('packets')
                    node_entry['tx_bytes'] = tx_info.get('bytes')
                    node_entry['tx_retries'] = tx_info.get('retries')
                    node_entry['tx_rate_curr'] = tx_info.get('rate')
                    node_entry['rx_packets'] = rx_info.get('packets')
                    node_entry['rx_bytes'] = rx_info.get('bytes')
                    node_entry['rx_drop_misc'] = rx_info.get('drop_misc')
                except (ValueError, TypeError):
                    continue

            for node_entry in nodeinfo_list:
                topo_entry = topology_by_mac.get(node_entry['macaddr'])
                if topo_entry:
                    node_entry.setdefault('nodeid', topo_entry.get('nodeid'))
                    node_entry.setdefault('ipaddr', topo_entry.get('ipaddr'))

            avg_rssi = sum(node['rssi'] for node in nodeinfo_list) / len(nodeinfo_list) if nodeinfo_list else 0.0
            avg_snr = sum(node['snr'] for node in nodeinfo_list) / len(nodeinfo_list) if nodeinfo_list else 0.0
            
            # 处理拓扑信息，计算平均链路质量
            def _to_float(value: Any) -> Optional[float]:
                try:
                    if value in (None, ''):
                        return None
                    return float(value)
                except (TypeError, ValueError):
                    return None

            link_qualities: List[float] = []

            for neighbor in neighbors_data:
                try:
                    neighbor_mac = neighbor.get('neighbor', '').lower()
                    matched_node = next((n for n in nodeinfo_list if n.get('macaddr') == neighbor_mac), None)
                    if not matched_node:
                        continue

                    neighbor_node = topology_by_mac.get(neighbor_mac)
                    if neighbor_node:
                        matched_node['nodeid'] = neighbor_node.get('nodeid') or matched_node.get('nodeid')
                        matched_node['ipaddr'] = neighbor_node.get('ipaddr') or matched_node.get('ipaddr')

                    metric = _to_float(neighbor.get('metric'))
                    if metric is not None and metric > 0:
                        link_qualities.append(metric)
                    matched_node['link_metric'] = metric
                    matched_node['tx_rate'] = _to_float(neighbor.get('tx_rate'))
                    matched_node['topology_snr'] = _to_float(neighbor.get('snr'))
                    matched_node['last_seen'] = neighbor.get('last_seen')
                except Exception as e:
                    if self.verbose:
                        print(f"处理邻居节点时出错: {e}")
                    continue
            
            avg_link_quality = sum(link_qualities) / len(link_qualities) if link_qualities else 0.0
            
            connected_nodes_count = len(nodeinfo_list) if nodeinfo_list else len(connected_nodes)
            disabled_value = mesh_info.get('disabled', '1')
            mesh_enabled = str(disabled_value).lower() in ('0', 'false')
            throughput_value = system_status.get('throughput', 'N/A')
            if (throughput_value in ('N/A', None, '')) and throughput_samples:
                throughput_value = f"{sum(throughput_samples) / len(throughput_samples):.3f}"

            return {
                'mesh_enabled': mesh_enabled,
                'channel': mesh_info.get('channel', 'N/A'),
                'frequency_band': mesh_info.get('chanbw', 'N/A'),
                'tx_power': mesh_info.get('txpower', 'N/A'),
                'work_mode': mesh_info.get('mode', 'N/A'),
                'node_id': mesh_info.get('nodeid', 'N/A'),
                'node_ip': node_ip,
                'wifi_quality': mesh_info.get('quality'),
                'wifi_quality_max': mesh_info.get('quality_max'),
                'wifi_noise': mesh_info.get('noise'),
                'wifi_bitrate': mesh_info.get('bitrate'),
                'wifi_mode': mesh_info.get('mode'),
                'channel_width': mesh_info.get('channel_width'),
                'connected_nodes': connected_nodes_count,
                'throughput': throughput_value,
                'cpu_usage': system_status.get('cpu', 'N/A'),
                'memory_usage': system_status.get('memory', 'N/A'),
                'load1': system_status.get('load1'),
                'load5': system_status.get('load5'),
                'load15': system_status.get('load15'),
                'mem_total': system_status.get('mem_total'),
                'mem_free': system_status.get('mem_free'),
                'mem_cached': system_status.get('mem_cached'),
                'bat_ipv4': mesh_info.get('bat_ipv4'),
                'bat_ipv6': mesh_info.get('bat_ipv6'),
                'uptime': system_status.get('uptime', 'N/A'),
                'firmware_version': system_status.get('firmware', 'N/A'),
                'topology_nodes': len(topology),
                'link_quality': avg_link_quality,
                'nodeinfo_list': nodeinfo_list,
                'typology': topology,
                'avg_rssi': avg_rssi,
                'avg_snr': avg_snr
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
            # 写入CSV文件，每个连接节点写一行
            with open(self.log_file, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                if data['nodeinfo_list']:
                    for node in data['nodeinfo_list']:
                        writer.writerow([
                            timestamp,                          # Unix时间戳
                            data['mesh_enabled'],               # Mesh启用状态
                            data['channel'],                    # 信道
                            data['frequency_band'],             # 频宽
                            data['tx_power'],                   # 发射功率
                            data['work_mode'],                  # 工作模式
                            data['node_id'],                    # 本节点ID
                            data.get('node_ip', 'N/A'),        # 本节点IP
                            data.get('wifi_quality', ''),
                            data.get('wifi_quality_max', ''),
                            data.get('wifi_noise', ''),
                            data.get('wifi_bitrate', ''),
                            data.get('wifi_mode', ''),
                            data.get('channel_width', ''),
                            data['connected_nodes'],            # 连接节点数
                            node.get('nodeid', ''),            # 连接的节点ID
                            node.get('macaddr', ''),           # 连接的节点MAC
                            node.get('ipaddr', ''),            # 连接的节点IP
                            node.get('rssi', ''),               # rssi
                            node.get('snr', ''),                # snr
                            node.get('topology_snr', ''),       # topo snr
                            node.get('link_metric', ''),        # metric
                            node.get('tx_rate', ''),            # tx rate
                            node.get('last_seen', ''),          # last seen
                            node.get('thr', ''),                # thr
                            node.get('tx_packets', ''),
                            node.get('tx_bytes', ''),
                            node.get('tx_retries', ''),
                            node.get('rx_packets', ''),
                            node.get('rx_bytes', ''),
                            node.get('rx_drop_misc', ''),
                            node.get('mesh_plink', ''),
                            node.get('mesh_llid', ''),
                            node.get('mesh_plid', ''),
                            node.get('mesh_local_ps', ''),
                            node.get('mesh_peer_ps', ''),
                            node.get('mesh_non_peer_ps', ''),
                            data['throughput'],                 # 吞吐量
                            data['cpu_usage'],                  # CPU使用率
                            data['memory_usage'],               # 内存使用率
                            data.get('load1', ''),
                            data.get('load5', ''),
                            data.get('load15', ''),
                            data.get('mem_total', ''),
                            data.get('mem_free', ''),
                            data.get('mem_cached', ''),
                            data.get('bat_ipv4', ''),
                            data.get('bat_ipv6', ''),
                            data['uptime'],                     # 运行时间
                            data['firmware_version'],           # 固件版本
                            data['topology_nodes'],             # 拓扑节点数
                            data['link_quality']                # 链路质量
                        ])
                else:
                    writer.writerow([
                        timestamp,
                        data['mesh_enabled'],
                        data['channel'],
                        data['frequency_band'],
                        data['tx_power'],
                        data['work_mode'],
                        data['node_id'],
                        data.get('node_ip', 'N/A'),
                        data.get('wifi_quality', ''),
                        data.get('wifi_quality_max', ''),
                        data.get('wifi_noise', ''),
                        data.get('wifi_bitrate', ''),
                        data.get('wifi_mode', ''),
                        data.get('channel_width', ''),
                        data['connected_nodes'],
                        '', '', '',
                        '', '', '',
                        '', '', '',
                        '', '', '',
                        '', '', '',
                        '', '', '',
                        data['throughput'],
                        data['cpu_usage'],
                        data['memory_usage'],
                        data.get('load1', ''),
                        data.get('load5', ''),
                        data.get('load15', ''),
                        data.get('mem_total', ''),
                        data.get('mem_free', ''),
                        data.get('mem_cached', ''),
                        data.get('bat_ipv4', ''),
                        data.get('bat_ipv6', ''),
                        data['uptime'],
                        data['firmware_version'],
                        data['topology_nodes'],
                        data['link_quality']
                    ])
            # 写拓扑数据到json文件
            topology_snapshot = data.get('typology')
            if topology_snapshot:
                self.log_topology_edges(timestamp, topology_snapshot)
    
            # 从data中移除typology，避免在CSV中显示
            data.pop('typology', None)
    
            # 显示当前数据（格式与UDP测试系统保持一致）
            if self.verbose:
                print(
                    f"Nexfi logged at {timestamp:.6f}: "
                    f"Nodes: {data['connected_nodes']}, "
                    f"RSSI: {data['avg_rssi']:.1f}dBm, "
                    f"SNR: {data['avg_snr']:.1f}dB, "
                    f"Throughput: {data['throughput']}"
                )
        except Exception as e:
            print(f"记录Nexfi状态数据时出错: {e}")

    def log_topology_edges(self, timestamp: float, topology: List[Dict[str, Any]]):
        """把完整拓扑边写入CSV"""
        if not topology or self.topology_edges_disabled:
            return
        if not self.topology_edges_initialized:
            self.init_topology_edges_file()
            if not self.topology_edges_initialized:
                return

        nodes_by_mac = {}
        for node in topology:
            primary = str(node.get('primary', '')).lower()
            if not primary:
                continue
            nodes_by_mac[primary] = node

        try:
            with open(self.topology_edges_file, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                for node in topology:
                    router_mac = str(node.get('primary', '')).lower()
                    router_ip = node.get('ipaddr', '')
                    router_nodeid = node.get('nodeid', '')
                    neighbors = node.get('neighbors', [])
                    if not isinstance(neighbors, list):
                        continue
                    for neighbor in neighbors:
                        neighbor_mac = str(neighbor.get('neighbor', '')).lower()
                        neighbor_entry = nodes_by_mac.get(neighbor_mac, {})
                        writer.writerow([
                            timestamp,
                            router_mac,
                            router_ip,
                            router_nodeid,
                            neighbor_mac,
                            neighbor_entry.get('ipaddr', ''),
                            neighbor_entry.get('nodeid', ''),
                            neighbor.get('metric', ''),
                            neighbor.get('tx_rate', ''),
                            neighbor.get('snr', ''),
                            neighbor.get('last_seen', ''),
                        ])
        except Exception as e:
            if self.verbose:
                print(f"写入拓扑边数据失败: {e}")

        
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


def parse_args() -> Tuple[Dict[str, Any], argparse.Namespace]:
    """解析命令行参数"""
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
    parser.add_argument('--bat-interface', default=DEFAULT_CONFIG["bat_interface"],
                       help=f'batman-adv接口名称 (默认: {DEFAULT_CONFIG["bat_interface"]})')
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
        "bat_interface": args.bat_interface,
        "verbose": args.verbose.lower() == 'true',
    }
    
    return config, args


def main():
    """主函数"""
    try:
        config, args = parse_args()
        
        if args.monitor:
            # 监控模式 - 使用原有的显示功能
            client = NexfiClient(
                config["nexfi_ip"],
                config["username"],
                config["password"],
                device_name=config["device_name"],
                bat_interface=config["bat_interface"],
            )
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
            client = NexfiClient(
                config["nexfi_ip"],
                config["username"],
                config["password"],
                device_name=config["device_name"],
                bat_interface=config["bat_interface"],
            )
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
