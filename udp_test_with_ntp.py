#!/usr/bin/env python3
"""
无人机UDP通信测试系统 - 集成NTP时间同步
完整的测试启动脚本，包含时间同步、UDP发送/接收、GPS记录、状态监控等功能
"""

import os
import sys
import time
import json
import socket
import argparse
import subprocess
import threading
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

class NTPSyncManager:
    """NTP时间同步管理器"""
    
    def __init__(self, local_ip: str, ntp_peer_ip: str, log_path: str = "./logs", mode: str = "sender"):
        self.local_ip = local_ip
        self.ntp_peer_ip = ntp_peer_ip  # 参数含义：sender=本机NTP服务IP, receiver=要连接的NTP服务器IP
        self.log_path = log_path
        self.mode = mode  # 'sender' or 'receiver'
        self.role = None  # 'server' or 'client'
        self.sync_status = {'synced': False, 'offset_ms': None}
        
        # 根据模式确定NTP配置
        if self.mode == 'sender':
            self.ntp_server_ip = ntp_peer_ip  # sender的NTP服务器监听IP
            self.ntp_client_ip = None  # sender不需要知道客户端IP
        else:  # receiver
            self.ntp_server_ip = ntp_peer_ip  # receiver要连接的NTP服务器IP
            self.ntp_client_ip = None  # 客户端不需要指定自己的IP
        
        # 设置日志
        self.setup_logging()
        
    def setup_logging(self):
        """设置日志配置"""
        os.makedirs(self.log_path, exist_ok=True)
        log_file = os.path.join(self.log_path, f"ntp_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def determine_role(self) -> str:
        """基于sender/receiver模式确定NTP角色"""
        # 始终使用内部同步模式：sender=server, receiver=client
        
        if self.mode == 'sender':
            self.role = 'server'
            self.logger.info(f"NTP模式: 内部直接同步 (sender作为NTP服务器)")
            self.logger.info(f"NTP服务器将在 {self.ntp_server_ip} 上监听")
        else:  # receiver
            self.role = 'client'
            self.logger.info(f"NTP模式: 内部直接同步 (receiver作为NTP客户端)")
            self.logger.info(f"NTP客户端将连接到 {self.ntp_server_ip}")
        
        self.logger.info(f"角色确定: {self.role}")
        self.logger.info(f"本地通信IP: {self.local_ip}")
        
        return self.role
    
    def wait_for_peer(self, timeout: int = 30) -> bool:
        """等待对方无人机上线（内部同步模式）"""
        if self.role == 'server':
            # 服务器不需要等待，直接返回成功
            self.logger.info("NTP服务器模式，无需等待其他设备")
            return True
        else:
            # 客户端需要等待服务器上线
            self.logger.info(f"等待NTP服务器 {self.ntp_server_ip} 上线...")
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    result = subprocess.run(['ping', '-c', '1', '-W', '1', self.ntp_server_ip], 
                                          capture_output=True, timeout=5)
                    if result.returncode == 0:
                        self.logger.info(f"NTP服务器 {self.ntp_server_ip} 已上线")
                        return True
                except Exception as e:
                    self.logger.debug(f"ping NTP服务器出错: {e}")
                
                time.sleep(2)
            
            self.logger.warning(f"NTP服务器 {self.ntp_server_ip} 在{timeout}秒内未上线")
            return False
    
    def install_chrony(self) -> bool:
        """安装chrony（如果需要）"""
        try:
            # 检查chrony是否已安装
            result = subprocess.run(['which', 'chronyc'], capture_output=True)
            if result.returncode == 0:
                self.logger.info("Chrony already installed")
                return True
            
            # 安装chrony
            self.logger.info("Installing chrony...")
            subprocess.run(['sudo', 'apt-get', 'update'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'chrony'], check=True)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to install chrony: {e}")
            return False
    
    def configure_ntp_server(self) -> bool:
        """配置为NTP服务器"""
        # 获取NTP服务器监听网段
        ntp_server_network = '.'.join(self.ntp_server_ip.split('.')[:-1]) + '.0/24'
        
        # 检查指定IP是否存在于本机
        bind_address = "0.0.0.0"  # 默认监听所有接口
        try:
            result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                interfaces = []
                for line in result.stdout.split('\n'):
                    if 'inet ' in line and not '127.0.0.1' in line:
                        ip_part = line.strip().split()[1].split('/')[0]
                        interfaces.append(ip_part)
                
                if self.ntp_server_ip in interfaces:
                    bind_address = self.ntp_server_ip
                    print(f"✓ 将在指定IP {self.ntp_server_ip} 上监听")
                else:
                    print(f"⚠️  指定IP {self.ntp_server_ip} 不存在，将监听所有接口")
        except Exception as e:
            print(f"⚠️  无法检查网络接口: {e}，将监听所有接口")
        
        # 配置为内部NTP服务器
        config = f"""# NTP Server Configuration - Generated by UDP Test System (Internal Sync)
# Sender作为NTP服务器，在指定IP地址上提供NTP服务
# 使用本地时钟作为时间源
local stratum 8

# 允许来自NTP网段的客户端访问
allow {ntp_server_network}

# 允许来自UDP通信网段的访问（如果不同）
allow 192.168.104.0/24

# 允许本地查询（用于监控）
cmdallow 127.0.0.1
cmdallow {self.local_ip}

# 如果NTP服务器IP与本地IP不同，也允许查询
cmdallow {self.ntp_server_ip}

# 监听指定的IP地址（如果存在）或所有接口
bindaddress {bind_address}

# 日志配置
logdir /var/log/chrony
log measurements statistics tracking

# 其他配置
driftfile /var/lib/chrony/drift
makestep 1.0 3
rtcsync
"""
        
        return self.write_chrony_config(config)
    
    def configure_ntp_client(self) -> bool:
        """配置为NTP客户端"""
        # 内部同步模式：连接对方无人机的NTP服务器
        config = f"""# NTP Client Configuration - Generated by UDP Test System (Internal Sync)
# Receiver作为NTP客户端，连接Sender的NTP服务器进行时间同步
# NTP对时可以使用与UDP通信不同的网段
# 使用对方无人机作为时间源
server {self.ntp_server_ip} iburst prefer

# 快速同步配置
makestep 1.0 3
maxupdateskew 100.0

# 日志配置
logdir /var/log/chrony
log measurements statistics tracking

# 其他配置
driftfile /var/lib/chrony/drift
rtcsync
"""
        
        return self.write_chrony_config(config)
    
    def check_sudo_access(self) -> bool:
        """检查sudo权限"""
        try:
            print("检查sudo权限...")
            result = subprocess.run(['sudo', '-n', 'true'], 
                                  capture_output=True, timeout=5)
            if result.returncode == 0:
                print("✓ 已有sudo权限")
                return True
            else:
                print("⚠️  需要输入sudo密码")
                return True  # 仍然返回True，让后续命令处理密码输入
        except Exception as e:
            self.logger.debug(f"Sudo check failed: {e}")
            print("⚠️  无法检查sudo权限，将在需要时提示")
            return True
    
    def write_chrony_config(self, config: str) -> bool:
        """写入chrony配置文件"""
        try:
            print("⚠️  需要sudo权限来配置chrony，请准备输入密码...")
            
            # 备份原配置文件
            backup_file = f"/etc/chrony/chrony.conf.backup.{int(time.time())}"
            result = subprocess.run(['sudo', 'cp', '/etc/chrony/chrony.conf', backup_file], 
                                  capture_output=False)
            if result.returncode != 0:
                self.logger.error("Failed to backup chrony config")
                return False
            
            # 写入新配置
            with open('/tmp/chrony.conf.new', 'w') as f:
                f.write(config)
            
            print("正在更新chrony配置文件...")
            result = subprocess.run(['sudo', 'cp', '/tmp/chrony.conf.new', '/etc/chrony/chrony.conf'])
            if result.returncode != 0:
                self.logger.error("Failed to update chrony config")
                return False
            
            print("正在重启chrony服务...")
            result = subprocess.run(['sudo', 'systemctl', 'restart', 'chrony'])
            if result.returncode != 0:
                self.logger.error("Failed to restart chrony service")
                return False
                
            time.sleep(3)  # 等待服务启动
            
            self.logger.info(f"Chrony configured as {self.role}")
            print("✓ Chrony配置完成")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to configure chrony: {e}")
            print(f"✗ Chrony配置失败: {e}")
            return False
    
    def verify_sync(self, timeout: int = 60) -> bool:
        """验证时间同步状态"""
        if self.role == 'server':
            return self.verify_server_status(timeout)
        else:
            return self.verify_client_sync(timeout)
    
    def verify_server_status(self, timeout: int) -> bool:
        """验证服务器状态"""
        print(f"⏱️  正在验证NTP服务器状态 (超时: {timeout}秒)...")
        start_time = time.time()
        check_count = 0
        
        while time.time() - start_time < timeout:
            check_count += 1
            try:
                print(f"🔍 第{check_count}次检查NTP服务器状态...")
                
                # 检查chrony服务状态
                tracking_result = subprocess.run(['chronyc', 'tracking'], 
                                               capture_output=True, text=True, timeout=5)
                if tracking_result.returncode == 0:
                    print(f"📊 NTP服务器状态:")
                    for line in tracking_result.stdout.split('\n'):
                        if line.strip():
                            print(f"   {line}")
                    
                    if "Stratum" in tracking_result.stdout:
                        self.logger.info("NTP server: running normally")
                        print("✓ NTP服务器运行正常")
                        
                        # 检查是否有客户端连接
                        clients_result = subprocess.run(['chronyc', 'clients'], 
                                                      capture_output=True, text=True, timeout=5)
                        if clients_result.returncode == 0 and "Not authorised" not in clients_result.stdout:
                            print(f"📊 NTP客户端连接状态:")
                            print(f"   {clients_result.stdout.strip()}")
                            if self.ntp_peer_ip in clients_result.stdout:
                                print(f"✅ 检测到客户端 {self.ntp_peer_ip} 已连接!")
                                self.sync_status['synced'] = True
                                return True
                        else:
                            print("📊 无法查询客户端连接状态，但服务器运行正常")
                        
                        # 服务器正常运行，认为配置成功
                        self.sync_status['synced'] = True
                        return True
                
            except Exception as e:
                print(f"⚠️  检查NTP服务器状态时出错: {e}")
                self.logger.debug(f"Error checking server status: {e}")
            
            print(f"⏱️  等待5秒后重试... (剩余时间: {timeout - int(time.time() - start_time)}秒)")
            time.sleep(5)
        
        print("❌ NTP服务器状态验证超时!")
        self.logger.warning("NTP server: verification timeout")
        return False
    
    def verify_client_sync(self, timeout: int) -> bool:
        """验证客户端同步状态"""
        print(f"⏱️  正在验证时间同步状态 (超时: {timeout}秒)...")
        start_time = time.time()
        check_count = 0
        
        while time.time() - start_time < timeout:
            check_count += 1
            try:
                result = subprocess.run(['chronyc', 'sources', '-v'], 
                                      capture_output=True, text=True, timeout=5)
                lines = result.stdout.split('\n')
                
                print(f"🔍 第{check_count}次检查同步状态...")
                
                for line in lines:
                    # 查找活跃的时间源（以*开头）
                    if line.startswith('^*'):
                        print(f"✓ 发现活跃时间源: {line.strip()}")
                        
                        # 解析偏移量
                        parts = line.split()
                        if len(parts) >= 7:
                            try:
                                # 偏移量在第7列，格式可能是 "-24ms[" 或 "+1.2us[" 或 "-3069ns[+1489us]"
                                offset_str = parts[6]
                                
                                # 处理复合格式，只取第一个值
                                if '[' in offset_str:
                                    # 提取括号前的部分，如 "-3069ns[+1489us]" -> "-3069ns"
                                    first_part = offset_str.split('[')[0]
                                else:
                                    first_part = offset_str
                                
                                # 移除单位
                                if first_part.endswith('ms'):
                                    clean_offset = first_part[:-2]
                                    unit = 'ms'
                                elif first_part.endswith('us'):
                                    clean_offset = first_part[:-2]
                                    unit = 'us'
                                elif first_part.endswith('ns'):
                                    clean_offset = first_part[:-2]
                                    unit = 'ns'
                                elif first_part.endswith('s'):
                                    clean_offset = first_part[:-1]
                                    unit = 's'
                                else:
                                    clean_offset = first_part
                                    unit = 'ms'  # 默认
                                
                                offset = float(clean_offset)
                                
                                # 根据单位转换为毫秒
                                if unit == 'us':
                                    offset_ms = offset / 1000  # 微秒转毫秒
                                elif unit == 'ns':
                                    offset_ms = offset / 1000000  # 纳秒转毫秒
                                elif unit == 'ms':
                                    offset_ms = offset  # 已经是毫秒
                                elif unit == 's':
                                    offset_ms = offset * 1000  # 秒转毫秒
                                else:
                                    offset_ms = offset
                                
                                self.sync_status['offset_ms'] = offset_ms
                                
                                print(f"📊 时间偏移量: {offset_ms:.3f}ms (原始: {offset_str})")
                                
                                if abs(offset_ms) < 50:  # 50ms以内认为同步成功
                                    print(f"✅ 时间同步成功! 偏移量: {offset_ms:.3f}ms (< 50ms)")
                                    self.logger.info(f"NTP client synced successfully, offset: {offset_ms:.2f}ms")
                                    self.sync_status['synced'] = True
                                    return True
                                else:
                                    print(f"⏳ 同步中... 当前偏移量: {offset_ms:.3f}ms (需要 < 50ms)")
                                    self.logger.info(f"NTP client syncing, current offset: {offset_ms:.2f}ms")
                            except (ValueError, IndexError) as e:
                                print(f"⚠️  解析偏移量失败: {e}")
                                self.logger.debug(f"Error parsing offset: {e}")
                                continue
                        break
                else:
                    print("⏳ 未找到活跃时间源，继续等待...")
                
            except Exception as e:
                print(f"⚠️  检查同步状态时出错: {e}")
                self.logger.debug(f"Error checking sync status: {e}")
            
            print(f"⏱️  等待5秒后重试... (剩余时间: {timeout - int(time.time() - start_time)}秒)")
            time.sleep(5)
        
        print("❌ 时间同步验证超时!")
        self.logger.error("Failed to achieve time sync within timeout")
        return False
    
    def get_sync_status(self) -> Dict[str, Any]:
        """获取当前同步状态"""
        if self.role == 'client':
            try:
                result = subprocess.run(['chronyc', 'sources', '-v'], 
                                      capture_output=True, text=True, timeout=5)
                lines = result.stdout.split('\n')
                for line in lines:
                    if '*' in line and self.ntp_server_ip in line:
                        parts = line.split()
                        if len(parts) >= 7:
                            offset = float(parts[6]) * 1000  # 转换为毫秒
                            self.sync_status['offset_ms'] = offset
                            self.sync_status['synced'] = abs(offset) < 10
                            break
            except Exception:
                pass
        
        return self.sync_status.copy()
    
    def setup_time_sync(self, skip_config: bool = False) -> bool:
        """设置时间同步"""
        try:
            # 1. 安装chrony
            if not self.install_chrony():
                return False
            
            # 2. 确定角色
            role = self.determine_role()
            print(f"This drone will act as NTP {role}")
            
            if skip_config:
                print("⚠️  跳过chrony配置，使用现有配置")
                # 直接验证同步
                if self.verify_sync(timeout=30):
                    print(f"✓ Time synchronization successful! Role: {role}")
                    return True
                else:
                    print("✗ Time synchronization failed with existing config!")
                    return False
            
            # 3. 检查sudo权限
            if not self.check_sudo_access():
                print("✗ 无法获取sudo权限，无法配置chrony")
                print("💡 提示：您可以手动配置chrony或使用 --skip-ntp-config 选项")
                return False
            
            # 4. 网络接口检查
            print(f"\n🔧 进行网络配置检查...")
            if not self.check_network_interface():
                if self.role == 'client':
                    print("✗ 网络检查失败，无法继续")
                    return False
                else:
                    print("⚠️  网络检查有警告，但继续配置")
            
            # 5. 等待对方上线（仅客户端）
            if self.role == 'client':
                if not self.wait_for_peer():
                    print("⚠️  NTP服务器暂时不可达，但继续配置...")
            
            # 6. 配置NTP
            print(f"\n🔧 配置NTP {role}...")
            if role == 'server':
                success = self.configure_ntp_server()
                if success:
                    print(f"✓ NTP服务器配置完成，正在启动服务...")
                    # 给服务器一些时间完全启动
                    time.sleep(5)
            else:
                success = self.configure_ntp_client()
                if success:
                    print(f"✓ NTP客户端配置完成")
                    # 客户端配置后，检查端口连通性
                    print(f"\n🔧 检查NTP连通性...")
                    self.check_ntp_port()
            
            if not success:
                return False
            
            # 7. 验证同步
            print(f"\n🔧 验证时间同步...")
            if self.verify_sync():
                print(f"✅ Time synchronization successful! Role: {role}")
                return True
            else:
                print("❌ Time synchronization failed!")
                return False
                
        except Exception as e:
            self.logger.error(f"NTP setup failed: {e}")
            return False
    
    def check_network_interface(self) -> bool:
        """检查网络接口配置"""
        try:
            if self.role == 'server':
                # 对于server，检查本机是否有NTP服务器IP
                print(f"🔍 检查NTP服务器网络接口配置...")
                result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    print(f"📊 当前网络接口：")
                    interfaces = []
                    for line in result.stdout.split('\n'):
                        if 'inet ' in line and not '127.0.0.1' in line:
                            ip_part = line.strip().split()[1].split('/')[0]
                            interfaces.append(ip_part)
                            print(f"   {ip_part}")
                    
                    # 检查NTP服务器IP是否在本机接口上
                    if self.ntp_server_ip in interfaces:
                        print(f"✓ NTP服务器IP {self.ntp_server_ip} 在本机接口上")
                        return True
                    else:
                        print(f"⚠️  NTP服务器IP {self.ntp_server_ip} 不在本机接口上")
                        print(f"   chrony将尝试监听所有接口 (0.0.0.0)")
                        return True  # 不阻止继续，让chrony尝试
            else:
                # 对于client，检查能否ping通服务器
                print(f"🔍 检查到NTP服务器 {self.ntp_server_ip} 的网络连接...")
                result = subprocess.run(['ping', '-c', '1', '-W', '3', self.ntp_server_ip], 
                                      capture_output=True, timeout=10)
                if result.returncode == 0:
                    print(f"✓ NTP服务器 {self.ntp_server_ip} 网络可达")
                    return True
                else:
                    print(f"❌ NTP服务器 {self.ntp_server_ip} 网络不可达")
                    return False
        except Exception as e:
            print(f"⚠️  网络接口检查失败: {e}")
            return True  # 不阻止继续执行
    
    def check_ntp_port(self) -> bool:
        """检查NTP端口连通性"""
        if self.role == 'client':
            try:
                print(f"🔍 检查NTP端口连通性 (UDP 123)...")
                # 使用nc检查端口
                result = subprocess.run(['nc', '-u', '-z', '-w', '3', self.ntp_server_ip, '123'], 
                                      capture_output=True, timeout=10)
                if result.returncode == 0:
                    print(f"✓ NTP端口 {self.ntp_server_ip}:123 可达")
                    return True
                else:
                    print(f"⚠️  NTP端口 {self.ntp_server_ip}:123 可能不可达")
                    return False
            except Exception as e:
                print(f"⚠️  NTP端口检查失败: {e}")
                return True  # 不阻止继续执行
        return True


class UDPTestManager:
    """UDP测试管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.log_path = config.get('log_path', './logs')
        self.mode = config.get('mode', 'sender')  # 'sender' or 'receiver'
        
        # 创建日志目录
        os.makedirs(self.log_path, exist_ok=True)
        
        # 设置日志
        self.setup_logging()
        
        # NTP配置
        self.enable_ntp = config.get('enable_ntp', True)  # 默认启用NTP
        self.ntp_manager = None
        
        if self.enable_ntp:
            # 初始化NTP管理器
            local_ip = config.get('local_ip', '192.168.104.10')
            ntp_peer_ip = config.get('ntp_peer_ip', config.get('peer_ip', '192.168.104.20'))  # 默认使用peer_ip
            self.ntp_manager = NTPSyncManager(local_ip, ntp_peer_ip, self.log_path, self.mode)
        
        # 状态监控
        self.monitoring = False
        self.monitor_thread = None
        
        # 配置选项
        self.skip_ntp_config = config.get('skip_ntp_config', False)
        
        # GPS记录器进程
        self.gps_process = None
        self.enable_gps = config.get('enable_gps', False)
        self.drone_id = config.get('drone_id', 'drone0')
        self.gps_interval = config.get('gps_interval', 1.0)
        
        # Nexfi状态记录器进程
        self.nexfi_process = None
        self.enable_nexfi = config.get('enable_nexfi', False)
        self.nexfi_ip = config.get('nexfi_ip', '192.168.104.1')
        self.nexfi_username = config.get('nexfi_username', 'root')
        self.nexfi_password = config.get('nexfi_password', 'nexfi')
        self.nexfi_interval = config.get('nexfi_interval', 1.0)
        self.nexfi_device = config.get('nexfi_device', 'adhoc0')
    
    def setup_logging(self):
        """设置日志"""
        log_file = os.path.join(self.log_path, f"udp_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(f"{__name__}.UDPTestManager")
    
    def start_gps_logging(self) -> bool:
        """启动GPS记录器"""
        if not self.enable_gps:
            self.logger.info("GPS logging disabled")
            return True
            
        try:
            self.logger.info("Starting GPS logger...")
            
            # GPS记录器运行时间 = UDP通信时间 + 准备时间 + 缓冲时间
            udp_time = self.config.get('running_time', 60)
            if self.mode == 'receiver':
                # 接收端需要更长的GPS记录时间
                buffer_time = max(60, udp_time * 0.2)
                total_gps_time = udp_time + buffer_time + 120  # 额外2分钟用于准备和清理
            else:
                # 发送端GPS记录时间
                total_gps_time = udp_time + 120  # 额外2分钟用于准备和清理
            
            # 确保时间参数为整数
            total_gps_time = int(total_gps_time)
            
            # 构建GPS记录器命令
            cmd = [
                'python3', 'gps.py',
                '--drone-id', self.drone_id,
                '--log-path', self.log_path,
                '--interval', str(self.gps_interval),
                '--time', str(total_gps_time),
                '--verbose', 'true'
            ]
            
            # 如果使用仿真时间
            if self.config.get('use_sim_time', False):
                cmd.append('--sim-time')
            
            # 启动GPS记录器进程
            self.gps_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 等待一下确保GPS记录器启动
            time.sleep(2)
            
            # 检查进程是否正常运行
            if self.gps_process.poll() is None:
                self.logger.info(f"GPS logger started successfully (will run for {total_gps_time}s)")
                return True
            else:
                stdout, stderr = self.gps_process.communicate()
                self.logger.error(f"GPS logger failed to start: {stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to start GPS logger: {e}")
            return False
    
    def stop_gps_logging(self):
        """停止GPS记录器"""
        if self.gps_process and self.gps_process.poll() is None:
            self.logger.info("Stopping GPS logger...")
            try:
                self.gps_process.terminate()
                self.gps_process.wait(timeout=10)
                self.logger.info("GPS logger stopped")
            except subprocess.TimeoutExpired:
                self.logger.warning("GPS logger did not stop gracefully, killing...")
                self.gps_process.kill()
                self.gps_process.wait()
            except Exception as e:
                self.logger.error(f"Error stopping GPS logger: {e}")
    
    def start_nexfi_logging(self) -> bool:
        """启动Nexfi状态记录器"""
        if not self.enable_nexfi:
            self.logger.info("Nexfi status logging disabled")
            return True
            
        try:
            self.logger.info("Starting Nexfi status logger...")
            
            # Nexfi记录器运行时间 = UDP通信时间 + 准备时间 + 缓冲时间
            udp_time = self.config.get('running_time', 60)
            if self.mode == 'receiver':
                # 接收端需要更长的Nexfi记录时间
                buffer_time = max(60, udp_time * 0.2)
                total_nexfi_time = udp_time + buffer_time + 120  # 额外2分钟用于准备和清理
            else:
                # 发送端Nexfi记录时间
                total_nexfi_time = udp_time + 120  # 额外2分钟用于准备和清理
            
            # 确保时间参数为整数
            total_nexfi_time = int(total_nexfi_time)
            
            # 构建Nexfi状态记录器命令
            cmd = [
                'python3', 'nexfi_client.py',
                '--nexfi-ip', self.nexfi_ip,
                '--username', self.nexfi_username,
                '--password', self.nexfi_password,
                '--log-path', self.log_path,
                '--interval', str(self.nexfi_interval),
                '--time', str(total_nexfi_time),
                '--device', self.nexfi_device,
                '--verbose', 'true'
            ]
            
            # 启动Nexfi状态记录器进程
            self.nexfi_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 等待一下确保Nexfi记录器启动
            time.sleep(2)
            
            # 检查进程是否正常运行
            if self.nexfi_process.poll() is None:
                self.logger.info(f"Nexfi status logger started successfully (will run for {total_nexfi_time}s)")
                return True
            else:
                stdout, stderr = self.nexfi_process.communicate()
                self.logger.warning(f"Nexfi status logger failed to start: {stderr}")
                self.logger.info("Nexfi status logger will use mock data")
                return True  # 返回True因为可以使用模拟数据
                
        except Exception as e:
            self.logger.error(f"Failed to start Nexfi status logger: {e}")
            return False
    
    def stop_nexfi_logging(self):
        """停止Nexfi状态记录器"""
        if self.nexfi_process and self.nexfi_process.poll() is None:
            self.logger.info("Stopping Nexfi status logger...")
            try:
                self.nexfi_process.terminate()
                self.nexfi_process.wait(timeout=10)
                self.logger.info("Nexfi status logger stopped")
            except subprocess.TimeoutExpired:
                self.logger.warning("Nexfi status logger did not stop gracefully, killing...")
                self.nexfi_process.kill()
                self.nexfi_process.wait()
            except Exception as e:
                self.logger.error(f"Error stopping Nexfi status logger: {e}")
    
    def start_monitoring(self):
        """启动状态监控"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("Status monitoring started")
    
    def stop_monitoring(self):
        """停止状态监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("Status monitoring stopped")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                # 获取NTP同步状态
                if self.enable_ntp and self.ntp_manager:
                    sync_status = self.ntp_manager.get_sync_status()
                    ntp_role = self.ntp_manager.role
                    ntp_synced = sync_status.get('synced', False)
                    ntp_offset_ms = sync_status.get('offset_ms')
                else:
                    ntp_role = None
                    ntp_synced = None
                    ntp_offset_ms = None
                
                # 检查GPS记录器状态
                gps_status = "running" if (self.gps_process and self.gps_process.poll() is None) else "stopped"
                
                # 检查Nexfi状态记录器状态
                nexfi_status = "running" if (self.nexfi_process and self.nexfi_process.poll() is None) else "stopped"
                
                # 记录状态
                status_info = {
                    'timestamp': datetime.now().isoformat(),
                    'ntp_enabled': self.enable_ntp,
                    'ntp_role': ntp_role,
                    'ntp_synced': ntp_synced,
                    'ntp_offset_ms': ntp_offset_ms,
                    'gps_logger_status': gps_status,
                    'enable_gps': self.enable_gps,
                    'nexfi_logger_status': nexfi_status,
                    'enable_nexfi': self.enable_nexfi,
                }
                
                # 写入监控日志
                monitor_file = os.path.join(self.log_path, "system_monitor.jsonl")
                with open(monitor_file, 'a') as f:
                    f.write(json.dumps(status_info) + '\n')
                
                # 如果启用NTP且同步状态异常，发出警告
                if self.enable_ntp and self.ntp_manager and not ntp_synced and self.ntp_manager.role == 'client':
                    self.logger.warning(f"Time sync lost! Offset: {ntp_offset_ms}ms")
                
                # 如果GPS记录器意外停止，发出警告
                if self.enable_gps and gps_status == "stopped":
                    self.logger.warning("GPS logger stopped unexpectedly")
                
                # 如果Nexfi状态记录器意外停止，发出警告
                if self.enable_nexfi and nexfi_status == "stopped":
                    self.logger.warning("Nexfi status logger stopped unexpectedly")
                
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
            
            time.sleep(10)  # 每10秒检查一次
    
    def run_udp_sender(self):
        """运行UDP发送端"""
        self.logger.info("Starting UDP sender...")
        
        # 构建命令
        cmd = [
            'python3', 'udp_sender.py',
            '--local-ip', self.config.get('local_ip', '0.0.0.0'),
            '--local-port', str(self.config.get('local_port', 20002)),
            '--remote-ip', self.config.get('remote_ip', '192.168.104.20'),
            '--remote-port', str(self.config.get('remote_port', 20001)),
            '--packet-size', str(self.config.get('packet_size', 1000)),
            '--frequency', str(self.config.get('frequency', 10)),
            '--time', str(self.config.get('running_time', 60)),
            '--log-path', self.log_path,
            '--network-retry-delay', str(self.config.get('network_retry_delay', 1.0)),
            '--log-network-errors', str(self.config.get('log_network_errors', True)),
        ]
        
        try:
            result = subprocess.run(cmd, check=True)
            self.logger.info("UDP sender completed successfully")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"UDP sender failed: {e}")
            return False
    
    def run_udp_receiver(self):
        """运行UDP接收端"""
        self.logger.info("Starting UDP receiver...")
        
        # 接收端运行时间 = UDP通信时间 + 额外缓冲时间
        udp_time = self.config.get('running_time', 60)
        buffer_time = max(60, udp_time * 0.2)  # 至少60秒缓冲，或者20%的额外时间
        total_receiver_time = udp_time + buffer_time
        
        # 确保时间参数为整数
        total_receiver_time = int(total_receiver_time)
        
        self.logger.info(f"Receiver will run for {total_receiver_time}s (UDP: {udp_time}s + buffer: {buffer_time}s)")
        
        # 构建命令
        cmd = [
            'python3', 'udp_receiver.py',
            '--local-ip', self.config.get('local_ip', '0.0.0.0'),
            '--local-port', str(self.config.get('local_port', 20001)),
            '--buffer-size', str(self.config.get('buffer_size', 1500)),
            '--time', str(total_receiver_time),
            '--log-path', self.log_path
        ]
        
        try:
            result = subprocess.run(cmd, check=True)
            self.logger.info("UDP receiver completed successfully")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"UDP receiver failed: {e}")
            return False
    
    def run_test(self):
        """运行完整测试"""
        try:
            print("=" * 60)
            print("无人机UDP通信测试系统 - 集成NTP时间同步")
            print("=" * 60)
            
            # 显示时间配置说明
            udp_time = self.config.get('running_time', 60)
            print(f"\n⏱️  时间配置说明:")
            print(f"   - UDP通信时间: {udp_time}秒")
            if self.mode == 'receiver':
                buffer_time = max(60, udp_time * 0.2)
                total_receiver_time = udp_time + buffer_time
                print(f"   - 接收端总运行时间: {total_receiver_time}秒 (含{buffer_time}秒缓冲)")
            print(f"   - 程序包含准备时间(NTP对时、GPS启动等)，实际UDP通信将在准备完成后开始")
            
            step_num = 1
            
            # 记录测试开始时间
            test_start_time = time.time()
            
            # 1. 设置时间同步（可选）
            if self.enable_ntp:
                print(f"\n{step_num}. 设置时间同步...")
                if not self.ntp_manager.setup_time_sync(skip_config=self.skip_ntp_config):
                    print("✗ 时间同步设置失败，测试终止")
                    return False
                step_num += 1
            else:
                print(f"\n{step_num}. 跳过时间同步（NTP已禁用）")
                step_num += 1
            
            # 2. 启动GPS记录器
            if self.enable_gps:
                print(f"\n{step_num}. 启动GPS记录器...")
                if not self.start_gps_logging():
                    print("✗ GPS记录器启动失败，继续测试...")
                else:
                    print("✓ GPS记录器启动成功")
                step_num += 1
            
            # 3. 启动Nexfi状态记录器
            if self.enable_nexfi:
                print(f"\n{step_num}. 启动Nexfi状态记录器...")
                if not self.start_nexfi_logging():
                    print("✗ Nexfi状态记录器启动失败，继续测试...")
                else:
                    print("✓ Nexfi状态记录器启动成功")
                step_num += 1
            
            # 4. 启动状态监控
            print(f"\n{step_num}. 启动状态监控...")
            self.start_monitoring()
            step_num += 1
            
            # 5. 等待时间同步稳定（仅在启用NTP时）
            if self.enable_ntp:
                print(f"\n{step_num}. 等待时间同步稳定...")
                time.sleep(10)
                step_num += 1
            
            # 6. 协调启动时序（sender需要额外等待）
            if self.mode == 'sender':
                print(f"\n{step_num}. 等待receiver准备完成...")
                print("   📡 为确保数据完整性，sender将额外等待20秒")
                print("   💡 这确保了receiver有足够时间完成所有准备工作")
                
                # 显示倒计时
                for i in range(20, 0, -5):
                    print(f"   ⏱️  等待receiver准备: {i}秒...")
                    time.sleep(5)
                print("   ✅ 等待完成，开始UDP发送")
                step_num += 1
            else:
                print(f"\n{step_num}. Receiver模式，无需额外等待")
                step_num += 1
            
            # 7. 准备完成，记录准备时间
            preparation_time = time.time() - test_start_time
            print(f"\n{step_num}. 准备工作完成，耗时 {preparation_time:.1f}秒")
            print(f"   📡 现在开始 {udp_time}秒 的UDP通信测试...")
            step_num += 1
            
            # 8. 运行UDP测试
            print(f"\n{step_num}. 运行UDP测试 (模式: {self.mode})...")
            
            if self.mode == 'sender':
                success = self.run_udp_sender()
            elif self.mode == 'receiver':
                success = self.run_udp_receiver()
            else:
                self.logger.error(f"Unknown mode: {self.mode}")
                return False
            step_num += 1
            
            # 9. 停止GPS记录器
            if self.enable_gps:
                print(f"\n{step_num}. 停止GPS记录器...")
                self.stop_gps_logging()
                step_num += 1
            
            # 10. 停止Nexfi状态记录器
            if self.enable_nexfi:
                print(f"\n{step_num}. 停止Nexfi状态记录器...")
                self.stop_nexfi_logging()
                step_num += 1
            
            # 11. 停止监控
            print(f"\n{step_num}. 停止状态监控...")
            self.stop_monitoring()
            
            # 显示总结信息
            total_time = time.time() - test_start_time
            print(f"\n📊 测试完成总结:")
            print(f"   - 总运行时间: {total_time:.1f}秒")
            print(f"   - 准备时间: {preparation_time:.1f}秒")
            print(f"   - UDP通信时间: {udp_time}秒")
            
            if success:
                print(f"\n✓ 测试完成！日志保存在: {self.log_path}")
                return True
            else:
                print("\n✗ 测试失败！")
                return False
                
        except KeyboardInterrupt:
            print("\n测试被用户中断")
            if self.enable_gps:
                self.stop_gps_logging()
            if self.enable_nexfi:
                self.stop_nexfi_logging()
            self.stop_monitoring()
            return False
        except Exception as e:
            self.logger.error(f"Test failed: {e}")
            if self.enable_gps:
                self.stop_gps_logging()
            if self.enable_nexfi:
                self.stop_nexfi_logging()
            self.stop_monitoring()
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='无人机UDP通信测试系统 - 集成NTP时间同步')
    
    # 基本参数
    parser.add_argument('--mode', choices=['sender', 'receiver'], required=True,
                       help='运行模式: sender(发送端) 或 receiver(接收端)')
    parser.add_argument('--local-ip', default='192.168.104.10',
                       help='本地IP地址 (默认: 192.168.104.10)')
    parser.add_argument('--peer-ip', default='192.168.104.20',
                       help='对方IP地址，用于UDP通信 (默认: 192.168.104.20)')
    parser.add_argument('--log-path', default='./logs',
                       help='日志保存路径 (默认: ./logs)')
    
    # UDP发送端参数
    parser.add_argument('--remote-ip', 
                       help='远程IP地址 (发送端使用，默认为peer-ip)')
    parser.add_argument('--remote-port', type=int, default=20001,
                       help='远程端口 (默认: 20001)')
    parser.add_argument('--local-port', type=int, default=20002,
                       help='本地端口 (默认: 20002)')
    parser.add_argument('--packet-size', type=int, default=1000,
                       help='数据包大小(字节) (默认: 1000)')
    parser.add_argument('--frequency', type=float, default=10.0,
                       help='发送频率(Hz) (默认: 10.0)')
    parser.add_argument('--running-time', type=int, default=60,
                       help='运行时间(秒) (默认: 60)')
    
    # UDP网络错误处理参数 🆕
    parser.add_argument('--network-retry-delay', type=float, default=1.0,
                       help='网络错误重试延迟(秒) (默认: 1.0)')
    parser.add_argument('--log-network-errors', type=bool, default=True,
                       help='是否记录网络错误到日志 (默认: True)')

    # UDP接收端参数
    parser.add_argument('--buffer-size', type=int, default=1500,
                       help='缓冲区大小(字节) (默认: 1500)')
    
    # GPS记录参数
    parser.add_argument('--enable-gps', action='store_true',
                       help='启用GPS数据记录')
    parser.add_argument('--drone-id', default='drone0',
                       help='无人机命名空间 (默认: drone0)')
    parser.add_argument('--gps-interval', type=float, default=1.0,
                       help='GPS记录间隔(秒) (默认: 1.0)')
    parser.add_argument('--use-sim-time', action='store_true',
                       help='使用仿真时间')
    
    # Nexfi通信状态记录参数
    parser.add_argument('--enable-nexfi', action='store_true',
                       help='启用Nexfi通信状态记录')
    parser.add_argument('--nexfi-ip', default='192.168.104.1',
                       help='Nexfi服务器IP地址 (默认: 192.168.104.1)')
    parser.add_argument('--nexfi-username', default='root',
                       help='Nexfi服务器用户名 (默认: root)')
    parser.add_argument('--nexfi-password', default='nexfi',
                       help='Nexfi服务器密码 (默认: nexfi)')
    parser.add_argument('--nexfi-interval', type=float, default=1.0,
                       help='Nexfi记录间隔(秒) (默认: 1.0)')
    parser.add_argument('--nexfi-device', default='adhoc0',
                       help='Nexfi设备名称 (默认: adhoc0)')
    
    # NTP时间同步参数
    parser.add_argument('--skip-ntp', action='store_true',
                       help='完全跳过NTP时间同步功能')
    parser.add_argument('--ntp-peer-ip', 
                       help='NTP对时的对方IP地址 (默认使用--peer-ip的值)')
    parser.add_argument('--skip-ntp-config', action='store_true',
                       help='跳过chrony配置，使用现有配置')
    
    args = parser.parse_args()
    
    # 构建配置
    config = {
        'mode': args.mode,
        'local_ip': args.local_ip,
        'peer_ip': args.peer_ip,
        'log_path': args.log_path,
        'remote_ip': args.remote_ip or args.peer_ip,
        'remote_port': args.remote_port,
        'local_port': args.local_port if args.mode == 'sender' else args.remote_port,
        'packet_size': args.packet_size,
        'frequency': args.frequency,
        'running_time': args.running_time,
        'buffer_size': args.buffer_size,
        'enable_gps': args.enable_gps,
        'drone_id': args.drone_id,
        'gps_interval': args.gps_interval,
        'use_sim_time': args.use_sim_time,
        'enable_nexfi': args.enable_nexfi,
        'nexfi_ip': args.nexfi_ip,
        'nexfi_username': args.nexfi_username,
        'nexfi_password': args.nexfi_password,
        'nexfi_interval': args.nexfi_interval,
        'nexfi_device': args.nexfi_device,
        'enable_ntp': not args.skip_ntp,  # 默认启用NTP，除非明确跳过
        'ntp_peer_ip': args.ntp_peer_ip or args.peer_ip,  # 默认使用peer_ip
        'skip_ntp_config': args.skip_ntp_config,
        'network_retry_delay': args.network_retry_delay,
        'log_network_errors': args.log_network_errors,
    }
    
    # 调整接收端的端口配置
    if args.mode == 'receiver':
        config['local_port'] = args.remote_port  # 接收端监听remote_port
    
    # 创建并运行测试管理器
    test_manager = UDPTestManager(config)
    success = test_manager.run_test()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 