#!/bin/bash

# 无人机UDP通信测试系统 - 一键部署脚本
# 自动安装所有依赖并配置环境

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

# 检查系统要求
check_system() {
    print_info "检查系统要求..."
    
    # 检查操作系统
    if [[ ! -f /etc/os-release ]]; then
        print_error "无法检测操作系统"
        return 1
    fi
    
    # 检查是否为Ubuntu/Debian
    if ! grep -q -E "Ubuntu|Debian" /etc/os-release; then
        print_warning "此脚本针对Ubuntu/Debian系统优化，其他系统可能需要手动调整"
    fi
    
    # 检查Python3
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 未安装"
        return 1
    fi
    
    print_success "系统检查通过"
    return 0
}

# 安装系统依赖
install_system_deps() {
    print_info "安装系统依赖..."
    
    # 更新包列表
    sudo apt-get update
    
    # 安装基本工具
    sudo apt-get install -y \
        python3-pip \
        python3-venv \
        chrony \
        net-tools \
        iputils-ping \
        curl \
        git
    
    print_success "系统依赖安装完成"
}

# 创建Python虚拟环境
setup_python_env() {
    print_info "创建Python虚拟环境..."
    
    # 创建虚拟环境
    python3 -m venv venv
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 升级pip
    pip install --upgrade pip
    
    print_success "Python虚拟环境创建完成"
}

# 安装Python依赖
install_python_deps() {
    print_info "安装Python依赖包..."
    
    # 确保在虚拟环境中
    source venv/bin/activate
    
    # 安装requirements.txt中的依赖
    if [[ -f requirements.txt ]]; then
        pip install -r requirements.txt
    else
        # 如果没有requirements.txt，安装基本依赖
        pip install requests>=2.25.0
        pip install pandas>=1.3.0
        pip install numpy>=1.20.0
        pip install matplotlib>=3.4.0
        pip install psutil>=5.8.0
    fi
    
    print_success "Python依赖安装完成"
}

# 设置文件权限
setup_permissions() {
    print_info "设置文件权限..."
    
    # 设置脚本可执行权限
    chmod +x start_test.sh
    chmod +x udp_test_with_ntp.py
    chmod +x udp_sender.py
    chmod +x udp_receiver.py
    chmod +x gps.py
    chmod +x nexfi_client.py
    
    print_success "文件权限设置完成"
}

# 创建必要目录
create_directories() {
    print_info "创建必要目录..."
    
    # 创建日志目录
    mkdir -p logs
    
    # 创建备份目录
    mkdir -p backups
    
    print_success "目录创建完成"
}

# 验证安装
verify_installation() {
    print_info "验证安装..."
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 检查Python包
    python3 -c "import requests; print('✓ requests 库已安装')"
    python3 -c "import pandas; print('✓ pandas 库已安装')"
    python3 -c "import numpy; print('✓ numpy 库已安装')"
    
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
    echo "   source venv/bin/activate"
    echo ""
    echo "2. 运行测试："
    echo "   ./start_test.sh sender    # 发送端"
    echo "   ./start_test.sh receiver  # 接收端"
    echo ""
    echo "3. 查看帮助："
    echo "   ./start_test.sh --help"
    echo ""
    echo "4. 查看示例："
    echo "   cat example_usage.sh"
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