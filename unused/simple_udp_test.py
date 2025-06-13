#!/usr/bin/env python3
"""
简化的UDP通信测试 - 跳过NTP配置
"""

import sys
import argparse
import subprocess

def main():
    parser = argparse.ArgumentParser(description='简化UDP通信测试')
    parser.add_argument('--mode', choices=['sender', 'receiver'], required=True)
    parser.add_argument('--local-ip', required=True)
    parser.add_argument('--peer-ip', required=True)
    parser.add_argument('--time', type=int, default=60)
    parser.add_argument('--frequency', type=float, default=10)
    parser.add_argument('--packet-size', type=int, default=1000)
    
    args = parser.parse_args()
    
    print(f"启动简化UDP测试 - 模式: {args.mode}")
    print(f"本地IP: {args.local_ip}, 对方IP: {args.peer_ip}")
    
    if args.mode == 'sender':
        cmd = [
            'python3', 'udp_sender.py',
            '--local-ip', args.local_ip,
            '--local-port', '20002',
            '--remote-ip', args.peer_ip,
            '--remote-port', '20001',
            '--packet-size', str(args.packet_size),
            '--frequency', str(args.frequency),
            '--time', str(args.time),
            '--log-path', './logs'
        ]
    else:  # receiver
        cmd = [
            'python3', 'udp_receiver.py',
            '--local-ip', args.local_ip,
            '--local-port', '20001',
            '--buffer-size', '1500',
            '--time', str(args.time),
            '--log-path', './logs'
        ]
    
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True)
        print("测试完成！")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"测试失败: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 