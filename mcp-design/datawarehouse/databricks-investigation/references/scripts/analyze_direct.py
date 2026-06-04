#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
直连数据仓库分析入口脚本

提供命令行接口执行直连Databricks的OCPP事件分析。

使用方式：
    # 单个分析
    python scripts/analyze_direct.py \
        --timestamp "2026-03-01 14:30:00" \
        --evse DE*UBI*E10071616 \
        --ai
    
    # 使用SSO ID
    python scripts/analyze_direct.py \
        --timestamp "2026-03-01 14:30:00" \
        --sso sebe1100000591 \
        --ai
    
    # 交互模式
    python scripts/analyze_direct.py --interactive
    
    # 批量分析（从CSV读取）
    python scripts/analyze_direct.py --batch input.csv --output results/
"""

import argparse
import csv
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.heartbeat_analysis.analyzers.direct_analyzer import DirectAnalyzer
from src.heartbeat_analysis.utils.datetime_utils import parse_timestamp
from src.heartbeat_analysis.utils.logging_config import setup_logging


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='直连数据仓库OCPP事件分析',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # 分析模式
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='交互模式'
    )
    mode_group.add_argument(
        '--batch', '-b',
        type=str,
        help='批量分析：CSV文件路径'
    )
    
    # 单个分析参数
    parser.add_argument(
        '--timestamp', '-t',
        type=str,
        help='查询时间戳 (格式: YYYY-MM-DD HH:MM:SS)'
    )
    parser.add_argument(
        '--evse', '-e',
        type=str,
        help='EVSE ID'
    )
    parser.add_argument(
        '--sso', '-s',
        type=str,
        help='SSO ID'
    )
    
    # 功能选项
    parser.add_argument(
        '--ai',
        action='store_true',
        help='启用AI分析'
    )
    parser.add_argument(
        '--save-db',
        action='store_true',
        help='保存结果到DuckDB数据库（默认不保存）'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='输出文件路径（默认 output/direct_analysis_result.txt）'
    )
    
    # 日志选项
    parser.add_argument(
        '--debug',
        action='store_true',
        help='启用调试日志'
    )
    
    return parser.parse_args()


def format_result_as_text(result: dict, index: int, total: int) -> str:
    """
    将分析结果格式化为可读文本
    
    Args:
        result: 单个分析结果
        index: 当前索引
        total: 总数
        
    Returns:
        格式化的文本字符串
    """
    lines = []
    lines.append("=" * 70)
    lines.append(f"Analysis Result {index}/{total}")
    lines.append("=" * 70)
    
    # Part 1: Charging Attempt Information
    lines.append("\n[Charging Attempt Info]")
    lines.append("-" * 40)
    attempt = result['attempt']
    lines.append(f"EVSE ID:       {attempt['evse_id']}")
    lines.append(f"SSO ID:        {attempt['sso_id']}")
    lines.append(f"Connector:     {attempt['connector_id']}")
    lines.append(f"Start Time:    {attempt['attempt_start']}")
    lines.append(f"End Time:      {attempt['attempt_end']}")
    lines.append(f"Consumption:   {attempt['total_consumption_kwh']:.3f} kWh")
    lines.append(f"Attempt Count: {attempt['attempt_count']}")
    lines.append(f"Duration:      {attempt['duration_seconds']} seconds")
    
    # Part 2: OCPP Events Summary
    processed_events = result.get('processed_events', [])
    lines.append(f"\n[OCPP Events Summary] ({len(processed_events)} events)")
    lines.append("-" * 40)
    
    if processed_events:
        for event in processed_events:
            time_offset = event.get('time_offset_seconds', 0)
            ocpp_type = event.get('ocpp_type', 'Unknown')
            
            if time_offset >= 0:
                time_str = f"+{time_offset:>8.3f}s"
            else:
                time_str = f"{time_offset:>9.3f}s"
            
            if ocpp_type == 'StatusNotification' and 'status_info' in event:
                status_info = event['status_info']
                error_code = status_info.get('errorCode', 'Unknown')
                status = status_info.get('status', 'Unknown')
                lines.append(f"{time_str} | {ocpp_type:20} | {status:12} | {error_code}")
            else:
                lines.append(f"{time_str} | {ocpp_type}")
    else:
        lines.append("(No OCPP events)")
    
    # Part 3: AI Analysis Result
    if result.get('ai_result'):
        lines.append(f"\n[AI Analysis Result]")
        lines.append("-" * 40)
        lines.append(result['ai_result'])
    
    lines.append("")
    return "\n".join(lines)


def run_single_analysis(
    analyzer: DirectAnalyzer,
    timestamp: str,
    evse_id: Optional[str],
    sso_id: Optional[str],
    save_result: bool = False,
    output_path: Optional[str] = None
):
    """
    执行单个分析
    
    Args:
        analyzer: 分析器实例
        timestamp: 时间戳字符串
        evse_id: EVSE ID
        sso_id: SSO ID
        save_result: 是否保存结果到数据库（默认False）
        output_path: 输出文件路径（默认 output/direct_analysis_result.txt）
    """
    # 默认输出路径
    if output_path is None:
        output_dir = os.path.join(project_root, 'output')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'direct_analysis_result.txt')
    
    try:
        ts = parse_timestamp(timestamp)
        results = analyzer.analyze(
            input_timestamp=ts,
            evse_id=evse_id,
            sso_id=sso_id,
            save_result=save_result
        )
        
        if not results:
            print("No matching charging attempt records found")
            return
        
        # Build output text
        output_lines = []
        output_lines.append(f"OCPP Event Analysis Report (Direct Databricks Query)")
        output_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output_lines.append(f"Query Timestamp: {timestamp}")
        output_lines.append(f"EVSE ID: {evse_id or 'Not specified'}")
        output_lines.append(f"SSO ID: {sso_id or 'Not specified'}")
        output_lines.append("")
        
        # Format each result
        for i, result in enumerate(results):
            output_lines.append(format_result_as_text(result, i + 1, len(results)))
        
        output_text = "\n".join(output_lines)
        
        # Print to console
        print(output_text)
        
        # Save to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(output_text)
        print(f"\n{'='*70}")
        print(f"Result saved to: {output_path}")
            
    except Exception as e:
        print(f"Analysis failed: {e}")
        raise


def run_interactive_mode(analyzer: DirectAnalyzer):
    """
    Interactive mode
    
    Args:
        analyzer: Analyzer instance
    """
    print("="*60)
    print("OCPP Event Analysis - Interactive Mode")
    print("="*60)
    print("Enter 'quit' or 'q' to exit")
    print(f"Results will be saved to: output/direct_analysis_result.txt")
    print()
    
    while True:
        try:
            timestamp = input("Enter timestamp (YYYY-MM-DD HH:MM:SS): ").strip()
            if timestamp.lower() in ('quit', 'q'):
                break
            
            evse_id = input("Enter EVSE ID (optional, press Enter to skip): ").strip() or None
            sso_id = input("Enter SSO ID (optional, press Enter to skip): ").strip() or None
            
            if not evse_id and not sso_id:
                print("Error: At least one of EVSE ID or SSO ID is required")
                continue
            
            ai_input = input("Enable AI analysis? (y/n, default y): ").strip().lower()
            enable_ai = ai_input != 'n'
            
            original_ai_setting = analyzer.enable_ai
            analyzer.enable_ai = enable_ai
            
            print("\nAnalyzing...")
            run_single_analysis(
                analyzer,
                timestamp,
                evse_id,
                sso_id,
                save_result=False
            )
            
            analyzer.enable_ai = original_ai_setting
            
            print()
            
        except KeyboardInterrupt:
            print("\n\nExited")
            break
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    print("Thank you for using!")


def run_batch_analysis(
    analyzer: DirectAnalyzer,
    batch_file: str,
    output_dir: Optional[str],
    save_results: bool = True
):
    """
    Batch analysis
    
    Args:
        analyzer: Analyzer instance
        batch_file: CSV input file path
        output_dir: Output directory
        save_results: Whether to save results to database
    """
    # 确保输出目录存在
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # 读取CSV文件
    inputs = []
    with open(batch_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            inputs.append({
                'timestamp': row.get('timestamp'),
                'evse_id': row.get('evse_id') or None,
                'sso_id': row.get('sso_id') or None
            })
    
    print(f"Loaded {len(inputs)} records for analysis")
    
    # Execute batch analysis
    all_results = analyzer.analyze_batch(inputs, save_results=save_results)
    
    # Save results
    if output_dir:
        output_file = os.path.join(
            output_dir, 
            f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
        print(f"Results saved to: {output_file}")
    
    print(f"Batch analysis completed, {len(all_results)} results")


def main():
    """主函数"""
    args = parse_args()
    
    # 设置日志
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(level=log_level)
    
    # 创建分析器
    enable_ai = args.ai
    with DirectAnalyzer(enable_ai=enable_ai) as analyzer:
        
        if args.interactive:
            # 交互模式
            run_interactive_mode(analyzer)
            
        elif args.batch:
            # 批量模式
            run_batch_analysis(
                analyzer,
                args.batch,
                args.output,
                save_results=args.save_db
            )
            
        elif args.timestamp:
            # Single analysis
            if not args.evse and not args.sso:
                print("Error: --evse or --sso parameter is required")
                sys.exit(1)
            
            run_single_analysis(
                analyzer,
                args.timestamp,
                args.evse,
                args.sso,
                save_result=args.save_db,
                output_path=args.output
            )
            
        else:
            # 默认进入交互模式
            run_interactive_mode(analyzer)


if __name__ == '__main__':
    main()
