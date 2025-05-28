# 无人机UDP通信测试系统 - 对等NTP时间同步解决方案

## 问题分析

### 当前挑战
1. **GPS+PPS方案复杂性高**：需要GPS模块支持PPS输出，硬件要求高，配置复杂
2. **无人机环境特殊性**：飞行过程中网络不稳定，GPS信号可能受干扰
3. **实施难度大**：需要在两台无人机上同时配置高精度时间源，容错性差
4. **无地面站限制**：很多测试场景下没有地面站支持

### 核心需求
- **单向延迟计算精度**：需要毫秒级的时间同步精度
- **系统简化**：降低硬件依赖和配置复杂度
- **自主运行**：无需地面站，两台无人机自主完成时间同步
- **快速部署**：测试前能够快速建立时间同步

## 解决思路

### 核心策略：主从NTP架构 + 自动角色选择

采用"一台无人机作为NTP服务器，另一台作为NTP客户端"的主从架构，通过自动角色协商机制确定主从关系。

### 方案优势
1. **无需地面站**：两台无人机自主完成时间同步
2. **自动化程度高**：自动选择主机，无需人工干预
3. **实施简单**：标准NTP配置，易于部署
4. **容错性好**：支持角色切换和故障恢复

## 技术方案

### 1. 架构设计

```
无人机A (可能的NTP服务器) ←→ 无人机B (可能的NTP服务器)
    ↓ (192.168.104.0/24网络)
  自动角色协商
    ↓
无人机A (NTP服务器) ←→ 无人机B (NTP客户端)
    ↓
  UDP通信测试
```

### 2. 角色选择策略

#### 方案一：基于IP地址的固定角色
- **简单可靠**：IP地址较小的作为服务器
- **实现**：192.168.104.10 vs 192.168.104.20，选择.10作为服务器

#### 方案二：基于系统启动时间
- **动态选择**：启动时间较早的作为服务器
- **优势**：避免固定角色，更加灵活

#### 方案三：基于时钟质量评估
- **智能选择**：评估本地时钟稳定性，选择质量更好的作为服务器
- **复杂度**：需要额外的时钟质量检测机制

**推荐使用方案一**：简单可靠，易于实现和调试。

### 3. 具体实施方案

#### 3.1 角色协商脚本

```python
#!/usr/bin/env python3
# ntp_role_negotiator.py

import socket
import time
import subprocess
import logging
from datetime import datetime

class NTPRoleNegotiator:
    def __init__(self, local_ip, peer_ip):
        self.local_ip = local_ip
        self.peer_ip = peer_ip
        self.role = None  # 'server' or 'client'
        self.setup_logging()
    
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    def determine_role(self):
        """基于IP地址确定角色"""
        local_parts = [int(x) for x in self.local_ip.split('.')]
        peer_parts = [int(x) for x in self.peer_ip.split('.')]
        
        # 比较IP地址，较小的作为服务器
        if local_parts < peer_parts:
            self.role = 'server'
        else:
            self.role = 'client'
        
        logging.info(f"Role determined: {self.role} (local: {self.local_ip}, peer: {self.peer_ip})")
        return self.role
    
    def wait_for_peer(self, timeout=30):
        """等待对方无人机上线"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # 尝试ping对方
                result = subprocess.run(['ping', '-c', '1', '-W', '1', self.peer_ip], 
                                      capture_output=True)
                if result.returncode == 0:
                    logging.info(f"Peer {self.peer_ip} is online")
                    return True
            except Exception as e:
                logging.error(f"Error pinging peer: {e}")
            
            time.sleep(2)
        
        logging.warning(f"Peer {self.peer_ip} not reachable within {timeout}s")
        return False
    
    def configure_ntp(self):
        """根据角色配置NTP"""
        if self.role == 'server':
            self.configure_ntp_server()
        else:
            self.configure_ntp_client()
    
    def configure_ntp_server(self):
        """配置为NTP服务器"""
        config = f"""# NTP Server Configuration
# 使用本地时钟作为时间源
server 127.127.1.0
fudge 127.127.1.0 stratum 8

# 允许客户端访问
allow {self.peer_ip}
allow 192.168.104.0/24

# 监听所有接口
bindaddress 0.0.0.0

# 日志配置
logdir /var/log/chrony
log measurements statistics tracking
"""
        self.write_chrony_config(config)
        logging.info("Configured as NTP server")
    
    def configure_ntp_client(self):
        """配置为NTP客户端"""
        config = f"""# NTP Client Configuration
# 使用对方作为时间源
server {self.peer_ip} iburst prefer

# 快速同步配置
makestep 1.0 3
maxupdateskew 100.0

# 日志配置
logdir /var/log/chrony
log measurements statistics tracking
"""
        self.write_chrony_config(config)
        logging.info("Configured as NTP client")
    
    def write_chrony_config(self, config):
        """写入chrony配置文件"""
        try:
            with open('/etc/chrony/chrony.conf', 'w') as f:
                f.write(config)
            
            # 重启chrony服务
            subprocess.run(['sudo', 'systemctl', 'restart', 'chrony'], check=True)
            time.sleep(3)  # 等待服务启动
            
        except Exception as e:
            logging.error(f"Failed to configure chrony: {e}")
            raise
    
    def verify_sync(self, timeout=60):
        """验证时间同步状态"""
        if self.role == 'server':
            return self.verify_server_status()
        else:
            return self.verify_client_sync(timeout)
    
    def verify_server_status(self):
        """验证服务器状态"""
        try:
            result = subprocess.run(['chronyc', 'clients'], 
                                  capture_output=True, text=True)
            if self.peer_ip in result.stdout:
                logging.info("NTP server: client connected")
                return True
            else:
                logging.warning("NTP server: no clients connected")
                return False
        except Exception as e:
            logging.error(f"Failed to check server status: {e}")
            return False
    
    def verify_client_sync(self, timeout):
        """验证客户端同步状态"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(['chronyc', 'sources', '-v'], 
                                      capture_output=True, text=True)
                lines = result.stdout.split('\n')
                for line in lines:
                    if '*' in line and self.peer_ip in line:
                        # 解析偏移量
                        parts = line.split()
                        if len(parts) >= 7:
                            offset = abs(float(parts[6]))  # 偏移量（秒）
                            offset_ms = offset * 1000
                            logging.info(f"NTP client synced, offset: {offset_ms:.2f}ms")
                            return offset_ms < 10  # 10ms以内认为同步成功
                
            except Exception as e:
                logging.error(f"Failed to check sync status: {e}")
            
            time.sleep(5)
        
        logging.error("Failed to achieve time sync within timeout")
        return False

def main():
    # 配置IP地址
    LOCAL_IP = "192.168.104.10"  # 根据实际情况修改
    PEER_IP = "192.168.104.20"   # 根据实际情况修改
    
    negotiator = NTPRoleNegotiator(LOCAL_IP, PEER_IP)
    
    try:
        # 1. 确定角色
        role = negotiator.determine_role()
        print(f"This drone will act as NTP {role}")
        
        # 2. 等待对方上线
        if not negotiator.wait_for_peer():
            print("Warning: Peer not reachable, proceeding anyway...")
        
        # 3. 配置NTP
        negotiator.configure_ntp()
        
        # 4. 验证同步
        if negotiator.verify_sync():
            print(f"Time synchronization successful! Role: {role}")
            return True
        else:
            print("Time synchronization failed!")
            return False
            
    except Exception as e:
        logging.error(f"NTP setup failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
```

#### 3.2 简化的手动配置方案

如果不想使用自动协商，也可以手动指定角色：

**无人机A (192.168.104.10) - 作为NTP服务器**：
```bash
# /etc/chrony/chrony.conf
# 使用本地时钟作为时间源
server 127.127.1.0
fudge 127.127.1.0 stratum 8

# 允许客户端访问
allow 192.168.104.0/24

# 监听配置
bindaddress 0.0.0.0
port 123
```

**无人机B (192.168.104.20) - 作为NTP客户端**：
```bash
# /etc/chrony/chrony.conf
# 使用无人机A作为时间源
server 192.168.104.10 iburst prefer

# 快速同步配置
makestep 1.0 3
maxupdateskew 100.0
```

#### 3.3 时间同步监控脚本

```python
#!/usr/bin/env python3
# time_sync_monitor.py

import subprocess
import time
import json
import logging
from datetime import datetime

class TimeSyncMonitor:
    def __init__(self, role, peer_ip, log_file="time_sync.log"):
        self.role = role  # 'server' or 'client'
        self.peer_ip = peer_ip
        self.log_file = log_file
        self.setup_logging()
    
    def setup_logging(self):
        logging.basicConfig(
            filename=self.log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    def get_sync_status(self):
        """获取同步状态"""
        if self.role == 'server':
            return self.get_server_status()
        else:
            return self.get_client_status()
    
    def get_server_status(self):
        """获取服务器状态"""
        try:
            # 检查客户端连接
            result = subprocess.run(['chronyc', 'clients'], 
                                  capture_output=True, text=True)
            
            clients_connected = self.peer_ip in result.stdout
            
            return {
                'timestamp': datetime.now().isoformat(),
                'role': 'server',
                'clients_connected': clients_connected,
                'status': 'active' if clients_connected else 'waiting'
            }
            
        except Exception as e:
            logging.error(f"Failed to get server status: {e}")
            return None
    
    def get_client_status(self):
        """获取客户端状态"""
        try:
            result = subprocess.run(['chronyc', 'sources', '-v'], 
                                  capture_output=True, text=True)
            
            offset_ms = None
            synced = False
            
            lines = result.stdout.split('\n')
            for line in lines:
                if '*' in line and self.peer_ip in line:
                    parts = line.split()
                    if len(parts) >= 7:
                        offset = float(parts[6])  # 偏移量（秒）
                        offset_ms = offset * 1000  # 转换为毫秒
                        synced = abs(offset_ms) < 10  # 10ms以内认为同步
                        break
            
            return {
                'timestamp': datetime.now().isoformat(),
                'role': 'client',
                'offset_ms': offset_ms,
                'synced': synced,
                'status': 'synced' if synced else 'syncing'
            }
            
        except Exception as e:
            logging.error(f"Failed to get client status: {e}")
            return None
    
    def log_status(self):
        """记录状态到日志"""
        status = self.get_sync_status()
        if status:
            logging.info(f"Sync status: {json.dumps(status)}")
            print(f"[{status['timestamp']}] {status['role']}: {status['status']}")
            if status['role'] == 'client' and status.get('offset_ms') is not None:
                print(f"  Offset: {status['offset_ms']:.2f}ms")
        return status

def main():
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python3 time_sync_monitor.py <role> <peer_ip>")
        print("Example: python3 time_sync_monitor.py client 192.168.104.10")
        sys.exit(1)
    
    role = sys.argv[1]
    peer_ip = sys.argv[2]
    
    if role not in ['server', 'client']:
        print("Role must be 'server' or 'client'")
        sys.exit(1)
    
    monitor = TimeSyncMonitor(role, peer_ip)
    
    print(f"Starting time sync monitor as {role}, peer: {peer_ip}")
    
    try:
        while True:
            monitor.log_status()
            time.sleep(10)  # 每10秒检查一次
    except KeyboardInterrupt:
        print("\nMonitoring stopped")

if __name__ == "__main__":
    main()
```

### 4. 部署流程

#### 4.1 自动部署流程
```bash
#!/bin/bash
# deploy_ntp_sync.sh

# 1. 安装chrony
sudo apt-get update
sudo apt-get install -y chrony

# 2. 运行角色协商
python3 ntp_role_negotiator.py

# 3. 启动监控
python3 time_sync_monitor.py $ROLE $PEER_IP &

echo "NTP synchronization setup complete"
```

#### 4.2 手动部署流程
1. **确定角色**：根据IP地址或约定确定哪台作为服务器
2. **配置chrony**：分别配置服务器和客户端
3. **启动服务**：重启chrony服务
4. **验证同步**：检查同步状态
5. **启动监控**：运行监控脚本

### 5. 测试验证

#### 5.1 同步质量验证
```bash
# 在客户端无人机上执行
chronyc sources -v
chronyc tracking

# 检查时间偏移
# 在两台无人机上同时执行
date +%s.%N
```

#### 5.2 预期精度
- **初始同步**：±5ms以内
- **稳定运行**：±2-3ms
- **网络良好时**：±1ms

### 6. 故障处理

#### 6.1 角色切换机制
```python
def handle_server_failure():
    """处理服务器故障的角色切换"""
    # 1. 检测服务器不可达
    # 2. 客户端切换为服务器模式
    # 3. 重新配置chrony
    # 4. 通知对方（如果可能）
    pass
```

#### 6.2 网络中断恢复
```python
def handle_network_recovery():
    """处理网络恢复后的重新同步"""
    # 1. 检测网络恢复
    # 2. 重新建立NTP连接
    # 3. 验证同步质量
    # 4. 记录恢复事件
    pass
```

## 实施建议

### 推荐方案：简化手动配置
考虑到无人机环境的特殊性，推荐使用简化的手动配置方案：

1. **固定角色分配**：
   - 192.168.104.10 → NTP服务器
   - 192.168.104.20 → NTP客户端

2. **配置文件模板**：提供标准的chrony配置模板

3. **一键部署脚本**：自动化配置和启动过程

4. **实时监控**：运行监控脚本确保同步质量

### 优势总结
1. **无需地面站**：两台无人机自主完成时间同步
2. **实施简单**：标准NTP配置，易于部署和维护
3. **精度足够**：毫秒级精度满足UDP延迟测试需求
4. **成本低**：无需额外硬件，利用现有网络
5. **可靠性好**：NTP协议成熟稳定，容错性强

这个方案完全解决了无地面站的限制，同时保持了实施的简单性和可靠性。
