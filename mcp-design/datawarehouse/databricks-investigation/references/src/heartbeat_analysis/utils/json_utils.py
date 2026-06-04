#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
JSON处理工具模块

职责：
- 提供JSON解析、格式化功能
- 处理特殊的JSON格式（如OCPP消息）

主要函数：
- safe_json_loads(): 安全的JSON解析
- format_json(): 格式化输出JSON
"""

import datetime
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def safe_json_loads(json_str: str) -> Optional[Any]:
    """
    安全的JSON解析
    
    Args:
        json_str: JSON字符串
        
    Returns:
        解析后的对象，失败时返回None
    """
    if not json_str:
        return None
    
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug(f"JSON解析失败: {e}")
        return None


def format_json(
    obj: Any, 
    indent: int = 2, 
    ensure_ascii: bool = False
) -> str:
    """
    格式化输出JSON
    
    Args:
        obj: 要序列化的对象
        indent: 缩进空格数
        ensure_ascii: 是否转义非ASCII字符
        
    Returns:
        格式化的JSON字符串
    """
    return json.dumps(
        obj, 
        indent=indent, 
        ensure_ascii=ensure_ascii, 
        default=_json_serializer
    )


def _json_serializer(obj: Any) -> Any:
    """
    JSON序列化器，处理特殊类型
    
    Args:
        obj: 要序列化的对象
        
    Returns:
        可序列化的对象
    """
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    return str(obj)


def extract_from_ocpp_array(ocpp_str: str, index: int) -> Optional[Any]:
    """
    从OCPP数组格式的字符串中提取元素
    
    OCPP消息格式通常为: [messageType, messageId, action, payload]
    
    Args:
        ocpp_str: OCPP消息字符串
        index: 要提取的元素索引
        
    Returns:
        提取的元素，失败时返回None
    """
    if not ocpp_str:
        return None
    
    try:
        parsed = json.loads(ocpp_str)
        if isinstance(parsed, list) and len(parsed) > index:
            return parsed[index]
    except (json.JSONDecodeError, ValueError):
        pass
    
    return None


def merge_json_objects(*objects: Dict) -> Dict:
    """
    合并多个JSON对象
    
    Args:
        *objects: 要合并的字典对象
        
    Returns:
        合并后的字典
    """
    result = {}
    for obj in objects:
        if obj:
            result.update(obj)
    return result
