#!/bin/bash

# 无人机UDP通信测试系统 - 发送端启动脚本

# 默认配置
REMOTE_IP="192.168.104.2"
REMOTE_PORT=20001
LOCAL_PORT=20002
FREQUENCY=10
PACKET_SIZE=200
RUNNING_TIME=60
LOG_PATH="./logs"
GPS_INTERVAL=1.0
COMMS_INTERVAL=1.0

# 创建日志目录
mkdir -p $LOG_PATH

# 解析命令行参数
while [[ $# -gt 0 ]]; do
  case $1 in
    --remote-ip=*)
      REMOTE_IP="${1#*=}"
      shift
      ;;
    --remote-port=*)
      REMOTE_PORT="${1#*=}"
      shift
      ;;
    --local-port=*)
      LOCAL_PORT="${1#*=}"
      shift
      ;;
    --frequency=*)
      FREQUENCY="${1#*=}"
      shift
      ;;
    --packet-size=*)
      PACKET_SIZE="${1#*=}"
      shift
      ;;
    --time=*)
      RUNNING_TIME="${1#*=}"
      shift
      ;;
    --log-path=*)
      LOG_PATH="${1#*=}"
      shift
      ;;
    --gps-interval=*)
      GPS_INTERVAL="${1#*=}"
      shift
      ;;
    --comms-interval=*)
      COMMS_INTERVAL="${1#*=}"
      shift
      ;;
    -h|--help)
      echo "使用方法: $0 [选项]"
      echo "选项:"
      echo "  --remote-ip=IP        远程IP地址 (默认: 192.168.104.2)"
      echo "  --remote-port=PORT    远程端口 (默认: 20001)"
      echo "  --local-port=PORT     本地端口 (默认: 20002)"
      echo "  --frequency=FREQ      发送频率(Hz) (默认: 10)"
      echo "  --packet-size=SIZE    数据包大小(字节) (默认: 200)"
      echo "  --time=TIME           运行时间(秒) (默认: 60)"
      echo "  --log-path=PATH       日志目录 (默认: ./logs)"
      echo "  --gps-interval=INT    GPS记录间隔(秒) (默认: 1.0)"
      echo "  --comms-interval=INT  通信模块记录间隔(秒) (默认: 1.0)"
      echo "  -h, --help            显示帮助信息"
      exit 0
      ;;
    *)
      echo "未知选项: $1"
      echo "使用 --help 查看帮助信息"
      exit 1
      ;;
  esac
done

# 确认参数
echo "正在使用以下参数:"
echo "远程IP地址: $REMOTE_IP"
echo "远程端口: $REMOTE_PORT"
echo "本地端口: $LOCAL_PORT"
echo "发送频率: $FREQUENCY Hz"
echo "数据包大小: $PACKET_SIZE 字节"
echo "运行时间: $RUNNING_TIME 秒"
echo "日志目录: $LOG_PATH"
echo "GPS记录间隔: $GPS_INTERVAL 秒"
echo "通信模块记录间隔: $COMMS_INTERVAL 秒"
echo ""
echo "按回车键继续，或按Ctrl+C取消..."
read

# 在后台启动GPS记录器
echo "正在启动GPS记录器..."
python gps_logger.py --interval=$GPS_INTERVAL --time=$RUNNING_TIME --log-path=$LOG_PATH &
GPS_PID=$!

# 在后台启动通信模块记录器
echo "正在启动通信模块记录器..."
python comms_logger.py --interval=$COMMS_INTERVAL --time=$RUNNING_TIME --log-path=$LOG_PATH &
COMMS_PID=$!

# 稍等一下，确保记录器已经启动
sleep 2

# 启动UDP发送端
echo "正在启动UDP发送端..."
python udp_sender.py --remote-ip=$REMOTE_IP --remote-port=$REMOTE_PORT --local-port=$LOCAL_PORT \
                     --frequency=$FREQUENCY --packet-size=$PACKET_SIZE --time=$RUNNING_TIME \
                     --log-path=$LOG_PATH

# 测试完成后，确保后台进程已经结束
echo "UDP发送完成，等待记录器完成..."
wait $GPS_PID
wait $COMMS_PID

echo "发送端测试完成！"
echo "日志文件已保存到 $LOG_PATH 目录" 