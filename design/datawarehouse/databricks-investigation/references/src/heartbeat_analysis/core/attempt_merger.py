#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
充电尝试合并逻辑

## 面向AI说明

### 业务背景
电动汽车充电过程中，由于设备信号抖动、网络延迟等原因，数据仓库的
`kpi_charging_attempts_enriched_v` 表中**同一次用户充电行为可能产生多条记录**。
本模块负责将这些"抖动记录"按规则合并为真正的"用户充电尝试"。

### 核心概念
- **sso_id**: 充电桩设备唯一标识（如 `sebe1100000591`）
- **connector_id**: 充电枪编号，一个充电桩通常有1-2个枪（值为1或2，0表示设备级）
- **合并阈值**: 同一 sso_id + connector_id 下，启动时间相差≤60秒的记录视为同一次尝试

### 数据流
```
DataFrame（原始记录） → merge() → List[Dict]（合并后尝试）
                              ↓
                     assign_business_keys() → 带 attempt_bk 的尝试
                              ↓
                     build_index() → Dict[sso_id, List[attempt]]
```

### 输入数据结构示例
```python
# merge() 输入的 DataFrame 必须包含以下列：
df = pd.DataFrame({
    'source_device_id': ['sebe1100000591', 'sebe1100000591'],
    'ocpi_connector_id': [1, 1],
    'charging_attempt_start': [datetime(2026,1,1,10,0,0), datetime(2026,1,1,10,0,30)],
    'charging_attempt_end': [datetime(2026,1,1,10,5,0), datetime(2026,1,1,10,6,0)],
    'session_consumption_kwh': [2.5, 0.1]
})
```

### 输出数据结构示例
```python
# merge() 返回的合并后记录
merged_attempt = {
    'sso_id': 'sebe1100000591',
    'connector_id': 1,
    'attempt_count': 2,              # 合并了2条原始记录
    'consumption_kwh': 2.6,          # 累加的充电量
    'earliest_start': datetime(...), # 最早开始时间
    'latest_end': datetime(...),     # 最晚结束时间
    'original_records': [],          # 关联的OCPP事件（由OCPPProcessor填充）
    'attempt_bk': '20260101100000000sebe11000005911'  # 业务主键
}
```

### 典型调用流程
```python
merger = AttemptMerger()
merged_attempts = merger.merge(df)           # 步骤1：合并
merger.assign_business_keys(merged_attempts) # 步骤2：分配主键
index = merger.build_index(merged_attempts)  # 步骤3：建立索引供OCPP匹配
```

### 依赖关系
- 本模块为纯业务逻辑，不依赖数据库连接
- 输出被 `OCPPProcessor.match_event_to_attempts()` 使用
- 被 `importers/attempts_importer.py` 调用

### 注意事项
- `original_records` 初始为空列表，由后续 OCPP 匹配过程填充
- 业务主键格式：17位时间戳 + sso_id + connector_id，保证全局唯一
"""

import datetime
import logging
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class AttemptMerger:
    """
    充电尝试合并器
    
    负责将原始的充电尝试记录按规则合并为用户级别的尝试记录。
    合并规则：同一sso_id和connector_id下，启动时间相差不超过1分钟的记录合并。
    """
    
    # 合并阈值：两条记录的时间差（秒）
    MERGE_THRESHOLD_SECONDS = 60
    
    def merge(self, df: pd.DataFrame) -> List[Dict]:
        """
        合并充电尝试记录
        
        Args:
            df: 充电尝试记录的DataFrame，需包含：
                - source_device_id: 设备ID
                - ocpi_connector_id: connector ID
                - charging_attempt_start: 开始时间
                - charging_attempt_end: 结束时间
                - session_consumption_kwh: 充电量
                
        Returns:
            合并后的充电尝试列表
        """
        if df.empty:
            return []
        
        merged_list = []
        
        # 按sso_id和connector_id分组
        for (sso_id, connector_id), group_df in df.groupby(
            ['source_device_id', 'ocpi_connector_id']
        ):
            connector_id = int(connector_id) if not pd.isna(connector_id) else 0
            sso_id = str(sso_id)
            
            # 按charging_attempt_start排序
            group_df = group_df.sort_values('charging_attempt_start').reset_index(drop=True)
            
            # 合并逻辑：启动时间相差不超过阈值的记录合并
            current_group = []
            
            for idx, row in group_df.iterrows():
                if not current_group:
                    current_group.append(row)
                else:
                    last_start = current_group[-1]['charging_attempt_start']
                    current_start = row['charging_attempt_start']
                    time_diff = (current_start - last_start).total_seconds()
                    
                    if time_diff <= self.MERGE_THRESHOLD_SECONDS:
                        current_group.append(row)
                    else:
                        merged_record = self._create_merged_record(
                            current_group, sso_id, connector_id
                        )
                        merged_list.append(merged_record)
                        current_group = [row]
            
            # 处理最后一组
            if current_group:
                merged_record = self._create_merged_record(
                    current_group, sso_id, connector_id
                )
                merged_list.append(merged_record)
        
        logger.info(f"合并后共有 {len(merged_list)} 条记录")
        return merged_list
    
    def _create_merged_record(
        self, 
        group: List[pd.Series], 
        sso_id: str, 
        connector_id: int
    ) -> Dict:
        """
        创建合并后的记录
        
        Args:
            group: 同一组的记录列表
            sso_id: 设备ID
            connector_id: connector ID
            
        Returns:
            合并后的记录字典
        """
        # 计算consumption_kwh（累加）
        consumption_values = [
            r['session_consumption_kwh'] for r in group 
            if pd.notna(r['session_consumption_kwh'])
        ]
        consumption_kwh = sum(consumption_values) if consumption_values else 0.0
        
        # 获取最早和最晚时间
        earliest_start = min(r['charging_attempt_start'] for r in group)
        latest_end = max(r['charging_attempt_end'] for r in group)
        
        return {
            'sso_id': sso_id,
            'connector_id': connector_id,
            'attempt_count': len(group),
            'consumption_kwh': consumption_kwh,
            'earliest_start': earliest_start,
            'latest_end': latest_end,
            'original_records': []
        }
    
    def build_index(self, merged_attempts: List[Dict]) -> Dict[str, List[Dict]]:
        """
        建立sso_id到尝试记录的映射索引
        
        用于加速OCPP事件匹配过程。
        
        Args:
            merged_attempts: 合并后的尝试记录列表
            
        Returns:
            映射字典，Key为sso_id，Value为该sso_id对应的所有尝试记录列表
        """
        attempts_index = {}
        
        for attempt in merged_attempts:
            sso_id = attempt['sso_id']
            if sso_id not in attempts_index:
                attempts_index[sso_id] = []
            attempts_index[sso_id].append(attempt)
        
        logger.info(
            f"建立索引完成: {len(attempts_index)} 个sso_id, "
            f"共 {len(merged_attempts)} 条尝试记录"
        )
        return attempts_index
    
    @staticmethod
    def generate_business_key(
        sso_id: str, 
        connector_id: int, 
        attempt_start_time: datetime.datetime
    ) -> str:
        """
        生成业务主键
        
        格式：时间戳（17位）+ sso_id + connector_id
        
        Args:
            sso_id: 设备ID
            connector_id: connector ID
            attempt_start_time: 尝试开始时间（精确到毫秒）
            
        Returns:
            业务主键字符串
        """
        # 格式化时间戳：YYYYMMDDHHMMSSmmm（共17位）
        timestamp_str = attempt_start_time.strftime('%Y%m%d%H%M%S%f')[:17]
        return f"{timestamp_str}{sso_id}{connector_id}"
    
    def assign_business_keys(self, merged_attempts: List[Dict]) -> None:
        """
        为合并后的尝试记录分配业务主键
        
        Args:
            merged_attempts: 合并后的尝试记录列表（会被修改）
        """
        for attempt in merged_attempts:
            if 'attempt_bk' not in attempt or attempt['attempt_bk'] is None:
                attempt['attempt_bk'] = self.generate_business_key(
                    attempt['sso_id'],
                    attempt['connector_id'],
                    attempt['earliest_start']
                )
        
        logger.info(f"已为 {len(merged_attempts)} 条记录分配业务主键")
