#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
proxy 多日重连与 Heartbeat 波动分析入口脚本

使用方式：
    venv/bin/python scripts/analyze_proxy_reconnect_heartbeat.py

可选参数：
    venv/bin/python scripts/analyze_proxy_reconnect_heartbeat.py \
        --input-dir data/input \
        --output-dir output \
        --analysis-year 2026 \
        --heartbeat-min-days 12 \
        --reconnect-max-threshold 30 \
        --reconnect-cv-threshold 0.8 \
        --debug
"""

import argparse
import logging
import os
import sys

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.heartbeat_analysis.analyzers.proxy_reconnect_heartbeat_analyzer import (  # noqa: E402
    ProxyReconnectHeartbeatAnalyzer,
)
from src.heartbeat_analysis.utils.logging_config import setup_logging  # noqa: E402


class ProxyReconnectHeartbeatCli:
    """
    proxy 多日重连与 Heartbeat 波动分析命令行入口。

    主函数只保留高层流程，具体逻辑交由分析器类处理。
    """

    DEFAULT_INPUT_DIR = os.path.join(PROJECT_ROOT, 'data', 'input')
    DEFAULT_OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'output')

    @classmethod
    def run(cls) -> None:
        """执行命令行入口。"""
        args = cls._parse_args()
        cls._setup_logging(args.debug)
        cls._run_analysis(args)

    @classmethod
    def _parse_args(cls) -> argparse.Namespace:
        """解析命令行参数。"""
        parser = argparse.ArgumentParser(
            description='生成 proxy 多日重连与 Heartbeat 波动分析结果',
        )
        parser.add_argument(
            '--input-dir',
            type=str,
            default=cls.DEFAULT_INPUT_DIR,
            help='按天重连文件所在目录',
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default=cls.DEFAULT_OUTPUT_DIR,
            help='输出目录',
        )
        parser.add_argument(
            '--file-glob',
            type=str,
            default=ProxyReconnectHeartbeatAnalyzer.DEFAULT_FILE_GLOB,
            help='输入文件匹配模式',
        )
        parser.add_argument(
            '--analysis-year',
            type=int,
            default=ProxyReconnectHeartbeatAnalyzer.DEFAULT_ANALYSIS_YEAR,
            help='文件名中的日期所属年份',
        )
        parser.add_argument(
            '--heartbeat-min-days',
            type=int,
            default=ProxyReconnectHeartbeatAnalyzer.DEFAULT_HEARTBEAT_MIN_DAYS,
            help='候选设备要求的最少 heartbeat 天数',
        )
        parser.add_argument(
            '--reconnect-max-threshold',
            type=int,
            default=ProxyReconnectHeartbeatAnalyzer.DEFAULT_RECONNECT_MAX_THRESHOLD,
            help='候选设备要求的最小重连峰值',
        )
        parser.add_argument(
            '--reconnect-cv-threshold',
            type=float,
            default=ProxyReconnectHeartbeatAnalyzer.DEFAULT_RECONNECT_CV_THRESHOLD,
            help='候选设备要求的最小重连波动系数',
        )
        parser.add_argument(
            '--model-prefix',
            type=str,
            default=ProxyReconnectHeartbeatAnalyzer.DEFAULT_MODEL_PREFIX,
            help='可选的设备型号前缀过滤，例如 suby',
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='启用调试日志',
        )
        return parser.parse_args()

    @classmethod
    def _setup_logging(cls, debug_enabled: bool) -> None:
        """初始化日志。"""
        log_level = logging.DEBUG if debug_enabled else logging.INFO
        setup_logging(level=log_level)

    @classmethod
    def _run_analysis(cls, args: argparse.Namespace) -> None:
        """执行分析并打印摘要。"""
        with ProxyReconnectHeartbeatAnalyzer(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            file_glob=args.file_glob,
            analysis_year=args.analysis_year,
            heartbeat_min_days=args.heartbeat_min_days,
            reconnect_max_threshold=args.reconnect_max_threshold,
            reconnect_cv_threshold=args.reconnect_cv_threshold,
            model_prefix=args.model_prefix,
        ) as analyzer:
            summary = analyzer.run()

        cls._print_summary(summary)

    @classmethod
    def _print_summary(cls, summary: dict) -> None:
        """打印执行摘要。"""
        print("proxy 多日重连与 Heartbeat 波动分析完成")
        print(f"输入文件数: {summary['input_file_count']}")
        print(
            f"分析日期范围: {summary['analysis_start_date']} 到 "
            f"{summary['analysis_end_date']}"
        )
        print(f"设备数: {summary['device_count']}")
        print(f"长表行数: {summary['long_row_count']}")
        print(f"候选异常设备数: {summary['candidate_count']}")
        print(f"宽表设备数: {summary['wide_row_count']}")
        print(f"长表输出: {summary['long_output_path']}")
        print(f"摘要输出: {summary['summary_output_path']}")
        print(f"宽表输出: {summary['wide_output_path']}")


def main() -> None:
    """主函数。"""
    ProxyReconnectHeartbeatCli.run()


if __name__ == '__main__':
    main()
