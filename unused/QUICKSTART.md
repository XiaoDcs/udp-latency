# 🚀 快速入门指南

## 1. 克隆并部署

```bash
# 克隆仓库
git clone <repository-url>
cd udp-latency

# 一键部署环境
chmod +x setup.sh
./setup.sh
```

## 2. 立即开始测试

```bash
# 激活环境
source venv/bin/activate

# 在第一台无人机上运行发送端
./start_test.sh sender

# 在第二台无人机上运行接收端  
./start_test.sh receiver
```

## 3. 查看结果

测试完成后，日志文件保存在 `./logs/` 目录中。

## 4. 更多选项

```bash
# 查看帮助
./start_test.sh --help

# 查看详细文档
cat README_NTP_INTEGRATION.md

# 检查环境
./check_environment.sh
```

## 5. GPS记录功能（可选）

如需GPS记录，请先安装ROS2环境，然后：

```bash
# 启用GPS记录的测试
./start_test.sh sender --enable-gps --drone-id=drone0
./start_test.sh receiver --enable-gps --drone-id=drone1
```

---

**就这么简单！** 🎉

更多详细信息请查看 `README_NTP_INTEGRATION.md` 
