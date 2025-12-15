# 无人机 UDP 通信测试系统（集成 NTP 对时，可选 GPS / Nexfi）

本项目用于在两台无人机/机载电脑之间进行 UDP 通信性能测试（延迟、丢包等），并可选集成：
- NTP（chrony）对时：用于单向延迟计算需要的时间基准
- GPS 记录：从 Aerostack2 / PSDK ROS2 话题采集飞行状态快照
- Nexfi 状态记录：采集 Mesh 链路/拓扑与设备状态

> 主流程：`start_test.sh` → `udp_test_with_ntp.py` → `udp_sender.py/udp_receiver.py`（可选 `gps.py/nexfi_client.py`）。

---

## 关键约定（先看这个）

### NTP 角色固定分配
- `sender` 模式：固定作为 **NTP server**
- `receiver` 模式：固定作为 **NTP client**
- 角色不再基于 IP 大小自动推断；谁是 server/client 由你启动时的 `--mode` 决定。

### 日志目录命名
每次运行会创建：
- `logs/sender_YYYYMMDD_HHMMSS/`
- `logs/receiver_YYYYMMDD_HHMMSS/`

---

## 快速开始

### 1) 部署（两端路径保持一致）

```bash
chmod +x setup.sh
./setup.sh
source venv/bin/activate
```

可选检查：
```bash
./check_environment.sh
```

### 2) 推荐：使用 tmux 一键脚本（现场最稳）

两端分别运行（脚本内可通过环境变量覆盖路径/参数）：
```bash
./scripts/run_drone12_tmux.sh   # 示例：发送端
./scripts/run_drone9_tmux.sh    # 示例：接收端
```

### 3) 手动运行（按需）

发送端：
```bash
source venv/bin/activate
./start_test.sh sender --local-ip=192.168.104.10 --peer-ip=192.168.104.20
```

接收端：
```bash
source venv/bin/activate
./start_test.sh receiver --local-ip=192.168.104.20 --peer-ip=192.168.104.10
```

---

## 参数与行为说明

### `--time`（重要）
`--time` 表示**实际 UDP 通信时间**（不包含准备阶段），并且：
- 发送端总时间 ≈ 准备时间 + UDP 通信时间
- 接收端总时间 ≈ 准备时间 + UDP 通信时间 + 自动缓冲时间
- 自动缓冲时间 = `max(60, time * 0.2)`（用于尽量完整接收）

### `--ntp-peer-ip`（重要：支持 NTP 与 UDP 分网段）
`--ntp-peer-ip` 用于指定 **NTP 对时链路的对端 IP**（默认等于 `--peer-ip`）。

- `receiver` 模式：它就是 **NTP server 地址**，chrony 会连接 `server <ntp-peer-ip>` 完成对时。
- `sender` 模式：它表示 **对端 NTP client 的 IP**，主要用于：
  - 推导 chrony `allow <peer>/24` 放行网段（适配 NTP/UDP 分网段）
  - 在 `chronyc clients` 中匹配该 IP，辅助判断对端是否连上（不影响 UDP 收发）

双网段示例（UDP=192.168.104.x，NTP=192.168.1.x）：
```bash
# sender（NTP server）：对端 receiver 的 NTP IP 是 192.168.1.20
./start_test.sh sender --local-ip=192.168.104.10 --peer-ip=192.168.104.20 --ntp-peer-ip=192.168.1.20

# receiver（NTP client）：要连接的 NTP server 是 192.168.1.10
./start_test.sh receiver --local-ip=192.168.104.20 --peer-ip=192.168.104.10 --ntp-peer-ip=192.168.1.10
```

### 纯 UDP（不对时）
```bash
./start_test.sh sender --skip-ntp ...
./start_test.sh receiver --skip-ntp ...
```

### GPS（可选）
启用后会启动 `gps.py` 记录 `gps_logger_*.csv`：
```bash
./start_test.sh sender --enable-gps --drone-id=drone12 --gps-interval=0.1
```
要求：ROS2 + Aerostack2 + `as2_python_api`（由系统环境提供，不在 `requirements.txt` 内）。
> 记录停止条件：`gps.py` 以 `--time`（秒）作为最长运行时间，到点自动退出；行数约为 `time / gps-interval`（再加 1 行表头），与 CSV 文件大小无关。
> - sender：`gps.py --time = UDP_time + 120`
> - receiver：`gps.py --time = UDP_time + max(60, UDP_time * 0.2) + 120`

### Nexfi（可选）
启用后会启动 `nexfi_client.py` 记录 `nexfi_status_*.csv` 与 `typology_edges_*.csv`：
```bash
./start_test.sh receiver --enable-nexfi --nexfi-ip=192.168.104.1 --nexfi-interval=0.5
```
Python 依赖：`requests`（已在 `requirements.txt` 中）。
> 记录停止条件：`nexfi_client.py` 同样以 `--time`（秒）作为最长运行时间，到点自动退出；与 CSV 文件大小无关。
> - sender：`nexfi_client.py --time = UDP_time + 120`
> - receiver：`nexfi_client.py --time = UDP_time + max(60, UDP_time * 0.2) + 120`
> 注：`nexfi_status_*.csv` 可能按“每个邻居/链路一行”写入，因此总行数不一定严格等于 `time / nexfi-interval`。

### 静态路由（可选）
用于强制 UDP 流量走指定 Mesh 链路：
```bash
./start_test.sh sender --enable-static-route --static-route-via=192.168.104.9
```

---

## 输出与日志

每次运行目录：`logs/<mode>_<timestamp>/`，常见文件：
- `udp_test_<timestamp>.log`：主流程日志（对时/启动/退出信息）
- `system_monitor_<timestamp>.jsonl`：周期性状态快照（是否启用NTP、是否同步、GPS/Nexfi 子进程状态等）
- `udp_sender_<timestamp>.csv`：发送端发包日志
- `udp_receiver_<timestamp>.csv`：接收端收包日志
- `ntp_sync_*.log`：对时过程日志
- `gps_logger_<drone_id>_<timestamp>.csv`：GPS/姿态/电源/避障等字段（仅启用 GPS 时）
- `nexfi_status_<timestamp>.csv`：Mesh 邻居链路状态（仅启用 Nexfi 时）
- `typology_edges_<timestamp>.csv`：Mesh 拓扑边（仅启用 Nexfi 时）

---

## GPS：字段与来源说明

`gps_logger_*.csv` 的表头由 `gps.py` 写死（与写入顺序一致）。数据来源分两条链路：
- **Aerostack2（as2_python_api DroneInterface）**：例如 `latitude/longitude/altitude`、`local_*`、`connected/armed/offboard`、`linear_v*`、`roll/pitch/yaw`、`platform_*` 等。
- **PSDK ROS2 话题（`psdk_ros2/*` 订阅）**：例如 `psdk_*`、`gps_nav_*`、`rtk_*`、`battery*`、`esc_*`、`relative_obstacle_*`、`hms_error_summary` 等。

更明确一点：当前版本里来自 **Aerostack2** 的字段主要是（直接读取 `DroneInterfaceGPS`）：
- `latitude` / `longitude` / `altitude`
- `local_x` / `local_y` / `local_z`
- `connected` / `armed` / `offboard`
- `linear_vx` / `linear_vy` / `linear_vz`
- `roll` / `pitch` / `yaw`
- `platform_state` / `platform_yaw_mode` / `platform_control_mode` / `platform_reference_frame`

除以上字段外，其余字段均来自 `psdk_ros2/*` 等 ROS2 订阅（见 `gps.py` 的 `setup_additional_subscribers()`）。

### GPS CSV 字段表（完整）

> 下表字段与 `gps.py` 写入的 `gps_logger_*.csv` 表头一致（顺序一致），共 **127** 列。部分字段单位由 Aerostack2/PSDK 上游定义，建议以实际输出/上游消息定义为准。

| 序号 | 字段名 | 说明 |
|---:|---|---|
| 1 | `timestamp` | Unix 时间戳（秒） |
| 2 | `latitude` | GNSS 坐标（deg） |
| 3 | `longitude` | GNSS 坐标（deg） |
| 4 | `altitude` | GNSS 高度（m） |
| 5 | `local_x` | Aerostack 本地坐标 X（m） |
| 6 | `local_y` | Aerostack 本地坐标 Y（m） |
| 7 | `local_z` | Aerostack 本地坐标 Z（m） |
| 8 | `connected` | 飞控/平台状态 |
| 9 | `armed` | 飞控/平台状态 |
| 10 | `offboard` | 飞控/平台状态 |
| 11 | `linear_vx` | 线速度（m/s） |
| 12 | `linear_vy` | 线速度（m/s） |
| 13 | `linear_vz` | 线速度（m/s） |
| 14 | `angular_vx` | 角速度（rad/s） |
| 15 | `angular_vy` | 角速度（rad/s） |
| 16 | `angular_vz` | 角速度（rad/s） |
| 17 | `roll` | 姿态欧拉角（rad） |
| 18 | `pitch` | 姿态欧拉角（rad） |
| 19 | `yaw` | 姿态欧拉角（rad） |
| 20 | `psdk_vel_x` | PSDK 速度（m/s） |
| 21 | `psdk_vel_y` | PSDK 速度（m/s） |
| 22 | `psdk_vel_z` | PSDK 速度（m/s） |
| 23 | `psdk_acc_ground_x` | PSDK 地理系加速度（m/s²） |
| 24 | `psdk_acc_ground_y` | PSDK 地理系加速度（m/s²） |
| 25 | `psdk_acc_ground_z` | PSDK 地理系加速度（m/s²） |
| 26 | `psdk_acc_body_raw_x` | PSDK 机体系原始加速度（m/s²） |
| 27 | `psdk_acc_body_raw_y` | PSDK 机体系原始加速度（m/s²） |
| 28 | `psdk_acc_body_raw_z` | PSDK 机体系原始加速度（m/s²） |
| 29 | `psdk_acc_body_fused_x` | PSDK 机体系融合加速度（m/s²） |
| 30 | `psdk_acc_body_fused_y` | PSDK 机体系融合加速度（m/s²） |
| 31 | `psdk_acc_body_fused_z` | PSDK 机体系融合加速度（m/s²） |
| 32 | `psdk_ang_rate_body_x` | PSDK 机体系角速度（rad/s） |
| 33 | `psdk_ang_rate_body_y` | PSDK 机体系角速度（rad/s） |
| 34 | `psdk_ang_rate_body_z` | PSDK 机体系角速度（rad/s） |
| 35 | `psdk_att_qx` | PSDK 姿态四元数 |
| 36 | `psdk_att_qy` | PSDK 姿态四元数 |
| 37 | `psdk_att_qz` | PSDK 姿态四元数 |
| 38 | `psdk_att_qw` | PSDK 姿态四元数 |
| 39 | `height_above_ground` | 距地高度 AGL（m） |
| 40 | `altitude_barometric` | 高度（m） |
| 41 | `altitude_sea_level` | 高度（m） |
| 42 | `position_fused_x` | PSDK 融合位置（m） |
| 43 | `position_fused_y` | PSDK 融合位置（m） |
| 44 | `position_fused_z` | PSDK 融合位置（m） |
| 45 | `position_fused_health_x` | PSDK 融合位置健康度 |
| 46 | `position_fused_health_y` | PSDK 融合位置健康度 |
| 47 | `position_fused_health_z` | PSDK 融合位置健康度 |
| 48 | `mag_field_x` | 磁场（μT） |
| 49 | `mag_field_y` | 磁场（μT） |
| 50 | `mag_field_z` | 磁场（μT） |
| 51 | `gps_nav_lat` | PSDK GNSS 坐标（deg） |
| 52 | `gps_nav_lon` | PSDK GNSS 坐标（deg） |
| 53 | `gps_nav_alt` | PSDK GNSS 高度（m） |
| 54 | `gps_nav_vel_x` | PSDK GNSS 速度（m/s） |
| 55 | `gps_nav_vel_y` | PSDK GNSS 速度（m/s） |
| 56 | `gps_nav_vel_z` | PSDK GNSS 速度（m/s） |
| 57 | `gps_fix_state` | GNSS fix 状态 |
| 58 | `gps_horizontal_dop` | DOP 指标 |
| 59 | `gps_position_dop` | DOP 指标 |
| 60 | `gps_vertical_accuracy` | 定位精度（单位取决于 PSDK 输出） |
| 61 | `gps_horizontal_accuracy` | 定位精度（单位取决于 PSDK 输出） |
| 62 | `gps_speed_accuracy` | 速度精度（单位取决于 PSDK 输出） |
| 63 | `gps_satellites_gps` | 卫星数量 |
| 64 | `gps_satellites_glonass` | 卫星数量 |
| 65 | `gps_satellites_total` | 卫星数量 |
| 66 | `gps_counter` | GPS 数据计数 |
| 67 | `gps_signal_level` | 信号等级 |
| 68 | `home_point_lat` | Home 点信息 |
| 69 | `home_point_lon` | Home 点信息 |
| 70 | `home_point_alt` | Home 点信息 |
| 71 | `home_point_status` | Home 点信息 |
| 72 | `home_point_altitude` | Home 点信息 |
| 73 | `rtk_lat` | RTK 坐标（deg） |
| 74 | `rtk_lon` | RTK 坐标（deg） |
| 75 | `rtk_alt` | RTK 高度（m） |
| 76 | `rtk_vel_x` | RTK 速度（m/s） |
| 77 | `rtk_vel_y` | RTK 速度（m/s） |
| 78 | `rtk_vel_z` | RTK 速度（m/s） |
| 79 | `rtk_connection_status` | RTK 链路状态 |
| 80 | `rtk_yaw` | RTK Yaw |
| 81 | `platform_state` | Aerostack 平台状态/模式 |
| 82 | `platform_yaw_mode` | Aerostack 平台状态/模式 |
| 83 | `platform_control_mode` | Aerostack 平台状态/模式 |
| 84 | `platform_reference_frame` | Aerostack 平台状态/模式 |
| 85 | `display_mode` | DJI DisplayMode |
| 86 | `psdk_control_mode` | PSDK 控制信息 |
| 87 | `psdk_device_mode` | PSDK 控制信息 |
| 88 | `psdk_control_auth` | PSDK 控制信息 |
| 89 | `flight_status` | 飞行状态/异常 |
| 90 | `flight_anomaly_flags` | 飞行状态/异常 |
| 91 | `rc_axis_0` | 遥控器摇杆输入 |
| 92 | `rc_axis_1` | 遥控器摇杆输入 |
| 93 | `rc_axis_2` | 遥控器摇杆输入 |
| 94 | `rc_axis_3` | 遥控器摇杆输入 |
| 95 | `rc_button_0` | 遥控器按键 |
| 96 | `rc_button_1` | 遥控器按键 |
| 97 | `rc_air_connection` | 遥控器链路状态 |
| 98 | `rc_ground_connection` | 遥控器链路状态 |
| 99 | `rc_app_connection` | 遥控器链路状态 |
| 100 | `rc_link_disconnected` | 遥控器链路状态 |
| 101 | `battery1_voltage` | 电池1 |
| 102 | `battery1_current` | 电池1 |
| 103 | `battery1_capacity_remain` | 电池1 |
| 104 | `battery1_capacity_pct` | 电池1 |
| 105 | `battery1_temperature` | 电池1 |
| 106 | `battery2_voltage` | 电池2 |
| 107 | `battery2_current` | 电池2 |
| 108 | `battery2_capacity_remain` | 电池2 |
| 109 | `battery2_capacity_pct` | 电池2 |
| 110 | `battery2_temperature` | 电池2 |
| 111 | `esc_avg_current` | ESC 统计 |
| 112 | `esc_avg_voltage` | ESC 统计 |
| 113 | `esc_avg_temperature` | ESC 统计 |
| 114 | `esc_max_temperature` | ESC 统计 |
| 115 | `relative_obstacle_up` | 避障距离（m） |
| 116 | `relative_obstacle_down` | 避障距离（m） |
| 117 | `relative_obstacle_front` | 避障距离（m） |
| 118 | `relative_obstacle_back` | 避障距离（m） |
| 119 | `relative_obstacle_left` | 避障距离（m） |
| 120 | `relative_obstacle_right` | 避障距离（m） |
| 121 | `relative_obstacle_up_health` | 避障健康度 |
| 122 | `relative_obstacle_down_health` | 避障健康度 |
| 123 | `relative_obstacle_front_health` | 避障健康度 |
| 124 | `relative_obstacle_back_health` | 避障健康度 |
| 125 | `relative_obstacle_left_health` | 避障健康度 |
| 126 | `relative_obstacle_right_health` | 避障健康度 |
| 127 | `hms_error_summary` | HMS 错误摘要 |

---

## Nexfi：字段与来源说明

`nexfi_status_*.csv` 与 `typology_edges_*.csv` 的表头由 `nexfi_client.py` 写死。

数据来源优先走 Nexfi 的 ubus JSON-RPC（`http://<nexfi-ip>/ubus`）：
- `nexfi.system.status`：系统状态（吞吐、CPU、内存等）
- `nexfi.mesh.status`：Mesh/射频状态（信道、功率、质量等）
- `nexfi.mesh.sites`：已连接站点列表（邻居的 MAC/RSSI/SNR 等，依固件可能不同）
- `nexfi.mesh.vis`：batman-adv 拓扑（节点/邻居/metric/速率/SNR 等）

如果固件不支持上述接口，会自动降级到（依然通过 ubus）：
- `iwinfo.info` / `iwinfo.assoclist`（无线信息/关联站点）
- `file.exec` 调用 `/usr/sbin/batadv-vis -f jsondoc`（拓扑）
- `system.info` / `system.board`、`network.interface.<bat_if>.status`（系统/接口信息）

### `nexfi_status_*.csv` 字段表（完整）

> 记录模式会在**同一个时间戳**下对每个已连接节点各写一行：公共字段会重复；如果无已连接节点，会写一行并将“节点相关字段”置空。

| 序号 | 字段名 | 说明 |
|---:|---|---|
| 1 | `timestamp` | Unix 时间戳（秒） |
| 2 | `mesh_enabled` | Mesh 是否启用（由 `disabled` 推导） |
| 3 | `channel` | 信道号 |
| 4 | `frequency_band` | 频宽/HT 模式（例如 `HT20`/`HT40`，取决于固件输出） |
| 5 | `tx_power` | 发射功率（常见为 dBm，取决于固件输出） |
| 6 | `work_mode` | 工作模式（mesh status 的 `mode`，部分固件与 `wifi_mode` 相同） |
| 7 | `node_id` | 本节点 ID（常见为 BSSID/MAC，取决于固件输出） |
| 8 | `node_ip` | 本节点 IP（优先来自拓扑节点 `ipaddr`；否则可能为空/`N/A`） |
| 9 | `wifi_quality` | Wi-Fi 质量值 |
| 10 | `wifi_quality_max` | Wi-Fi 质量上限 |
| 11 | `wifi_noise` | 噪声 |
| 12 | `wifi_bitrate` | 当前速率/bitrate（值类型依固件） |
| 13 | `wifi_mode` | Wi-Fi 模式（与 `work_mode` 保留兼容） |
| 14 | `channel_width` | 信道宽度/HT 模式（部分固件与 `frequency_band` 相同） |
| 15 | `connected_nodes` | 连接节点数量 |
| 16 | `connected_node_id` | 连接节点 ID（可能为空；尽量从拓扑补齐） |
| 17 | `connected_node_mac` | 连接节点 MAC（小写） |
| 18 | `connected_node_ip` | 连接节点 IP（可能为空；尽量从拓扑补齐） |
| 19 | `rssi` | 该连接节点的 RSSI（dBm，依固件/驱动） |
| 20 | `snr` | 该连接节点的 SNR（dB，依固件/驱动） |
| 21 | `topology_snr` | 拓扑里给出的 SNR（可能与 `snr` 不同） |
| 22 | `link_metric` | 拓扑链路 metric（数值含义依 batman-adv/Nexfi 输出） |
| 23 | `tx_rate` | 拓扑链路 tx rate（值类型依固件） |
| 24 | `last_seen` | 拓扑里最后可达/最近一次看到（值类型依固件） |
| 25 | `thr` | 站点吞吐估计（多来自 assoclist/sites 的原始字段） |
| 26 | `tx_packets` | 该站点发送包数（来自 assoclist/sites 原始字段） |
| 27 | `tx_bytes` | 该站点发送字节数（来自 assoclist/sites 原始字段） |
| 28 | `tx_retries` | 该站点发送重传次数（来自 assoclist/sites 原始字段） |
| 29 | `rx_packets` | 该站点接收包数（来自 assoclist/sites 原始字段） |
| 30 | `rx_bytes` | 该站点接收字节数（来自 assoclist/sites 原始字段） |
| 31 | `rx_drop_misc` | 该站点接收丢弃统计（来自 assoclist/sites 原始字段） |
| 32 | `mesh_plink` | mesh plink 状态（来自 assoclist 原始字段，可能为空） |
| 33 | `mesh_llid` | mesh llid（来自 assoclist 原始字段，可能为空） |
| 34 | `mesh_plid` | mesh plid（来自 assoclist 原始字段，可能为空） |
| 35 | `mesh_local_ps` | 本地省电状态（来自 assoclist 原始字段，可能为空） |
| 36 | `mesh_peer_ps` | 对端省电状态（来自 assoclist 原始字段，可能为空） |
| 37 | `mesh_non_peer_ps` | 非对端省电状态（来自 assoclist 原始字段，可能为空） |
| 38 | `throughput` | 吞吐量（优先来自 `nexfi.system.status`；否则用 `thr` 采样估算，可能为 `N/A`） |
| 39 | `cpu_usage` | CPU 使用率（字符串或数值，依固件） |
| 40 | `memory_usage` | 内存使用率（字符串或数值，依固件） |
| 41 | `load1` | 1 分钟负载（fallback 时会归一化到 float） |
| 42 | `load5` | 5 分钟负载 |
| 43 | `load15` | 15 分钟负载 |
| 44 | `mem_total` | 内存总量（单位依固件） |
| 45 | `mem_free` | 内存空闲（单位依固件） |
| 46 | `mem_cached` | 缓存内存（单位依固件） |
| 47 | `bat_ipv4` | batman-adv 接口 IPv4（可能为空） |
| 48 | `bat_ipv6` | batman-adv 接口 IPv6（可能为空） |
| 49 | `uptime` | 运行时间（如 `1234s` 或固件自带格式） |
| 50 | `firmware_version` | 固件版本/描述（依固件） |
| 51 | `topology_nodes` | 拓扑节点数 |
| 52 | `link_quality` | 平均链路质量（由拓扑 metric 汇总得到） |

### `typology_edges_*.csv` 字段表（完整）

> 每行表示拓扑中的一条有向边：`router_*` → `neighbor_*`（来自 `nexfi.mesh.vis` 或 `batadv-vis` 输出）。

| 序号 | 字段名 | 说明 |
|---:|---|---|
| 1 | `timestamp` | Unix 时间戳（秒） |
| 2 | `router_mac` | 路由节点 MAC（拓扑节点 `primary`） |
| 3 | `router_ip` | 路由节点 IP（拓扑节点 `ipaddr`，可能为空） |
| 4 | `router_nodeid` | 路由节点 nodeid（可能为空） |
| 5 | `neighbor_mac` | 邻居节点 MAC（拓扑邻居 `neighbor`） |
| 6 | `neighbor_ip` | 邻居节点 IP（从拓扑节点映射补齐，可能为空） |
| 7 | `neighbor_nodeid` | 邻居节点 nodeid（可能为空） |
| 8 | `metric` | 链路 metric（值含义依 batman-adv/Nexfi 输出） |
| 9 | `tx_rate` | 链路 tx rate（值类型依固件） |
| 10 | `snr` | 链路 SNR（值类型依固件） |
| 11 | `last_seen` | 最后可达/最近一次看到（值类型依固件） |

---

## 故障排除（简版）

- NTP 相关：`chronyc tracking` / `chronyc sources -v`；必要时用 `--skip-ntp` 先跑通 UDP。
- GPS 相关：确认已 source ROS2/Aerostack2 环境，且 `ros2 topic list` 能看到 `/.../psdk_ros2/*`。
- Nexfi 相关：确认能访问 Nexfi IP（`ping` / `curl`），并且 venv 中有 `requests`。
