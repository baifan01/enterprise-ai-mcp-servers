#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
直连数据仓库的OCPP事件获取器

## 面向AI说明

### 业务背景
本模块负责从Databricks直连查询OCPP事件，并处理**事件边界扩展**问题。

**为什么需要边界扩展？**
由于网络延迟、设备处理时间等因素，OCPP事件的时间戳可能与充电尝试的开始/结束时间
存在毫秒级偏差。例如：
- `StatusNotification.Preparing` 可能比 `charging_attempt_start` 早500毫秒
- `StopTransaction` 可能比 `charging_attempt_end` 晚300毫秒

如果严格按充电尝试时间范围查询，可能丢失关键事件。

### 核心参数
- **TIME_BUFFER_SECONDS = 3**: 查询时自动扩展±3秒范围
- **BOUNDARY_EXPAND_MS = 500**: 如果事件与边界相差≤500ms，则扩展边界

### 数据流
```
DirectMergedAttempt（来自DirectAttemptFinder）
         ↓
fetch_events() → 查询Databricks（时间范围±3秒）
         ↓
expand_boundaries() → 检测并扩展时间边界
         ↓
更新 merged_attempt 的时间范围
         ↓
筛选并返回最终事件列表
```

### 边界扩展算法
```
原始范围: [attempt_start, attempt_end]
         
1. 查询 [start-3s, end+3s] 范围内的所有事件

2. 向前扩展检查:
   - 找 attempt_start 之前的事件
   - 如果与当前边界相差 ≤500ms，更新 new_start
   - 递归检查直到间隔 >500ms

3. 向后扩展检查:
   - 找 attempt_end 之后的事件
   - 如果与当前边界相差 ≤500ms，更新 new_end
   - 递归检查直到间隔 >500ms

4. 返回扩展后的时间范围
```

### 输入数据结构示例
```python
# DirectMergedAttempt 对象（来自DirectAttemptFinder）
merged_attempt = DirectMergedAttempt(
    sso_id='sebe1100000591',
    connector_id=1,
    attempt_start=datetime(2026, 3, 1, 14, 25, 0),
    attempt_end=datetime(2026, 3, 1, 15, 10, 0),
    ...
)
```

### 输出数据结构示例
```python
# fetch_events() 返回的OCPP事件列表
[
    {
        'sso_id': 'sebe1100000591',
        'operation_timestamp': datetime(2026, 3, 1, 14, 24, 59, 500000),
        'ocpp_message_type': 'StatusNotification',
        'ocpp_request_body': '[2, "uuid", "StatusNotification", {...}]',
        'ocpp_response_body': '[3, "uuid", {}]'
    },
    ...
]
```

### 典型调用流程
```python
fetcher = DirectOCPPFetcher(databricks_client)

# 完整调用（推荐）
events = fetcher.fetch_and_expand(merged_attempt)
# merged_attempt 的时间范围会被更新
# events 会被保存到 merged_attempt.raw_ocpp_events

# 分步调用
events = fetcher.fetch_events(sso_id, start, end)
new_start, new_end = fetcher.expand_boundaries(events, merged_attempt)
```

### 依赖关系
- 依赖 `DatabricksClient` 执行SQL查询
- 依赖 `DirectMergedAttempt` 数据模型
- 输入来自 `DirectAttemptFinder`
- 输出被 `OCPPProcessor.process_events_batch()` 使用
- 被 `DirectAnalyzer` 调用

### 注意事项
- `fetch_and_expand()` 会**修改**传入的 `merged_attempt` 对象（更新时间范围）
- 查询自动过滤 `Heartbeat` 消息（心跳包无分析价值）
- 返回的事件已按 `operation_timestamp` 升序排序
"""

import datetime
import logging
from typing import Dict, List, Optional, Tuple

from ..data.databricks_client import DatabricksClient
from ..data.models import DirectMergedAttempt
from ..utils.datetime_utils import parse_timestamp

logger = logging.getLogger(__name__)


class DirectOCPPFetcher:
    """
    直连数据仓库的OCPP事件获取器
    
    从Databricks查询OCPP事件，并处理边界扩展逻辑。
    """
    
    # 时间缓冲：±3秒
    TIME_BUFFER_SECONDS = 3
    
    # 边界扩展阈值：500毫秒
    BOUNDARY_EXPAND_MS = 500
    
    def __init__(self, databricks_client: DatabricksClient):
        """
        初始化获取器
        
        Args:
            databricks_client: Databricks客户端实例
        """
        self.db_client = databricks_client
    
    def fetch_events(
        self,
        sso_id: str,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        connector_id: Optional[int] = None
    ) -> List[Dict]:
        """
        步骤4: 查询OCPP事件（带时间缓冲）
        
        查询范围会自动扩展±3秒以捕获边界事件。
        
        Args:
            sso_id: 设备SSO ID
            start_time: 开始时间
            end_time: 结束时间
            connector_id: Connector ID（可选，用于过滤）
            
        Returns:
            OCPP事件列表
        """
        # 添加时间缓冲
        buffer = datetime.timedelta(seconds=self.TIME_BUFFER_SECONDS)
        query_start = start_time - buffer
        query_end = end_time + buffer
        
        start_str = query_start.strftime('%Y-%m-%d %H:%M:%S.%f')
        end_str = query_end.strftime('%Y-%m-%d %H:%M:%S.%f')
        
        query = f"""
        SELECT 
            REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) as sso_id,
            CAST(operation_timestamp AS STRING) as operation_timestamp,
            ocpp_message_type,
            ocpp_request_body,
            ocpp_response_body
        FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_ocpp_operations_v
        WHERE REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) = '{sso_id}'
          AND operation_timestamp >= TIMESTAMP('{start_str}')
          AND operation_timestamp <= TIMESTAMP('{end_str}')
          AND ocpp_message_type != 'Heartbeat'
        ORDER BY operation_timestamp ASC
        """
        
        logger.info(f"查询OCPP事件: sso_id={sso_id}, "
                   f"范围={start_str} 到 {end_str}")
        
        try:
            columns, rows = self.db_client.execute_query(query)
            
            if not rows:
                logger.info("未找到OCPP事件")
                return []
            
            # 转换为字典列表
            events = []
            for row in rows:
                event = dict(zip(columns, row))
                event['operation_timestamp'] = parse_timestamp(
                    event['operation_timestamp']
                )
                events.append(event)
            
            logger.info(f"找到 {len(events)} 条OCPP事件")
            return events
            
        except Exception as e:
            logger.error(f"查询OCPP事件失败: {e}")
            raise
    
    def expand_boundaries(
        self,
        events: List[Dict],
        merged_attempt: DirectMergedAttempt
    ) -> Tuple[datetime.datetime, datetime.datetime]:
        """
        步骤4: 边界扩展逻辑
        
        处理毫秒级延迟导致的事件顺序问题。
        如果相邻事件时间差≤500ms，则扩展边界。
        
        Args:
            events: OCPP事件列表（已按时间排序）
            merged_attempt: 合并后的尝试记录
            
        Returns:
            (扩展后的开始时间, 扩展后的结束时间) 元组
        """
        if not events:
            return merged_attempt.attempt_start, merged_attempt.attempt_end
        
        expand_threshold = datetime.timedelta(
            milliseconds=self.BOUNDARY_EXPAND_MS
        )
        
        new_start = merged_attempt.attempt_start
        new_end = merged_attempt.attempt_end
        
        # 向前扩展：从attempt_start往前找
        events_before_start = [
            e for e in events 
            if e['operation_timestamp'] < merged_attempt.attempt_start
        ]
        
        if events_before_start:
            # 从最接近start的事件开始，向前检查
            events_before_start.sort(
                key=lambda x: x['operation_timestamp'], 
                reverse=True
            )
            
            current_boundary = merged_attempt.attempt_start
            for event in events_before_start:
                event_time = event['operation_timestamp']
                time_diff = current_boundary - event_time
                
                if time_diff <= expand_threshold:
                    current_boundary = event_time
                    new_start = event_time
                else:
                    break
        
        # 向后扩展：从attempt_end往后找
        events_after_end = [
            e for e in events 
            if e['operation_timestamp'] > merged_attempt.attempt_end
        ]
        
        if events_after_end:
            # 从最接近end的事件开始，向后检查
            events_after_end.sort(key=lambda x: x['operation_timestamp'])
            
            current_boundary = merged_attempt.attempt_end
            for event in events_after_end:
                event_time = event['operation_timestamp']
                time_diff = event_time - current_boundary
                
                if time_diff <= expand_threshold:
                    current_boundary = event_time
                    new_end = event_time
                else:
                    break
        
        if new_start != merged_attempt.attempt_start:
            logger.debug(f"开始时间向前扩展: "
                        f"{merged_attempt.attempt_start} -> {new_start}")
        if new_end != merged_attempt.attempt_end:
            logger.debug(f"结束时间向后扩展: "
                        f"{merged_attempt.attempt_end} -> {new_end}")
        
        return new_start, new_end
    
    def fetch_and_expand(
        self,
        merged_attempt: DirectMergedAttempt
    ) -> List[Dict]:
        """
        完整的获取和边界扩展流程
        
        Args:
            merged_attempt: 合并后的尝试记录
            
        Returns:
            筛选后的OCPP事件列表（在扩展后的时间范围内）
        """
        # 查询事件
        events = self.fetch_events(
            sso_id=merged_attempt.sso_id,
            start_time=merged_attempt.attempt_start,
            end_time=merged_attempt.attempt_end,
            connector_id=merged_attempt.connector_id
        )
        
        if not events:
            return []
        
        # 边界扩展
        new_start, new_end = self.expand_boundaries(events, merged_attempt)
        
        # 更新merged_attempt的时间范围
        merged_attempt.attempt_start = new_start
        merged_attempt.attempt_end = new_end
        merged_attempt.duration_seconds = int(
            (new_end - new_start).total_seconds()
        )
        
        # 筛选在扩展后范围内的事件
        filtered_events = [
            e for e in events
            if new_start <= e['operation_timestamp'] <= new_end
        ]
        
        # 保存到merged_attempt
        merged_attempt.raw_ocpp_events = filtered_events
        
        logger.info(f"获取并筛选后: {len(filtered_events)} 条OCPP事件")
        return filtered_events
