#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
充电桩位置导入模块

职责：
- 从Databricks导入充电桩位置数据到本地DuckDB

主要接口：
- LocationImporter: 位置导入器
  - import_locations(): 导入充电桩位置数据
"""

import datetime
import logging
from typing import Dict

import pandas as pd

from ..data.databricks_client import DatabricksClient
from ..data.duckdb_client import LegacyDuckDBClient

logger = logging.getLogger(__name__)


class LocationImporter:
    """
    充电桩位置导入器
    
    从Databricks导入充电桩位置信息到本地DuckDB。
    """
    
    def __init__(self):
        """初始化导入器"""
        self.databricks_client = DatabricksClient()
        self.duckdb_client = LegacyDuckDBClient()
    
    def query_locations(self) -> pd.DataFrame:
        """
        从Databricks查询充电桩位置数据
        
        Returns:
            位置数据DataFrame
        """
        today = datetime.date.today().strftime('%Y-%m-%d')
        
        query = f"""
        SELECT 
            sso_id,
            evse_id,
            evse_count,
            unique_location_id,
            source_location_id,
            country_code,
            district_name,
            city,
            postcode,
            street,
            latitude,
            longitude,
            socket_hardware_serial_number,
            socket_manufacturer_serial_number,
            socket_last_contact_firmware_version,
            model_type,
            project_name,
            project_number
        FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_location_charger_v 
        WHERE sso_valid_to > ('{today}')
        """
        
        logger.info("查询充电桩位置数据...")
        columns, rows = self.databricks_client.execute_query(query)
        
        if not rows:
            logger.warning("未找到充电桩位置数据")
            return pd.DataFrame(columns=columns)
        
        df = pd.DataFrame(rows, columns=columns)
        
        # 添加ID列
        df = df.reset_index(drop=True)
        df['id'] = df.index + 1
        
        logger.info(f"找到 {len(df)} 条充电桩位置记录")
        return df
    
    def _drop_table(self) -> None:
        """删除表"""
        self.duckdb_client.execute("DROP TABLE IF EXISTS Charger_Location")
        logger.info("已删除 Charger_Location 表")
    
    def _create_table(self) -> None:
        """创建表"""
        create_sql = """
        CREATE TABLE Charger_Location (
            id BIGINT NOT NULL PRIMARY KEY,
            sso_id VARCHAR NOT NULL,
            evse_id VARCHAR,
            evse_count INTEGER,
            unique_location_id VARCHAR,
            source_location_id VARCHAR,
            country_code VARCHAR,
            district_name VARCHAR,
            city VARCHAR,
            postcode VARCHAR,
            street VARCHAR,
            latitude DOUBLE,
            longitude DOUBLE,
            socket_hardware_serial_number VARCHAR,
            socket_manufacturer_serial_number VARCHAR,
            socket_last_contact_firmware_version VARCHAR,
            model_type VARCHAR,
            project_name VARCHAR,
            project_number VARCHAR
        )
        """
        self.duckdb_client.execute(create_sql)
        logger.info("已创建 Charger_Location 表")
    
    def import_locations(self) -> int:
        """
        导入充电桩位置数据
        
        Returns:
            导入的记录数
        """
        try:
            self.databricks_client.connect()
            self.duckdb_client.connect()
            
            # 删除并重建表
            self._drop_table()
            self._create_table()
            
            # 查询数据
            df = self.query_locations()
            
            if df.empty:
                return 0
            
            # 批量插入
            inserted = self.duckdb_client.insert_dataframe(
                'Charger_Location',
                df,
                'temp_location'
            )
            
            logger.info(f"成功导入 {inserted} 条充电桩位置记录")
            return inserted
            
        finally:
            self.databricks_client.close()
            self.duckdb_client.close()
