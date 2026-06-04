#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据导入脚本

用于从Databricks导入充电尝试、OCPP事件、充电桩位置等数据到本地DuckDB。

使用示例：
    python scripts/import_data.py --type attempts --start 2026-03-01 --end 2026-03-03
    python scripts/import_data.py --type feedback
    python scripts/import_data.py --type location
"""

import argparse
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.heartbeat_analysis.utils.logging_config import setup_logging
from src.heartbeat_analysis.importers.attempts_importer import AttemptsImporter
from src.heartbeat_analysis.importers.feedback_importer import FeedbackImporter
from src.heartbeat_analysis.importers.location_importer import LocationImporter


def import_attempts(start_date: str, end_date: str = None):
    """导入充电尝试和OCPP事件"""
    importer = AttemptsImporter()
    result = importer.import_data(start_date, end_date)
    print(f"\n导入结果:")
    print(f"  充电尝试: {result['attempts_imported']} 条")
    print(f"  OCPP事件: {result['ocpp_events_imported']} 条")
    print(f"  已删除: {result['deleted_count']} 条")


def import_feedback(csv_path: str = None):
    """导入用户反馈"""
    importer = FeedbackImporter(csv_path)
    count = importer.import_from_csv()
    print(f"\n导入完成: {count} 条用户反馈")


def import_location():
    """导入充电桩位置"""
    importer = LocationImporter()
    count = importer.import_locations()
    print(f"\n导入完成: {count} 条充电桩位置")


def main():
    parser = argparse.ArgumentParser(description='数据导入工具')
    parser.add_argument(
        '--type', '-t',
        choices=['attempts', 'feedback', 'location', 'all'],
        required=True,
        help='导入类型'
    )
    parser.add_argument(
        '--start', '-s',
        help='开始日期 (YYYY-MM-DD)，用于attempts导入'
    )
    parser.add_argument(
        '--end', '-e',
        help='结束日期 (YYYY-MM-DD)，用于attempts导入'
    )
    parser.add_argument(
        '--csv',
        help='CSV文件路径，用于feedback导入'
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
        if args.type == 'attempts':
            if not args.start:
                parser.error("attempts导入需要 --start 参数")
            import_attempts(args.start, args.end)
            
        elif args.type == 'feedback':
            import_feedback(args.csv)
            
        elif args.type == 'location':
            import_location()
            
        elif args.type == 'all':
            if args.start:
                import_attempts(args.start, args.end)
            import_feedback(args.csv)
            import_location()
            
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
