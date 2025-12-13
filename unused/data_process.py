#!/usr/bin/env python3
"""
数据处理脚本
处理GPS和Nexfi状态数据文件，进行拆分和合并操作
"""

import os
import pandas as pd
import numpy as np
import glob
from datetime import datetime
import argparse
import sys
from typing import List, Dict, Optional
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataProcessor:
    """数据处理类，用于处理GPS和Nexfi状态数据"""
    
    def __init__(self, logs_path: str = "./logs"):
        """
        初始化数据处理器
        
        Args:
            logs_path: 日志文件路径
        """
        self.logs_path = logs_path
        self.processed_data_path = os.path.join(logs_path, "processed_data")
        
        # 确保输出目录存在
        os.makedirs(self.processed_data_path, exist_ok=True)
        
        logger.info(f"数据处理器初始化完成")
        logger.info(f"日志路径: {self.logs_path}")
        logger.info(f"处理后数据保存路径: {self.processed_data_path}")
    
    def find_files(self, pattern: str) -> List[str]:
        """
        查找匹配模式的文件
        
        Args:
            pattern: 文件模式
            
        Returns:
            匹配的文件列表
        """
        file_pattern = os.path.join(self.logs_path, pattern)
        files = glob.glob(file_pattern)
        files.sort()  # 按文件名排序
        return files
    
    def load_gps_data(self, file_path: str) -> pd.DataFrame:
        """
        加载GPS数据文件
        
        Args:
            file_path: GPS数据文件路径
            
        Returns:
            GPS数据DataFrame
        """
        try:
            # 读取CSV文件
            df = pd.read_csv(file_path)
            
            # 确保timestamp列存在
            if 'timestamp' not in df.columns:
                logger.error(f"GPS文件 {file_path} 缺少timestamp列")
                return pd.DataFrame()
            
            # 确保timestamp为数值型
            df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
            
            # 删除无效行
            df = df.dropna(subset=['timestamp'])
            
            logger.info(f"成功加载GPS数据: {file_path}, 共{len(df)}行")
            return df
            
        except Exception as e:
            logger.error(f"加载GPS数据文件失败 {file_path}: {e}")
            return pd.DataFrame()
    
    def load_nexfi_data(self, file_path: str) -> pd.DataFrame:
        """
        加载Nexfi状态数据文件
        
        Args:
            file_path: Nexfi数据文件路径
            
        Returns:
            Nexfi数据DataFrame
        """
        try:
            # 读取CSV文件
            df = pd.read_csv(file_path)
            
            # 确保必要列存在
            required_columns = ['timestamp', 'connected_node_id', 'node_id']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                logger.error(f"Nexfi文件 {file_path} 缺少必要列: {missing_columns}")
                return pd.DataFrame()
            
            # 确保timestamp为数值型
            df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
            
            # 删除无效行
            df = df.dropna(subset=['timestamp'])
            
            logger.info(f"成功加载Nexfi数据: {file_path}, 共{len(df)}行")
            return df
            
        except Exception as e:
            logger.error(f"加载Nexfi数据文件失败 {file_path}: {e}")
            return pd.DataFrame()
    
    def split_nexfi_by_connected_nodes(self, nexfi_df: pd.DataFrame, source_file: str) -> Dict[str, pd.DataFrame]:
        """
        根据connected_node_id拆分Nexfi数据
        
        Args:
            nexfi_df: Nexfi数据DataFrame
            source_file: 源文件名（用于生成输出文件名）
            
        Returns:
            按connected_node_id分组的字典
        """
        if nexfi_df.empty:
            return {}
        
        # 获取所有唯一的connected_node_id值
        unique_connected_node_ids = nexfi_df['connected_node_id'].unique()
        unique_connected_node_ids = sorted([x for x in unique_connected_node_ids if pd.notna(x)])
        
        split_data = {}
        
        for node_id in unique_connected_node_ids:
            # 过滤数据
            filtered_df = nexfi_df[nexfi_df['connected_node_id'] == node_id].copy()
            
            if not filtered_df.empty:
                # 生成输出文件名
                base_name = os.path.splitext(os.path.basename(source_file))[0]
                output_filename = f"{base_name}_node_{node_id}.csv"
                
                # 保存拆分后的数据
                output_path = os.path.join(self.processed_data_path, output_filename)
                filtered_df.to_csv(output_path, index=False)
                
                split_data[f"node_{node_id}"] = filtered_df
                logger.info(f"拆分Nexfi数据: connected_node_id={node_id}, 共{len(filtered_df)}行, 保存到: {output_filename}")
        
        return split_data
    
    def merge_with_gps_data(self, gps_df: pd.DataFrame, nexfi_split_data: Dict[str, pd.DataFrame], 
                           gps_source_file: str, nexfi_source_file: str) -> None:
        """
        将GPS数据与拆分后的Nexfi数据按时间戳合并
        
        Args:
            gps_df: GPS数据DataFrame
            nexfi_split_data: 拆分后的Nexfi数据字典
            gps_source_file: GPS源文件名
            nexfi_source_file: Nexfi源文件名
        """
        if gps_df.empty:
            logger.warning("GPS数据为空，跳过合并")
            return
        
        gps_base_name = os.path.splitext(os.path.basename(gps_source_file))[0]
        nexfi_base_name = os.path.splitext(os.path.basename(nexfi_source_file))[0]
        
        for split_key, nexfi_df in nexfi_split_data.items():
            if nexfi_df.empty:
                continue
            
            try:
                # 使用时间戳进行合并（使用最近邻合并）
                merged_df = self.merge_by_timestamp(gps_df, nexfi_df)
                
                if not merged_df.empty:
                    # 生成合并后的文件名
                    output_filename = f"merged_{gps_base_name}_{nexfi_base_name}_{split_key}.csv"
                    output_path = os.path.join(self.processed_data_path, output_filename)
                    
                    # 保存合并后的数据
                    merged_df.to_csv(output_path, index=False)
                    logger.info(f"合并数据保存到: {output_filename}, 共{len(merged_df)}行")
                else:
                    logger.warning(f"合并后数据为空: {split_key}")
                    
            except Exception as e:
                logger.error(f"合并数据时出错 {split_key}: {e}")
    
    def merge_by_timestamp(self, gps_df: pd.DataFrame, nexfi_df: pd.DataFrame, 
                          tolerance: float = 1.0) -> pd.DataFrame:
        """
        根据时间戳合并GPS和Nexfi数据
        
        Args:
            gps_df: GPS数据DataFrame
            nexfi_df: Nexfi数据DataFrame
            tolerance: 时间戳匹配容忍度（秒）
            
        Returns:
            合并后的DataFrame
        """
        try:
            # 确保两个DataFrame都有timestamp列
            if 'timestamp' not in gps_df.columns or 'timestamp' not in nexfi_df.columns:
                logger.error("缺少timestamp列")
                return pd.DataFrame()
            
            # 创建副本以避免修改原始数据
            gps_copy = gps_df.copy()
            nexfi_copy = nexfi_df.copy()
            
            # 添加前缀以区分列
            gps_copy = gps_copy.add_prefix('gps_')
            nexfi_copy = nexfi_copy.add_prefix('nexfi_')
            
            # 重命名timestamp列
            gps_copy.rename(columns={'gps_timestamp': 'timestamp'}, inplace=True)
            nexfi_copy.rename(columns={'nexfi_timestamp': 'nexfi_timestamp'}, inplace=True)
            
            # 使用pandas的merge_asof进行时间戳匹配
            # 先按timestamp排序
            gps_copy = gps_copy.sort_values('timestamp')
            nexfi_copy = nexfi_copy.sort_values('nexfi_timestamp')
            
            # 使用merge_asof进行最近邻合并
            merged_df = pd.merge_asof(
                gps_copy, 
                nexfi_copy,
                left_on='timestamp',
                right_on='nexfi_timestamp',
                tolerance=tolerance,
                direction='nearest'
            )
            
            # 计算时间差
            merged_df['time_diff'] = abs(merged_df['timestamp'] - merged_df['nexfi_timestamp'])
            
            # 过滤掉时间差太大的记录
            merged_df = merged_df[merged_df['time_diff'] <= tolerance]
            
            return merged_df
            
        except Exception as e:
            logger.error(f"时间戳合并失败: {e}")
            return pd.DataFrame()
    
    def get_latest_file(self, files: List[str]) -> Optional[str]:
        """
        获取最新的文件（基于修改时间）
        
        Args:
            files: 文件列表
            
        Returns:
            最新的文件路径，如果没有文件则返回None
        """
        if not files:
            return None
        
        # 获取每个文件的修改时间
        file_times = []
        for file in files:
            try:
                mtime = os.path.getmtime(file)
                file_times.append((file, mtime))
            except OSError:
                logger.warning(f"无法获取文件修改时间: {file}")
                continue
        
        if not file_times:
            return None
        
        # 按修改时间排序，获取最新的
        file_times.sort(key=lambda x: x[1], reverse=True)
        latest_file = file_times[0][0]
        latest_time = datetime.fromtimestamp(file_times[0][1])
        
        logger.info(f"选择最新文件: {os.path.basename(latest_file)} (修改时间: {latest_time})")
        return latest_file

    def process_files(self, gps_pattern: str = "gps_logger_drone1_*.csv", 
                     nexfi_pattern: str = "nexfi_status_*.csv") -> None:
        """
        处理时间最近的GPS和Nexfi文件
        
        Args:
            gps_pattern: GPS文件模式
            nexfi_pattern: Nexfi文件模式
        """
        logger.info("开始处理文件...")
        
        # 查找文件
        gps_files = self.find_files(gps_pattern)
        nexfi_files = self.find_files(nexfi_pattern)
        
        if not gps_files:
            logger.warning(f"未找到匹配的GPS文件: {gps_pattern}")
            return
        if not nexfi_files:
            logger.warning(f"未找到匹配的Nexfi文件: {nexfi_pattern}")
            return
        
        logger.info(f"找到GPS文件: {len(gps_files)}个")
        logger.info(f"找到Nexfi文件: {len(nexfi_files)}个")
        
        # 获取最新的文件
        latest_gps_file = self.get_latest_file(gps_files)
        latest_nexfi_file = self.get_latest_file(nexfi_files)
        
        if not latest_gps_file:
            logger.error("没有有效的GPS文件")
            return
        if not latest_nexfi_file:
            logger.error("没有有效的Nexfi文件")
            return
        
        logger.info(f"处理最新的GPS文件: {os.path.basename(latest_gps_file)}")
        logger.info(f"处理最新的Nexfi文件: {os.path.basename(latest_nexfi_file)}")
        
        # 加载Nexfi数据
        nexfi_df = self.load_nexfi_data(latest_nexfi_file)
        if nexfi_df.empty:
            logger.error("Nexfi数据为空")
            return
        
        # 根据connected_node_id拆分
        nexfi_split_data = self.split_nexfi_by_connected_nodes(nexfi_df, latest_nexfi_file)
        
        # 加载GPS数据
        gps_df = self.load_gps_data(latest_gps_file)
        if gps_df.empty:
            logger.error("GPS数据为空")
            return
        
        # 合并数据
        self.merge_with_gps_data(gps_df, nexfi_split_data, latest_gps_file, latest_nexfi_file)
        
        logger.info("文件处理完成!")
    
    def generate_summary_report(self) -> None:
        """生成处理结果汇总报告"""
        try:
            # 统计处理后的文件
            processed_files = glob.glob(os.path.join(self.processed_data_path, "*.csv"))
            
            report_content = []
            report_content.append("=== 数据处理汇总报告 ===")
            report_content.append(f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report_content.append(f"处理后文件数量: {len(processed_files)}")
            report_content.append("")
            
            # 分类统计
            split_files = [f for f in processed_files if "_node_" in os.path.basename(f)]
            merged_files = [f for f in processed_files if "merged_" in os.path.basename(f)]
            
            report_content.append(f"拆分后的Nexfi文件: {len(split_files)}个")
            report_content.append(f"合并后的数据文件: {len(merged_files)}个")
            report_content.append("")
            
            # 详细文件列表
            report_content.append("=== 拆分后的文件 ===")
            for file in split_files:
                file_name = os.path.basename(file)
                file_size = os.path.getsize(file)
                report_content.append(f"  {file_name} ({file_size} bytes)")
            
            report_content.append("")
            report_content.append("=== 合并后的文件 ===")
            for file in merged_files:
                file_name = os.path.basename(file)
                file_size = os.path.getsize(file)
                report_content.append(f"  {file_name} ({file_size} bytes)")
            
            # 保存报告
            report_path = os.path.join(self.processed_data_path, "processing_report.txt")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_content))
            
            logger.info(f"汇总报告已保存到: {report_path}")
            
            # 打印报告
            print('\n'.join(report_content))
            
        except Exception as e:
            logger.error(f"生成汇总报告失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='GPS和Nexfi数据处理工具')
    parser.add_argument('--logs-path', default='./logs', 
                       help='日志文件路径 (默认: ./logs)')
    parser.add_argument('--gps-pattern', default='gps_logger_drone1_*.csv',
                       help='GPS文件模式 (默认: gps_logger_drone1_*.csv)')
    parser.add_argument('--nexfi-pattern', default='nexfi_status_*.csv',
                       help='Nexfi文件模式 (默认: nexfi_status_*.csv)')
    parser.add_argument('--tolerance', type=float, default=1.0,
                       help='时间戳匹配容忍度(秒) (默认: 1.0)')
    parser.add_argument('--verbose', action='store_true',
                       help='显示详细信息')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # 创建数据处理器
        processor = DataProcessor(args.logs_path)
        
        # 处理文件
        processor.process_files(args.gps_pattern, args.nexfi_pattern)
        
        # 生成汇总报告
        processor.generate_summary_report()
        
        print(f"\n✅ 数据处理完成！")
        print(f"处理后的文件保存在: {processor.processed_data_path}")
        
    except Exception as e:
        logger.error(f"数据处理失败: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
