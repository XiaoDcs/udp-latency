#!/usr/bin/env bash

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

# 默认检查参数（可通过环境变量覆盖）
EXPECTED_LAN_PREFIX="${EXPECTED_LAN_PREFIX:-192.168.104.}"
NEXFI_IP="${NEXFI_IP:-192.168.104.1}"
VENV_DIR="${VENV_DIR:-venv}"

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

have_cmd() {
    command -v "$1" >/dev/null 2>&1
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
    print_warn "无法检测操作系统（非Linux环境将跳过部分检查）"
fi

# 2. 检查Python3
print_check "Python3"
if have_cmd "python3"; then
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    print_pass "版本 $PYTHON_VERSION"
else
    print_fail "Python3 未安装"
fi

# 3. 检查虚拟环境
print_check "Python虚拟环境"
if [[ -f "${VENV_DIR}/bin/activate" ]]; then
    print_pass "${VENV_DIR}/bin/activate 存在"
else
    print_fail "${VENV_DIR}/bin/activate 不存在，请运行 ./setup.sh"
fi

# 4. 检查Python包（在虚拟环境中）
if [[ -f "${VENV_DIR}/bin/activate" ]]; then
    # shellcheck disable=SC1090
    source "${VENV_DIR}/bin/activate" 2>/dev/null || true

    print_check "requests库（启用 --enable-nexfi 时需要）"
    if python3 -c "import requests" 2>/dev/null; then
        VERSION=$(python3 -c "import requests; print(requests.__version__)")
        print_pass "版本 $VERSION"
    else
        print_warn "未安装（不启用 Nexfi 仍可运行）"
    fi
fi

# 5. 检查chrony
print_check "chrony (NTP服务)"
if have_cmd "chronyc"; then
    print_pass "已安装"
else
    print_fail "未安装（默认NTP对时需要）。建议: sudo apt-get install chrony"
fi

# 6. 检查常用系统/网络工具（主流程依赖）
print_check "ip/ping/timeout"
missing_tools=()
for tool in ip ping timeout; do
    if ! have_cmd "$tool"; then
        missing_tools+=("$tool")
    fi
done
if [[ ${#missing_tools[@]} -eq 0 ]]; then
    print_pass "已安装"
else
    print_fail "缺少: ${missing_tools[*]}"
fi

# 7. 检查tmux（scripts/ 主流程推荐使用）
print_check "tmux（scripts/ 推荐主流程）"
if have_cmd "tmux"; then
    print_pass "已安装"
else
    print_warn "未安装（不影响手动运行 start_test.sh）"
fi

# 8. 检查必要脚本文件
echo ""
echo "检查脚本文件："
SCRIPTS=(
    "setup.sh"
    "start_test.sh"
    "udp_test_with_ntp.py"
    "udp_sender.py"
    "udp_receiver.py"
    "gps.py"
    "nexfi_client.py"
    "check_environment.sh"
    "scripts/run_drone12_tmux.sh"
    "scripts/run_drone9_tmux.sh"
    "scripts/stop_aerostack_tmux.sh"
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

# 9. 检查ROS2环境（可选）
echo ""
echo "检查可选组件："
print_check "ROS2环境"
if have_cmd "ros2"; then
    ROS_DISTRO=${ROS_DISTRO:-"未设置"}
    print_pass "ROS2 $ROS_DISTRO"
else
    print_warn "未安装（GPS记录需要）"
fi

# 10. 检查as2_python_api
print_check "as2_python_api"
if python3 -c "from as2_python_api.drone_interface_gps import DroneInterfaceGPS" 2>/dev/null; then
    print_pass "已安装"
else
    print_warn "未安装或未source环境（GPS记录需要）"
fi

# 11. 检查网络连接
echo ""
echo "检查网络连接："
print_check "本地IP配置（期望网段: ${EXPECTED_LAN_PREFIX}*）"
if have_cmd "ip"; then
    if ip -o -4 addr show | grep -q "${EXPECTED_LAN_PREFIX}"; then
        LOCAL_IP=$(ip -o -4 addr show | grep "${EXPECTED_LAN_PREFIX}" | awk '{print $4}' | cut -d'/' -f1 | head -1)
        print_pass "检测到 $LOCAL_IP"
    else
        print_warn "未检测到 ${EXPECTED_LAN_PREFIX} 网段配置（如使用其他网段可忽略或设置 EXPECTED_LAN_PREFIX）"
    fi
else
    print_warn "ip 命令不可用，跳过本地IP检查"
fi

# 12. 检查Nexfi设备连接（可选）
print_check "Nexfi设备 (${NEXFI_IP})"
if timeout 2 ping -c 1 "${NEXFI_IP}" &> /dev/null; then
    print_pass "可达"
elif have_cmd "curl" && timeout 2 curl -s "http://${NEXFI_IP}" &> /dev/null; then
    print_pass "HTTP可达"
else
    print_warn "不可达（Nexfi记录将被跳过）"
fi

# 13. 检查日志目录
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
    echo "2. 查看 README_DETAIL.md 了解详细要求"
fi

echo "==========================================" 
