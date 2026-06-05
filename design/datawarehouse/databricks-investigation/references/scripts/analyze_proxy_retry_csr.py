#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
proxy 重连次数与 3 个月 CSR 基础表分析入口脚本

使用方式：
    python scripts/analyze_proxy_retry_csr.py

可选参数：
    python scripts/analyze_proxy_retry_csr.py \
        --input data/input/proxy-11-3.log \
        --output output/proxy-11-3-csr-poc.csv \
        --debug
"""

import argparse
import logging
import os
import sys

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.heartbeat_analysis.analyzers.proxy_retry_csr_analyzer import (  # noqa: E402
    ProxyRetryCsrAnalyzer,
)
from src.heartbeat_analysis.utils.logging_config import setup_logging  # noqa: E402


class ProxyRetryCsrCli:
    """
    proxy 重连与长期 CSR 分析命令行入口。

    主函数只保留高层流程，细节交由分析器类处理。
    """

    DEFAULT_INPUT_PATH = os.path.join(
        PROJECT_ROOT,
        'data',
        'input',
        'proxy-11-3.log',
    )
    DEFAULT_OUTPUT_PATH = os.path.join(
        PROJECT_ROOT,
        'output',
        'proxy-11-3-csr-poc.csv',
    )

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
            description='生成 proxy 重连次数与 3 个月 CSR 的 POC 基础表',
        )
        parser.add_argument(
            '--input',
            type=str,
            default=cls.DEFAULT_INPUT_PATH,
            help='输入重连文件路径',
        )
        parser.add_argument(
            '--output',
            type=str,
            default=cls.DEFAULT_OUTPUT_PATH,
            help='输出 CSV 路径',
        )
        parser.add_argument(
            '--model-prefix',
            type=str,
            default=ProxyRetryCsrAnalyzer.DEFAULT_MODEL_PREFIX,
            help='设备型号前缀过滤条件，默认 suby',
        )
        parser.add_argument(
            '--window-start',
            type=str,
            default=ProxyRetryCsrAnalyzer.DEFAULT_WINDOW_START,
            help='充电记录统计开始日期',
        )
        parser.add_argument(
            '--window-end',
            type=str,
            default=ProxyRetryCsrAnalyzer.DEFAULT_WINDOW_END,
            help='充电记录统计结束日期',
        )
        parser.add_argument(
            '--energy-threshold',
            type=float,
            default=ProxyRetryCsrAnalyzer.DEFAULT_ENERGY_THRESHOLD,
            help='成功记录的充电量阈值',
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
        with ProxyRetryCsrAnalyzer(
            input_path=args.input,
            output_path=args.output,
            model_prefix=args.model_prefix,
            window_start=args.window_start,
            window_end=args.window_end,
            energy_threshold=args.energy_threshold,
        ) as analyzer:
            summary = analyzer.run()

        cls._print_summary(args.output, summary)

    @classmethod
    def _print_summary(cls, output_path: str, summary: dict) -> None:
        """打印执行摘要。"""
        print("proxy 重连次数与 3 个月 CSR 基础表生成完成")
        print(f"输入文件有效行数: {summary['input_row_count']}")
        print(f"重连文件设备数: {summary['retry_device_count']}")
        print(f"充电聚合设备数: {summary['charging_device_count']}")
        print(f"输出行数: {summary['output_row_count']}")
        print(f"重连缺失设备数: {summary['retry_missing_count']}")
        print(f"CSR 缺失设备数: {summary['csr_missing_count']}")
        print(f"输出文件: {output_path}")


def main() -> None:
    """主函数。"""
    ProxyRetryCsrCli.run()


if __name__ == '__main__':
    main()
