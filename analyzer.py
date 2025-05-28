#!/usr/bin/env python3
import os
import sys
import pandas as pd
import numpy as np
import glob
import json
import argparse
from typing import Dict, List, Any, Optional, Tuple

class UDPTestAnalyzer:
    """
    UDP通信测试分析器，用于处理和分析测试日志，
    生成综合报告，包括丢包率、延迟、GPS位置和通信模块状态等信息。
    """
    def __init__(
        self,
        sender_log: str,
        receiver_log: str,
        sender_gps_log: Optional[str] = None,
        receiver_gps_log: Optional[str] = None,
        sender_comms_log: Optional[str] = None,
        receiver_comms_log: Optional[str] = None,
        output_path: str = "./analysis",
        output_format: str = "csv"
    ) -> None:
        """
        初始化分析器
        Args:
            sender_log: 发送端UDP日志文件路径
            receiver_log: 接收端UDP日志文件路径
            sender_gps_log: 发送端GPS日志文件路径(可选)
            receiver_gps_log: 接收端GPS日志文件路径(可选)
            sender_comms_log: 发送端通信模块日志文件路径(可选)
            receiver_comms_log: 接收端通信模块日志文件路径(可选)
            output_path: 输出目录路径
            output_format: 输出格式(csv或json)
        """
        self.sender_log = sender_log
        self.receiver_log = receiver_log
        self.sender_gps_log = sender_gps_log
        self.receiver_gps_log = receiver_gps_log
        self.sender_comms_log = sender_comms_log
        self.receiver_comms_log = receiver_comms_log
        self.output_path = output_path
        self.output_format = output_format
        
        # 确保输出目录存在
        os.makedirs(output_path, exist_ok=True)
        
        # 初始化数据框
        self.df_sender = None
        self.df_receiver = None
        self.df_sender_gps = None
        self.df_receiver_gps = None
        self.df_sender_comms = None
        self.df_receiver_comms = None
        self.df_merged = None
    
    def load_data(self) -> None:
        """
        加载所有日志文件数据
        """
        print("Loading data files...")
        
        # 加载UDP发送日志
        if os.path.exists(self.sender_log):
            self.df_sender = pd.read_csv(self.sender_log)
            print(f"Loaded sender log: {len(self.df_sender)} records")
        else:
            print(f"Warning: Sender log file not found: {self.sender_log}")
            self.df_sender = pd.DataFrame()
        
        # 加载UDP接收日志
        if os.path.exists(self.receiver_log):
            self.df_receiver = pd.read_csv(self.receiver_log)
            print(f"Loaded receiver log: {len(self.df_receiver)} records")
        else:
            print(f"Warning: Receiver log file not found: {self.receiver_log}")
            self.df_receiver = pd.DataFrame()
        
        # 加载GPS日志(如果存在)
        if self.sender_gps_log and os.path.exists(self.sender_gps_log):
            self.df_sender_gps = pd.read_csv(self.sender_gps_log)
            print(f"Loaded sender GPS log: {len(self.df_sender_gps)} records")
        
        if self.receiver_gps_log and os.path.exists(self.receiver_gps_log):
            self.df_receiver_gps = pd.read_csv(self.receiver_gps_log)
            print(f"Loaded receiver GPS log: {len(self.df_receiver_gps)} records")
        
        # 加载通信模块日志(如果存在)
        if self.sender_comms_log and os.path.exists(self.sender_comms_log):
            self.df_sender_comms = pd.read_csv(self.sender_comms_log)
            print(f"Loaded sender comms log: {len(self.df_sender_comms)} records")
        
        if self.receiver_comms_log and os.path.exists(self.receiver_comms_log):
            self.df_receiver_comms = pd.read_csv(self.receiver_comms_log)
            print(f"Loaded receiver comms log: {len(self.df_receiver_comms)} records")
    
    def process_data(self) -> None:
        """
        处理数据，包括:
        1. 合并发送和接收日志
        2. 识别丢失的数据包
        3. 计算延迟统计
        4. 与GPS和通信模块日志关联
        """
        if len(self.df_sender) == 0 or len(self.df_receiver) == 0:
            print("Error: Cannot process data without sender and receiver logs")
            return
        
        print("Processing data...")
        
        # 确保发送端日志有时间戳列
        if 'timestamp' not in self.df_sender.columns:
            print("Error: Sender log missing 'timestamp' column")
            return
        
        # 确保接收端日志有seq_num和send_timestamp列
        if 'seq_num' not in self.df_receiver.columns or 'send_timestamp' not in self.df_receiver.columns:
            print("Error: Receiver log missing required columns")
            return
        
        # 创建所有发送包的完整序列
        all_seq_nums = set(self.df_sender['seq_num'].unique())
        received_seq_nums = set(self.df_receiver['seq_num'].unique())
        lost_seq_nums = all_seq_nums - received_seq_nums
        
        print(f"Total packets sent: {len(all_seq_nums)}")
        print(f"Packets received: {len(received_seq_nums)}")
        print(f"Packets lost: {len(lost_seq_nums)}")
        
        # 计算丢包率
        packet_loss_rate = len(lost_seq_nums) / len(all_seq_nums) * 100 if all_seq_nums else 0
        print(f"Packet loss rate: {packet_loss_rate:.2f}%")
        
        # 合并发送和接收日志
        # 右连接以包含接收到的所有包
        merged_df = pd.merge(
            self.df_sender,
            self.df_receiver,
            on='seq_num',
            how='outer',
            suffixes=('_sender', '_receiver')
        )
        
        # 标记丢失的包
        merged_df['packet_lost'] = merged_df['recv_timestamp'].isna()
        
        # 对于接收到的包，计算延迟
        merged_df['delay'] = np.where(
            merged_df['packet_lost'],
            np.nan,
            merged_df['recv_timestamp'] - merged_df['send_timestamp']
        )
        
        # 添加GPS数据(如果有)
        if self.df_sender_gps is not None:
            # 确保GPS数据有时间戳列
            if 'timestamp' in self.df_sender_gps.columns:
                # 使用最近邻匹配将GPS数据与发送时间关联
                sender_gps_cols = [col for col in self.df_sender_gps.columns if col != 'timestamp']
                merged_df = pd.merge_asof(
                    merged_df.sort_values('timestamp_sender'),
                    self.df_sender_gps.sort_values('timestamp'),
                    left_on='timestamp_sender',
                    right_on='timestamp',
                    direction='nearest',
                    suffixes=('', '_sender_gps')
                )
                
                # 重命名GPS列以便区分
                for col in sender_gps_cols:
                    if col in merged_df.columns and f"{col}_sender_gps" not in merged_df.columns:
                        merged_df.rename(columns={col: f"{col}_sender_gps"}, inplace=True)
        
        if self.df_receiver_gps is not None and not merged_df['packet_lost'].all():
            # 确保GPS数据有时间戳列
            if 'timestamp' in self.df_receiver_gps.columns:
                # 使用最近邻匹配将GPS数据与接收时间关联
                receiver_gps_cols = [col for col in self.df_receiver_gps.columns if col != 'timestamp']
                # 只对接收到的包进行匹配
                received_df = merged_df[~merged_df['packet_lost']].copy()
                received_df = pd.merge_asof(
                    received_df.sort_values('recv_timestamp'),
                    self.df_receiver_gps.sort_values('timestamp'),
                    left_on='recv_timestamp',
                    right_on='timestamp',
                    direction='nearest',
                    suffixes=('', '_receiver_gps')
                )
                
                # 重命名GPS列以便区分
                for col in receiver_gps_cols:
                    if col in received_df.columns and f"{col}_receiver_gps" not in received_df.columns:
                        received_df.rename(columns={col: f"{col}_receiver_gps"}, inplace=True)
                
                # 合并回主数据框
                merged_df = pd.merge(
                    merged_df,
                    received_df[['seq_num'] + [f"{col}_receiver_gps" for col in receiver_gps_cols if f"{col}_receiver_gps" in received_df.columns]],
                    on='seq_num',
                    how='left'
                )
        
        # 添加通信模块数据(如果有)
        if self.df_sender_comms is not None:
            if 'timestamp' in self.df_sender_comms.columns:
                sender_comms_cols = [col for col in self.df_sender_comms.columns if col != 'timestamp']
                merged_df = pd.merge_asof(
                    merged_df.sort_values('timestamp_sender'),
                    self.df_sender_comms.sort_values('timestamp'),
                    left_on='timestamp_sender',
                    right_on='timestamp',
                    direction='nearest',
                    suffixes=('', '_sender_comms')
                )
                
                for col in sender_comms_cols:
                    if col in merged_df.columns and f"{col}_sender_comms" not in merged_df.columns:
                        merged_df.rename(columns={col: f"{col}_sender_comms"}, inplace=True)
        
        if self.df_receiver_comms is not None and not merged_df['packet_lost'].all():
            if 'timestamp' in self.df_receiver_comms.columns:
                receiver_comms_cols = [col for col in self.df_receiver_comms.columns if col != 'timestamp']
                received_df = merged_df[~merged_df['packet_lost']].copy()
                received_df = pd.merge_asof(
                    received_df.sort_values('recv_timestamp'),
                    self.df_receiver_comms.sort_values('timestamp'),
                    left_on='recv_timestamp',
                    right_on='timestamp',
                    direction='nearest',
                    suffixes=('', '_receiver_comms')
                )
                
                for col in receiver_comms_cols:
                    if col in received_df.columns and f"{col}_receiver_comms" not in received_df.columns:
                        received_df.rename(columns={col: f"{col}_receiver_comms"}, inplace=True)
                
                merged_df = pd.merge(
                    merged_df,
                    received_df[['seq_num'] + [f"{col}_receiver_comms" for col in receiver_comms_cols if f"{col}_receiver_comms" in received_df.columns]],
                    on='seq_num',
                    how='left'
                )
        
        # 保存处理后的数据
        self.df_merged = merged_df
        
        # 计算统计信息
        if not merged_df['delay'].isna().all():
            delay_stats = {
                'min_delay': merged_df['delay'].min(),
                'max_delay': merged_df['delay'].max(),
                'avg_delay': merged_df['delay'].mean(),
                'median_delay': merged_df['delay'].median(),
                'std_delay': merged_df['delay'].std(),
                'packet_loss_rate': packet_loss_rate
            }
            print("\nDelay Statistics:")
            print(f"Min delay: {delay_stats['min_delay']:.6f} seconds")
            print(f"Max delay: {delay_stats['max_delay']:.6f} seconds")
            print(f"Average delay: {delay_stats['avg_delay']:.6f} seconds")
            print(f"Median delay: {delay_stats['median_delay']:.6f} seconds")
            print(f"Standard deviation: {delay_stats['std_delay']:.6f} seconds")
            
            # 保存统计信息
            with open(os.path.join(self.output_path, 'statistics.json'), 'w') as f:
                json.dump(delay_stats, f, indent=4)
    
    def save_results(self) -> None:
        """
        保存分析结果到CSV或JSON文件
        """
        if self.df_merged is None or len(self.df_merged) == 0:
            print("No data to save")
            return
        
        print("\nSaving results...")
        
        # 创建输出文件名
        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(self.output_path, f"udp_test_results_{timestamp}")
        
        # 根据格式保存
        if self.output_format.lower() == 'csv':
            csv_file = f"{output_file}.csv"
            self.df_merged.to_csv(csv_file, index=False)
            print(f"Results saved to {csv_file}")
        
        elif self.output_format.lower() == 'json':
            json_file = f"{output_file}.json"
            # 将数据转换为JSON格式(每行一个记录)
            with open(json_file, 'w') as f:
                f.write(self.df_merged.to_json(orient='records', lines=True))
            print(f"Results saved to {json_file}")
        
        else:
            print(f"Unsupported output format: {self.output_format}")
    
    def analyze(self) -> None:
        """
        执行完整的分析流程
        """
        self.load_data()
        self.process_data()
        self.save_results()
        print("\nAnalysis completed")


def parse_args() -> argparse.Namespace:
    """
    解析命令行参数
    """
    parser = argparse.ArgumentParser(description='Analyze UDP communication test results')
    
    parser.add_argument('--sender-log', required=True, 
                        help='Path to sender UDP log file')
    parser.add_argument('--receiver-log', required=True, 
                        help='Path to receiver UDP log file')
    parser.add_argument('--sender-gps', 
                        help='Path to sender GPS log file')
    parser.add_argument('--receiver-gps', 
                        help='Path to receiver GPS log file')
    parser.add_argument('--sender-comms', 
                        help='Path to sender communication module log file')
    parser.add_argument('--receiver-comms', 
                        help='Path to receiver communication module log file')
    parser.add_argument('--output-path', default='./analysis', 
                        help='Output directory path')
    parser.add_argument('--output-format', choices=['csv', 'json'], default='csv', 
                        help='Output file format')
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    analyzer = UDPTestAnalyzer(
        sender_log=args.sender_log,
        receiver_log=args.receiver_log,
        sender_gps_log=args.sender_gps,
        receiver_gps_log=args.receiver_gps,
        sender_comms_log=args.sender_comms,
        receiver_comms_log=args.receiver_comms,
        output_path=args.output_path,
        output_format=args.output_format
    )
    
    analyzer.analyze() 