#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
充电尝试导入模块

职责：
- 从Databricks导入充电尝试数据
- 合并尝试记录并导入本地DuckDB
- 匹配OCPP事件到尝试记录

主要接口：
- AttemptsImporter: 充电尝试导入器类
  - import_data(): 执行完整导入流程
"""

import datetime
import logging
from typing import Dict, List, Optional

import pandas as pd

from ..data.databricks_client import DatabricksClient
from ..data.duckdb_client import LegacyDuckDBClient
from ..core.attempt_merger import AttemptMerger
from ..core.ocpp_processor import OCPPProcessor
from ..utils.datetime_utils import parse_timestamp

logger = logging.getLogger(__name__)


class AttemptsImporter:
    """
    充电尝试导入器
    
    负责从Databricks查询充电尝试和OCPP事件数据，
    经过合并处理后导入本地DuckDB数据库。
    """
    
    def __init__(self):
        """初始化导入器"""
        self.databricks_client = DatabricksClient()
        self.duckdb_client = LegacyDuckDBClient()
        self.merger = AttemptMerger()
        self.ocpp_processor = OCPPProcessor()
    
    def query_charging_attempts(
        self, 
        start_date: datetime.datetime, 
        end_date: datetime.datetime
    ) -> pd.DataFrame:
        """
        查询充电尝试记录
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            充电尝试记录DataFrame
        """
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        query = f"""
        SELECT 
            source_device_id,
            ocpi_connector_id,
            CAST(charging_attempt_start AS STRING) as charging_attempt_start,
            CAST(charging_attempt_end AS STRING) as charging_attempt_end,
            session_consumption_kwh
        FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.kpi_charging_attempts_enriched_v
        WHERE DATE(charging_attempt_start) >= DATE('{start_str}')
          AND DATE(charging_attempt_start) <= DATE('{end_str}')
        ORDER BY source_device_id, ocpi_connector_id, charging_attempt_start ASC
        """
        
        logger.info(f"查询充电尝试记录: {start_str} 到 {end_str}")
        
        columns, rows = self.databricks_client.execute_query(query)
        
        if not rows:
            logger.info("未找到充电尝试记录")
            return pd.DataFrame(columns=columns)
        
        df = pd.DataFrame(rows, columns=columns)
        df = self._preprocess_attempts(df)
        
        logger.info(f"找到 {len(df)} 条充电尝试记录")
        return df
    
    def query_ocpp_events_paginated(
        self, 
        start_date: datetime.datetime, 
        end_date: datetime.datetime,
        page_size: int = 1000000,
        last_timestamp: Optional[datetime.datetime] = None
    ) -> pd.DataFrame:
        """
        分页查询OCPP事件（使用时间戳游标）
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            page_size: 每页大小
            last_timestamp: 上一页最后时间戳
            
        Returns:
            OCPP事件DataFrame
        """
        start_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
        end_str = end_date.strftime('%Y-%m-%d %H:%M:%S')
        
        where_conditions = [
            "ocpp_message_type != 'Heartbeat'",
            f"operation_timestamp >= TIMESTAMP('{start_str}')",
            f"operation_timestamp <= TIMESTAMP('{end_str}')"
        ]
        
        if last_timestamp:
            if isinstance(last_timestamp, datetime.datetime):
                if last_timestamp.microsecond > 0:
                    ts_str = last_timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')
                else:
                    ts_str = last_timestamp.strftime('%Y-%m-%d %H:%M:%S')
            else:
                ts_str = str(last_timestamp)
            where_conditions.append(f"operation_timestamp > TIMESTAMP('{ts_str}')")
        
        where_clause = " AND ".join(where_conditions)
        
        query = f"""
        SELECT 
            REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) as sso_id,
            CAST(operation_timestamp AS STRING) as operation_timestamp,
            ocpp_message_type,
            ocpp_request_body,
            ocpp_response_body
        FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_ocpp_operations_v
        WHERE {where_clause}
        ORDER BY operation_timestamp ASC
        LIMIT {page_size}
        """
        
        logger.info(f"分页查询OCPP事件, page_size={page_size}")
        
        columns, rows = self.databricks_client.execute_query(query)
        
        if not rows:
            return pd.DataFrame(columns=columns)
        
        df = pd.DataFrame(rows, columns=columns)
        df = self._preprocess_ocpp_events(df)
        
        logger.info(f"找到 {len(df)} 条OCPP事件")
        return df
    
    def _preprocess_attempts(self, df: pd.DataFrame) -> pd.DataFrame:
        """预处理充电尝试数据"""
        df['charging_attempt_start'] = df['charging_attempt_start'].apply(parse_timestamp)
        df['charging_attempt_end'] = df['charging_attempt_end'].apply(parse_timestamp)
        df = df.dropna(subset=['charging_attempt_start', 'charging_attempt_end'])
        df['ocpi_connector_id'] = df['ocpi_connector_id'].fillna(0).astype(int)
        return df
    
    def _preprocess_ocpp_events(self, df: pd.DataFrame) -> pd.DataFrame:
        """预处理OCPP事件数据"""
        df['operation_timestamp'] = df['operation_timestamp'].apply(parse_timestamp)
        df = df.dropna(subset=['operation_timestamp'])
        return df
    
    def delete_existing_data(
        self, 
        start_date: datetime.datetime, 
        end_date: datetime.datetime
    ) -> int:
        """
        删除指定日期范围的现有数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            删除的记录数
        """
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        with self.duckdb_client.transaction():
            # 计算要删除的记录数
            count_query = f"""
            SELECT COUNT(*) FROM Charger_Attempts
            WHERE DATE(attempt_start_time) >= DATE('{start_str}')
              AND DATE(attempt_start_time) <= DATE('{end_str}')
            """
            result = self.duckdb_client.query(count_query)
            deleted_count = result[0][0]
            
            if deleted_count == 0:
                logger.info("没有需要删除的记录")
                return 0
            
            # 删除OCPP事件
            delete_ocpp = f"""
            DELETE FROM OCPP_Events
            USING Charger_Attempts
            WHERE OCPP_Events.charger_attempts_bk = Charger_Attempts.attempt_bk
              AND DATE(Charger_Attempts.attempt_start_time) >= DATE('{start_str}')
              AND DATE(Charger_Attempts.attempt_start_time) <= DATE('{end_str}')
            """
            self.duckdb_client.execute(delete_ocpp)
            
            # 删除充电尝试
            delete_attempt = f"""
            DELETE FROM Charger_Attempts
            WHERE DATE(attempt_start_time) >= DATE('{start_str}')
              AND DATE(attempt_start_time) <= DATE('{end_str}')
            """
            self.duckdb_client.execute(delete_attempt)
        
        logger.info(f"删除了 {deleted_count} 条记录")
        return deleted_count
    
    def import_attempts(self, merged_attempts: List[Dict]) -> int:
        """
        导入充电尝试记录到DuckDB
        
        Args:
            merged_attempts: 合并后的尝试记录列表
            
        Returns:
            插入的记录数
        """
        if not merged_attempts:
            return 0
        
        # 准备数据
        attempts_data = []
        for attempt in merged_attempts:
            attempts_data.append({
                'attempt_bk': attempt['attempt_bk'],
                'sso_id': attempt['sso_id'],
                'connector_id': attempt['connector_id'],
                'attempt_count': attempt['attempt_count'],
                'consumption_kwh': attempt.get('consumption_kwh', 0.0) or 0.0,
                'attempt_start_time': attempt['earliest_start'],
                'attempt_end_time': attempt['latest_end']
            })
        
        df = pd.DataFrame(attempts_data)
        
        # 批量插入
        conn = self.duckdb_client.connect()
        conn.register('temp_attempts', df)
        
        insert_query = """
        INSERT INTO Charger_Attempts 
        (attempt_bk, sso_id, connector_id, attempt_count, consumption_kwh, 
         attempt_start_time, attempt_end_time)
        SELECT attempt_bk, sso_id, connector_id, attempt_count, consumption_kwh,
               attempt_start_time, attempt_end_time
        FROM temp_attempts
        WHERE attempt_bk NOT IN (SELECT attempt_bk FROM Charger_Attempts)
        """
        conn.execute(insert_query)
        
        try:
            conn.execute("DROP TABLE IF EXISTS temp_attempts")
        except:
            pass
        
        logger.info(f"导入 {len(df)} 条充电尝试记录")
        return len(df)
    
    def import_ocpp_events(self, merged_attempts: List[Dict]) -> int:
        """
        导入OCPP事件到DuckDB
        
        Args:
            merged_attempts: 合并后的尝试记录列表
            
        Returns:
            导入的事件数量
        """
        batch_size = 1000000
        import_list = []
        total_imported = 0
        
        for attempt in merged_attempts:
            attempt_bk = attempt['attempt_bk']
            
            for ocpp_event in attempt.get('original_records', []):
                import_list.append({
                    'charger_attempts_bk': attempt_bk,
                    'operation_timestamp': ocpp_event['operation_timestamp'],
                    'ocpp_message_type': ocpp_event['ocpp_message_type'],
                    'ocpp_request_body': ocpp_event.get('ocpp_request_body'),
                    'ocpp_response_body': ocpp_event.get('ocpp_response_body')
                })
                
                if len(import_list) >= batch_size:
                    total_imported += self._insert_ocpp_batch(import_list)
                    import_list.clear()
        
        # 处理剩余数据
        if import_list:
            total_imported += self._insert_ocpp_batch(import_list)
        
        logger.info(f"导入 {total_imported} 条OCPP事件")
        return total_imported
    
    def _insert_ocpp_batch(self, records: List[Dict]) -> int:
        """插入一批OCPP事件"""
        df = pd.DataFrame(records)
        conn = self.duckdb_client.connect()
        
        conn.register('temp_ocpp', df)
        insert_query = """
        INSERT INTO OCPP_Events 
        (charger_attempts_bk, operation_timestamp, ocpp_message_type, 
         ocpp_request_body, ocpp_response_body)
        SELECT charger_attempts_bk, operation_timestamp, ocpp_message_type,
               ocpp_request_body, ocpp_response_body
        FROM temp_ocpp
        """
        conn.execute(insert_query)
        
        try:
            conn.execute("DROP TABLE IF EXISTS temp_ocpp")
        except:
            pass
        
        return len(records)
    
    def import_data(
        self, 
        start_date: str, 
        end_date: Optional[str] = None
    ) -> Dict:
        """
        主导入方法
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (可选)
            
        Returns:
            导入统计信息
        """
        # 解析日期
        start_dt = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if end_date:
            end_dt = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        else:
            end_dt = datetime.datetime.now()
        end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # 验证日期范围
        days_diff = (end_dt - start_dt).days
        if days_diff > 31:
            raise ValueError(f"日期范围超过一个月: {days_diff} 天")
        
        logger.info(f"开始导入数据: {start_date} 到 {end_date or '今日'}")
        
        try:
            # 连接数据库
            self.duckdb_client.connect()
            self.databricks_client.connect()
            
            # 删除现有数据
            deleted_count = self.delete_existing_data(start_dt, end_dt)
            
            # 查询充电尝试
            attempts_df = self.query_charging_attempts(start_dt, end_dt)
            
            if attempts_df.empty:
                return {
                    'attempts_imported': 0,
                    'ocpp_events_imported': 0,
                    'deleted_count': deleted_count
                }
            
            # 合并尝试记录
            merged_attempts = self.merger.merge(attempts_df)
            
            if not merged_attempts:
                return {
                    'attempts_imported': 0,
                    'ocpp_events_imported': 0,
                    'deleted_count': deleted_count
                }
            
            # 建立索引
            attempts_index = self.merger.build_index(merged_attempts)
            
            # 分页读取OCPP事件并匹配
            last_timestamp = None
            total_matched = 0
            page_number = 0
            
            while True:
                ocpp_df = self.query_ocpp_events_paginated(
                    start_dt, end_dt, 1000000, last_timestamp
                )
                
                if ocpp_df.empty:
                    break
                
                page_number += 1
                
                for _, row in ocpp_df.iterrows():
                    ocpp_event = {
                        'sso_id': row.get('sso_id', ''),
                        'operation_timestamp': row['operation_timestamp'],
                        'ocpp_message_type': row['ocpp_message_type'],
                        'ocpp_request_body': row.get('ocpp_request_body'),
                        'ocpp_response_body': row.get('ocpp_response_body')
                    }
                    
                    matched = self.ocpp_processor.match_event_to_attempts(
                        ocpp_event, attempts_index
                    )
                    total_matched += matched
                
                if not ocpp_df.empty:
                    last_timestamp = ocpp_df['operation_timestamp'].iloc[-1]
                    logger.info(f"第 {page_number} 页完成, 匹配 {total_matched} 条事件")
            
            # 分配业务主键
            self.merger.assign_business_keys(merged_attempts)
            
            # 导入数据
            attempts_imported = self.import_attempts(merged_attempts)
            ocpp_imported = self.import_ocpp_events(merged_attempts)
            
            logger.info("=" * 60)
            logger.info("导入完成")
            logger.info(f"充电尝试: {attempts_imported} 条")
            logger.info(f"OCPP事件: {ocpp_imported} 条")
            logger.info("=" * 60)
            
            return {
                'attempts_imported': attempts_imported,
                'ocpp_events_imported': ocpp_imported,
                'deleted_count': deleted_count
            }
            
        finally:
            self.databricks_client.close()
            self.duckdb_client.close()
