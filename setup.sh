#!/usr/bin/env bash
set -euo pipefail

# 无人机UDP通信测试系统 - 一键部署脚本
# 目标：最小可用、可重复执行（idempotent），只安装当前主流程所需依赖

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

VENV_DIR="venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

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

# 检查命令是否存在
have_cmd() {
    command -v "$1" >/dev/null 2>&1
}

# 在虚拟环境中运行命令
venv_exec() {
    # shellcheck disable=SC1090
    source "${VENV_DIR}/bin/activate"
    "$@"
}

# 检查系统要求
check_system() {
    print_info "检查系统要求..."
    
    # 检查Python3
    if ! have_cmd "${PYTHON_BIN}"; then
        print_error "Python3 未安装"
        return 1
    fi

    # 检查操作系统（仅用于决定是否自动 apt 安装）
    if [[ -f "/etc/os-release" ]]; then
        if ! grep -q -E "Ubuntu|Debian" "/etc/os-release"; then
            print_warning "检测到非Ubuntu/Debian系统：将跳过系统依赖自动安装（请手动安装 chrony/iproute2/tmux 等）"
        fi
    else
        print_warning "无法检测操作系统：将跳过系统依赖自动安装"
    fi

    print_success "系统检查通过"
    return 0
}

# 安装系统依赖
install_system_deps() {
    print_info "安装系统依赖..."

    if [[ ! -f "/etc/os-release" ]] || ! grep -q -E "Ubuntu|Debian" "/etc/os-release"; then
        print_warning "非Ubuntu/Debian环境：跳过 apt-get 自动安装"
        return 0
    fi

    if ! have_cmd "apt-get"; then
        print_warning "apt-get 未找到：跳过系统依赖自动安装"
        return 0
    fi

    if ! have_cmd "sudo"; then
        print_error "sudo 未找到：无法自动安装系统依赖"
        return 1
    fi

    # 更新包列表
    sudo apt-get update

    # 安装当前主流程所需的最小系统依赖
    # - chrony: NTP对时
    # - iproute2/iputils-ping: start_test.sh 与 udp_test_with_ntp.py 依赖 ip/ping
    # - python3-venv/python3-pip: 虚拟环境与依赖安装
    # - tmux: scripts/run_drone*_tmux.sh 推荐主流程依赖
    sudo apt-get install -y \
        python3-pip \
        python3-venv \
        chrony \
        iproute2 \
        iputils-ping \
        tmux \
        curl

    print_success "系统依赖安装完成"
}

# 创建Python虚拟环境
setup_python_env() {
    print_info "创建Python虚拟环境..."
    
    if [[ -d "${VENV_DIR}" ]]; then
        if [[ -f "${VENV_DIR}/bin/activate" ]]; then
            print_info "检测到已存在的虚拟环境：${VENV_DIR}/，将复用"
        else
            print_error "发现同名目录 '${VENV_DIR}'，但不是有效虚拟环境（缺少 bin/activate）"
            return 1
        fi
    else
        "${PYTHON_BIN}" -m venv "${VENV_DIR}"
    fi

    # 升级pip（在 venv 内）
    venv_exec python -m pip install --upgrade pip
    
    print_success "Python虚拟环境创建完成"
}

# 安装Python依赖
install_python_deps() {
    print_info "安装Python依赖包..."

    if [[ -f "requirements.txt" ]]; then
        venv_exec python -m pip install -r "requirements.txt"
    else
        # 兜底：主流程只有 Nexfi 需要 requests
        venv_exec python -m pip install "requests>=2.25.0"
    fi
    
    print_success "Python依赖安装完成"
}

# 设置文件权限
setup_permissions() {
    print_info "设置文件权限..."
    
    # 设置脚本可执行权限
    chmod +x "start_test.sh"
    chmod +x "udp_test_with_ntp.py"
    chmod +x "udp_sender.py"
    chmod +x "udp_receiver.py"
    chmod +x "gps.py"
    chmod +x "nexfi_client.py"
    chmod +x "check_environment.sh"
    
    print_success "文件权限设置完成"
}

# 创建必要目录
create_directories() {
    print_info "创建必要目录..."
    
    # 创建日志目录
    mkdir -p "logs"
    
    print_success "目录创建完成"
}

# 验证安装
verify_installation() {
    print_info "验证安装..."
    
    # 检查Python包
    venv_exec python -c "import requests; print('✓ requests 库已安装')"
    
    # 检查chrony
    if command -v chronyc &> /dev/null; then
        print_success "chrony 已安装"
    else
        print_warning "chrony 未正确安装"
    fi
    
    # 检查脚本文件
    local required_files=(
        "start_test.sh"
        "udp_test_with_ntp.py"
        "udp_sender.py"
        "udp_receiver.py"
        "gps.py"
        "nexfi_client.py"
        "check_environment.sh"
    )
    
    local missing_files=0
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            print_warning "缺少文件: $file"
            missing_files=$((missing_files + 1))
        fi
    done
    
    if [[ $missing_files -eq 0 ]]; then
        print_success "所有必要文件都存在"
    else
        print_warning "缺少 $missing_files 个文件"
    fi
}

# 显示使用说明
show_usage() {
    echo ""
    echo "=========================================="
    echo "        部署完成！"
    echo "=========================================="
    echo ""
    echo "使用方法："
    echo ""
    echo "1. 激活Python虚拟环境："
    echo "   source ${VENV_DIR}/bin/activate"
    echo ""
    echo "2. 运行测试（推荐先用 scripts/ 下 tmux 脚本）："
    echo "   ./scripts/run_drone12_tmux.sh   # 发送端（示例）"
    echo "   ./scripts/run_drone9_tmux.sh    # 接收端（示例）"
    echo ""
    echo "   或者手动："
    echo "   ./start_test.sh sender    # 发送端"
    echo "   ./start_test.sh receiver  # 接收端"
    echo ""
    echo "3. 查看帮助："
    echo "   ./start_test.sh --help"
    echo ""
    echo "4. 环境检查（可选）："
    echo "   ./check_environment.sh"
    echo ""
}

# 主函数
main() {
    echo ""
    echo "=========================================="
    echo "  无人机UDP通信测试系统 - 一键部署"
    echo "=========================================="
    echo ""
    
    # 检查系统
    if ! check_system; then
        print_error "系统检查失败，请手动解决问题后重试"
        exit 1
    fi
    
    # 安装系统依赖
    install_system_deps
    
    # 创建Python环境
    setup_python_env
    
    # 安装Python依赖
    install_python_deps
    
    # 设置权限
    setup_permissions
    
    # 创建目录
    create_directories
    
    # 验证安装
    verify_installation
    
    # 显示使用说明
    show_usage
    
    print_success "部署完成！"
}

# 执行主函数
main 
