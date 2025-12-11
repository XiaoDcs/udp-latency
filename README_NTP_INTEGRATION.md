# 无人机UDP通信测试系统 - 集成NTP时间同步

## 📋 最新功能更新 (v2.3) 🆕

### ⏱️ 优化时间配置逻辑
- **明确时间参数**: `--time` 参数现在明确表示实际UDP通信时间，不包括准备时间
- **自动缓冲机制**: 接收端自动增加20%缓冲时间（最少60秒），确保完整接收所有数据
- **智能时间管理**: GPS和Nexfi记录器自动延长运行时间以覆盖整个测试周期
- **详细时间显示**: 程序会显示准备时间、UDP通信时间、缓冲时间等详细信息

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
git clone https://github.com/XiaoDcs/udp-latency
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

### 3. 启动 Scripts 目录下的 tmux 主流程（推荐）

Scripts 目录提供了成对的 tmux 自动化脚本，会依次启动 Aerostack2、附着到会话确认状态，然后在新的 tmux 窗口里激活虚拟环境并执行 `start_test.sh`。它们已经内置常用 IP、Nexfi、GPS 与静态路由参数，是部署后主流程的首选入口：

- `scripts/run_drone12_tmux.sh`：发送端一键流程，默认把 drone12 作为 UDP 发送端，结束前保持 `drone12_udp` tmux 会话持续运行。
- `scripts/run_drone9_tmux.sh`：接收端一键流程，默认把 drone9 作为 UDP 接收端，并将 `start_test.sh receiver ...` 固定在 `drone9_udp` tmux 中。

两脚本的可选参数（`--auto-udp`、`--skip-udp`、`--skip-aero` 等）可控制是否跳过 Aerostack2 或自动发起 UDP 测试；通过环境变量可覆盖 ROS/Aerostack/虚拟环境路径。执行示例：

```bash
cd scripts
./run_drone12_tmux.sh      # 推荐在发送端无人机上运行
./run_drone9_tmux.sh       # 推荐在接收端无人机上运行
```

当需要针对不同无人机或 IP 组合时，可通过环境变量（如 `DRONE_ID`、`ROS_DOMAIN_ID_VALUE`、`UDP_PROJECT`）或直接编辑脚本来调整参数。脚本会在 tmux 中持续运行测试，即使 SSH 断连也不会中断。

### 4. 手动运行 start_test.sh（按需）

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
├── scripts/                   # 自动化脚本目录（主流程在此）
│   ├── run_drone12_tmux.sh    # 发送端 tmux 启动脚本（推荐）
│   ├── run_drone9_tmux.sh     # 接收端 tmux 启动脚本（推荐）
│   └── ...                    # 其他运维脚本（如 stop_aerostack_tmux.sh）
├── README_NTP_INTEGRATION.md  # 本文档
├── venv/                      # Python虚拟环境 (setup.sh创建)
├── logs/                      # 测试日志目录 (自动创建)
│   └── 20231211_153045/       # 每次运行自动创建的时间戳子目录 (示例)
│       ├── udp_test_20231211_153045.log
│       ├── system_monitor_20231211_153045.jsonl
│       ├── udp_receiver_20231211_153045.csv
│       ├── gps_logger_drone9_20231211_153045.csv
│       ├── nexfi_status_20231211_153045.csv
│       └── typology_edges_20231211_153045.csv
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
- Nexfi通信模块设备 (可选，无法连接时仅跳过状态记录)
- 网络连接到Nexfi设备 (通常为192.168.104.1)

## 详细使用说明

> 推荐：先使用 `scripts/run_drone12_tmux.sh` 与 `scripts/run_drone9_tmux.sh` 完成标准发送端/接收端流程，它们会自动调用 `start_test.sh` 并保持 tmux 会话。以下章节介绍如何在需要自定义参数或排障时手动执行各组件。

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

### 时间相关参数 🆕

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--time` | int | 60 | UDP通信时间(秒)，不包括准备时间 |

**时间配置逻辑**:
- **发送端总时间** = 准备时间 + UDP通信时间
- **接收端总时间** = 准备时间 + UDP通信时间 + 缓冲时间
- **准备时间**: NTP对时(~10-30s) + GPS启动(~5s) + Nexfi启动(~5s) + 其他初始化
- **缓冲时间**: max(60秒, UDP通信时间 × 20%)

**示例**:
```bash
# 设置300秒UDP通信时间
./start_test.sh sender --time=300
# 发送端: 准备~60s + UDP发送300s = 总计~360s

./start_test.sh receiver --time=300  
# 接收端: 准备~60s + UDP接收300s + 缓冲60s = 总计~420s
```

### NTP相关参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--skip-ntp` | flag | false | 完全跳过NTP时间同步功能 |
| `--ntp-peer-ip` | string | 使用--peer-ip的值 | NTP对时的对方IP地址 |
| `--skip-ntp-config` | flag | false | 跳过chrony配置，使用现有配置 |

### 静态路由参数 🆕

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--enable-static-route` | flag | false | 启用自动静态路由，强制UDP只走指定Mesh链路 |
| `--static-route-via` | string | 空 | 指定下一跳（通常是对端通信模块IP，如192.168.104.12） |
| `--static-route-interface` | string | 空 | （可选）指定出接口，例如 `bat0` |

脚本会自动执行：

```bash
sudo ip route add <peer-ip>/32 via <static-route-via> [dev <interface>]
```

并在退出时自动删除该路由，防止影响地面站与无人机之间的常规控制链路。

**示例：**

```bash
# 无人机A (192.168.104.109) 发送端
./start_test.sh sender \
  --local-ip=192.168.104.109 \
  --peer-ip=192.168.104.112 \
  --enable-static-route \
  --static-route-via=192.168.104.12 \
  --static-route-interface=bat0

# 无人机B (192.168.104.112) 接收端
./start_test.sh receiver \
  --local-ip=192.168.104.112 \
  --peer-ip=192.168.104.109 \
  --enable-static-route \
  --static-route-via=192.168.104.9 \
  --static-route-interface=bat0
```

这样测试用UDP会被强制走 `.12 ↔ .9` 的直连链路，而来自 192.168.104.1 的日常控制仍按照默认路由转发。

### 使用场景说明

#### 何时使用新的时间配置
- ✅ 需要精确控制UDP通信时长
- ✅ 两端启动时机不同步的环境
- ✅ 长时间测试，确保数据完整性
- ✅ 自动化测试脚本，需要可预测的时间

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

每次执行 `udp_test_with_ntp.py` 时，都会在 `logs/` 目录下创建一个以 `YYYYMMDD_HHMMSS` 命名的子目录，本文称之为 `RUN_DIR`。所有本次实验产生的日志文件都会集中保存在该目录中，方便一次性复制与归档。

快速定位最新一次实验的目录：

```bash
RUN_DIR=$(ls -td logs/*/ | head -1)
echo "当前分析目录: $RUN_DIR"
```

后续命令示例中若出现 `$RUN_DIR`，请替换为上述得到的路径。

测试完成后，会在 `RUN_DIR` 内生成以下文件：

### NTP同步日志
- `RUN_DIR/ntp_sync_YYYYMMDD_HHMMSS.log`: NTP同步过程日志
- `RUN_DIR/system_monitor_YYYYMMDD_HHMMSS.jsonl`: 系统状态监控日志 (JSON Lines格式)

### UDP测试日志
- `RUN_DIR/udp_sender_YYYYMMDD_HHMMSS.csv`: 发送端日志
- `RUN_DIR/udp_receiver_YYYYMMDD_HHMMSS.csv`: 接收端日志
- `RUN_DIR/udp_test_YYYYMMDD_HHMMSS.log`: 测试过程日志

### GPS记录日志
- `RUN_DIR/gps_logger_[drone_id]_YYYYMMDD_HHMMSS.csv`: GPS位置和状态日志

### Nexfi通信状态日志
- `RUN_DIR/nexfi_status_YYYYMMDD_HHMMSS.csv`: Nexfi通信模块状态和链路质量日志（逐链路行，包含Wi‑Fi物理层、链路统计、系统负载等扩展字段）
- `RUN_DIR/typology_edges_YYYYMMDD_HHMMSS.csv` 🆕: 每次轮询生成的拓扑边CSV，记录整张Mesh图中任意路由器与邻居的metric/tx_rate/SNR/last_seen，可直接做全网分析

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

**Nexfi通信状态日志 (CSV)** (节选):
```csv
timestamp,mesh_enabled,channel,node_id,node_ip,wifi_quality,wifi_noise,connected_node_ip,rssi,snr,topology_snr,link_metric,tx_rate,thr,tx_packets,tx_retries,rx_packets,rx_drop_misc,mesh_plink,throughput,cpu_usage,load1,mem_total,bat_ipv4
1765254430.25,True,6,B8:8E:DF:01:E7:D5,192.168.104.9,66,-102,192.168.104.12,-57,45,49,243,17,32906,48228,27207,198233,271,ESTAB,30.843,36.0%,0.36,59281408,192.168.104.9
1765254430.25,True,6,B8:8E:DF:01:E7:D5,192.168.104.9,66,-102,192.168.104.1,-40,62,64,255,20,28781,107101,59854,242890,642,ESTAB,30.843,36.0%,0.36,59281408,192.168.104.9
```
> 每一行代表“本机 ↔ 某个邻居”链路；其余字段（频宽、channel_width、tx/rx字节、CPU/内存等）也在同一行同步记录。

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

> **2025-12 更新**：`gps.py` 现在会自动订阅 Aerostack2/PSDK 的姿态、速度、GNSS、RTK、控制、电源、避障等 40+ 个话题，一并写入 `gps_logger_*.csv`。无需改系统包，只要按照下方环境要求运行即可获得完整的无人机状态快照。

### GPS数据字段说明（按类别划分）

**核心位姿与状态**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| timestamp | float | Unix时间戳 |
| latitude / longitude / altitude | float | GNSS原始坐标 (deg/m) |
| local_x / local_y / local_z | float | Aerostack本地坐标 (m) |
| connected / armed / offboard | bool | 平台连接、解锁、Offboard 状态 |
| linear_vx / vy / vz | float | `DroneInterface` 线速度 (m/s) |
| angular_vx / vy / vz | float | `psdk_ros2/angular_rate_ground_fused` 角速度 (rad/s) |
| roll / pitch / yaw | float | 欧拉角 (rad) |
| psdk_vel_x / y / z | float | PSDK Ground Fused 速度 (m/s) |
| psdk_acc_ground_x / y / z | float | 地理系线加速度 (m/s²) |
| psdk_acc_body_raw_* / psdk_acc_body_fused_* | float | 机体系原始/融合加速度 |
| psdk_ang_rate_body_* | float | 机体系角速度 |
| psdk_att_qx / qy / qz / qw | float | PSDK 姿态四元数 |
| height_above_ground | float | 距地高度 (m) |
| altitude_barometric / altitude_sea_level | float | 气压/海平面高度 (m) |
| position_fused_* | float | PSDK ENU 位置 |
| position_fused_health_* | uint8 | 各轴健康度 |
| mag_field_x / y / z | float | 磁场 (µT) |

**GNSS / RTK 字段**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| gps_nav_lat / lon / alt | float | `psdk_ros2/gps_position` 经纬高 |
| gps_nav_vel_x / y / z | float | `psdk_ros2/gps_velocity` 速度 |
| gps_fix_state | float | `GPSDetails.fix_state` (0~5) |
| gps_horizontal_dop / position_dop | float | DOP 指标 |
| gps_vertical_accuracy / horizontal_accuracy | float | 精度 (mm) |
| gps_speed_accuracy | float | 速度精度 (cm/s) |
| gps_satellites_gps / glonass / total | uint | 使用的卫星数量 |
| gps_counter | uint | PSDK GPS数据计数 |
| gps_signal_level | uint8 | 信号等级 (0~5) |
| home_point_lat / lon / alt | float | 返航点坐标 |
| home_point_status | bool | 返航点是否锁定 |
| home_point_altitude | float | 返航点高度 (m) |
| rtk_lat / lon / alt | float | RTK 坐标 |
| rtk_vel_x / y / z | float | RTK 速度 |
| rtk_connection_status | uint16 | RTK 链路状态 |
| rtk_yaw | uint16 | RTK Yaw (deg) |

**控制与姿态状态**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| platform_state / yaw_mode / control_mode / reference_frame | int | `platform/info` 中的状态机与控制模式 |
| display_mode | uint8 | PSDK 显示模式 (DJI Flight Mode) |
| psdk_control_mode / device_mode / control_auth | uint8 | `psdk_ros2/control_mode` |
| flight_status | uint8 | 起降状态 (0停、1地面、2空中) |
| flight_anomaly_flags | str | 将 `psdk_ros2/flight_anomaly` 中为 1 的字段用 `|` 拼接（无异常时为 `none`） |
| rc_axis_0~3 | float | 摇杆 XYZ/Yaw 输入 |
| rc_button_0~1 | int | 常用按键值 |
| rc_air_connection / ground_connection / app_connection / rc_link_disconnected | uint8 | 遥控链路状态 |

**电源 / ESC / 避障 / HMS**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| battery1_* / battery2_* | float | 两块电池的电压、电流、剩余容量、百分比、温度 |
| esc_avg_current / voltage / temperature | float | 所有电调平均电参 |
| esc_max_temperature | float | 电调最高温 (℃) |
| relative_obstacle_up / down / front / back / left / right | float | 各方向避障距离 (m) |
| relative_obstacle_*_health | uint8 | 避障传感器健康度 |
| hms_error_summary | str | `psdk_ros2/hms_info_table` 中存在错误码的 `error_code:error_level` 列表 |

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

> **运行建议**
> 1. 当前测试环境（drone9）使用 `ROS_DOMAIN_ID=9`，且 Aerostack2/PSDK 进程默认采用 **Cyclone DDS**。运行 GPS 记录器前，请使用 root 执行：
>    ```bash
>    sudo -s
>    export ROS_DOMAIN_ID=9
>    export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
>    source /opt/ros/humble/setup.bash
>    source /home/amov/aerostack2_ws/install/setup.bash
>    cd /home/amov/udp_test/udp-latency
>    python3 gps.py --drone-id=drone9 --log-path ./logs --time 600 --interval 0.5
>    ```
> 2. 若在其他无人机命名空间运行，请将 `ROS_DOMAIN_ID`、`--drone-id` 替换为相应值，并确认目标 Aerostack2 进程使用的 DDS 实现；必要时移除 `RMW_IMPLEMENTATION` 或与实际值保持一致。
> 3. 脚本会先写入若干 `nan`（等待 ROS 话题出现），属于正常现象，可在后处理中过滤。

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
| node_id | str | 节点ID（本机MAC） |
| node_ip | str | 节点管理IP |
| wifi_quality / wifi_quality_max | int | `iwinfo` 返回的信号质量及上限 |
| wifi_noise | int | 噪声电平 (dBm) |
| wifi_bitrate | float | 当前物理速率 (kbps) |
| wifi_mode | str | Mesh/AP/Client 模式 |
| channel_width | str | HT20/HT40/VHT 等通道宽度 |
| connected_nodes | int | 连接的节点数量 |
| connected_node_id | str | 邻居节点ID（来自拓扑） |
| connected_node_mac | str | 邻居MAC |
| connected_node_ip | str | 邻居IP（若可解析） |
| rssi / snr | float | 来自主机视角的瞬时RSSI和SNR |
| topology_snr | float | `batadv-vis` 提供的SNR |
| link_metric | float | Batman TQ metric (0-255) |
| tx_rate | float | 拓扑中的速率估计 (Mbps) |
| last_seen | str | 邻居最后可达时间 (秒) |
| thr | float | `iwinfo` 估算的链路吞吐量 (kbps) |
| tx_packets / tx_bytes | int | Wi‑Fi接口向该邻居发送的包/字节数 |
| tx_retries | int | Wi‑Fi重传次数 |
| rx_packets / rx_bytes | int | Wi‑Fi接口从该邻居接收的包/字节数 |
| rx_drop_misc | int | 接收丢包计数 |
| mesh_plink | str | Mesh链路状态 (ESTAB/DISABLED/...) |
| mesh_llid / mesh_plid | int | Mesh链路标识 |
| mesh_local_ps / mesh_peer_ps / mesh_non_peer_ps | str | Mesh省电状态 |
| throughput | str | 平均吞吐量 (Mbps)，取系统统计或thr均值 |
| cpu_usage | str | CPU使用率 |
| memory_usage | str | 内存使用率 |
| load1 / load5 / load15 | float | 系统1/5/15分钟平均负载 |
| mem_total / mem_free / mem_cached | int | 内存统计 (字节) |
| bat_ipv4 / bat_ipv6 | str | batman-adv 接口IP列表（逗号分隔） |
| uptime | str | 系统运行时间 |
| firmware_version | str | 固件版本 |
| topology_nodes | int | 拓扑中的节点总数 |
| link_quality | float | 本节点邻居平均链路质量 |
| avg_rssi / avg_snr | float | 所有邻居的平均RSSI/SNR（便于快速浏览） |

### Nexfi记录器独立使用

Nexfi记录器也可以独立运行：

```bash
# 基本使用 - 记录到CSV
python3 nexfi_client.py --nexfi-ip=192.168.104.1 --interval=1.0 --time=300

# 自定义参数
python3 nexfi_client.py --nexfi-ip=192.168.104.1 --username=admin --password=mypass --device=wlan0

# 指定batman-adv接口 (默认bat0)
python3 nexfi_client.py --nexfi-ip=192.168.104.1 --device=mesh0 --bat-interface=bat0

# 监控模式 - 实时显示状态
python3 nexfi_client.py --nexfi-ip=192.168.104.1 --monitor=5

# 保存当前状态到JSON
python3 nexfi_client.py --nexfi-ip=192.168.104.1 --save --output=nexfi_snapshot.json

# 查看帮助
python3 nexfi_client.py --help
```

### 拓扑边CSV字段说明 🆕

`$RUN_DIR/typology_edges_*.csv` 会为每次轮询追加整张Mesh中的所有边，字段定义如下：

| 字段名 | 说明 |
|--------|------|
| timestamp | Unix时间戳（与 `nexfi_status` 同步） |
| router_mac / router_ip / router_nodeid | 边的起点节点信息 |
| neighbor_mac / neighbor_ip / neighbor_nodeid | 边的终点节点信息 |
| metric | Batman TQ (0-255) |
| tx_rate | 邻居速率估计 (Mbps) |
| snr | 邻居信噪比 |
| last_seen | 邻居最后可达 (秒) |

> 提示：配合主CSV里的 `connected_node_ip` 可以只筛选无人机链路；如需历史拓扑，可对该CSV按时间聚合即可，无需大量JSON文件。

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

### Nexfi设备不可达时的行为

当无法连接到Nexfi设备时，`nexfi_client.py` 会直接退出并提示检查设备连接，不会写入任何伪造或模拟的数据。主测试流程（udp_test_with_ntp.py、UDP收发脚本等）会继续执行，只是不会生成新的 Nexfi 状态日志。

> 提示：若需要无设备情况下快速验证主流程，可在 `config` 中关闭 `enable_nexfi`，或允许脚本在启动时提示“将跳过Nexfi状态记录”，这样既不会阻塞测试，也不会产生失真的实验结果。

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
**症状**: Nexfi日志为空，或控制台提示“Nexfi状态记录器无法获取真实数据，将直接退出”
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
tail -f "$RUN_DIR"/gps_logger_drone0_*.csv

# 验证GPS数据格式
python3 -c "
import os, glob
import pandas as pd

run_dir = os.environ.get('RUN_DIR') or sorted(glob.glob('logs/*/'))[-1]
gps_file = sorted(glob.glob(os.path.join(run_dir, 'gps_logger_drone0_*.csv')))[0]
df = pd.read_csv(gps_file)
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
import os, glob

run_dir = os.environ.get('RUN_DIR') or sorted(glob.glob('logs/*/'))[-1]
gps_file = sorted(glob.glob(os.path.join(run_dir, 'gps_logger_drone0_*.csv')))[0]
df = pd.read_csv(gps_file)

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
import os, glob
run_dir = os.environ.get('RUN_DIR') or sorted(glob.glob('logs/*/'))[-1]
gps_file = sorted(glob.glob(os.path.join(run_dir, 'gps_logger_drone0_*.csv')))[0]
udp_file = sorted(glob.glob(os.path.join(run_dir, 'udp_receiver_*.csv')))[0]
gps_df = pd.read_csv(gps_file)
udp_df = pd.read_csv(udp_file)

# 时间对齐和分析
# ... 分析代码
```

### Nexfi通信状态分析
```python
import pandas as pd
import matplotlib.pyplot as plt
import os, glob

run_dir = os.environ.get('RUN_DIR') or sorted(glob.glob('logs/*/'))[-1]
nexfi_file = sorted(glob.glob(os.path.join(run_dir, 'nexfi_status_*.csv')))[0]
nexfi_df = pd.read_csv(nexfi_file)

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
import os, glob
run_dir = os.environ.get('RUN_DIR') or sorted(glob.glob('logs/*/'))[-1]
udp_file = sorted(glob.glob(os.path.join(run_dir, 'udp_receiver_*.csv')))[0]
gps_file = sorted(glob.glob(os.path.join(run_dir, 'gps_logger_*.csv')))[0]
nexfi_file = sorted(glob.glob(os.path.join(run_dir, 'nexfi_status_*.csv')))[0]
udp_df = pd.read_csv(udp_file)
gps_df = pd.read_csv(gps_file)
nexfi_df = pd.read_csv(nexfi_file)

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
4. **时间配置**: --time参数是UDP通信时间，接收端会自动增加缓冲时间 🆕
5. **启动时机**: 建议两端尽量同时启动，避免过大的时间差 🆕
6. **防火墙**: 确保相关端口未被防火墙阻止
7. **系统负载**: 避免在高负载时进行测试
8. **ROS2环境**: GPS记录需要正确配置的ROS2环境
9. **GPS信号**: 确保GPS信号良好，特别是在室外环境
10. **存储空间**: 确保有足够空间存储日志文件
11. **Nexfi设备**: 确保Nexfi设备正常工作并可访问
12. **网络权限**: Nexfi API访问需要正确的用户名和密码
13. **多网卡环境**: 使用--ntp-peer-ip时确保NTP网络路由正确 🆕
14. **测试时长**: 长时间测试(>10分钟)建议监控系统资源使用情况 🆕
15. **数据完整性**: 检查日志文件确保接收端接收到完整的数据包 🆕

## 新功能测试示例 🆕

### 测试场景1: 时间配置验证 🆕

**目标**: 验证新的时间配置逻辑是否正确工作

```bash
# 短时间测试 (60秒)
./start_test.sh sender --time=60 > sender_60s.log 2>&1 &
./start_test.sh receiver --time=60 > receiver_60s.log 2>&1

# 检查实际运行时间
grep "总运行时间" sender_60s.log receiver_60s.log
grep "UDP通信时间" sender_60s.log receiver_60s.log
grep "缓冲时间" receiver_60s.log

# 长时间测试 (300秒)
./start_test.sh sender --time=300 > sender_300s.log 2>&1 &
./start_test.sh receiver --time=300 > receiver_300s.log 2>&1

# 验证接收端是否有足够的缓冲时间
grep "缓冲时间" receiver_300s.log  # 应该显示60秒缓冲时间
```

**预期结果**:
- 发送端: 准备~60s + UDP发送60s = 总计~120s
- 接收端: 准备~60s + UDP接收60s + 缓冲60s = 总计~180s
- 接收端应该能完整接收所有数据包

### 测试场景2: 跳过NTP对时的快速UDP测试

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
- 发送端: 准备~20s + UDP发送120s = 总计~140s
- 接收端: 准备~20s + UDP接收120s + 缓冲60s = 总计~200s
- 系统监控日志中 `ntp_enabled` 为 `false`

### 测试场景3: 双网卡环境（管理网络+数据网络）

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
- 发送端: 准备~60s + UDP发送300s = 总计~360s
- 接收端: 准备~60s + UDP接收300s + 缓冲60s = 总计~420s
- 两个网络可以独立优化和管理

### 测试场景4: 验证NTP参数功能

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

# 检查时间配置差异
grep "准备时间" standard_ntp.log skip_ntp.log
grep "UDP通信时间" standard_ntp.log skip_ntp.log

# 检查系统监控日志差异
tail -5 $(ls -t "$RUN_DIR"/system_monitor_*.jsonl | head -1) | jq '.ntp_enabled'
```

### 测试场景5: 故障排除模式

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

#### ✅ 测试新的时间配置逻辑 🆕
- [ ] 确认--time参数表示UDP通信时间
- [ ] 确认接收端自动增加缓冲时间
- [ ] 确认GPS/Nexfi记录器运行时间自动计算
- [ ] 确认程序显示详细的时间分解信息
- [ ] 确认接收端能完整接收所有数据包

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
echo "=== 测试新时间配置和NTP功能 ==="

echo "1. 测试时间配置逻辑..."
timeout 90 ./start_test.sh sender --time=30 > time_test.log 2>&1 &
SENDER_PID=$!
sleep 5
timeout 120 ./start_test.sh receiver --time=30 > receiver_time_test.log 2>&1 &
RECEIVER_PID=$!

wait $SENDER_PID $RECEIVER_PID

# 检查时间配置
if grep -q "UDP通信时间: 30秒" time_test.log && grep -q "缓冲时间:" receiver_time_test.log; then
    echo "✓ 时间配置逻辑正确"
else
    echo "✗ 时间配置逻辑有问题"
fi

echo "2. 测试跳过NTP功能..."
timeout 60 ./start_test.sh sender --skip-ntp --time=20 > skip_ntp_test.log 2>&1 &
wait
if grep -q "跳过时间同步" skip_ntp_test.log; then
    echo "✓ 跳过NTP功能正常"
else
    echo "✗ 跳过NTP功能有问题"
fi

echo "3. 测试独立NTP IP功能..."
timeout 90 ./start_test.sh sender --ntp-peer-ip=192.168.1.20 --time=20 > ntp_ip_test.log 2>&1 &
wait
if grep -q "NTP对时专用IP" ntp_ip_test.log || grep -q "192.168.1.20" ntp_ip_test.log; then
    echo "✓ 独立NTP IP功能正常"
else
    echo "✗ 独立NTP IP功能有问题"
fi

echo "4. 检查系统监控日志..."
latest_run=$(ls -td logs/*/ 2>/dev/null | head -1)
if [ -n "$latest_run" ]; then
    latest_monitor=$(ls -t "${latest_run}"/system_monitor_*.jsonl 2>/dev/null | head -1)
else
    latest_monitor=""
fi
if [ -n "$latest_monitor" ]; then
    echo "最新监控记录:"
    tail -1 "$latest_monitor" | jq '.'
    echo "✓ 监控日志格式正确"
else
    echo "⚠ 监控日志文件未找到"
fi

echo "=== 测试完成 ==="
echo "详细日志文件："
ls -la *test.log
```

## 技术支持

如果遇到问题，请检查以下日志文件：
- 系统日志: `/var/log/syslog`
- Chrony日志: `/var/log/chrony/`
- 测试日志: `./logs/<timestamp>/`
- ROS2日志: `~/.ros/log/`

对于新功能相关的问题：
- NTP跳过功能: 检查 `RUN_DIR/system_monitor_*.jsonl` 中的 `ntp_enabled` 字段
- 独立NTP IP: 检查网络路由和连通性
- 参数兼容性: 查看详细的错误日志

或者联系技术支持团队。

## 时间配置最佳实践 🆕

### 时间参数规划指南

#### 短时间测试 (< 2分钟)
```bash
# 适用于快速验证或调试
./start_test.sh sender --time=60    # 发送端: ~120s总时间
./start_test.sh receiver --time=60  # 接收端: ~180s总时间
```
- 缓冲时间: 60秒 (固定最小值)
- 适用场景: 功能验证、参数调试、快速测试

#### 中等时间测试 (2-10分钟)
```bash
# 适用于性能测试
./start_test.sh sender --time=300   # 发送端: ~360s总时间
./start_test.sh receiver --time=300 # 接收端: ~420s总时间
```
- 缓冲时间: 60秒 (20% = 60s)
- 适用场景: 性能评估、稳定性测试、数据收集

#### 长时间测试 (> 10分钟)
```bash
# 适用于压力测试和长期稳定性验证
./start_test.sh sender --time=1800   # 发送端: ~1860s总时间
./start_test.sh receiver --time=1800 # 接收端: ~2220s总时间
```
- 缓冲时间: 360秒 (20% = 360s)
- 适用场景: 压力测试、长期稳定性、生产环境验证

### 时间配置常见问题

#### 问题1: 接收端提前关闭

**症状**: 
```
接收端日志显示: "UDP receiver completed"
发送端仍在运行，但接收端已停止
数据包丢失率异常高
```

**原因**: 
- 接收端和发送端启动时间差异太大
- 准备时间估算不准确
- 网络延迟导致时间差

**解决方案**:
```bash
# 方案1: 增加UDP通信时间
./start_test.sh receiver --time=400  # 而不是300

# 方案2: 手动同步启动
# 在两台无人机上几乎同时执行命令

# 方案3: 使用脚本自动化
./synchronized_test.sh 300  # 自定义脚本处理同步
```

#### 问题2: GPS/Nexfi记录时间不够

**症状**:
```
GPS记录器在UDP测试完成前就停止了
Nexfi状态记录缺失测试后期数据
```

**解决方案**:
程序已自动处理此问题：
- GPS记录时间 = UDP时间 + 缓冲时间 + 120秒准备时间
- Nexfi记录时间 = UDP时间 + 缓冲时间 + 120秒准备时间

#### 问题3: 准备时间预估不准确

**症状**:
```
实际准备时间超过预期
NTP对时花费时间过长
GPS启动缓慢
```

**监控和诊断**:
```bash
# 查看详细时间分解
grep "准备时间" "$RUN_DIR"/udp_test_*.log
grep "总运行时间" "$RUN_DIR"/udp_test_*.log

# 检查各组件启动时间
grep "NTP.*成功" "$RUN_DIR"/udp_test_*.log
grep "GPS.*启动成功" "$RUN_DIR"/udp_test_*.log
grep "Nexfi.*启动成功" "$RUN_DIR"/udp_test_*.log
```

### 自动化测试脚本建议

#### 创建同步启动脚本

`synchronized_test.sh`:
```bash
#!/bin/bash
# 使用方法: ./synchronized_test.sh <mode> <time> [other_args]

MODE=$1
TIME=$2
shift 2

echo "=== 同步UDP测试启动 ==="
echo "模式: $MODE"
echo "UDP通信时间: ${TIME}秒"

# 计算预期总时间
if [[ "$MODE" == "sender" ]]; then
    TOTAL_TIME=$((TIME + 80))  # 80秒准备时间预估
else
    BUFFER_TIME=$((TIME > 300 ? TIME / 5 : 60))
    TOTAL_TIME=$((TIME + BUFFER_TIME + 80))
fi

echo "预计总时间: ${TOTAL_TIME}秒"
echo "启动倒计时..."

# 3秒倒计时
for i in 3 2 1; do
    echo "$i..."
    sleep 1
done

echo "启动!"
./start_test.sh $MODE --time=$TIME "$@"
```

#### 批量测试脚本

`batch_test.sh`:
```bash
#!/bin/bash
# 批量测试不同时间配置

TEST_TIMES=(60 300 600 1200)

for time in "${TEST_TIMES[@]}"; do
    echo "=== 测试 ${time}秒 UDP通信 ==="
    
    # 创建测试目录
    mkdir -p "test_results/${time}s"
    
    # 运行测试
    ./start_test.sh $1 --time=$time --log-path="test_results/${time}s" || {
        echo "测试失败: ${time}秒"
        continue
    }
    
    # 分析结果
    echo "测试完成: ${time}秒"
    if [ -f "test_results/${time}s/udp_receiver_*.csv" ]; then
        PACKET_COUNT=$(tail -n +2 "test_results/${time}s/udp_receiver_*.csv" | wc -l)
        echo "接收数据包数: $PACKET_COUNT"
    fi
    
    sleep 10  # 间隔时间
done
```

### 性能调优建议

#### 网络环境优化
- **有线连接**: 使用有线网络可减少准备时间和提高稳定性
- **网络延迟**: 高延迟网络需要增加更多缓冲时间
- **带宽限制**: 低带宽环境建议降低发送频率或包大小

#### 系统资源优化
- **CPU负载**: 高CPU使用率会影响时间精度，建议关闭不必要服务
- **内存使用**: 确保有足够内存避免swap影响性能
- **磁盘I/O**: 使用SSD可提高日志写入性能

#### 时间同步优化
- **本地时钟**: 使用高精度时钟源
- **NTP配置**: 优化chrony配置参数
- **网络路径**: NTP流量使用专用网络路径

## 时间同步机制 
