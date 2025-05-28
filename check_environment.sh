#!/bin/bash

# 无人机UDP通信测试系统 - 环境检查脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查结果计数
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

# 打印函数
print_check() {
    echo -n "检查 $1... "
}

print_pass() {
    echo -e "${GREEN}[通过]${NC} $1"
    ((PASS_COUNT++))
}

print_fail() {
    echo -e "${RED}[失败]${NC} $1"
    ((FAIL_COUNT++))
}

print_warn() {
    echo -e "${YELLOW}[警告]${NC} $1"
    ((WARN_COUNT++))
}

echo "=========================================="
echo "    无人机UDP通信测试系统 - 环境检查"
echo "=========================================="
echo ""

# 1. 检查操作系统
print_check "操作系统"
if [[ -f /etc/os-release ]]; then
    OS_NAME=$(grep "^NAME=" /etc/os-release | cut -d'"' -f2)
    print_pass "$OS_NAME"
else
    print_fail "无法检测操作系统"
fi

# 2. 检查Python3
print_check "Python3"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    print_pass "版本 $PYTHON_VERSION"
else
    print_fail "Python3 未安装"
fi

# 3. 检查虚拟环境
print_check "Python虚拟环境"
if [[ -d "venv" ]]; then
    print_pass "venv 目录存在"
else
    print_fail "venv 目录不存在，请运行 setup.sh"
fi

# 4. 检查Python包（在虚拟环境中）
if [[ -d "venv" ]]; then
    source venv/bin/activate 2>/dev/null
    
    # 检查requests
    print_check "requests库"
    if python3 -c "import requests" 2>/dev/null; then
        VERSION=$(python3 -c "import requests; print(requests.__version__)")
        print_pass "版本 $VERSION"
    else
        print_fail "未安装"
    fi
    
    # 检查pandas
    print_check "pandas库"
    if python3 -c "import pandas" 2>/dev/null; then
        VERSION=$(python3 -c "import pandas; print(pandas.__version__)")
        print_pass "版本 $VERSION"
    else
        print_warn "未安装（数据分析需要）"
    fi
    
    # 检查numpy
    print_check "numpy库"
    if python3 -c "import numpy" 2>/dev/null; then
        VERSION=$(python3 -c "import numpy; print(numpy.__version__)")
        print_pass "版本 $VERSION"
    else
        print_warn "未安装（数据分析需要）"
    fi
fi

# 5. 检查chrony
print_check "chrony (NTP服务)"
if command -v chronyc &> /dev/null; then
    print_pass "已安装"
else
    print_fail "未安装，请运行: sudo apt-get install chrony"
fi

# 6. 检查网络工具
print_check "网络工具"
if command -v ping &> /dev/null && command -v netstat &> /dev/null; then
    print_pass "已安装"
else
    print_fail "缺少网络工具"
fi

# 7. 检查必要脚本文件
echo ""
echo "检查脚本文件："
SCRIPTS=(
    "start_test.sh"
    "udp_test_with_ntp.py"
    "udp_sender.py"
    "udp_receiver.py"
    "gps.py"
    "nexfi_client.py"
)

for script in "${SCRIPTS[@]}"; do
    print_check "$script"
    if [[ -f "$script" ]]; then
        if [[ -x "$script" ]]; then
            print_pass "存在且可执行"
        else
            print_warn "存在但不可执行"
        fi
    else
        print_fail "文件不存在"
    fi
done

# 8. 检查ROS2环境（可选）
echo ""
echo "检查可选组件："
print_check "ROS2环境"
if command -v ros2 &> /dev/null; then
    ROS_DISTRO=${ROS_DISTRO:-"未设置"}
    print_pass "ROS2 $ROS_DISTRO"
else
    print_warn "未安装（GPS记录需要）"
fi

# 9. 检查as2_python_api
print_check "as2_python_api"
if python3 -c "from as2_python_api.drone_interface_gps import DroneInterfaceGPS" 2>/dev/null; then
    print_pass "已安装"
else
    print_warn "未安装（GPS记录需要）"
fi

# 10. 检查网络连接
echo ""
echo "检查网络连接："
print_check "本地IP配置"
if ip addr show | grep -q "192.168.104"; then
    LOCAL_IP=$(ip addr show | grep "192.168.104" | awk '{print $2}' | cut -d'/' -f1 | head -1)
    print_pass "检测到 $LOCAL_IP"
else
    print_warn "未检测到192.168.104网段配置"
fi

# 11. 检查Nexfi设备连接
print_check "Nexfi设备 (192.168.104.1)"
if timeout 2 ping -c 1 192.168.104.1 &> /dev/null; then
    print_pass "可达"
elif timeout 2 curl -s http://192.168.104.1 &> /dev/null; then
    print_pass "HTTP可达"
else
    print_warn "不可达（Nexfi记录将使用模拟数据）"
fi

# 12. 检查日志目录
print_check "日志目录"
if [[ -d "logs" ]]; then
    print_pass "logs/ 目录存在"
else
    print_warn "logs/ 目录不存在，将自动创建"
fi

# 总结
echo ""
echo "=========================================="
echo "检查结果总结："
echo -e "通过: ${GREEN}$PASS_COUNT${NC}"
echo -e "失败: ${RED}$FAIL_COUNT${NC}"
echo -e "警告: ${YELLOW}$WARN_COUNT${NC}"
echo ""

if [[ $FAIL_COUNT -eq 0 ]]; then
    echo -e "${GREEN}环境检查通过！可以开始测试。${NC}"
    echo ""
    echo "下一步："
    echo "1. 激活虚拟环境: source venv/bin/activate"
    echo "2. 运行测试: ./start_test.sh sender 或 ./start_test.sh receiver"
else
    echo -e "${RED}环境检查失败！请先解决上述问题。${NC}"
    echo ""
    echo "建议："
    echo "1. 运行 ./setup.sh 自动安装依赖"
    echo "2. 查看 README_NTP_INTEGRATION.md 了解详细要求"
fi

echo "==========================================" 