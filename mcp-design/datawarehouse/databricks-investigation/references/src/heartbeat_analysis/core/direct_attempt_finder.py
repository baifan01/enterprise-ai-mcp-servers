#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
直连数据仓库的充电尝试查找器

## 面向AI说明

### 业务背景
本模块用于**实时分析场景**：用户提供一个时间戳和设备标识，系统需要直连Databricks
数据仓库查找该时间附近的充电尝试，并将"抖动记录"合并为真正的用户尝试。

与 `AttemptMerger` 的区别：
- `AttemptMerger`: 用于批量导入，处理本地DataFrame
- `DirectAttemptFinder`: 用于实时查询，直连Databricks

### 核心概念
- **EVSE ID**: 欧洲充电桩标识（如 `DE*UBI*E10071616`），可能包含多个值用逗号分隔
- **SSO ID**: 设备内部标识（如 `sebe1100000591`）
- **搜索窗口**: 输入时间戳前后±30分钟
- **合并阈值**: 同一Connector下，启动时间相差≤60秒的记录合并

### 数据流（3步流程）
```
输入: timestamp + evse_id/sso_id
         ↓
步骤1: find_nearby_attempts() → 查询Databricks，获取时间窗口内所有记录
         ↓
步骤2: find_adjacent_records() → 向前向后扩展搜索临近记录
         ↓
步骤3: merge_to_user_attempt() → 合并为 DirectMergedAttempt 对象
         ↓
输出: List[DirectMergedAttempt]（每个Connector一个）
```

### 查询逻辑详解
查找时间附近的充电尝试，满足以下任一条件：
1. `charging_attempt_start` 在输入时间戳前后30分钟内
2. 输入时间戳位于 `start` 和 `end` 之间
3. `charging_attempt_end` 在输入时间戳前后30分钟内

### 输入参数示例
```python
finder = DirectAttemptFinder(databricks_client)
merged = finder.find_and_merge(
    input_timestamp=datetime(2026, 3, 1, 14, 30, 0),
    evse_id='DE*UBI*E10071616',  # 或使用 sso_id
    sso_id=None
)
```

### 输出数据结构示例
```python
# DirectMergedAttempt 对象
{
    'evse_id': 'DE*UBI*E10071616',
    'sso_id': 'sebe1100000591',
    'connector_id': 1,
    'attempt_start': datetime(2026, 3, 1, 14, 25, 0),
    'attempt_end': datetime(2026, 3, 1, 15, 10, 0),
    'total_consumption_kwh': 12.5,
    'attempt_count': 3,           # 合并了3条原始记录
    'duration_seconds': 2700,     # 45分钟
    'original_records': [...],    # 原始Databricks记录
    'raw_ocpp_events': [],        # 由DirectOCPPFetcher填充
    'processed_events': []        # 由OCPPProcessor填充
}
```

### 典型调用流程
```python
# 完整调用（推荐）
merged_attempts = finder.find_and_merge(timestamp, evse_id=evse)

# 分步调用（需要更多控制时）
records = finder.find_nearby_attempts(timestamp, evse_id=evse)
for connector_id in unique_connectors:
    expanded = finder.find_adjacent_records(anchors, connector_id, records)
    merged = finder.merge_to_user_attempt(expanded, evse, sso, connector_id)
```

### 依赖关系
- 依赖 `DatabricksClient` 执行SQL查询
- 依赖 `DirectMergedAttempt` 数据模型
- 输出被 `DirectOCPPFetcher` 使用
- 被 `DirectAnalyzer` 调用

### 注意事项
- `evse_id` 和 `sso_id` 至少提供一个，否则抛出 ValueError
- 同一充电桩可能有多个Connector同时工作，返回多个合并结果
- 查询使用 LIKE 匹配 evse_id（支持部分匹配）
"""

import datetime
import logging
from typing import Dict, List, Optional, Tuple

import pandas as pd

from ..data.databricks_client import DatabricksClient
from ..data.models import DirectMergedAttempt
from ..utils.datetime_utils import parse_timestamp

logger = logging.getLogger(__name__)


class DirectAttemptFinder:
    """
    直连数据仓库的充电尝试查找器
    
    从Databricks直接查询并合并充电尝试记录，
    用于实时分析少量尝试或用户反馈问题。
    """
    
    # 搜索窗口：±30分钟
    SEARCH_WINDOW_MINUTES = 30
    
    # 合并阈值：1分钟（两条记录的时间差）
    MERGE_THRESHOLD_SECONDS = 60
    
    def __init__(self, databricks_client: DatabricksClient):
        """
        初始化查找器
        
        Args:
            databricks_client: Databricks客户端实例
        """
        self.db_client = databricks_client
    
    def _lookup_sso_by_evse(self, evse_id: str) -> Optional[str]:
        """
        根据EVSE ID查找对应的SSO ID
        
        通过charger_location_charger_v表查找映射关系。
        
        Args:
            evse_id: EVSE ID（如 DE*UBI*E10071616）
            
        Returns:
            对应的sso_id，未找到时返回None
        """
        query = f"""
        SELECT sso_id
        FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_location_charger_v
        WHERE evse_id LIKE '%{evse_id}%'
          AND sso_valid_to > CURRENT_DATE()
        LIMIT 1
        """
        
        logger.info(f"[DEBUG] 查询EVSE到SSO映射，SQL:\n{query}")
        
        try:
            columns, rows = self.db_client.execute_query(query)
            logger.info(f"[DEBUG] 查询结果: columns={columns}, rows={rows}")
            
            if rows and rows[0]:
                sso_id = rows[0][0]
                logger.info(f"EVSE ID {evse_id} 对应的 SSO ID: {sso_id}")
                return sso_id
            else:
                logger.warning(f"未找到 EVSE ID {evse_id} 对应的 SSO ID")
                return None
        except Exception as e:
            logger.error(f"查询EVSE到SSO映射失败: {e}")
            return None
    
    def find_nearby_attempts(
        self,
        input_timestamp: datetime.datetime,
        evse_id: Optional[str] = None,
        sso_id: Optional[str] = None
    ) -> List[Dict]:
        """
        步骤1: 查找附近的充电尝试记录
        
        查询条件：
        - charging_attempt_start 在输入时间戳前后30分钟内
        - 或输入时间戳在 start 和 end 之间
        - 或charging_attempt_end 在输入时间戳前后30分钟内
        
        Args:
            input_timestamp: 用户指定的时间戳
            evse_id: EVSE ID（可选）
            sso_id: SSO ID（可选，与evse_id至少提供一个）
            
        Returns:
            符合条件的充电尝试记录列表
        """
        if not evse_id and not sso_id:
            raise ValueError("evse_id 和 sso_id 至少需要提供一个")
        
        # 如果提供了evse_id但没有sso_id，先查找对应的sso_id
        resolved_sso_id = sso_id
        resolved_evse_id = evse_id
        
        if evse_id and not sso_id:
            resolved_sso_id = self._lookup_sso_by_evse(evse_id)
            if not resolved_sso_id:
                logger.warning(f"无法解析 EVSE ID {evse_id}，尝试继续查询")
                # 如果找不到映射，仍然尝试用evse_id查询（可能表结构有变化）
        
        # 计算时间窗口
        window = datetime.timedelta(minutes=self.SEARCH_WINDOW_MINUTES)
        start_window = input_timestamp - window
        end_window = input_timestamp + window
        
        # 格式化时间
        input_ts_str = input_timestamp.strftime('%Y-%m-%d %H:%M:%S')
        start_str = start_window.strftime('%Y-%m-%d %H:%M:%S')
        end_str = end_window.strftime('%Y-%m-%d %H:%M:%S')
        
        # 使用sso_id查询（kpi_charging_attempts_enriched_v表没有evse_id列）
        if not resolved_sso_id:
            raise ValueError(f"无法解析设备标识: evse_id={evse_id}, sso_id={sso_id}")
        
        logger.info(f"[DEBUG] 解析结果: evse_id={evse_id} -> resolved_sso_id={resolved_sso_id}")
        logger.info(f"[DEBUG] 时间窗口: {start_str} 到 {end_str}")
        
        query = f"""
        SELECT 
            source_device_id as sso_id,
            ocpi_connector_id as connector_id,
            CAST(charging_attempt_start AS STRING) as charging_attempt_start,
            CAST(charging_attempt_end AS STRING) as charging_attempt_end,
            session_consumption_kwh
        FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.kpi_charging_attempts_enriched_v
        WHERE source_device_id = '{resolved_sso_id}'
          AND (
            -- 条件1: charging_attempt_start 在输入时间戳前后30分钟内
            (charging_attempt_start >= TIMESTAMP('{start_str}') 
             AND charging_attempt_start <= TIMESTAMP('{end_str}'))
            OR
            -- 条件2: 输入时间戳在 start 和 end 之间
            (TIMESTAMP('{input_ts_str}') >= charging_attempt_start 
             AND TIMESTAMP('{input_ts_str}') <= charging_attempt_end)
            OR
            -- 条件3: charging_attempt_end 在输入时间戳前后30分钟内
            (charging_attempt_end >= TIMESTAMP('{start_str}') 
             AND charging_attempt_end <= TIMESTAMP('{end_str}'))
          )
        ORDER BY ocpi_connector_id, charging_attempt_start
        """
        
        logger.info(f"查找附近的充电尝试: timestamp={input_ts_str}, "
                   f"evse_id={evse_id}, sso_id={sso_id}")
        logger.info(f"[DEBUG] 充电尝试查询SQL:\n{query}")
        
        try:
            columns, rows = self.db_client.execute_query(query)
            logger.info(f"[DEBUG] 查询返回: {len(rows) if rows else 0} 条记录")
            
            if not rows:
                logger.info("未找到匹配的充电尝试记录")
                return []
            
            # 转换为字典列表并预处理时间戳
            records = []
            for row in rows:
                record = dict(zip(columns, row))
                record['charging_attempt_start'] = parse_timestamp(
                    record['charging_attempt_start']
                )
                record['charging_attempt_end'] = parse_timestamp(
                    record['charging_attempt_end']
                )
                record['connector_id'] = int(record['connector_id'] or 0)
                records.append(record)
            
            logger.info(f"找到 {len(records)} 条充电尝试记录")
            return records
            
        except Exception as e:
            logger.error(f"查询充电尝试记录失败: {e}")
            raise
    
    def _find_anchor_record(
        self,
        input_timestamp: datetime.datetime,
        records: List[Dict],
        connector_id: int
    ) -> Optional[Dict]:
        """
        按优先级查找锚点记录
        
        优先级：
        1. 包含时间戳的记录（start <= timestamp <= end）
        2. 结束时间早于时间戳且最近的记录（30分钟内）
        3. 开始时间早于时间戳且最近的记录（30分钟内）
        
        Args:
            input_timestamp: 输入时间戳
            records: 该Connector的所有记录
            connector_id: Connector ID
            
        Returns:
            锚点记录，未找到返回None
        """
        if not records:
            return None
        
        # 筛选该Connector的记录
        connector_records = [r for r in records if r['connector_id'] == connector_id]
        if not connector_records:
            return None
        
        window = datetime.timedelta(minutes=self.SEARCH_WINDOW_MINUTES)
        
        # 优先级1：包含时间戳的记录（start <= timestamp <= end）
        containing_records = [
            r for r in connector_records
            if r['charging_attempt_start'] <= input_timestamp <= r['charging_attempt_end']
        ]
        if containing_records:
            # 如果有多条，取开始时间最早的
            anchor = min(containing_records, key=lambda x: x['charging_attempt_start'])
            logger.info(f"[DEBUG] 优先级1命中 - 包含时间戳的记录: "
                       f"start={anchor['charging_attempt_start']}, "
                       f"end={anchor['charging_attempt_end']}")
            return anchor
        
        # 优先级2：结束时间早于时间戳且最近的记录（已完成的充电）
        ended_before_records = [
            r for r in connector_records
            if r['charging_attempt_end'] < input_timestamp
            and (input_timestamp - r['charging_attempt_end']) <= window
        ]
        if ended_before_records:
            # 取结束时间最接近输入时间戳的
            anchor = max(ended_before_records, key=lambda x: x['charging_attempt_end'])
            logger.info(f"[DEBUG] 优先级2命中 - 结束时间最近的记录: "
                       f"start={anchor['charging_attempt_start']}, "
                       f"end={anchor['charging_attempt_end']}")
            return anchor
        
        # 优先级3：开始时间早于时间戳且最近的记录
        started_before_records = [
            r for r in connector_records
            if r['charging_attempt_start'] < input_timestamp
            and (input_timestamp - r['charging_attempt_start']) <= window
        ]
        if started_before_records:
            # 取开始时间最接近输入时间戳的
            anchor = max(started_before_records, key=lambda x: x['charging_attempt_start'])
            logger.info(f"[DEBUG] 优先级3命中 - 开始时间最近的记录: "
                       f"start={anchor['charging_attempt_start']}, "
                       f"end={anchor['charging_attempt_end']}")
            return anchor
        
        logger.info(f"[DEBUG] Connector {connector_id} 未找到锚点记录")
        return None
    
    def _is_adjacent(self, record1: Dict, record2: Dict) -> bool:
        """
        判断两条记录是否相邻
        
        相邻条件（满足其一）：
        1. 两条记录的开始时间相差小于1分钟
        2. 一条记录的结束时间与另一条的开始时间相差小于5分钟（连续充电）
        
        Args:
            record1: 第一条记录
            record2: 第二条记录
            
        Returns:
            是否相邻
        """
        start1 = record1['charging_attempt_start']
        start2 = record2['charging_attempt_start']
        end1 = record1['charging_attempt_end']
        end2 = record2['charging_attempt_end']
        
        # 条件1：开始时间相差小于1分钟
        start_diff = abs((start1 - start2).total_seconds())
        if start_diff < 60:
            return True
        
        # 条件2：结束时间与开始时间相差小于5分钟（连续充电场景）
        # record1结束后record2开始
        if end1 < start2:
            gap = (start2 - end1).total_seconds()
            if gap < 300:  # 5分钟
                return True
        
        # record2结束后record1开始
        if end2 < start1:
            gap = (start1 - end2).total_seconds()
            if gap < 300:  # 5分钟
                return True
        
        return False
    
    def find_adjacent_records(
        self,
        anchor_record: Dict,
        all_records: List[Dict]
    ) -> List[Dict]:
        """
        从锚点记录向前向后搜索相邻记录
        
        相邻条件：
        1. 两条记录的开始时间相差小于1分钟
        2. 远一点的记录的结束时间与当前记录的开始时间相差小于5分钟（连续充电）
        
        Args:
            anchor_record: 锚点记录
            all_records: 所有候选记录
            
        Returns:
            包含锚点和所有相邻记录的列表
        """
        if not anchor_record:
            return []
        
        connector_id = anchor_record['connector_id']
        
        # 筛选相同connector的记录
        connector_records = [
            r for r in all_records 
            if r['connector_id'] == connector_id
        ]
        
        if not connector_records:
            return [anchor_record]
        
        # 按开始时间排序
        sorted_records = sorted(
            connector_records, 
            key=lambda x: x['charging_attempt_start']
        )
        
        # 初始化结果集
        result_set = {id(anchor_record)}
        result = [anchor_record]
        
        # 迭代扩展，直到没有新记录加入
        changed = True
        while changed:
            changed = False
            
            for record in sorted_records:
                if id(record) in result_set:
                    continue
                
                # 检查是否与结果集中任何记录相邻
                for existing in result:
                    if self._is_adjacent(record, existing):
                        result.append(record)
                        result_set.add(id(record))
                        changed = True
                        logger.debug(f"[DEBUG] 扩展记录: {record['charging_attempt_start']}")
                        break
        
        # 按时间排序返回
        result.sort(key=lambda x: x['charging_attempt_start'])
        
        logger.info(f"[DEBUG] Connector {connector_id}: 从1条锚点扩展到 {len(result)} 条记录")
        return result
    
    def merge_to_user_attempt(
        self,
        records: List[Dict],
        evse_id: Optional[str],
        sso_id: str,
        connector_id: int
    ) -> DirectMergedAttempt:
        """
        步骤3: 合并为用户尝试记录
        
        Args:
            records: 要合并的记录列表
            evse_id: EVSE ID
            sso_id: SSO ID
            connector_id: Connector ID
            
        Returns:
            合并后的DirectMergedAttempt实例
        """
        return DirectMergedAttempt.from_records(
            records=records,
            evse_id=evse_id,
            sso_id=sso_id,
            connector_id=connector_id
        )
    
    def find_and_merge(
        self,
        input_timestamp: datetime.datetime,
        evse_id: Optional[str] = None,
        sso_id: Optional[str] = None
    ) -> List[DirectMergedAttempt]:
        """
        完整的查找和合并流程（新逻辑）
        
        查找逻辑优先级：
        1. 查找包含时间戳的记录（start <= timestamp <= end）
        2. 查找结束时间早于时间戳且最近的记录（30分钟内）
        3. 查找开始时间晚于时间戳且最近的记录（30分钟内）
        
        找到唯一锚点后，向前向后扩展相邻记录，条件：
        - 开始时间相差小于1分钟
        - 或结束时间与开始时间相差小于5分钟（连续充电）
        
        Args:
            input_timestamp: 用户指定的时间戳
            evse_id: EVSE ID（可选）
            sso_id: SSO ID（可选）
            
        Returns:
            合并后的DirectMergedAttempt列表（最多1个，对应唯一锚点所在Connector）
        """
        # 步骤1: 查找时间窗口内所有候选记录
        all_records = self.find_nearby_attempts(
            input_timestamp, evse_id, sso_id
        )
        
        if not all_records:
            logger.info("[DEBUG] 没有找到任何候选记录")
            return []
        
        logger.info(f"[DEBUG] 候选记录总数: {len(all_records)}")
        for r in all_records:
            logger.info(f"[DEBUG]   - connector={r['connector_id']}, "
                       f"start={r['charging_attempt_start']}, "
                       f"end={r['charging_attempt_end']}, "
                       f"kwh={r.get('session_consumption_kwh', 'N/A')}")
        
        # 提取唯一的sso_id（如果未提供）
        if not sso_id:
            sso_id = all_records[0]['sso_id']
        
        # 步骤2: 按优先级在所有Connector中查找唯一锚点
        connector_ids = sorted(set(r['connector_id'] for r in all_records))
        anchor_record = None
        
        # 遍历每个Connector，按优先级查找锚点
        for connector_id in connector_ids:
            anchor = self._find_anchor_record(
                input_timestamp, all_records, connector_id
            )
            if anchor:
                # 第一个找到的锚点就是最优的
                anchor_record = anchor
                logger.info(f"[DEBUG] 选定锚点: connector={connector_id}, "
                           f"start={anchor['charging_attempt_start']}, "
                           f"end={anchor['charging_attempt_end']}")
                break
        
        if not anchor_record:
            logger.warning("[DEBUG] 未能在任何Connector中找到锚点记录")
            return []
        
        # 步骤3: 从锚点扩展相邻记录
        expanded_records = self.find_adjacent_records(anchor_record, all_records)
        
        # 步骤4: 合并
        connector_id = anchor_record['connector_id']
        merged = self.merge_to_user_attempt(
            expanded_records, evse_id, sso_id, connector_id
        )
        
        logger.info(f"[DEBUG] 合并完成: Connector {connector_id}, "
                   f"记录数={len(expanded_records)}, "
                   f"时间范围={merged.attempt_start} ~ {merged.attempt_end}, "
                   f"总电量={merged.total_consumption_kwh} kWh")
        
        return [merged]
