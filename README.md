# 无人机UDP通信测试系统

这是一个用于测试无人机之间UDP通信性能的系统。它能够发送UDP数据包，跟踪每个数据包的发送和接收状态，计算丢包率和单向延迟，并将这些通信性能指标与无人机的GPS位置和通信模块状态信息进行关联。

## 系统组件

系统由以下几个主要组件组成：

1. **UDP发送端** (`udp_sender.py`)：在发送端无人机上运行，发送带有序列号和时间戳的UDP数据包
2. **UDP接收端** (`udp_receiver.py`)：在接收端无人机上运行，接收UDP数据包并记录延迟
3. **GPS记录器** (`gps_logger.py`)：在两台无人机上运行，记录GPS位置信息
4. **通信模块记录器** (`comms_logger.py`)：在两台无人机上运行，记录通信模块状态
5. **数据分析器** (`analyzer.py`)：在测试完成后运行，处理和分析所有日志数据

## 系统要求

- Python 3.6+
- pandas (用于分析器)
- numpy (用于分析器)

可以使用以下命令安装依赖：

```bash
pip install pandas numpy
```

## 使用方法

### 准备工作

1. 确保两台无人机的系统时钟已经通过NTP同步，以保证单向延迟计算的准确性
2. 在两台无人机上分别创建日志目录：`mkdir -p logs`

### 在接收端无人机上

1. 启动UDP接收端：

```bash
python udp_receiver.py --local-ip 192.168.104.2 --local-port 20001
```

2. 启动GPS记录器：

```bash
python gps_logger.py --interval 1.0
```

3. 启动通信模块记录器：

```bash
python comms_logger.py --interval 1.0
```

### 在发送端无人机上

1. 启动UDP发送端：

```bash
python udp_sender.py --remote-ip 192.168.104.2 --remote-port 20001 --frequency 10 --packet-size 200 --time 60
```

2. 启动GPS记录器：

```bash
python gps_logger.py --interval 1.0
```

3. 启动通信模块记录器：

```bash
python comms_logger.py --interval 1.0
```

### 测试完成后

1. 从两台无人机上收集所有日志文件
2. 使用分析器处理日志数据：

```bash
python analyzer.py --sender-log logs/udp_sender_*.csv --receiver-log logs/udp_receiver_*.csv --sender-gps logs/gps_log_sender_*.csv --receiver-gps logs/gps_log_receiver_*.csv --sender-comms logs/comms_log_sender_*.csv --receiver-comms logs/comms_log_receiver_*.csv
```

## 命令行参数

### UDP发送端 (udp_sender.py)

```
-i, --local-ip=IP       本地IP地址 (默认: 0.0.0.0)
-p, --local-port=PORT   本地端口 (默认: 20002)
-r, --remote-ip=IP      远程IP地址 (默认: 192.168.104.2)
-o, --remote-port=PORT  远程端口 (默认: 20001)
-s, --packet-size=SIZE  数据包大小(字节) (默认: 200)
-f, --frequency=FREQ    发送频率(Hz) (默认: 10.0)
-t, --time=TIME         运行时间(秒) (默认: 60)
-v, --verbose=BOOL      是否打印详细信息 (默认: True)
    --log-path=PATH     日志文件路径 (默认: ./logs)
```

### UDP接收端 (udp_receiver.py)

```
-i, --local-ip=IP       本地IP地址 (默认: 0.0.0.0)
-p, --local-port=PORT   本地端口 (默认: 20001)
-b, --buffer-size=SIZE  缓冲区大小(字节) (默认: 1500)
-t, --time=TIME         最长运行时间(秒) (默认: 3600)
-v, --verbose=BOOL      是否打印详细信息 (默认: True)
    --log-path=PATH     日志文件路径 (默认: ./logs)
```

### GPS记录器 (gps_logger.py) 和通信模块记录器 (comms_logger.py)

```
-i, --interval=INTERVAL  记录间隔(秒) (默认: 1.0)
-t, --time=TIME          最长运行时间(秒) (默认: 3600)
-v, --verbose=BOOL       是否打印详细信息 (默认: True)
    --log-path=PATH      日志文件路径 (默认: ./logs)
```

### 数据分析器 (analyzer.py)

```
--sender-log         发送端UDP日志文件路径
--receiver-log       接收端UDP日志文件路径
--sender-gps         发送端GPS日志文件路径 (可选)
--receiver-gps       接收端GPS日志文件路径 (可选)
--sender-comms       发送端通信模块日志文件路径 (可选)
--receiver-comms     接收端通信模块日志文件路径 (可选)
--output-path        输出目录路径 (默认: ./analysis)
--output-format      输出文件格式 (csv或json) (默认: csv)
```

## 注意事项

1. **GPS和通信模块接口**：当前的GPS和通信模块记录器是占位实现，实际使用时需要根据具体的硬件接口进行开发。
2. **时间同步**：准确的延迟计算依赖于两台无人机之间精确的时钟同步，建议使用NTP或GPS+PPS进行时间同步。
3. **日志管理**：在长时间测试中，日志文件可能会变得很大，注意管理磁盘空间。
4. **网络设置**：确保无人机间的网络连接正常，且UDP端口未被防火墙阻止。
5. **MTU大小**：确保UDP数据包大小不超过网络链路的MTU，以避免IP分片。

## 许可证

[MIT](LICENSE)
