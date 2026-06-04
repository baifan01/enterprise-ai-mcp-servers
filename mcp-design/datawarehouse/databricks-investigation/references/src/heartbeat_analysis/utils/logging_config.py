#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
日志配置模块

职责：
- 提供统一的日志配置
- 支持不同的日志级别和输出格式

主要函数：
- setup_logging(): 配置日志系统
- get_logger(): 获取logger实例
"""

import logging
import os
import sys
from typing import Optional


# 默认日志格式
DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
SIMPLE_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# 默认日志级别
DEFAULT_LEVEL = logging.INFO


def setup_logging(
    level: int = DEFAULT_LEVEL,
    format_string: str = DEFAULT_FORMAT,
    log_file: Optional[str] = None,
    console: bool = True
) -> None:
    """
    配置日志系统
    
    Args:
        level: 日志级别
        format_string: 日志格式
        log_file: 日志文件路径（可选）
        console: 是否输出到控制台
    """
    handlers = []
    
    # 控制台处理器
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(format_string))
        handlers.append(console_handler)
    
    # 文件处理器
    if log_file:
        # 确保目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(format_string))
        handlers.append(file_handler)
    
    # 配置根日志器
    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=handlers
    )


def get_logger(name: str) -> logging.Logger:
    """
    获取logger实例
    
    Args:
        name: logger名称
        
    Returns:
        Logger实例
    """
    return logging.getLogger(name)


def set_level(level: int) -> None:
    """
    设置日志级别
    
    Args:
        level: 日志级别
    """
    logging.getLogger().setLevel(level)


def enable_debug() -> None:
    """启用调试模式"""
    set_level(logging.DEBUG)


def enable_quiet() -> None:
    """启用静默模式（仅显示警告和错误）"""
    set_level(logging.WARNING)
