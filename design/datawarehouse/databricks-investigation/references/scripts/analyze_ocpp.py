#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OCPP事件分析脚本

用于分析充电尝试的OCPP事件，支持AI辅助分析。

使用示例：
    python scripts/analyze_ocpp.py --attempt <attempt_bk>
    python scripts/analyze_ocpp.py --attempt bk1,bk2,bk3 --ai --output result.txt
    python scripts/analyze_ocpp.py --feedback --start 2026-03-01 --end 2026-03-03 --ai
"""

import argparse
import datetime
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.heartbeat_analysis.utils.logging_config import setup_logging
from src.heartbeat_analysis.analyzers.ocpp_analyzer import OCPPAnalyzer
from src.heartbeat_analysis.analyzers.feedback_analyzer import FeedbackAnalyzer


def parse_datetime(date_str: str) -> datetime.datetime:
    """解析日期字符串"""
    if len(date_str) == 10:
        dt = datetime.datetime.strptime(date_str, '%Y-%m-%d')
    else:
        dt = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    return dt


def analyze_attempts(attempt_bks: str, enable_ai: bool, output_file: str = None):
    """分析指定的充电尝试"""
    # 解析attempt_bk列表
    bks = [bk.strip() for bk in attempt_bks.split(',') if bk.strip()]
    
    if not bks:
        print("未提供有效的attempt_bk")
        return
    
    analyzer = OCPPAnalyzer(enable_ai=enable_ai)
    
    if len(bks) == 1:
        # 单个分析
        result = analyzer.analyze(bks[0])
        if result:
            analyzer.print_result(result)
    else:
        # 批量分析
        output = output_file or 'data/output/ocpp_analysis.txt'
        results = analyzer.analyze_batch(bks, output_file=output)
        print(f"\n分析完成，共 {len(results)} 个尝试")


def analyze_feedback(start_date: str, end_date: str, enable_ai: bool, output_file: str = None):
    """分析用户反馈"""
    start_dt = parse_datetime(start_date)
    
    if end_date:
        end_dt = parse_datetime(end_date)
    else:
        end_dt = datetime.datetime.now()
    
    # 调整结束时间到当天最后一刻
    if len(end_date or '') == 10:
        end_dt = end_dt.replace(hour=23, minute=59, second=59)
    
    analyzer = FeedbackAnalyzer(enable_ai=enable_ai)
    output = output_file or 'data/output/feedback_analysis.txt'
    
    results = analyzer.analyze(start_dt, end_dt, output_file=output)
    print(f"\n分析完成，共 {len(results)} 条反馈")


def interactive_mode():
    """交互模式"""
    print("\n请选择分析类型:")
    print("1. 分析OCPP事件（输入attempt_bk）")
    print("2. 分析用户反馈（输入时间范围）")
    print("3. 联合分析反馈与OCPP事件")
    print("4. 直接对尝试记录进行AI分析（批量）")
    
    choice = input("请输入选项 (1/2/3/4): ").strip()
    
    if choice == '1':
        attempt_bk = input("请输入attempt_bk: ").strip()
        if attempt_bk:
            analyze_attempts(attempt_bk, enable_ai=False)
            
    elif choice == '2':
        start = input("开始时间 (YYYY-MM-DD): ").strip()
        end = input("结束时间 (YYYY-MM-DD): ").strip()
        if start:
            analyze_feedback(start, end, enable_ai=False)
            
    elif choice == '3':
        start = input("开始时间 (YYYY-MM-DD): ").strip()
        end = input("结束时间 (YYYY-MM-DD): ").strip()
        ai_choice = input("是否启用AI分析？(y/n): ").strip().lower()
        if start:
            analyze_feedback(start, end, enable_ai=(ai_choice == 'y'))
            
    elif choice == '4':
        attempt_bks = input("请输入attempt_bk（多个用逗号分隔）: ").strip()
        if attempt_bks:
            analyze_attempts(attempt_bks, enable_ai=True)
    else:
        print("无效选项")


def main():
    parser = argparse.ArgumentParser(description='OCPP事件分析工具')
    parser.add_argument(
        '--attempt', '-a',
        help='充电尝试业务主键（多个用逗号分隔）'
    )
    parser.add_argument(
        '--feedback', '-f',
        action='store_true',
        help='分析用户反馈'
    )
    parser.add_argument(
        '--start', '-s',
        help='开始日期 (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end', '-e',
        help='结束日期 (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--ai',
        action='store_true',
        help='启用AI分析'
    )
    parser.add_argument(
        '--output', '-o',
        help='输出文件路径'
    )
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='交互模式'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='显示详细日志'
    )
    
    args = parser.parse_args()
    
    # 配置日志
    import logging
    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)
    
    try:
        if args.interactive or (not args.attempt and not args.feedback):
            interactive_mode()
        elif args.attempt:
            analyze_attempts(args.attempt, args.ai, args.output)
        elif args.feedback:
            if not args.start:
                parser.error("反馈分析需要 --start 参数")
            analyze_feedback(args.start, args.end, args.ai, args.output)
            
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
