#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
用户反馈导入模块

职责：
- 从CSV文件导入用户反馈数据到本地DuckDB

主要接口：
- FeedbackImporter: 用户反馈导入器
  - import_from_csv(): 从CSV导入
"""

import datetime
import logging
import os
from typing import Optional

import pandas as pd

from ..data.duckdb_client import LegacyDuckDBClient
from ..utils.datetime_utils import parse_timestamp

logger = logging.getLogger(__name__)


class FeedbackImporter:
    """
    用户反馈导入器
    
    从CSV文件导入用户反馈到本地DuckDB数据库。
    """
    
    # 默认CSV路径
    DEFAULT_CSV_PATH = 'data/input/direct_access_user_feedback.csv'
    LEGACY_CSV_PATH = 'source_data/direct_access_user_feedback.csv'
    
    # 截止日期（只导入此日期之后的反馈）
    CUTOFF_DATE = datetime.datetime(2026, 1, 15)
    
    def __init__(self, csv_path: Optional[str] = None):
        """
        初始化导入器
        
        Args:
            csv_path: CSV文件路径
        """
        self.csv_path = csv_path
        self.duckdb_client = LegacyDuckDBClient()
    
    def _find_csv_path(self) -> str:
        """查找CSV文件路径"""
        if self.csv_path and os.path.exists(self.csv_path):
            return self.csv_path
        
        for path in [self.DEFAULT_CSV_PATH, self.LEGACY_CSV_PATH]:
            if os.path.exists(path):
                return path
        
        raise FileNotFoundError(
            f"找不到用户反馈CSV文件: {self.csv_path or self.DEFAULT_CSV_PATH}"
        )
    
    def _read_csv(self) -> pd.DataFrame:
        """读取CSV文件"""
        path = self._find_csv_path()
        logger.info(f"读取CSV文件: {path}")
        
        df = pd.read_csv(path, encoding='utf-8')
        logger.info(f"读取到 {len(df)} 条记录")
        return df
    
    def _preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        预处理数据
        
        - 解析日期
        - 过滤截止日期之后的记录
        - 添加ID列
        - 处理列名映射
        """
        # 清理列名
        df.columns = df.columns.str.strip()
        
        # 删除空列
        df = df.dropna(axis=1, how='all')
        df = df.loc[:, ~df.columns.str.startswith('Unnamed')]
        
        # 解析日期
        if 'Date input' in df.columns:
            df['date_input'] = df['Date input'].apply(parse_timestamp)
        elif 'date_input' in df.columns:
            df['date_input'] = df['date_input'].apply(parse_timestamp)
        
        # 过滤截止日期之后的记录
        df = df[df['date_input'] >= self.CUTOFF_DATE].copy()
        logger.info(f"过滤后剩余 {len(df)} 条记录")
        
        # 添加ID列
        df = df.reset_index(drop=True)
        df['id'] = df.index + 1
        
        # 列名映射
        column_mapping = {
            'Date input': 'date_input',
            'rating': 'rating',
            'comment': 'comment',
            'session_id': 'session_id',
            'country_code': 'country_code',
            'postal_code': 'postal_code',
            'Category': 'category',
            'EVSE ID': 'evse_id'
        }
        
        # 重命名列
        for old_name, new_name in column_mapping.items():
            if old_name in df.columns and old_name != new_name:
                df[new_name] = df[old_name]
        
        return df
    
    def _create_table(self) -> None:
        """创建表（如果不存在）"""
        create_sql = """
        CREATE TABLE IF NOT EXISTS direct_access_user_feedback (
            id BIGINT NOT NULL PRIMARY KEY,
            date_input TIMESTAMP NOT NULL,
            rating INTEGER,
            comment VARCHAR,
            session_id VARCHAR,
            country_code VARCHAR,
            postal_code VARCHAR,
            category VARCHAR,
            evse_id VARCHAR
        )
        """
        self.duckdb_client.execute(create_sql)
        logger.info("表 direct_access_user_feedback 已创建/确认存在")
    
    def _clear_table(self) -> None:
        """清空表"""
        self.duckdb_client.execute("DELETE FROM direct_access_user_feedback")
        logger.info("已清空 direct_access_user_feedback 表")
    
    def import_from_csv(self) -> int:
        """
        从CSV导入数据
        
        Returns:
            导入的记录数
        """
        try:
            self.duckdb_client.connect()
            
            # 创建表
            self._create_table()
            
            # 清空表
            self._clear_table()
            
            # 读取并预处理
            df = self._read_csv()
            df = self._preprocess(df)
            
            if df.empty:
                logger.warning("没有数据需要导入")
                return 0
            
            # 准备插入数据
            columns = ['id', 'date_input', 'rating', 'comment', 
                      'session_id', 'country_code', 'postal_code',
                      'category', 'evse_id']
            
            insert_df = df[[c for c in columns if c in df.columns]].copy()
            
            # 批量插入
            inserted = self.duckdb_client.insert_dataframe(
                'direct_access_user_feedback',
                insert_df,
                'temp_feedback'
            )
            
            logger.info(f"成功导入 {inserted} 条用户反馈")
            return inserted
            
        finally:
            self.duckdb_client.close()
