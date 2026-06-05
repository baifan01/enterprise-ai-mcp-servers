#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
时间处理工具模块

职责：
- 提供时间解析、格式化功能
- 处理多种时间格式的兼容

主要函数：
- parse_timestamp(): 解析多种格式的时间戳
- format_datetime(): 格式化时间为ISO字符串
"""

import datetime
import logging
import re
from typing import Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)


# 支持的时间格式列表
SUPPORTED_FORMATS = [
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d %H:%M:%S.%f',
    '%Y-%m-%d',
    '%Y/%m/%dT%H:%M:%S.%fZ',
    '%Y/%m/%d %H:%M:%S',
    '%d/%m/%Y %H:%M:%S',
    '%d/%m/%Y %H:%M',
    '%m/%d/%Y %H:%M:%S',
    '%m/%d/%Y %H:%M',
]


def parse_timestamp(
    ts: Union[str, datetime.datetime, None]
) -> Optional[datetime.datetime]:
    """
    解析时间戳
    
    支持多种格式的时间字符串解析。
    
    Args:
        ts: 时间戳（字符串或datetime对象）
        
    Returns:
        datetime对象，无法解析时返回None
    """
    if pd.isna(ts) or ts is None:
        return None
    
    if isinstance(ts, datetime.datetime):
        return ts
    
    if not isinstance(ts, str):
        return ts
    
    # 预处理：去除GMT后缀、替换T
    ts_clean = ts.replace('T', ' ').replace(' GMT', '')
    
    for fmt in SUPPORTED_FORMATS:
        try:
            return datetime.datetime.strptime(ts_clean, fmt)
        except ValueError:
            continue
    
    logger.warning(f"无法解析时间戳: {ts}")
    return None


def format_datetime(
    dt: Union[datetime.datetime, str, None]
) -> Optional[str]:
    """
    将datetime格式化为ISO格式字符串
    
    Args:
        dt: datetime对象或字符串
        
    Returns:
        ISO格式字符串，None时返回None
    """
    if dt is None:
        return None
    if isinstance(dt, datetime.datetime):
        return dt.isoformat()
    return str(dt)


def parse_date_range(
    start_date: str,
    end_date: Optional[str] = None
) -> tuple:
    """
    解析日期范围
    
    Args:
        start_date: 开始日期字符串 (YYYY-MM-DD)
        end_date: 结束日期字符串 (可选，默认为今天)
        
    Returns:
        (start_datetime, end_datetime) 元组
    """
    start_dt = datetime.datetime.strptime(start_date, '%Y-%m-%d')
    start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if end_date:
        end_dt = datetime.datetime.strptime(end_date, '%Y-%m-%d')
    else:
        end_dt = datetime.datetime.now()
    
    end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    return start_dt, end_dt


def calculate_time_offset(
    event_time: datetime.datetime,
    anchor_time: datetime.datetime,
    precision: int = 3
) -> float:
    """
    计算时间偏移量
    
    Args:
        event_time: 事件时间
        anchor_time: 锚点时间
        precision: 小数位数（默认3位，即毫秒精度）
        
    Returns:
        时间偏移量（秒）
    """
    if isinstance(event_time, str):
        event_time = parse_timestamp(event_time)
    if isinstance(anchor_time, str):
        anchor_time = parse_timestamp(anchor_time)
    
    time_diff = (event_time - anchor_time).total_seconds()
    return round(time_diff, precision)
