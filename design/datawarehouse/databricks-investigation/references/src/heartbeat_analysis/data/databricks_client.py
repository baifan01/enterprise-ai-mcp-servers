#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Databricks数据仓库客户端

职责：
- 提供Databricks数据仓库的连接管理
- 封装与Databricks相关的SQL查询操作

主要接口：
- DatabricksClient: 数据仓库客户端类
  - connect(): 建立连接
  - query(): 执行查询
  - close(): 关闭连接
"""

import os
import logging
from typing import Dict, Optional, Any
from contextlib import contextmanager

from databricks import sql as databricks_sql

logger = logging.getLogger(__name__)


class DatabricksClient:
    """
    Databricks数据仓库客户端
    
    负责管理与Databricks的连接，执行SQL查询。
    支持上下文管理器模式，确保连接正确释放。
    """
    
    # 默认连接参数（从环境变量或使用默认值）
    DEFAULT_SERVER_HOSTNAME = os.environ.get(
        'DATABRICKS_SERVER_HOSTNAME',
        'shell-prj2778928-674688609822-eu-west-1-prd.cloud.databricks.com'
    )
    DEFAULT_HTTP_PATH = os.environ.get(
        'DATABRICKS_HTTP_PATH',
        '/sql/1.0/warehouses/d0ba8f87b62d10f2'
    )
    DEFAULT_ACCESS_TOKEN = os.environ.get(
        'DATABRICKS_TOKEN',
        'DATABRICKS_TOKEN_PLACEHOLDER'
    )
    
    def __init__(
        self,
        server_hostname: Optional[str] = None,
        http_path: Optional[str] = None,
        access_token: Optional[str] = None
    ):
        """
        初始化客户端
        
        Args:
            server_hostname: Databricks服务器主机名
            http_path: HTTP路径
            access_token: 访问令牌
        """
        self.server_hostname = server_hostname or self.DEFAULT_SERVER_HOSTNAME
        self.http_path = http_path or self.DEFAULT_HTTP_PATH
        self.access_token = access_token or self.DEFAULT_ACCESS_TOKEN
        self._connection = None
    
    def get_connection_params(self) -> Dict[str, str]:
        """获取连接参数字典"""
        return {
            "server_hostname": self.server_hostname,
            "http_path": self.http_path,
            "access_token": self.access_token
        }
    
    def connect(self) -> Any:
        """
        建立数据库连接
        
        Returns:
            Databricks连接对象
        """
        if self._connection is not None:
            return self._connection
            
        try:
            params = self.get_connection_params()
            self._connection = databricks_sql.connect(**params)
            logger.info("Databricks连接成功")
            return self._connection
        except Exception as e:
            logger.error(f"Databricks连接失败: {e}")
            raise
    
    def close(self) -> None:
        """关闭数据库连接"""
        if self._connection is not None:
            try:
                self._connection.close()
                logger.info("Databricks连接已关闭")
            except Exception as e:
                logger.warning(f"关闭Databricks连接时出错: {e}")
            finally:
                self._connection = None
    
    def execute_query(self, query: str, params: Optional[list] = None) -> list:
        """
        执行SQL查询
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            查询结果列表
        """
        conn = self.connect()
        try:
            with conn.cursor() as cursor:
                logger.debug(f"执行SQL: {query[:200]}...")
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                logger.info(f"查询返回 {len(rows)} 条记录")
                return columns, rows
                
        except Exception as e:
            logger.error(f"执行查询出错: {e}")
            logger.error(f"SQL语句: {query}")
            raise
    
    @contextmanager
    def get_cursor(self):
        """
        获取游标（上下文管理器）
        
        使用示例：
            with client.get_cursor() as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
        """
        conn = self.connect()
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
        return False
