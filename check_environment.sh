#!/bin/bash

# 无人机UDP通信测试系统 - 环境检查脚本
# 检查系统环境是否满足运行要求

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 检查结果统计
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0

# 打印函数
print_header() {
    echo -e "${BLUE}=========================================="
    echo "无人机UDP通信测试系统 - 环境检查"
    echo -e "==========================================${NC}"
    echo ""
}

print_check() {
    echo -n "检查 $1 ... "
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
}

print_pass() {
    echo -e "${GREEN}✓ 通过${NC}"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
}

print_fail() {
    echo -e "${RED}✗ 失败${NC}"
    if [ ! -z "$1" ]; then
        echo -e "  ${RED}原因: $1${NC}"
    fi
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
}

print_warning() {
    echo -e "${YELLOW}⚠ 警告${NC}"
    if [ ! -z "$1" ]; then
        echo -e "  ${YELLOW}说明: $1${NC}"
    fi
    WARNING_CHECKS=$((WARNING_CHECKS + 1))
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_summary() {
    echo ""
    echo -e "${BLUE}=========================================="
    echo "检查结果汇总"
    echo -e "==========================================${NC}"
    echo "总检查项: $TOTAL_CHECKS"
    echo -e "通过: ${GREEN}$PASSED_CHECKS${NC}"
    echo -e "警告: ${YELLOW}$WARNING_CHECKS${NC}"
    echo -e "失败: ${RED}$FAILED_CHECKS${NC}"
    echo ""
    
    if [ $FAILED_CHECKS -eq 0 ]; then
        echo -e "${GREEN}✓ 环境检查通过，可以运行测试系统${NC}"
        return 0
    else
        echo -e "${RED}✗ 环境检查失败，请解决上述问题后重试${NC}"
        return 1
    fi
}

# 检查基本系统环境
check_basic_system() {
    echo -e "${BLUE}=== 基本系统环境检查 ===${NC}"
    
    # 检查操作系统
    print_check "操作系统"
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        print_pass
        print_info "系统: $(lsb_release -d 2>/dev/null | cut -f2 || echo "Linux")"
    else
        print_fail "需要Linux系统"
    fi
    
    # 检查Python3
    print_check "Python3"
    if command -v python3 &> /dev/null; then
        python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
        print_pass
        print_info "版本: $python_version"
    else
        print_fail "Python3未安装"
    fi
    
    # 检查网络工具
    print_check "网络工具 (ping)"
    if command -v ping &> /dev/null; then
        print_pass
    else
        print_fail "ping命令不可用"
    fi
    
    # 检查sudo权限
    print_check "sudo权限"
    if sudo -n true 2>/dev/null; then
        print_pass
    else
        print_warning "需要sudo权限配置NTP"
    fi
    
    echo ""
}

# 检查必要文件
check_required_files() {
    echo -e "${BLUE}=== 必要文件检查 ===${NC}"
    
    files=("udp_test_with_ntp.py" "start_test.sh" "udp_sender.py" "udp_receiver.py" "gps.py")
    
    for file in "${files[@]}"; do
        print_check "文件 $file"
        if [[ -f "$file" ]]; then
            print_pass
        else
            print_fail "文件不存在"
        fi
    done
    
    # 检查脚本执行权限
    print_check "start_test.sh 执行权限"
    if [[ -x "start_test.sh" ]]; then
        print_pass
    else
        print_warning "建议添加执行权限: chmod +x start_test.sh"
    fi
    
    echo ""
}

# 检查Python依赖
check_python_dependencies() {
    echo -e "${BLUE}=== Python依赖检查 ===${NC}"
    
    # 基本依赖
    basic_deps=("socket" "time" "csv" "json" "subprocess" "threading" "logging")
    
    for dep in "${basic_deps[@]}"; do
        print_check "Python模块 $dep"
        if python3 -c "import $dep" &> /dev/null; then
            print_pass
        else
            print_fail "模块不可用"
        fi
    done
    
    echo ""
}

# 检查ROS2环境（GPS记录需要）
check_ros2_environment() {
    echo -e "${BLUE}=== ROS2环境检查 (GPS记录需要) ===${NC}"
    
    # 检查ROS2安装
    print_check "ROS2安装"
    if command -v ros2 &> /dev/null; then
        ros_distro=${ROS_DISTRO:-"未设置"}
        print_pass
        print_info "ROS发行版: $ros_distro"
    else
        print_warning "ROS2未安装或未source环境"
    fi
    
    # 检查rclpy
    print_check "rclpy模块"
    if python3 -c "import rclpy" &> /dev/null; then
        print_pass
    else
        print_warning "rclpy不可用，GPS记录功能无法使用"
    fi
    
    # 检查as2_python_api
    print_check "as2_python_api"
    if python3 -c "from as2_python_api.drone_interface_gps import DroneInterfaceGPS" &> /dev/null; then
        print_pass
    else
        print_warning "as2_python_api不可用，GPS记录功能无法使用"
    fi
    
    echo ""
}

# 检查网络配置
check_network_configuration() {
    echo -e "${BLUE}=== 网络配置检查 ===${NC}"
    
    # 检查默认IP配置
    print_check "默认IP地址 192.168.104.10"
    if ip addr show | grep -q "192.168.104.10"; then
        print_pass
    else
        print_warning "默认IP未配置，需要在启动时指定--local-ip"
    fi
    
    # 检查网络接口
    print_check "网络接口"
    interfaces=$(ip link show | grep -E "^[0-9]+:" | grep -v "lo:" | wc -l)
    if [ $interfaces -gt 0 ]; then
        print_pass
        print_info "可用网络接口数: $interfaces"
    else
        print_fail "没有可用的网络接口"
    fi
    
    # 检查防火墙状态
    print_check "防火墙状态"
    if command -v ufw &> /dev/null; then
        ufw_status=$(sudo ufw status 2>/dev/null | head -1)
        print_pass
        print_info "$ufw_status"
    else
        print_warning "ufw防火墙未安装"
    fi
    
    echo ""
}

# 检查NTP相关
check_ntp_requirements() {
    echo -e "${BLUE}=== NTP时间同步检查 ===${NC}"
    
    # 检查chrony
    print_check "chrony安装"
    if command -v chronyc &> /dev/null; then
        print_pass
        chrony_version=$(chronyc --version 2>&1 | head -1)
        print_info "$chrony_version"
    else
        print_warning "chrony未安装，系统会自动安装"
    fi
    
    # 检查systemctl
    print_check "systemctl (服务管理)"
    if command -v systemctl &> /dev/null; then
        print_pass
    else
        print_fail "systemctl不可用，无法管理chrony服务"
    fi
    
    echo ""
}

# 检查存储空间
check_storage_space() {
    echo -e "${BLUE}=== 存储空间检查 ===${NC}"
    
    print_check "当前目录可写"
    if [[ -w "." ]]; then
        print_pass
    else
        print_fail "当前目录不可写"
    fi
    
    print_check "磁盘空间"
    available_space=$(df . | tail -1 | awk '{print $4}')
    available_mb=$((available_space / 1024))
    
    if [ $available_mb -gt 100 ]; then
        print_pass
        print_info "可用空间: ${available_mb}MB"
    else
        print_warning "可用空间不足: ${available_mb}MB (建议>100MB)"
    fi
    
    echo ""
}

# 运行连接测试
run_connectivity_test() {
    echo -e "${BLUE}=== 网络连接测试 ===${NC}"
    
    # 测试本地回环
    print_check "本地回环连接"
    if ping -c 1 -W 1 127.0.0.1 &> /dev/null; then
        print_pass
    else
        print_fail "本地回环不可用"
    fi
    
    # 测试默认对端IP（如果可达）
    print_check "默认对端IP (192.168.104.20)"
    if ping -c 1 -W 3 192.168.104.20 &> /dev/null; then
        print_pass
    else
        print_warning "对端IP不可达（正常，对方可能未启动）"
    fi
    
    echo ""
}

# 主函数
main() {
    print_header
    
    check_basic_system
    check_required_files
    check_python_dependencies
    check_ros2_environment
    check_network_configuration
    check_ntp_requirements
    check_storage_space
    run_connectivity_test
    
    print_summary
    exit_code=$?
    
    echo ""
    echo -e "${BLUE}建议：${NC}"
    echo "1. 如果有警告项，建议解决后再运行测试"
    echo "2. GPS记录功能需要ROS2环境，如不需要可忽略相关警告"
    echo "3. 运行 ./example_usage.sh 查看使用示例"
    echo "4. 查看 README_NTP_INTEGRATION.md 了解详细说明"
    
    exit $exit_code
}

# 执行主函数
main "$@" 