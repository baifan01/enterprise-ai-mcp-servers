#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OCPP事件处理模块

## 面向AI说明

### 业务背景
OCPP (Open Charge Point Protocol) 1.6 是电动汽车充电桩与后台系统通信的标准协议。
本模块负责解析、匹配和格式化 OCPP 消息，是连接原始事件数据和 AI 分析的关键桥梁。

### OCPP协议核心知识
常见消息类型及其含义：
- **StatusNotification**: 充电桩状态变更（Available/Preparing/Charging/Finishing/Faulted）
- **RemoteStartTransaction**: 远程启动充电请求
- **StartTransaction**: 充电交易开始
- **StopTransaction**: 充电交易结束
- **MeterValues**: 电表读数（充电量、功率等）
- **Heartbeat**: 心跳包（通常过滤掉）

### 数据流
```
原始OCPP事件 → extract_connector_id() → 提取connector信息
     ↓
match_event_to_attempts() → 匹配到充电尝试（填充original_records）
     ↓
process_events_batch() → 生成AI分析格式（带时间偏移）
```

### 输入数据结构示例
```python
# 原始OCPP事件（来自Databricks charger_ocpp_operations_v表）
ocpp_event = {
    'sso_id': 'sebe1100000591',
    'operation_timestamp': datetime(2026, 1, 1, 10, 0, 5),
    'ocpp_message_type': 'StatusNotification',
    'ocpp_request_body': '[2, "uuid", "StatusNotification", {"connectorId":1,"errorCode":"NoError","status":"Preparing"}]',
    'ocpp_response_body': '[3, "uuid", {}]'
}
```

### 输出数据结构示例
```python
# process_event_for_analysis() 输出（用于AI分析）
processed_event = {
    'time_offset_seconds': 5.123,  # 相对第一条事件的秒数，精确到毫秒
    'ocpp_type': 'StatusNotification',
    'status_info': {'errorCode': 'NoError', 'status': 'Preparing'}  # 仅StatusNotification
}

# 非StatusNotification类型的输出
processed_event = {
    'time_offset_seconds': 10.456,
    'ocpp_type': 'RemoteStartTransaction',
    'request': '[2, "uuid", "RemoteStartTransaction", {...}]',  # 保留原始字符串
    'response': '[3, "uuid", {"status":"Accepted"}]'
}
```

### 典型调用场景

**场景1：批量导入时匹配OCPP事件到尝试记录**
```python
processor = OCPPProcessor()
attempts_index = merger.build_index(merged_attempts)  # sso_id → attempts 映射

for event in ocpp_events:
    matched = processor.match_event_to_attempts(event, attempts_index)
    # 事件会被添加到匹配的 attempt['original_records'] 中
```

**场景2：AI分析前处理事件序列**
```python
processor = OCPPProcessor()
anchor_time, processed = processor.process_events_batch(raw_events)
# processed 可直接用于 AIAnalyzer.analyze_attempt_only()
```

### 关键解析逻辑
- **connectorId提取**: 先尝试JSON解析，失败则用正则匹配 `"connectorId":(\d+)`
- **StatusNotification**: 只提取 `errorCode` 和 `status`，使用正则兼容非标准JSON
- **MeterValues**: 仅保留时间偏移和类型，内容太多无需AI分析
- **其他类型**: 保留完整的 request/response 原始字符串

### 依赖关系
- 依赖 `AttemptMerger.build_index()` 的输出
- 输出被 `AIAnalyzer` 和 `analyzers/*` 使用
- 被 `importers/attempts_importer.py` 和 `analyzers/*` 调用

### 注意事项
- OCPP消息格式非标准JSON（如 `[2, uuid, Type, {payload}]`），需特殊处理
- connector_id=0 或 None 表示设备级事件，应匹配所有时间范围内的尝试
- 时间偏移精确到毫秒（3位小数），用于AI理解事件时序
"""

import copy
import datetime
import json
import logging
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class OCPPProcessor:
    """
    OCPP事件处理器
    
    负责OCPP事件的解析、匹配和格式化处理。
    """
    
    # connectorId的不同命名格式
    CONNECTOR_ID_KEYS = ['connectorId', 'connector_id', 'connectorID']
    
    def extract_connector_id(self, body_str: str) -> Optional[int]:
        """
        从OCPP body中提取connectorId
        
        Args:
            body_str: OCPP请求体或响应体字符串
            
        Returns:
            connector ID（整数）或None（表示设备级事件）
        """
        if not body_str or pd.isna(body_str):
            return None
        
        try:
            # 尝试解析JSON
            body_dict = json.loads(body_str)
            
            # 查找connectorId字段
            for key in self.CONNECTOR_ID_KEYS:
                if key in body_dict:
                    return int(body_dict[key])
            
            return None
                
        except (json.JSONDecodeError, ValueError, TypeError):
            # JSON解析失败，尝试正则表达式
            patterns = [
                r'"connectorId"\s*:\s*(\d+)',
                r'"connector_id"\s*:\s*(\d+)',
                r'"connectorID"\s*:\s*(\d+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, body_str, re.IGNORECASE)
                if match:
                    return int(match.group(1))
            
            return None
    
    def extract_status_notification(self, request_body: str) -> Dict:
        """
        从StatusNotification的request_body中提取关键字段
        
        使用正则表达式查找，兼容不同格式的数据。
        
        Args:
            request_body: StatusNotification请求体字符串
            
        Returns:
            包含errorCode和status的字典
        """
        if not request_body:
            return {'errorCode': 'Unknown', 'status': 'Unknown'}
        
        error_code = 'Unknown'
        status = 'Unknown'
        
        # 匹配 "errorCode":"value"
        error_match = re.search(r'"errorCode"\s*:\s*"([^"]*)"', request_body)
        if error_match:
            error_code = error_match.group(1)
        
        # 匹配 "status":"value"
        status_match = re.search(r'"status"\s*:\s*"([^"]*)"', request_body)
        if status_match:
            status = status_match.group(1)
        
        return {
            'errorCode': error_code,
            'status': status
        }
    
    def match_event_to_attempts(
        self, 
        ocpp_event: Dict, 
        attempts_index: Dict[str, List[Dict]]
    ) -> int:
        """
        将单条OCPP事件匹配到合并后的尝试记录
        
        匹配逻辑：
        1. sso_id必须匹配
        2. 时间戳必须在尝试记录的时间范围内
        3. connector级事件必须匹配connector_id；设备级事件（connector_id=0或None）匹配所有
        
        Args:
            ocpp_event: 单条OCPP事件记录
            attempts_index: sso_id到尝试记录的映射字典
            
        Returns:
            匹配到的尝试记录数量
        """
        matched_count = 0
        
        # 1. 提取sso_id
        event_sso_id = ocpp_event.get('sso_id', '')
        if not event_sso_id:
            return 0
        
        # 2. 查找候选记录
        candidate_attempts = attempts_index.get(event_sso_id, [])
        if not candidate_attempts:
            return 0
        
        # 3. 提取connectorId
        connector_id = None
        if ocpp_event.get('ocpp_request_body'):
            connector_id = self.extract_connector_id(ocpp_event['ocpp_request_body'])
        if connector_id is None and ocpp_event.get('ocpp_response_body'):
            connector_id = self.extract_connector_id(ocpp_event['ocpp_response_body'])
        
        # 4. 获取事件时间戳
        event_timestamp = ocpp_event.get('operation_timestamp')
        if not event_timestamp:
            return 0
        
        # 5. 匹配到尝试记录
        for attempt in candidate_attempts:
            # 检查时间戳是否在范围内
            if not (attempt['earliest_start'] <= event_timestamp <= attempt['latest_end']):
                continue
            
            # connectorId匹配逻辑
            attempt_connector_id = attempt['connector_id']
            
            if connector_id is None or connector_id == 0:
                # 设备级事件：匹配所有时间范围内的尝试记录
                match = True
            else:
                # Connector级事件：必须匹配connector_id
                match = (connector_id == attempt_connector_id)
            
            if match:
                # 深拷贝OCPP事件记录并添加到尝试记录
                ocpp_event_copy = copy.deepcopy(ocpp_event)
                attempt['original_records'].append(ocpp_event_copy)
                matched_count += 1
        
        return matched_count
    
    def process_event_for_analysis(
        self, 
        event: Dict, 
        anchor_time: datetime.datetime
    ) -> Dict:
        """
        处理单个OCPP事件，生成分析格式
        
        Args:
            event: 原始OCPP事件字典
            anchor_time: 锚点时间（第一条事件的时间戳）
            
        Returns:
            处理后的事件字典
        """
        # 计算与锚点的时间差（精确到毫秒）
        event_time = event['operation_timestamp']
        if isinstance(event_time, str):
            event_time = datetime.datetime.fromisoformat(event_time)
        
        time_diff = (event_time - anchor_time).total_seconds()
        time_offset = round(time_diff, 3)
        
        ocpp_type = event['ocpp_message_type']
        
        # 基础结果
        result = {
            'time_offset_seconds': time_offset,
            'ocpp_type': ocpp_type
        }
        
        # 根据消息类型分类处理
        if ocpp_type == 'StatusNotification':
            result['status_info'] = self.extract_status_notification(
                event['ocpp_request_body']
            )
        elif ocpp_type == 'MeterValues':
            # MeterValues: 仅输出时间差和类型
            pass
        else:
            # 其他类型: 保留原始request_body和response_body
            if event.get('ocpp_request_body'):
                result['request'] = event['ocpp_request_body']
            if event.get('ocpp_response_body'):
                result['response'] = event['ocpp_response_body']
        
        return result
    
    def process_events_batch(
        self, 
        events: List[Dict]
    ) -> Tuple[datetime.datetime, List[Dict]]:
        """
        批量处理OCPP事件
        
        Args:
            events: 原始OCPP事件列表
            
        Returns:
            (anchor_time, processed_events) 元组
        """
        if not events:
            return None, []
        
        # 获取锚点时间
        anchor_time = events[0]['operation_timestamp']
        if isinstance(anchor_time, str):
            anchor_time = datetime.datetime.fromisoformat(anchor_time)
        
        # 处理所有事件
        processed_events = [
            self.process_event_for_analysis(event, anchor_time)
            for event in events
        ]
        
        return anchor_time, processed_events
