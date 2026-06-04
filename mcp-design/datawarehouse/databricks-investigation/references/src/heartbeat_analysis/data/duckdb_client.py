#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DuckDB本地数据库客户端

职责：
- 提供本地DuckDB数据库的连接管理
- 封装常用的数据库操作（查询、插入、删除等）

主要接口：
- DuckDBClient: 本地数据库客户端类
  - connect(): 建立连接
  - execute(): 执行SQL
  - query(): 执行查询并返回结果
  - close(): 关闭连接
"""

import os
import logging
from typing import Optional, Any, List, Tuple
from contextlib import contextmanager

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)


class DuckDBClient:
    """
    DuckDB本地数据库客户端
    
    负责管理与本地DuckDB数据库的连接和操作。
    支持上下文管理器模式和事务管理。
    """
    
    # 默认数据库路径
    DEFAULT_DB_DIR = 'data/database'
    DEFAULT_DB_NAME = 'localdb'
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化客户端
        
        Args:
            db_path: 数据库文件路径，默认为 data/database/localdb
        """
        if db_path is None:
            # 确保目录存在
            os.makedirs(self.DEFAULT_DB_DIR, exist_ok=True)
            self.db_path = os.path.join(self.DEFAULT_DB_DIR, self.DEFAULT_DB_NAME)
        else:
            self.db_path = db_path
            
        self._connection = None
    
    def connect(self) -> duckdb.DuckDBPyConnection:
        """
        建立数据库连接
        
        Returns:
            DuckDB连接对象
        """
        if self._connection is not None:
            return self._connection
            
        try:
            self._connection = duckdb.connect(self.db_path)
            # 启用关闭时自动checkpoint
            self._connection.execute("PRAGMA enable_checkpoint_on_shutdown")
            logger.info(f"DuckDB连接成功: {self.db_path}")
            return self._connection
        except Exception as e:
            logger.error(f"DuckDB连接失败: {e}")
            raise
    
    def close(self) -> None:
        """关闭数据库连接"""
        if self._connection is not None:
            try:
                self._connection.close()
                logger.info("DuckDB连接已关闭")
            except Exception as e:
                logger.warning(f"关闭DuckDB连接时出错: {e}")
            finally:
                self._connection = None
    
    def execute(self, query: str, params: Optional[list] = None) -> Any:
        """
        执行SQL语句
        
        Args:
            query: SQL语句
            params: 参数列表
            
        Returns:
            执行结果
        """
        conn = self.connect()
        try:
            logger.debug(f"执行SQL: {query[:200]}...")
            if params:
                return conn.execute(query, params)
            else:
                return conn.execute(query)
        except Exception as e:
            logger.error(f"执行SQL出错: {e}")
            logger.error(f"SQL语句: {query}")
            raise
    
    def query(self, query: str, params: Optional[list] = None) -> List[Tuple]:
        """
        执行查询并返回结果
        
        Args:
            query: SQL查询语句
            params: 参数列表
            
        Returns:
            查询结果列表
        """
        result = self.execute(query, params)
        return result.fetchall()
    
    def query_df(self, query: str, params: Optional[list] = None) -> pd.DataFrame:
        """
        执行查询并返回DataFrame
        
        Args:
            query: SQL查询语句
            params: 参数列表
            
        Returns:
            查询结果DataFrame
        """
        result = self.execute(query, params)
        return result.fetchdf()
    
    def insert_dataframe(
        self, 
        table_name: str, 
        df: pd.DataFrame,
        temp_table_name: Optional[str] = None
    ) -> int:
        """
        使用DataFrame批量插入数据
        
        Args:
            table_name: 目标表名
            df: 数据DataFrame
            temp_table_name: 临时表名，默认为 temp_{table_name}
            
        Returns:
            插入的记录数
        """
        if df.empty:
            logger.info(f"DataFrame为空，跳过插入 {table_name}")
            return 0
        
        conn = self.connect()
        temp_name = temp_table_name or f"temp_{table_name}"
        
        try:
            # 注册DataFrame为临时表
            conn.register(temp_name, df)
            
            # 获取列名
            columns = ', '.join(df.columns)
            
            # 执行批量插入
            insert_query = f"""
            INSERT INTO {table_name} ({columns})
            SELECT {columns} FROM {temp_name}
            """
            conn.execute(insert_query)
            
            inserted_count = len(df)
            logger.info(f"成功插入 {inserted_count} 条记录到 {table_name}")
            
            return inserted_count
            
        finally:
            # 清理临时表
            try:
                conn.execute(f"DROP TABLE IF EXISTS {temp_name}")
            except Exception as e:
                logger.debug(f"清理临时表 {temp_name} 时出错（可忽略）: {e}")
    
    @contextmanager
    def transaction(self):
        """
        事务上下文管理器
        
        使用示例：
            with client.transaction():
                client.execute("INSERT ...")
                client.execute("UPDATE ...")
        """
        conn = self.connect()
        conn.execute("BEGIN TRANSACTION")
        try:
            yield conn
            conn.execute("COMMIT")
            logger.debug("事务已提交")
        except Exception as e:
            conn.execute("ROLLBACK")
            logger.error(f"事务已回滚: {e}")
            raise
    
    def table_exists(self, table_name: str) -> bool:
        """
        检查表是否存在
        
        Args:
            table_name: 表名
            
        Returns:
            是否存在
        """
        query = """
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_name = ?
        """
        result = self.query(query, [table_name])
        return result[0][0] > 0
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
        return False


# 兼容旧代码的路径
class LegacyDuckDBClient(DuckDBClient):
    """兼容旧代码的客户端，使用旧的数据库路径"""
    
    DEFAULT_DB_DIR = 'local_database'
    DEFAULT_DB_NAME = 'localdb'
