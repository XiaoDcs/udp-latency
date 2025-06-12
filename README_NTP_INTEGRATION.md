# 无人机UDP通信测试系统 - 集成NTP时间同步

## 📋 最新功能更新 (v2.2) 🆕

### 🎛️ 灵活的NTP配置选项
- **可选NTP对时**: 新增 `--skip-ntp` 参数，可完全跳过NTP时间同步功能
- **独立NTP IP**: 新增 `--ntp-peer-ip` 参数，支持NTP对时IP与UDP通信IP分离
- **默认行为**: 默认启用NTP对时，向下兼容现有配置
- **使用场景**: 适合已有精确时间源的环境或测试纯UDP性能的场景

### 🔧 时间同步验证修复
- **修复问题**: 解决了chrony复合偏移量格式解析错误，如 `-3069ns[+1489us]` 格式
- **改进算法**: 重写偏移量解析逻辑，支持 `ns`, `us`, `ms`, `s` 等多种时间单位
- **提升稳定性**: 客户端现在能正确识别同步状态，不再卡在验证阶段
- **详细输出**: 增加时间同步过程的详细信息显示

### 🗑️ 移除RSSI模拟值
- **清理代码**: 移除了UDP发送端和接收端的模拟RSSI值
- **简化日志**: 日志文件不再包含无意义的固定RSSI值
- **提升性能**: 减少不必要的数据处理和存储

### 🛠️ 新增配置选项
- **跳过配置**: 新增 `--skip-ntp-config` 选项，可跳过chrony重新配置
- **权限检查**: 自动检查sudo权限，提供友好的用户提示
- **错误处理**: 改进错误处理机制，提供更清晰的故障诊断信息

---

## 🚀 快速开始 (拉取仓库后必读)

### 1. 克隆仓库后的第一步

```bash
# 1. 克隆仓库到本地
git clone <repository-url>
cd udp-latency

# 2. 运行一键部署脚本
chmod +x setup.sh
./setup.sh
```

**setup.sh 会自动完成以下操作：**
- ✅ 检查系统要求 (Linux + Python3)
- ✅ 安装系统依赖 (chrony, 网络工具等)
- ✅ 创建Python虚拟环境
- ✅ 安装Python依赖包
- ✅ 设置文件权限
- ✅ 创建必要目录
- ✅ 验证安装

### 2. 部署完成后的操作

```bash
# 激活Python虚拟环境
source venv/bin/activate

# 查看使用示例
./example_usage.sh

# 运行环境检查（可选）
./check_environment.sh
```

### 3. 立即开始测试

#### 基本测试（包含NTP时间同步）

**在第一台无人机上（发送端）：**
```bash
source venv/bin/activate
./start_test.sh sender
```

**在第二台无人机上（接收端）：**
```bash
source venv/bin/activate
./start_test.sh receiver
```

#### 跳过NTP时间同步的纯UDP测试

**在第一台无人机上（发送端）：**
```bash
source venv/bin/activate
./start_test.sh sender --skip-ntp
```

**在第二台无人机上（接收端）：**
```bash
source venv/bin/activate
./start_test.sh receiver --skip-ntp
```

#### 使用独立的NTP对时IP

**场景**: UDP通信使用192.168.104.x网段，NTP对时使用192.168.1.x网段

**在第一台无人机上（发送端）：**
```bash
source venv/bin/activate
./start_test.sh sender --peer-ip=192.168.104.20 --ntp-peer-ip=192.168.1.20
```

**在第二台无人机上（接收端）：**
```bash
source venv/bin/activate
./start_test.sh receiver --peer-ip=192.168.104.10 --ntp-peer-ip=192.168.1.10
```

### 4. 如需GPS记录功能

GPS记录功能需要ROS2环境，请单独安装：
```bash
# 安装ROS2 (以Humble为例)
sudo apt update
sudo apt install ros-humble-desktop

# Source ROS2环境
source /opt/ros/humble/setup.bash

# 安装as2_python_api (根据您的具体环境)
# 具体安装方法请参考您的无人机系统文档
```

---

## 概述

这是一个完整的无人机UDP通信测试系统，集成了自动NTP时间同步功能和GPS数据记录。系统能够自动在两台无人机之间建立时间同步，然后进行UDP通信性能测试，同时记录GPS位置信息，包括延迟、丢包率、位置轨迹等指标的测量。

## 主要特性

- ✅ **一键部署**: 运行setup.sh即可完成环境配置
- ✅ **灵活的NTP配置**: 支持启用/禁用NTP对时，支持独立NTP对时IP 🆕
- ✅ **自动时间同步**: 基于IP地址自动确定NTP服务器/客户端角色
- ✅ **无需地面站**: 两台无人机自主完成时间同步
- ✅ **一键启动**: 简化的启动脚本，自动化整个测试流程
- ✅ **GPS数据记录**: 集成GPS位置记录，支持ROS2环境
- ✅ **Nexfi通信状态记录**: 实时记录通信模块状态和链路质量
- ✅ **实时监控**: 持续监控时间同步状态和系统状态
- ✅ **完整日志**: 详细的测试日志、GPS轨迹、通信状态和同步状态记录
- ✅ **故障处理**: 自动处理网络中断和同步异常

## 系统架构

### 标准模式（启用NTP对时）
```
无人机A (192.168.104.10)          无人机B (192.168.104.20)
    ↓                                    ↓
自动成为NTP服务器              ←→    自动成为NTP客户端
    ↓                                    ↓
启动GPS记录器                  ←→    启动GPS记录器
    ↓                                    ↓
启动Nexfi状态记录器            ←→    启动Nexfi状态记录器
    ↓                                    ↓
运行UDP发送端/接收端           ←→    运行UDP接收端/发送端
    ↓                                    ↓
记录测试日志和GPS轨迹          ←→    记录测试日志和GPS轨迹
```

### 分离模式（NTP对时IP与通信IP不同）🆕
```
无人机A                               无人机B
├─ UDP通信: 192.168.104.10      ←→    ├─ UDP通信: 192.168.104.20
└─ NTP对时: 192.168.1.10        ←→    └─ NTP对时: 192.168.1.20
```

### 纯UDP模式（跳过NTP对时）🆕
```
无人机A (192.168.104.10)          无人机B (192.168.104.20)
    ↓                                    ↓
跳过NTP时间同步                ←→    跳过NTP时间同步
    ↓                                    ↓
直接启动GPS记录器              ←→    直接启动GPS记录器
    ↓                                    ↓
运行UDP发送端/接收端           ←→    运行UDP接收端/发送端
```

## 文件结构

```
udp-latency/
├── setup.sh                   # 一键部署脚本 ⭐
├── requirements.txt            # Python依赖包
├── start_test.sh              # 测试启动脚本 ⭐
├── udp_test_with_ntp.py       # 主测试程序
├── udp_sender.py              # UDP发送端
├── udp_receiver.py            # UDP接收端
├── gps.py                     # GPS数据记录器
├── nexfi_client.py            # Nexfi通信状态记录器 ⭐
├── example_usage.sh           # 使用示例
├── check_environment.sh       # 环境检查脚本
├── README_NTP_INTEGRATION.md  # 本文档
├── venv/                      # Python虚拟环境 (setup.sh创建)
├── logs/                      # 测试日志目录 (自动创建)
└── backups/                   # 备份目录 (自动创建)
```

## 环境要求

### 基本要求 (setup.sh会自动安装)
- Ubuntu 18.04+ 系统
- Python 3.6+ 
- 网络连通性 (192.168.104.0/24 网段)
- sudo 权限 (用于配置NTP)

### GPS记录额外要求 (需手动安装)
- ROS2 环境 (Humble/Galactic/Foxy)
- as2_python_api 包
- 无人机GPS接口正常工作

### Nexfi通信状态记录额外要求 (setup.sh会自动安装)
- requests 库 (HTTP请求)
- Nexfi通信模块设备 (可选，无设备时使用模拟数据)
- 网络连接到Nexfi设备 (通常为192.168.104.1)

## 详细使用说明

### 文件部署

如果您没有使用setup.sh自动部署，可以手动将以下文件部署到两台无人机的相同目录：
```
udp_test_with_ntp.py    # 主测试脚本
start_test.sh           # 启动脚本
udp_sender.py          # UDP发送端
udp_receiver.py        # UDP接收端
gps.py                 # GPS数据记录器
```

### 运行测试

#### 基本测试（默认启用NTP对时）

**无人机A (192.168.104.10) - 发送端**
```bash
source venv/bin/activate
./start_test.sh sender --local-ip=192.168.104.10 --peer-ip=192.168.104.20
```

**无人机B (192.168.104.20) - 接收端**
```bash
source venv/bin/activate
./start_test.sh receiver --local-ip=192.168.104.20 --peer-ip=192.168.104.10
```

#### 跳过NTP对时的纯UDP测试 🆕

**使用场景**: 
- 已有其他时间同步机制
- 测试纯UDP性能，不需要精确时间同步
- 临时测试或故障排除

**无人机A (192.168.104.10) - 发送端**
```bash
source venv/bin/activate
./start_test.sh sender --local-ip=192.168.104.10 --peer-ip=192.168.104.20 --skip-ntp
```

**无人机B (192.168.104.20) - 接收端**
```bash
source venv/bin/activate
./start_test.sh receiver --local-ip=192.168.104.20 --peer-ip=192.168.104.10 --skip-ntp
```

#### 使用独立NTP对时IP 🆕

**使用场景**:
- UDP通信网络与管理网络分离
- 多网卡环境，不同网卡承担不同功能
- 网络安全要求，时间同步使用专用网络

**无人机A - 发送端**
```bash
source venv/bin/activate
./start_test.sh sender \
  --local-ip=192.168.104.10 \
  --peer-ip=192.168.104.20 \
  --ntp-peer-ip=192.168.1.20
```

**无人机B - 接收端**
```bash
source venv/bin/activate
./start_test.sh receiver \
  --local-ip=192.168.104.20 \
  --peer-ip=192.168.104.10 \
  --ntp-peer-ip=192.168.1.10
```

#### 完整测试（含GPS记录）

**无人机A (192.168.104.10) - 发送端**
```bash
source venv/bin/activate
./start_test.sh sender --local-ip=192.168.104.10 --peer-ip=192.168.104.20 --enable-gps --drone-id=drone0
```

**无人机B (192.168.104.20) - 接收端**
```bash
source venv/bin/activate
./start_test.sh receiver --local-ip=192.168.104.20 --peer-ip=192.168.104.10 --enable-gps --drone-id=drone1
```

#### 完整测试（含Nexfi通信状态记录）

**无人机A (192.168.104.10) - 发送端**
```bash
source venv/bin/activate
./start_test.sh sender --local-ip=192.168.104.10 --peer-ip=192.168.104.20 --enable-nexfi --nexfi-ip=192.168.104.1
```

**无人机B (192.168.104.20) - 接收端**
```bash
source venv/bin/activate
./start_test.sh receiver --local-ip=192.168.104.20 --peer-ip=192.168.104.10 --enable-nexfi --nexfi-ip=192.168.104.1
```

#### 全功能测试（GPS + Nexfi + UDP，跳过NTP）🆕

**场景**: 在已有精确时间同步的环境中进行全功能测试

**无人机A (192.168.104.10) - 发送端**
```bash
source venv/bin/activate
./start_test.sh sender \
  --local-ip=192.168.104.10 \
  --peer-ip=192.168.104.20 \
  --enable-gps \
  --drone-id=drone0 \
  --enable-nexfi \
  --nexfi-ip=192.168.104.1 \
  --time=300 \
  --skip-ntp
```

**无人机B (192.168.104.20) - 接收端**
```bash
source venv/bin/activate
./start_test.sh receiver \
  --local-ip=192.168.104.20 \
  --peer-ip=192.168.104.10 \
  --enable-gps \
  --drone-id=drone1 \
  --enable-nexfi \
  --nexfi-ip=192.168.104.1 \
  --time=300 \
  --skip-ntp
```

#### 高级配置示例 🆕

**复杂网络环境配置**:
```bash
source venv/bin/activate
./start_test.sh sender \
  --local-ip=192.168.104.10 \         # UDP通信IP
  --peer-ip=192.168.104.20 \          # UDP通信对方IP
  --ntp-peer-ip=10.0.0.20 \          # NTP对时专用IP
  --enable-gps \
  --drone-id=drone_alpha \
  --enable-nexfi \
  --nexfi-ip=172.16.1.1 \            # Nexfi管理IP
  --time=600 \
  --frequency=20 \
  --packet-size=1400
```

## 新增命令行参数详解 🆕

### NTP相关参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--skip-ntp` | flag | false | 完全跳过NTP时间同步功能 |
| `--ntp-peer-ip` | string | 使用--peer-ip的值 | NTP对时的对方IP地址 |
| `--skip-ntp-config` | flag | false | 跳过chrony配置，使用现有配置 |

### 使用场景说明

#### 何时使用 `--skip-ntp`
- ✅ 系统已有其他时间同步机制（如GPS时钟、PTP等）
- ✅ 测试纯UDP性能，不关心时间戳精度
- ✅ 临时测试或故障排除
- ✅ 不具备sudo权限配置chrony
- ❌ 需要精确测量网络延迟时

#### 何时使用 `--ntp-peer-ip`
- ✅ 多网卡环境，管理网络与数据网络分离
- ✅ 安全要求，时间同步使用专用安全网络
- ✅ 网络拓扑复杂，最优路由不同
- ✅ 带宽管理，避免NTP流量影响数据传输

## 日志文件说明

测试完成后，会在指定的日志目录生成以下文件：

### NTP同步日志
- `ntp_sync_YYYYMMDD_HHMMSS.log`: NTP同步过程日志
- `system_monitor.jsonl`: 系统状态监控日志 (JSON Lines格式)

### UDP测试日志
- `udp_sender_YYYYMMDD_HHMMSS.csv`: 发送端日志
- `udp_receiver_YYYYMMDD_HHMMSS.csv`: 接收端日志
- `udp_test_YYYYMMDD_HHMMSS.log`: 测试过程日志

### GPS记录日志
- `gps_logger_[drone_id]_YYYYMMDD_HHMMSS.csv`: GPS位置和状态日志

### Nexfi通信状态日志
- `nexfi_status_YYYYMMDD_HHMMSS.csv`: Nexfi通信模块状态和链路质量日志

### 日志格式示例

**发送端日志 (CSV)**:
```csv
seq_num,timestamp,packet_size
1,1640995200.123456,200
2,1640995200.223456,200
```

**接收端日志 (CSV)**:
```csv
seq_num,send_timestamp,recv_timestamp,delay,src_ip,src_port,packet_size
1,1640995200.123456,1640995200.125456,0.002,192.168.104.10,20002,200
2,1640995200.223456,1640995200.225456,0.002,192.168.104.10,20002,200
```

**GPS记录日志 (CSV)**:
```csv
timestamp,latitude,longitude,altitude,local_x,local_y,local_z,connected,armed,offboard
1640995200.123456,39.123456,116.123456,100.5,10.2,5.3,2.1,true,true,false
1640995201.123456,39.123457,116.123457,100.6,10.3,5.4,2.2,true,true,false
```

**Nexfi通信状态日志 (CSV)**:
```csv
timestamp,mesh_enabled,channel,frequency_band,tx_power,work_mode,node_id,connected_nodes,avg_rssi,avg_snr,throughput,cpu_usage,memory_usage,uptime,firmware_version,topology_nodes,link_quality
1640995200.123456,True,149,20,20,adhoc,1,2,-65.5,25.3,45.2,15%,42%,2h 30m,v1.0.0,3,180.5
1640995201.123456,True,149,20,20,adhoc,1,2,-66.1,24.8,44.8,16%,43%,2h 30m,v1.0.0,3,179.2
```

**系统监控日志 (JSON Lines)** 🆕:
```json
{"timestamp": "2021-12-31T12:00:00.123456", "ntp_enabled": true, "ntp_role": "client", "ntp_synced": true, "ntp_offset_ms": 2.3, "gps_logger_status": "running", "enable_gps": true, "nexfi_logger_status": "running", "enable_nexfi": true}
{"timestamp": "2021-12-31T12:00:10.123456", "ntp_enabled": true, "ntp_role": "client", "ntp_synced": true, "ntp_offset_ms": 1.8, "gps_logger_status": "running", "enable_gps": true, "nexfi_logger_status": "running", "enable_nexfi": true}
{"timestamp": "2021-12-31T12:00:20.123456", "ntp_enabled": false, "ntp_role": null, "ntp_synced": null, "ntp_offset_ms": null, "gps_logger_status": "running", "enable_gps": true, "nexfi_logger_status": "stopped", "enable_nexfi": false}
```

**系统监控日志字段说明** 🆕:

| 字段名 | 类型 | 说明 |
|--------|------|------|
| timestamp | string | ISO格式时间戳 |
| ntp_enabled | bool | 是否启用NTP时间同步 |
| ntp_role | string/null | NTP角色 ("server"/"client"/null) |
| ntp_synced | bool/null | NTP同步状态 (启用NTP时) |
| ntp_offset_ms | float/null | 时间偏移量毫秒 (启用NTP时) |
| gps_logger_status | string | GPS记录器状态 ("running"/"stopped") |
| enable_gps | bool | 是否启用GPS记录 |
| nexfi_logger_status | string | Nexfi记录器状态 ("running"/"stopped") |
| enable_nexfi | bool | 是否启用Nexfi状态记录 |

## GPS记录功能详解

### GPS数据字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| timestamp | float | Unix时间戳 |
| latitude | float | 纬度 (度) |
| longitude | float | 经度 (度) |
| altitude | float | 海拔高度 (米) |
| local_x | float | 本地坐标X (米) |
| local_y | float | 本地坐标Y (米) |
| local_z | float | 本地坐标Z (米) |
| connected | bool | 无人机连接状态 |
| armed | bool | 无人机解锁状态 |
| offboard | bool | Offboard模式状态 |

### GPS记录器独立使用

GPS记录器也可以独立运行：

```bash
# 基本使用
python3 gps.py --drone-id=drone0 --interval=1.0 --time=300

# 高频记录
python3 gps.py --drone-id=drone1 --interval=0.1 --time=600

# 仿真环境
python3 gps.py --drone-id=drone0 --sim-time --log-path=./sim_logs

# 查看帮助
python3 gps.py --help
```

### ROS2环境配置

确保ROS2环境正确配置：

```bash
# 检查ROS2环境
echo $ROS_DISTRO

# Source ROS2环境
source /opt/ros/humble/setup.bash  # 或其他版本

# 检查as2_python_api
python3 -c "from as2_python_api.drone_interface_gps import DroneInterfaceGPS; print('GPS接口可用')"

# 检查无人机连接
ros2 topic list | grep gps
```

## Nexfi通信状态记录功能详解

### Nexfi数据字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| timestamp | float | Unix时间戳 |
| mesh_enabled | bool | Mesh网络是否启用 |
| channel | str | 无线信道号 |
| frequency_band | str | 频宽 (MHz) |
| tx_power | str | 发射功率 (dBm) |
| work_mode | str | 工作模式 (adhoc/ap/client) |
| node_id | str | 节点ID |
| connected_nodes | int | 连接的节点数量 |
| avg_rssi | float | 平均信号强度 (dBm) |
| avg_snr | float | 平均信噪比 (dB) |
| throughput | str | 吞吐量 (Mbps) |
| cpu_usage | str | CPU使用率 |
| memory_usage | str | 内存使用率 |
| uptime | str | 系统运行时间 |
| firmware_version | str | 固件版本 |
| topology_nodes | int | 拓扑中的节点总数 |
| link_quality | float | 平均链路质量 (0-255) |

### Nexfi记录器独立使用

Nexfi记录器也可以独立运行：

```bash
# 基本使用 - 记录到CSV
python3 nexfi_client.py --nexfi-ip=192.168.104.1 --interval=1.0 --time=300

# 自定义参数
python3 nexfi_client.py --nexfi-ip=192.168.104.1 --username=admin --password=mypass --device=wlan0

# 监控模式 - 实时显示状态
python3 nexfi_client.py --nexfi-ip=192.168.104.1 --monitor=5

# 保存当前状态到JSON
python3 nexfi_client.py --nexfi-ip=192.168.104.1 --save --output=nexfi_snapshot.json

# 查看帮助
python3 nexfi_client.py --help
```

### Nexfi设备连接测试

在使用前可以先测试Nexfi设备连接：

```bash
# 测试HTTP连接
curl http://192.168.104.1

# 使用Python测试
python3 -c "
import requests
try:
    r = requests.get('http://192.168.104.1', timeout=3)
    print('Nexfi设备可达')
except:
    print('Nexfi设备不可达')
"
```

### 模拟数据模式

当无法连接到Nexfi设备时，记录器会自动使用模拟数据继续运行，确保测试不会中断。模拟数据包含合理的默认值，可用于测试和开发。

## 时间同步机制

### 角色分配
- **自动分配**: 基于IP地址，较小的IP自动成为NTP服务器
- **192.168.104.10**: 自动成为NTP服务器
- **192.168.104.20**: 自动成为NTP客户端

### 同步精度
- **初始同步**: ±5ms以内
- **稳定运行**: ±2-3ms
- **网络良好时**: ±1ms

### 监控机制
- 每10秒检查一次同步状态
- 自动记录时间偏移量
- 同步异常时发出警告
- GPS记录器状态监控

## 故障排除

### 常见问题

#### 1. GPS记录器启动失败
**症状**: 显示 "GPS logger failed to start"
**解决方案**:
```bash
# 检查ROS2环境
source /opt/ros/humble/setup.bash

# 检查无人机连接
ros2 topic list | grep drone

# 检查GPS接口
python3 -c "from as2_python_api.drone_interface_gps import DroneInterfaceGPS"

# 手动测试GPS记录器
python3 gps.py --drone-id=drone0 --time=10
```

#### 2. GPS数据全为0
**症状**: GPS坐标显示为 (0.0, 0.0, 0.0)
**解决方案**:
```bash
# 检查GPS话题
ros2 topic echo /drone0/sensor_measurements/gps

# 检查无人机状态
ros2 topic echo /drone0/platform/info

# 等待GPS定位
# GPS需要一定时间获取定位，特别是首次启动
```

#### 3. 时间同步失败
**症状**: 显示 "Time synchronization failed!"
**解决方案**:
```bash
# 检查chrony服务状态
sudo systemctl status chrony

# 手动重启chrony
sudo systemctl restart chrony

# 检查防火墙设置
sudo ufw status
```

#### 4. 对方无人机不可达
**症状**: ping 对方IP失败
**解决方案**:
```bash
# 检查网络配置
ip addr show
ip route show

# 检查网络连接
ping 192.168.104.20

# 检查防火墙
sudo ufw allow from 192.168.104.0/24
```

#### 5. UDP测试失败
**症状**: UDP发送/接收失败
**解决方案**:
```bash
# 检查端口占用
netstat -ulnp | grep 20001

# 检查防火墙端口
sudo ufw allow 20001/udp
sudo ufw allow 20002/udp
```

#### 6. 权限不足
**症状**: 配置chrony时权限错误
**解决方案**:
```bash
# 确保用户有sudo权限
sudo -l

# 或者手动配置chrony
sudo nano /etc/chrony/chrony.conf
```

#### 7. Nexfi状态记录器启动失败
**症状**: 显示 "Nexfi status logger failed to start"
**解决方案**:
```bash
# 检查requests库
pip install requests

# 测试Nexfi连接
python3 nexfi_client.py --nexfi-ip=192.168.104.1 --monitor=1

# 检查网络连接
ping 192.168.104.1

# 手动测试API
curl http://192.168.104.1/ubus
```

#### 8. Nexfi数据获取失败
**症状**: Nexfi日志显示模拟数据
**解决方案**:
```bash
# 检查Nexfi设备状态
# 确保Nexfi设备已开机并正常工作

# 检查防火墙
sudo ufw allow from 192.168.104.1

# 验证登录凭据
# 确保用户名和密码正确

# 使用浏览器访问
# 打开 http://192.168.104.1 查看Web界面
```

### 手动验证时间同步

```bash
# 检查chrony状态
chronyc tracking
chronyc sources -v

# 检查时间偏移
# 在两台无人机上同时执行
date +%s.%N
```

### GPS数据验证

```bash
# 检查GPS日志文件
tail -f ./logs/gps_logger_drone0_*.csv

# 验证GPS数据格式
python3 -c "
import pandas as pd
df = pd.read_csv('./logs/gps_logger_drone0_*.csv')
print(df.head())
print(f'GPS记录数: {len(df)}')
print(f'有效GPS坐标数: {len(df[(df.latitude != 0) | (df.longitude != 0)])}')
"
```

## 性能优化建议

### 网络优化
1. **减少网络延迟**: 使用有线连接或高质量无线链路
2. **QoS设置**: 为NTP和UDP测试流量设置优先级
3. **MTU优化**: 确保数据包大小小于链路MTU

### 系统优化
1. **CPU调度**: 设置实时调度优先级
2. **网络缓冲**: 调整网络缓冲区大小
3. **时钟源**: 使用高质量的系统时钟

### GPS记录优化
1. **记录频率**: 根据需求调整GPS记录间隔
2. **存储空间**: 确保有足够的磁盘空间存储GPS日志
3. **ROS2性能**: 优化ROS2节点通信性能

### 测试参数调优
1. **发送频率**: 根据网络带宽调整发送频率
2. **包大小**: 避免IP分片，保持包大小适中
3. **测试时长**: 足够长的测试时间以获得统计意义

## 数据分析建议

### GPS轨迹分析
```python
import pandas as pd
import matplotlib.pyplot as plt

# 读取GPS数据
df = pd.read_csv('logs/gps_logger_drone0_*.csv')

# 绘制轨迹图
plt.figure(figsize=(10, 8))
plt.plot(df['longitude'], df['latitude'], 'b-', alpha=0.7)
plt.scatter(df['longitude'].iloc[0], df['latitude'].iloc[0], c='green', s=100, label='起点')
plt.scatter(df['longitude'].iloc[-1], df['latitude'].iloc[-1], c='red', s=100, label='终点')
plt.xlabel('经度')
plt.ylabel('纬度')
plt.title('无人机飞行轨迹')
plt.legend()
plt.grid(True)
plt.show()
```

### 通信质量分析
```python
# 结合GPS和UDP数据分析通信质量与位置的关系
gps_df = pd.read_csv('logs/gps_logger_drone0_*.csv')
udp_df = pd.read_csv('logs/udp_receiver_*.csv')

# 时间对齐和分析
# ... 分析代码
```

### Nexfi通信状态分析
```python
import pandas as pd
import matplotlib.pyplot as plt

# 读取Nexfi状态数据
nexfi_df = pd.read_csv('logs/nexfi_status_*.csv')

# 绘制信号强度和信噪比变化
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

# RSSI变化图
ax1.plot(nexfi_df['timestamp'], nexfi_df['avg_rssi'], 'b-')
ax1.set_ylabel('RSSI (dBm)')
ax1.set_title('信号强度变化')
ax1.grid(True)

# SNR变化图
ax2.plot(nexfi_df['timestamp'], nexfi_df['avg_snr'], 'g-')
ax2.set_ylabel('SNR (dB)')
ax2.set_xlabel('时间戳')
ax2.set_title('信噪比变化')
ax2.grid(True)

plt.tight_layout()
plt.show()

# 分析连接稳定性
print(f"平均连接节点数: {nexfi_df['connected_nodes'].mean():.2f}")
print(f"平均RSSI: {nexfi_df['avg_rssi'].mean():.2f} dBm")
print(f"平均SNR: {nexfi_df['avg_snr'].mean():.2f} dB")
print(f"平均链路质量: {nexfi_df['link_quality'].mean():.2f}")
```

### 综合分析示例
```python
# 结合UDP延迟、GPS位置和Nexfi状态进行综合分析
import pandas as pd
import numpy as np

# 读取所有数据
udp_df = pd.read_csv('logs/udp_receiver_*.csv')
gps_df = pd.read_csv('logs/gps_logger_*.csv')
nexfi_df = pd.read_csv('logs/nexfi_status_*.csv')

# 时间对齐（使用最近邻匹配）
def align_data(df1, df2, time_col='timestamp'):
    merged = pd.merge_asof(
        df1.sort_values(time_col),
        df2.sort_values(time_col),
        on=time_col,
        direction='nearest',
        tolerance=1.0  # 1秒容差
    )
    return merged

# 合并数据
combined = align_data(udp_df, gps_df)
combined = align_data(combined, nexfi_df)

# 分析延迟与信号质量的关系
correlation = combined[['delay', 'avg_rssi', 'avg_snr']].corr()
print("延迟与信号质量相关性:")
print(correlation)
```

## 注意事项

1. **sudo权限**: 配置NTP需要sudo权限（使用--skip-ntp时不需要）🆕
2. **网络稳定**: 确保测试期间网络连接稳定
3. **时间同步**: 测试前确保时间同步成功（启用NTP时）🆕
4. **防火墙**: 确保相关端口未被防火墙阻止
5. **系统负载**: 避免在高负载时进行测试
6. **ROS2环境**: GPS记录需要正确配置的ROS2环境
7. **GPS信号**: 确保GPS信号良好，特别是在室外环境
8. **存储空间**: 确保有足够空间存储日志文件
9. **Nexfi设备**: 确保Nexfi设备正常工作并可访问
10. **网络权限**: Nexfi API访问需要正确的用户名和密码
11. **多网卡环境**: 使用--ntp-peer-ip时确保NTP网络路由正确 🆕

## 新功能测试示例 🆕

### 测试场景1: 跳过NTP对时的快速UDP测试

**适用情况**: 系统已有其他时间同步机制，或只需测试UDP性能

```bash
# 无人机A - 发送端
source venv/bin/activate
./start_test.sh sender --skip-ntp --time=120 --frequency=20 --packet-size=1400

# 无人机B - 接收端
source venv/bin/activate
./start_test.sh receiver --skip-ntp --time=120
```

**预期结果**: 
- 跳过所有NTP配置步骤
- 直接开始UDP通信测试
- 系统监控日志中 `ntp_enabled` 为 `false`

### 测试场景2: 双网卡环境（管理网络+数据网络）

**网络配置**:
- 管理网络: 192.168.1.x (用于NTP时间同步)
- 数据网络: 192.168.104.x (用于UDP通信)

```bash
# 无人机A - 发送端
source venv/bin/activate
./start_test.sh sender \
  --local-ip=192.168.104.10 \
  --peer-ip=192.168.104.20 \
  --ntp-peer-ip=192.168.1.20 \
  --time=300

# 无人机B - 接收端
source venv/bin/activate
./start_test.sh receiver \
  --local-ip=192.168.104.20 \
  --peer-ip=192.168.104.10 \
  --ntp-peer-ip=192.168.1.10 \
  --time=300
```

**预期结果**:
- NTP同步通过192.168.1.x网络
- UDP通信通过192.168.104.x网络
- 两个网络可以独立优化和管理

### 测试场景3: 验证NTP参数功能

**步骤1**: 运行标准NTP同步测试
```bash
# 记录标准模式的时间偏移量
./start_test.sh sender --time=60 > standard_ntp.log 2>&1
```

**步骤2**: 运行跳过NTP的测试
```bash
# 记录跳过NTP模式的性能
./start_test.sh sender --skip-ntp --time=60 > skip_ntp.log 2>&1
```

**步骤3**: 比较结果
```bash
# 查看NTP状态差异
grep "NTP" standard_ntp.log skip_ntp.log
grep "跳过" standard_ntp.log skip_ntp.log

# 检查系统监控日志差异
tail -5 logs/system_monitor.jsonl | jq '.ntp_enabled'
```

### 测试场景4: 故障排除模式

**模拟网络问题时的测试**:
```bash
# 在网络不稳定时使用跳过NTP模式继续测试
./start_test.sh sender --skip-ntp --enable-gps --time=180

# 或者使用备用网络进行NTP同步
./start_test.sh sender \
  --peer-ip=192.168.104.20 \
  --ntp-peer-ip=10.0.0.20 \
  --time=180
```

### 验证新功能的检查清单

#### ✅ 测试 `--skip-ntp` 参数
- [ ] 确认跳过了所有NTP配置步骤
- [ ] 确认系统监控日志中 `ntp_enabled` 为 `false`
- [ ] 确认UDP测试正常进行
- [ ] 确认不需要sudo权限

#### ✅ 测试 `--ntp-peer-ip` 参数
- [ ] 确认NTP同步使用指定的IP地址
- [ ] 确认UDP通信使用不同的IP地址
- [ ] 确认时间同步成功
- [ ] 确认网络流量分离

#### ✅ 测试向下兼容性
- [ ] 确认不使用新参数时行为不变
- [ ] 确认现有脚本和配置文件仍然工作
- [ ] 确认日志格式向下兼容

#### ✅ 测试错误处理
- [ ] 测试NTP网络不可达时的行为
- [ ] 测试无效IP地址的处理
- [ ] 测试参数冲突的处理

### 快速功能验证脚本

创建一个快速验证脚本 `test_new_features.sh`:

```bash
#!/bin/bash
echo "=== 测试新NTP功能 ==="

echo "1. 测试跳过NTP功能..."
timeout 30 ./start_test.sh sender --skip-ntp --time=10 &
wait
echo "✓ 跳过NTP测试完成"

echo "2. 测试独立NTP IP功能..."
timeout 30 ./start_test.sh sender --ntp-peer-ip=192.168.1.20 --time=10 &
wait
echo "✓ 独立NTP IP测试完成"

echo "3. 检查系统监控日志..."
if [ -f "logs/system_monitor.jsonl" ]; then
    echo "最新监控记录:"
    tail -1 logs/system_monitor.jsonl | jq '.'
    echo "✓ 监控日志格式正确"
else
    echo "⚠ 监控日志文件未找到"
fi

echo "=== 测试完成 ==="
```

## 技术支持

如果遇到问题，请检查以下日志文件：
- 系统日志: `/var/log/syslog`
- Chrony日志: `/var/log/chrony/`
- 测试日志: `./logs/`
- ROS2日志: `~/.ros/log/`

对于新功能相关的问题：
- NTP跳过功能: 检查 `system_monitor.jsonl` 中的 `ntp_enabled` 字段
- 独立NTP IP: 检查网络路由和连通性
- 参数兼容性: 查看详细的错误日志

或者联系技术支持团队。 