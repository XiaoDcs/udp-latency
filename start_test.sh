#!/bin/bash

# 无人机UDP通信测试系统 - 集成NTP时间同步启动脚本

# 默认配置
MODE=""
LOCAL_IP="192.168.104.10"
PEER_IP="192.168.104.20"
LOG_PATH="./logs"
FREQUENCY=10
PACKET_SIZE=1000
RUNNING_TIME=60
BUFFER_SIZE=1500

# NTP时间同步配置
ENABLE_NTP=true
NTP_PEER_IP=""
SKIP_NTP_CONFIG=false

# GPS记录相关配置
ENABLE_GPS=false
DRONE_ID="drone0"
GPS_INTERVAL=1.0
USE_SIM_TIME=false

# Nexfi通信状态记录配置
ENABLE_NEXFI=false
NEXFI_IP="192.168.104.1"
NEXFI_USERNAME="root"
NEXFI_PASSWORD="nexfi"
NEXFI_INTERVAL=1.0
NEXFI_DEVICE="adhoc0"

# 静态路由配置 🆕
ENABLE_STATIC_ROUTE=false
CONFIGURED_STATIC_ROUTE=""  # 记录已配置的静态路由，用于清理

# UDP网络错误处理配置 🆕
NETWORK_RETRY_DELAY=1.0
LOG_NETWORK_ERRORS=true

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助信息
show_help() {
    echo "无人机UDP通信测试系统 - 集成NTP时间同步"
    echo ""
    echo "使用方法: $0 [模式] [选项]"
    echo ""
    echo "模式:"
    echo "  sender                    运行发送端"
    echo "  receiver                  运行接收端"
    echo ""
    echo "选项:"
    echo "  --local-ip=IP            本地IP地址 (默认: 192.168.104.10)"
    echo "  --peer-ip=IP             对方IP地址，用于UDP通信 (默认: 192.168.104.20)"
    echo "  --log-path=PATH          日志保存路径 (默认: ./logs)"
    echo "  --frequency=FREQ         发送频率(Hz) (默认: 10)"
    echo "  --packet-size=SIZE       数据包大小(字节) (默认: 1000)"
    echo "  --time=TIME              UDP通信时间(秒) (默认: 60) 🆕"
    echo "                           注意: 这是实际UDP通信时间，不包括准备时间"
    echo "                           接收端会自动增加20%缓冲时间确保完整接收"
    echo "  --buffer-size=SIZE       缓冲区大小(字节) (默认: 1500)"
    echo ""
    echo "NTP时间同步选项:"
    echo "  --skip-ntp               完全跳过NTP时间同步功能"
    echo "  --ntp-peer-ip=IP         NTP对时的对方IP地址 (默认使用--peer-ip的值)"
    echo "  --skip-ntp-config        跳过chrony配置，使用现有配置"
    echo ""
    echo "GPS记录选项:"
    echo "  --enable-gps             启用GPS数据记录"
    echo "  --drone-id=ID            无人机命名空间 (默认: drone0)"
    echo "  --gps-interval=SEC       GPS记录间隔(秒) (默认: 1.0)"
    echo "  --use-sim-time           使用仿真时间"
    echo ""
    echo "Nexfi通信状态记录选项:"
    echo "  --enable-nexfi           启用Nexfi通信状态记录"
    echo "  --nexfi-ip=IP            Nexfi服务器IP地址 (默认: 192.168.104.1)"
    echo "  --nexfi-username=USERNAME Nexfi服务器用户名 (默认: root)"
    echo "  --nexfi-password=PASSWORD Nexfi服务器密码 (默认: nexfi)"
    echo "  --nexfi-interval=SEC     Nexfi记录间隔(秒) (默认: 1.0)"
    echo "  --nexfi-device=DEVICE    Nexfi设备名称 (默认: adhoc0)"
    echo ""
    echo "静态路由配置选项 🆕:"
    echo "  --enable-static-route    启用静态路由配置"
    echo "                           自动配置: ip route add [local-ip]/32 via [nexfi-ip]"
    echo "                           适用于需要通过网关路由本地IP的场景"
    echo "                           注意: 脚本退出时会自动清理配置的静态路由"
    echo ""
    echo "UDP网络错误处理选项 🆕:"
    echo "  --network-retry-delay=SEC  网络错误重试延迟(秒) (默认: 1.0)"
    echo "  --log-network-errors=BOOL  是否记录网络错误到日志 (默认: true)"
    echo "                             适用于无人机飞行中网络间歇性中断的场景"
    echo ""
    echo "  -h, --help               显示帮助信息"
    echo ""
    echo "⏱️  时间配置说明:"
    echo "  - --time参数指定的是实际UDP通信时间，不包括NTP对时、GPS启动等准备时间"
    echo "  - 发送端: 准备时间 + UDP通信时间"
    echo "  - 接收端: 准备时间 + UDP通信时间 + 自动缓冲时间(20%或最少60秒)"
    echo "  - GPS和Nexfi记录器会自动延长运行时间以覆盖整个测试周期"
    echo ""
    echo "示例:"
    echo "  $0 sender --local-ip=192.168.104.10 --peer-ip=192.168.104.20"
    echo "  $0 receiver --time=300 --enable-gps"
    echo "  $0 sender --enable-gps --drone-id=drone1 --gps-interval=0.5"
    echo "  $0 sender --enable-nexfi --nexfi-ip=192.168.104.1"
    echo "  $0 receiver --enable-gps --enable-nexfi --time=600"
    echo "  $0 sender --skip-ntp --peer-ip=192.168.104.20"
    echo "  $0 receiver --ntp-peer-ip=192.168.104.30 --peer-ip=192.168.104.20"
    echo "  $0 sender --enable-static-route --local-ip=192.168.104.112 --nexfi-ip=192.168.104.12"
    echo ""
    echo "时间配置示例:"
    echo "  $0 sender --time=300     # 发送端: 准备~60s + UDP发送300s"
    echo "  $0 receiver --time=300   # 接收端: 准备~60s + UDP接收300s + 缓冲60s"
    echo ""
    echo "注意:"
    echo "  - 两台无人机需要在同一网段内能够相互通信"
    echo "  - 始终使用内部NTP同步：sender自动成为NTP服务器，receiver成为客户端"
    echo "  - 可以使用--skip-ntp跳过NTP时间同步，直接进行UDP通信测试"
    echo "  - NTP对时IP可以与UDP通信IP不同，支持多网段NTP同步"
    echo "  - GPS记录需要ROS2环境和as2_python_api"
    echo "  - Nexfi状态记录需要requests库和Nexfi设备连接"
    echo "  - 接收端会自动延长运行时间，确保能接收到发送端的所有数据"
}

# 检查依赖
check_dependencies() {
    print_info "检查系统依赖..."
    
    # 检查Python3
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 未安装"
        return 1
    fi
    
    # 检查必要的Python脚本
    if [[ ! -f "udp_test_with_ntp.py" ]]; then
        print_error "找不到 udp_test_with_ntp.py"
        return 1
    fi
    
    if [[ ! -f "udp_sender.py" ]]; then
        print_error "找不到 udp_sender.py"
        return 1
    fi
    
    if [[ ! -f "udp_receiver.py" ]]; then
        print_error "找不到 udp_receiver.py"
        return 1
    fi
    
    # 如果启用GPS记录，检查GPS脚本和ROS2环境
    if [[ "$ENABLE_GPS" == "true" ]]; then
        if [[ ! -f "gps.py" ]]; then
            print_error "找不到 gps.py (GPS记录需要)"
            return 1
        fi
        
        # 检查ROS2环境
        if ! command -v ros2 &> /dev/null; then
            print_warning "ROS2 未找到，GPS记录可能无法工作"
            print_warning "请确保已安装ROS2并source了环境"
        fi
        
        # 检查Python包
        if ! python3 -c "import rclpy" &> /dev/null; then
            print_warning "rclpy 包未找到，GPS记录可能无法工作"
        fi
        
        if ! python3 -c "from as2_python_api.drone_interface_gps import DroneInterfaceGPS" &> /dev/null; then
            print_warning "as2_python_api 包未找到，GPS记录可能无法工作"
        fi
    fi
    
    # 如果启用Nexfi状态记录，检查Nexfi客户端脚本和依赖
    if [[ "$ENABLE_NEXFI" == "true" ]]; then
        if [[ ! -f "nexfi_client.py" ]]; then
            print_error "找不到 nexfi_client.py (Nexfi状态记录需要)"
            return 1
        fi
        
        # 检查requests库
        if ! python3 -c "import requests" &> /dev/null; then
            print_warning "requests 包未找到，Nexfi状态记录可能无法工作"
            print_warning "请运行: pip install requests"
        fi
        
        # 测试Nexfi连接
        print_info "测试Nexfi设备连接 ($NEXFI_IP)..."
        if timeout 5 python3 -c "
import requests
try:
    response = requests.get('http://$NEXFI_IP', timeout=3)
    print('Nexfi设备连接正常')
except:
    print('Nexfi设备连接失败，将使用模拟数据')
" 2>/dev/null; then
            print_success "Nexfi设备连接测试完成"
        else
            print_warning "Nexfi设备连接测试失败，将使用模拟数据继续运行"
        fi
    fi
    
    print_success "依赖检查通过"
    return 0
}

# 检查网络连接
check_network() {
    print_info "检查网络连接..."
    
    # 检查本地IP是否可用
    if ! ip addr show | grep -q "$LOCAL_IP"; then
        print_warning "本地IP $LOCAL_IP 可能未配置"
    fi
    
    # 尝试ping对方
    print_info "尝试连接对方无人机 $PEER_IP..."
    if ping -c 1 -W 3 "$PEER_IP" &> /dev/null; then
        print_success "对方无人机 $PEER_IP 可达"
    else
        print_warning "对方无人机 $PEER_IP 暂时不可达，测试时会自动重试"
    fi
}

# 配置静态路由 🆕
configure_static_route() {
    if [[ "$ENABLE_STATIC_ROUTE" != "true" ]]; then
        return 0
    fi
    
    print_info "配置静态路由..."
    
    # 检查是否已存在相同的路由
    existing_route=$(ip route show "$LOCAL_IP/32" 2>/dev/null | grep "via $NEXFI_IP" || true)
    if [[ -n "$existing_route" ]]; then
        print_info "静态路由已存在: $existing_route"
        CONFIGURED_STATIC_ROUTE="$existing_route"
        return 0
    fi
    
    # 验证nexfi_ip是否可达
    print_info "验证网关 $NEXFI_IP 连通性..."
    if ! ping -c 1 -W 3 "$NEXFI_IP" &> /dev/null; then
        print_warning "网关 $NEXFI_IP 不可达，但仍将配置静态路由"
    else
        print_success "网关 $NEXFI_IP 可达"
    fi
    
    # 配置静态路由
    route_cmd="ip route add $LOCAL_IP/32 via $NEXFI_IP"
    print_info "执行路由配置: $route_cmd"
    
    if sudo $route_cmd 2>/dev/null; then
        print_success "静态路由配置成功"
        print_info "路由信息: $(ip route show "$LOCAL_IP/32" 2>/dev/null || echo '未找到路由信息')"
        CONFIGURED_STATIC_ROUTE="$route_cmd"
    else
        print_error "静态路由配置失败"
        print_warning "请检查:"
        print_warning "  1. 是否有sudo权限"
        print_warning "  2. 网关IP $NEXFI_IP 是否正确"
        print_warning "  3. 本地IP $LOCAL_IP 是否正确"
        print_warning "  4. 是否存在冲突的路由规则"
        echo ""
        echo "当前路由表:"
        ip route show | head -10
        echo ""
        read -p "是否继续执行测试? [y/N]: " -r
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "测试已取消"
            return 1
        fi
    fi
    
    return 0
}

# 清理静态路由 🆕
cleanup_static_route() {
    if [[ "$ENABLE_STATIC_ROUTE" != "true" || -z "$CONFIGURED_STATIC_ROUTE" ]]; then
        return 0
    fi
    
    print_info "清理静态路由配置..."
    
    # 检查路由是否仍然存在
    existing_route=$(ip route show "$LOCAL_IP/32" 2>/dev/null | grep "via $NEXFI_IP" || true)
    if [[ -z "$existing_route" ]]; then
        print_info "静态路由已不存在，无需清理"
        return 0
    fi
    
    # 删除静态路由
    cleanup_cmd="ip route del $LOCAL_IP/32 via $NEXFI_IP"
    print_info "执行路由清理: $cleanup_cmd"
    
    if sudo $cleanup_cmd 2>/dev/null; then
        print_success "静态路由清理成功"
    else
        print_warning "静态路由清理失败，可能需要手动清理"
        print_warning "手动清理命令: sudo $cleanup_cmd"
    fi
}

# 清理函数 - 脚本退出时调用 🆕
cleanup_on_exit() {
    print_info "正在清理资源..."
    cleanup_static_route
    print_info "资源清理完成"
}

# 显示配置信息
show_config() {
    echo ""
    echo "=========================================="
    echo "           测试配置信息"
    echo "=========================================="
    echo "运行模式:     $MODE"
    echo "本地IP:       $LOCAL_IP"
    echo "对方IP:       $PEER_IP"
    echo "日志路径:     $LOG_PATH"
    
    # 计算时间配置
    UDP_TIME=$RUNNING_TIME
    if [[ "$MODE" == "sender" ]]; then
        echo "发送频率:     $FREQUENCY Hz"
        echo "数据包大小:   $PACKET_SIZE 字节"
        echo "UDP通信时间:  $UDP_TIME 秒"
        echo "预计总时间:   ~$((UDP_TIME + 60)) 秒 (含准备时间)"
        echo ""
        echo "网络错误处理配置 🆕:"
        echo "重试延迟:     $NETWORK_RETRY_DELAY 秒"
        echo "记录网络错误: $LOG_NETWORK_ERRORS"
    else
        BUFFER_TIME=$((UDP_TIME > 300 ? UDP_TIME / 5 : 60))  # 20%缓冲或最少60秒
        TOTAL_RECEIVER_TIME=$((UDP_TIME + BUFFER_TIME))
        echo "缓冲区大小:   $BUFFER_SIZE 字节"
        echo "UDP通信时间:  $UDP_TIME 秒"
        echo "缓冲时间:     $BUFFER_TIME 秒"
        echo "接收端总时间: $TOTAL_RECEIVER_TIME 秒"
        echo "预计总时间:   ~$((TOTAL_RECEIVER_TIME + 60)) 秒 (含准备时间)"
    fi
    echo ""
    echo "NTP时间同步配置:"
    echo "启用NTP同步:  $ENABLE_NTP"
    if [[ "$ENABLE_NTP" == "true" ]]; then
        if [[ -n "$NTP_PEER_IP" ]]; then
            echo "NTP对时IP:    $NTP_PEER_IP"
        else
            echo "NTP对时IP:    $PEER_IP (使用通信IP)"
        fi
        echo "跳过NTP配置:  $SKIP_NTP_CONFIG"
    fi
    echo ""
    echo "GPS记录配置:"
    echo "启用GPS记录:  $ENABLE_GPS"
    if [[ "$ENABLE_GPS" == "true" ]]; then
        echo "无人机ID:     $DRONE_ID"
        echo "GPS记录间隔:  $GPS_INTERVAL 秒"
        echo "使用仿真时间: $USE_SIM_TIME"
        if [[ "$MODE" == "receiver" ]]; then
            GPS_TOTAL_TIME=$((UDP_TIME + BUFFER_TIME + 120))
        else
            GPS_TOTAL_TIME=$((UDP_TIME + 120))
        fi
        echo "GPS记录时长:  $GPS_TOTAL_TIME 秒 (自动计算)"
    fi
    echo "Nexfi通信状态记录配置:"
    echo "启用Nexfi通信状态记录:  $ENABLE_NEXFI"
    if [[ "$ENABLE_NEXFI" == "true" ]]; then
        echo "Nexfi服务器IP:     $NEXFI_IP"
        echo "Nexfi服务器用户名: $NEXFI_USERNAME"
        echo "Nexfi服务器密码: $NEXFI_PASSWORD"
        echo "Nexfi记录间隔:  $NEXFI_INTERVAL 秒"
        echo "Nexfi设备名称: $NEXFI_DEVICE"
        if [[ "$MODE" == "receiver" ]]; then
            NEXFI_TOTAL_TIME=$((UDP_TIME + BUFFER_TIME + 120))
        else
            NEXFI_TOTAL_TIME=$((UDP_TIME + 120))
        fi
        echo "Nexfi记录时长: $NEXFI_TOTAL_TIME 秒 (自动计算)"
    fi
    echo ""
    echo "静态路由配置 🆕:"
    echo "启用静态路由:  $ENABLE_STATIC_ROUTE"
    if [[ "$ENABLE_STATIC_ROUTE" == "true" ]]; then
        echo "路由规则:     $CONFIGURED_STATIC_ROUTE"
        echo "说明:         配置本地IP到Nexfi网关的静态路由"
    fi
    echo "=========================================="
    echo ""
    echo "💡 时间说明:"
    echo "   - UDP通信时间: 实际UDP数据传输时间"
    echo "   - 准备时间: NTP对时、GPS启动等初始化操作"
    if [[ "$MODE" == "receiver" ]]; then
        echo "   - 缓冲时间: 接收端额外等待时间，确保接收完整"
    fi
    echo "   - 总运行时间: 准备 + UDP通信 + 缓冲(仅接收端)"
    echo ""
}

# 确认启动
confirm_start() {
    echo -n "确认启动测试? [y/N]: "
    read -r response
    case "$response" in
        [yY][eE][sS]|[yY]) 
            return 0
            ;;
        *)
            print_info "测试已取消"
            return 1
            ;;
    esac
}

# 运行测试
run_test() {
    print_info "启动UDP通信测试..."
    
    # 构建命令
    cmd="python3 udp_test_with_ntp.py --mode=$MODE --local-ip=$LOCAL_IP --peer-ip=$PEER_IP --log-path=$LOG_PATH"
    
    if [[ "$MODE" == "sender" ]]; then
        cmd="$cmd --frequency=$FREQUENCY --packet-size=$PACKET_SIZE --running-time=$RUNNING_TIME"
    else
        cmd="$cmd --buffer-size=$BUFFER_SIZE --running-time=$RUNNING_TIME"
    fi
    
    # 添加NTP参数
    if [[ "$ENABLE_NTP" == "false" ]]; then
        cmd="$cmd --skip-ntp"
    else
        if [[ -n "$NTP_PEER_IP" ]]; then
            cmd="$cmd --ntp-peer-ip=$NTP_PEER_IP"
        fi
        if [[ "$SKIP_NTP_CONFIG" == "true" ]]; then
            cmd="$cmd --skip-ntp-config"
        fi
    fi
    
    # 添加GPS记录参数
    if [[ "$ENABLE_GPS" == "true" ]]; then
        cmd="$cmd --enable-gps --drone-id=$DRONE_ID --gps-interval=$GPS_INTERVAL"
        if [[ "$USE_SIM_TIME" == "true" ]]; then
            cmd="$cmd --use-sim-time"
        fi
    fi
    
    # 添加Nexfi通信状态记录参数
    if [[ "$ENABLE_NEXFI" == "true" ]]; then
        cmd="$cmd --enable-nexfi --nexfi-ip=$NEXFI_IP --nexfi-username=$NEXFI_USERNAME --nexfi-password=$NEXFI_PASSWORD --nexfi-interval=$NEXFI_INTERVAL --nexfi-device=$NEXFI_DEVICE"
    fi
    
    # 添加网络错误处理参数
    cmd="$cmd --network-retry-delay=$NETWORK_RETRY_DELAY --log-network-errors=$LOG_NETWORK_ERRORS"
    
    print_info "执行命令: $cmd"
    echo ""
    
    # 执行测试
    if eval "$cmd"; then
        print_success "测试完成！"
        print_info "日志文件保存在: $LOG_PATH"
        return 0
    else
        print_error "测试失败！"
        return 1
    fi
}

# 解析命令行参数
parse_args() {
    # 检查是否有帮助参数
    for arg in "$@"; do
        if [[ "$arg" == "-h" || "$arg" == "--help" ]]; then
            show_help
            exit 0
        fi
    done
    
    # 第一个参数必须是模式
    if [[ $# -eq 0 ]]; then
        show_help
        exit 1
    fi
    
    MODE="$1"
    shift
    
    # 验证模式
    if [[ "$MODE" != "sender" && "$MODE" != "receiver" ]]; then
        print_error "无效的模式: $MODE"
        echo "支持的模式: sender, receiver"
        exit 1
    fi
    
    # 解析其他参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --local-ip=*)
                LOCAL_IP="${1#*=}"
                shift
                ;;
            --peer-ip=*)
                PEER_IP="${1#*=}"
                shift
                ;;
            --log-path=*)
                LOG_PATH="${1#*=}"
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
            --buffer-size=*)
                BUFFER_SIZE="${1#*=}"
                shift
                ;;
            --skip-ntp)
                ENABLE_NTP=false
                shift
                ;;
            --ntp-peer-ip=*)
                NTP_PEER_IP="${1#*=}"
                shift
                ;;
            --skip-ntp-config)
                SKIP_NTP_CONFIG=true
                shift
                ;;
            --enable-gps)
                ENABLE_GPS=true
                shift
                ;;
            --drone-id=*)
                DRONE_ID="${1#*=}"
                shift
                ;;
            --gps-interval=*)
                GPS_INTERVAL="${1#*=}"
                shift
                ;;
            --use-sim-time)
                USE_SIM_TIME=true
                shift
                ;;
            --enable-nexfi)
                ENABLE_NEXFI=true
                shift
                ;;
            --nexfi-ip=*)
                NEXFI_IP="${1#*=}"
                shift
                ;;
            --nexfi-username=*)
                NEXFI_USERNAME="${1#*=}"
                shift
                ;;
            --nexfi-password=*)
                NEXFI_PASSWORD="${1#*=}"
                shift
                ;;
            --nexfi-interval=*)
                NEXFI_INTERVAL="${1#*=}"
                shift
                ;;
            --nexfi-device=*)
                NEXFI_DEVICE="${1#*=}"
                shift
                ;;
            --network-retry-delay=*)
                NETWORK_RETRY_DELAY="${1#*=}"
                shift
                ;;
            --log-network-errors=*)
                LOG_NETWORK_ERRORS="${1#*=}"
                shift
                ;;
            --enable-static-route)
                ENABLE_STATIC_ROUTE=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                print_error "未知选项: $1"
                echo "使用 --help 查看帮助信息"
                exit 1
                ;;
        esac
    done
}

# 主函数
main() {
    # 设置退出时清理 🆕
    trap cleanup_on_exit EXIT INT TERM
    
    # 解析参数
    parse_args "$@"
    
    # 显示标题
    echo ""
    echo "=========================================="
    echo "    无人机UDP通信测试系统"
    echo "      集成NTP时间同步"
    if [[ "$ENABLE_GPS" == "true" ]]; then
        echo "        + GPS数据记录"
    fi
    echo "=========================================="
    echo ""
    
    # 检查依赖
    if ! check_dependencies; then
        exit 1
    fi
    
    # 检查网络
    check_network
    
    # 配置静态路由
    if ! configure_static_route; then
        exit 1
    fi
    
    # 显示配置
    show_config
    
    # 确认启动
    if ! confirm_start; then
        exit 0
    fi
    
    # 运行测试
    if run_test; then
        exit 0
    else
        exit 1
    fi
}

# 执行主函数
main "$@" 