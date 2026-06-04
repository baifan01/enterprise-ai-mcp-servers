#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
proxy-11-3 固件版本分析入口脚本

使用方式：
    python scripts/analyze_proxy_firmware.py

可选参数：
    python scripts/analyze_proxy_firmware.py \
        --input data/input/proxy-11-3.log \
        --output output/proxy-11-3-analysis.csv \
        --batch-size 500 \
        --debug
"""

import argparse
import logging
import os
import sys

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.heartbeat_analysis.analyzers.proxy_firmware_analyzer import (  # noqa: E402
    ProxyFirmwareAnalyzer,
)
from src.heartbeat_analysis.utils.logging_config import setup_logging  # noqa: E402


class ProxyFirmwareCli:
    """
    proxy 固件版本分析命令行入口。

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
        'proxy-11-3-analysis.csv',
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
            description='批量查询 proxy-11-3 设备的固件版本',
        )
        parser.add_argument(
            '--input',
            type=str,
            default=cls.DEFAULT_INPUT_PATH,
            help='输入文件路径',
        )
        parser.add_argument(
            '--output',
            type=str,
            default=cls.DEFAULT_OUTPUT_PATH,
            help='输出 CSV 路径',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=ProxyFirmwareAnalyzer.DEFAULT_BATCH_SIZE,
            help='每批查询的设备数量',
        )
        parser.add_argument(
            '--query-start',
            type=str,
            default=ProxyFirmwareAnalyzer.DEFAULT_QUERY_START,
            help='BootNotification 查询起始时间',
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
        with ProxyFirmwareAnalyzer(
            input_path=args.input,
            output_path=args.output,
            batch_size=args.batch_size,
            query_start=args.query_start,
        ) as analyzer:
            summary = analyzer.run()

        cls._print_summary(args.output, summary)

    @classmethod
    def _print_summary(cls, output_path: str, summary: dict) -> None:
        """打印执行摘要。"""
        print("proxy-11-3 固件与配置分析完成")
        print(f"输入行数: {summary['input_row_count']}")
        print(f"解析到固件版本的设备数: {summary['firmware_found_count']}")
        print(
            "解析到 GetConfiguration 配置的设备数: "
            f"{summary['get_configuration_found_count']}"
        )
        print(f"输出行数: {summary['output_row_count']}")
        print(f"输出文件: {output_path}")


def main() -> None:
    """主函数。"""
    ProxyFirmwareCli.run()


if __name__ == '__main__':
    main()
