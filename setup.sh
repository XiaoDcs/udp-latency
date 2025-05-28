#!/bin/bash

# 无人机UDP通信测试系统 - 环境部署脚本
# 一键部署脚本，自动安装依赖、配置环境

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 打印函数
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

print_header() {
    echo -e "${BLUE}=========================================="
    echo "无人机UDP通信测试系统 - 环境部署"
    echo -e "==========================================${NC}"
    echo ""
}

# 检查系统要求
check_system_requirements() {
    print_info "检查系统要求..."
    
    # 检查操作系统
    if [[ "$OSTYPE" != "linux-gnu"* ]]; then
        print_error "此系统需要Linux环境"
        exit 1
    fi
    
    # 检查Python3
    if ! command -v python3 &> /dev/null; then
        print_error "Python3未安装，请先安装Python3"
        exit 1
    fi
    
    python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
    print_success "Python版本: $python_version"
    
    # 检查pip3
    if ! command -v pip3 &> /dev/null; then
        print_warning "pip3未安装，尝试安装..."
        sudo apt-get update
        sudo apt-get install -y python3-pip
    fi
    
    print_success "系统要求检查通过"
}

# 安装系统依赖
install_system_dependencies() {
    print_info "安装系统依赖..."
    
    # 更新包列表
    print_info "更新包列表..."
    sudo apt-get update
    
    # 安装基本工具
    print_info "安装基本工具..."
    sudo apt-get install -y \
        curl \
        wget \
        net-tools \
        iputils-ping \
        chrony \
        python3-venv \
        python3-dev \
        build-essential
    
    print_success "系统依赖安装完成"
}

# 创建Python虚拟环境
setup_python_environment() {
    print_info "设置Python虚拟环境..."
    
    # 删除旧的虚拟环境（如果存在）
    if [[ -d "venv" ]]; then
        print_warning "删除旧的虚拟环境..."
        rm -rf venv
    fi
    
    # 创建新的虚拟环境
    print_info "创建虚拟环境..."
    python3 -m venv venv
    
    # 激活虚拟环境
    print_info "激活虚拟环境..."
    source venv/bin/activate
    
    # 升级pip
    print_info "升级pip..."
    pip install --upgrade pip
    
    # 安装Python依赖
    print_info "安装Python依赖..."
    pip install -r requirements.txt
    
    print_success "Python环境设置完成"
}

# 设置文件权限
setup_file_permissions() {
    print_info "设置文件权限..."
    
    # 设置脚本执行权限
    chmod +x start_test.sh
    chmod +x example_usage.sh
    chmod +x check_environment.sh
    chmod +x setup.sh
    
    # 设置Python脚本权限
    chmod +x udp_test_with_ntp.py
    chmod +x udp_sender.py
    chmod +x udp_receiver.py
    chmod +x gps.py
    
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

# 配置网络（可选）
configure_network() {
    print_info "检查网络配置..."
    
    # 检查是否已有默认IP配置
    if ip addr show | grep -q "192.168.104"; then
        print_success "检测到192.168.104网段配置"
    else
        print_warning "未检测到默认网段配置"
        print_info "如需配置静态IP，请参考README中的网络配置说明"
    fi
}

# 验证安装
verify_installation() {
    print_info "验证安装..."
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 检查Python脚本语法
    print_info "检查Python脚本语法..."
    python3 -m py_compile udp_test_with_ntp.py
    python3 -m py_compile udp_sender.py
    python3 -m py_compile udp_receiver.py
    python3 -m py_compile gps.py
    
    # 运行环境检查脚本
    print_info "运行环境检查..."
    ./check_environment.sh
    
    print_success "安装验证完成"
}

# 显示完成信息
show_completion_info() {
    echo ""
    echo -e "${GREEN}=========================================="
    echo "环境部署完成！"
    echo -e "==========================================${NC}"
    echo ""
    echo -e "${YELLOW}下一步操作：${NC}"
    echo ""
    echo "1. 激活Python虚拟环境："
    echo "   source venv/bin/activate"
    echo ""
    echo "2. 查看使用示例："
    echo "   ./example_usage.sh"
    echo ""
    echo "3. 运行基本测试："
    echo "   # 在第一台无人机上："
    echo "   ./start_test.sh sender"
    echo ""
    echo "   # 在第二台无人机上："
    echo "   ./start_test.sh receiver"
    echo ""
    echo "4. 查看详细文档："
    echo "   cat README_NTP_INTEGRATION.md"
    echo ""
    echo -e "${YELLOW}注意事项：${NC}"
    echo "- 确保两台无人机在同一网段"
    echo "- 如需GPS记录功能，请单独安装ROS2环境"
    echo "- 建议先运行接收端，再运行发送端"
    echo ""
    echo -e "${GREEN}环境部署成功！${NC}"
}

# 错误处理
handle_error() {
    print_error "部署过程中出现错误"
    print_info "请检查错误信息并重新运行setup.sh"
    exit 1
}

# 主函数
main() {
    # 设置错误处理
    set -e
    trap handle_error ERR
    
    print_header
    
    # 检查是否以root权限运行
    if [[ $EUID -eq 0 ]]; then
        print_error "请不要以root权限运行此脚本"
        print_info "脚本会在需要时自动请求sudo权限"
        exit 1
    fi
    
    # 执行部署步骤
    check_system_requirements
    install_system_dependencies
    setup_python_environment
    setup_file_permissions
    create_directories
    configure_network
    verify_installation
    show_completion_info
    
    print_success "环境部署完成！"
}

# 执行主函数
main "$@" 