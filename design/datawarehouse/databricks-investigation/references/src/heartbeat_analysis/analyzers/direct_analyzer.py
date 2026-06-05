#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
直连数据仓库分析器

职责：
- 协调各组件完成直连Databricks的完整分析流程
- 调用AI分析
- 存储分析结果到本地DuckDB

主要接口：
- DirectAnalyzer: 主分析器类
  - analyze(): 单个分析
  - analyze_batch(): 批量分析

依赖：
- DatabricksClient: 数据仓库连接
- LegacyDuckDBClient: 本地数据库连接
- DirectAttemptFinder: 尝试查找器
- DirectOCPPFetcher: OCPP事件获取器
- OCPPProcessor: OCPP事件处理器
- AIAnalyzer: AI分析器
"""

import datetime
import json
import logging
from typing import Dict, List, Optional

from ..core.ai_analyzer import AIAnalyzer
from ..core.direct_attempt_finder import DirectAttemptFinder
from ..core.direct_ocpp_fetcher import DirectOCPPFetcher
from ..core.ocpp_processor import OCPPProcessor
from ..data.databricks_client import DatabricksClient
from ..data.duckdb_client import LegacyDuckDBClient
from ..data.models import DirectAnalysisResult, DirectMergedAttempt
from ..utils.datetime_utils import parse_timestamp

logger = logging.getLogger(__name__)


class DirectAnalyzer:
    """
    直连数据仓库分析器
    
    协调各组件完成从Databricks直连查询、合并、
    OCPP事件处理、AI分析到结果存储的完整流程。
    """
    
    # 结果表名
    RESULT_TABLE_NAME = 'ocpp_ai_analysis_results'
    
    def __init__(self, enable_ai: bool = True):
        """
        初始化分析器
        
        Args:
            enable_ai: 是否启用AI分析
        """
        self._databricks_client: Optional[DatabricksClient] = None
        self._duckdb_client: Optional[LegacyDuckDBClient] = None
        self._attempt_finder: Optional[DirectAttemptFinder] = None
        self._ocpp_fetcher: Optional[DirectOCPPFetcher] = None
        self._ocpp_processor: Optional[OCPPProcessor] = None
        self._ai_analyzer: Optional[AIAnalyzer] = None
        
        self.enable_ai = enable_ai
    
    # ========================
    # 第一部分：连接管理
    # ========================
    
    @property
    def databricks_client(self) -> DatabricksClient:
        """懒加载Databricks客户端"""
        if self._databricks_client is None:
            self._databricks_client = DatabricksClient()
            self._databricks_client.connect()
        return self._databricks_client
    
    @property
    def duckdb_client(self) -> LegacyDuckDBClient:
        """懒加载DuckDB客户端"""
        if self._duckdb_client is None:
            self._duckdb_client = LegacyDuckDBClient()
            self._duckdb_client.connect()
            self._ensure_result_table()
        return self._duckdb_client
    
    @property
    def attempt_finder(self) -> DirectAttemptFinder:
        """懒加载尝试查找器"""
        if self._attempt_finder is None:
            self._attempt_finder = DirectAttemptFinder(self.databricks_client)
        return self._attempt_finder
    
    @property
    def ocpp_fetcher(self) -> DirectOCPPFetcher:
        """懒加载OCPP事件获取器"""
        if self._ocpp_fetcher is None:
            self._ocpp_fetcher = DirectOCPPFetcher(self.databricks_client)
        return self._ocpp_fetcher
    
    @property
    def ocpp_processor(self) -> OCPPProcessor:
        """懒加载OCPP处理器"""
        if self._ocpp_processor is None:
            self._ocpp_processor = OCPPProcessor()
        return self._ocpp_processor
    
    @property
    def ai_analyzer(self) -> Optional[AIAnalyzer]:
        """懒加载AI分析器"""
        if self.enable_ai and self._ai_analyzer is None:
            self._ai_analyzer = AIAnalyzer()
        return self._ai_analyzer
    
    def close(self):
        """关闭所有连接"""
        if self._databricks_client:
            self._databricks_client.close()
            self._databricks_client = None
        if self._duckdb_client:
            self._duckdb_client.close()
            self._duckdb_client = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    # ========================
    # 第二部分：结果表管理
    # ========================
    
    def _ensure_result_table(self):
        """确保结果表存在"""
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.RESULT_TABLE_NAME} (
            id INTEGER PRIMARY KEY,
            analysis_timestamp TIMESTAMP NOT NULL,
            input_timestamp TIMESTAMP,
            evse_id VARCHAR,
            sso_id VARCHAR NOT NULL,
            connector_id INTEGER,
            attempt_start TIMESTAMP,
            attempt_end TIMESTAMP,
            total_consumption_kwh DOUBLE,
            attempt_count INTEGER,
            ocpp_event_count INTEGER,
            ai_analysis_result TEXT,
            raw_ocpp_events TEXT
        )
        """
        self.duckdb_client.execute(create_sql)
        logger.debug(f"确保结果表 {self.RESULT_TABLE_NAME} 存在")
    
    def _get_next_id(self) -> int:
        """获取下一个ID"""
        result = self.duckdb_client.query(
            f"SELECT COALESCE(MAX(id), 0) + 1 FROM {self.RESULT_TABLE_NAME}"
        )
        return result[0][0] if result else 1
    
    def _save_result(
        self,
        result: DirectAnalysisResult
    ) -> int:
        """
        保存分析结果到本地数据库
        
        Args:
            result: 分析结果对象
            
        Returns:
            插入的记录ID
        """
        result.id = self._get_next_id()
        
        insert_sql = f"""
        INSERT INTO {self.RESULT_TABLE_NAME} (
            id, analysis_timestamp, input_timestamp, evse_id, sso_id,
            connector_id, attempt_start, attempt_end, total_consumption_kwh,
            attempt_count, ocpp_event_count, ai_analysis_result, raw_ocpp_events
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = [
            result.id,
            result.analysis_timestamp,
            result.input_timestamp,
            result.evse_id,
            result.sso_id,
            result.connector_id,
            result.attempt_start,
            result.attempt_end,
            result.total_consumption_kwh,
            result.attempt_count,
            result.ocpp_event_count,
            result.ai_analysis_result,
            result.raw_ocpp_events
        ]
        
        self.duckdb_client.execute(insert_sql, params)
        logger.info(f"分析结果已保存，ID={result.id}")
        
        return result.id
    
    # ========================
    # 第三部分：核心分析逻辑
    # ========================
    
    def analyze(
        self,
        input_timestamp: datetime.datetime,
        evse_id: Optional[str] = None,
        sso_id: Optional[str] = None,
        save_result: bool = True
    ) -> List[Dict]:
        """
        主分析方法
        
        执行完整的分析流程：
        1. 查找并合并充电尝试
        2. 获取OCPP事件
        3. 整理OCPP事件
        4. AI分析
        5. 保存结果
        
        Args:
            input_timestamp: 查询时间戳
            evse_id: EVSE ID（可选）
            sso_id: SSO ID（可选，与evse_id至少提供一个）
            save_result: 是否保存结果到数据库
            
        Returns:
            分析结果列表（每个Connector一个）
        """
        if not evse_id and not sso_id:
            raise ValueError("evse_id 和 sso_id 至少需要提供一个")
        
        logger.info(f"开始分析: timestamp={input_timestamp}, "
                   f"evse_id={evse_id}, sso_id={sso_id}")
        
        # 步骤1-3: 查找并合并充电尝试
        merged_attempts = self.attempt_finder.find_and_merge(
            input_timestamp, evse_id, sso_id
        )
        
        if not merged_attempts:
            logger.warning("未找到任何充电尝试记录")
            return []
        
        results = []
        
        for attempt in merged_attempts:
            try:
                result = self._analyze_single_attempt(
                    attempt, input_timestamp, save_result
                )
                results.append(result)
            except Exception as e:
                logger.error(f"分析Connector {attempt.connector_id} 失败: {e}")
                continue
        
        logger.info(f"分析完成，共 {len(results)} 个结果")
        return results
    
    def _analyze_single_attempt(
        self,
        attempt: DirectMergedAttempt,
        input_timestamp: datetime.datetime,
        save_result: bool
    ) -> Dict:
        """
        分析单个合并后的尝试
        
        Args:
            attempt: 合并后的尝试
            input_timestamp: 输入时间戳
            save_result: 是否保存结果
            
        Returns:
            分析结果字典
        """
        logger.info(f"分析 Connector {attempt.connector_id}...")
        
        # 步骤4: 获取OCPP事件（带边界扩展）
        raw_events = self.ocpp_fetcher.fetch_and_expand(attempt)
        
        # 步骤5: 整理OCPP事件
        processed_events = []
        if raw_events:
            _, processed_events = self.ocpp_processor.process_events_batch(
                [self._convert_event_format(e) for e in raw_events]
            )
            attempt.processed_events = processed_events
        
        # 步骤6: AI分析
        ai_result = None
        if self.ai_analyzer and processed_events:
            ai_result = self._call_ai_analysis(attempt, processed_events)
        
        # 步骤7: 保存结果
        analysis_result = DirectAnalysisResult.from_merged_attempt(
            attempt, input_timestamp, ai_result
        )
        
        if save_result:
            self._save_result(analysis_result)
        
        return {
            'attempt': attempt.to_dict(),
            'processed_events': processed_events,
            'ai_result': ai_result,
            'saved_id': analysis_result.id if save_result else None
        }
    
    def _convert_event_format(self, event: Dict) -> Dict:
        """
        转换事件格式以适配OCPPProcessor
        
        OCPPProcessor期望的键名是ocpp_request_body/ocpp_response_body
        
        Args:
            event: 原始事件字典
            
        Returns:
            转换后的事件字典
        """
        return {
            'operation_timestamp': event['operation_timestamp'],
            'ocpp_message_type': event['ocpp_message_type'],
            'ocpp_request_body': event.get('ocpp_request_body'),
            'ocpp_response_body': event.get('ocpp_response_body')
        }
    
    def _call_ai_analysis(
        self,
        attempt: DirectMergedAttempt,
        processed_events: List[Dict]
    ) -> Optional[str]:
        """
        调用AI分析
        
        Args:
            attempt: 合并后的尝试
            processed_events: 处理后的OCPP事件
            
        Returns:
            AI分析结果文本
        """
        try:
            attempt_info = {
                'evse_id': attempt.evse_id,
                'sso_id': attempt.sso_id,
                'connector_id': attempt.connector_id,
                'attempt_start': attempt.attempt_start.isoformat(),
                'attempt_end': attempt.attempt_end.isoformat(),
                'total_consumption_kwh': attempt.total_consumption_kwh,
                'attempt_count': attempt.attempt_count,
                'duration_seconds': attempt.duration_seconds
            }
            
            result = self.ai_analyzer.analyze_attempt_only(
                attempt_info, processed_events
            )
            return result
            
        except Exception as e:
            logger.error(f"AI分析失败: {e}")
            return None
    
    # ========================
    # 第四部分：批量分析
    # ========================
    
    def analyze_batch(
        self,
        inputs: List[Dict],
        save_results: bool = True
    ) -> List[Dict]:
        """
        批量分析
        
        Args:
            inputs: 输入列表，每个元素包含:
                - timestamp: 时间戳（字符串或datetime）
                - evse_id: EVSE ID（可选）
                - sso_id: SSO ID（可选）
            save_results: 是否保存结果
            
        Returns:
            所有分析结果列表
        """
        all_results = []
        
        for i, input_item in enumerate(inputs):
            logger.info(f"批量分析进度: {i+1}/{len(inputs)}")
            
            try:
                # 解析时间戳
                ts = input_item.get('timestamp')
                if isinstance(ts, str):
                    ts = parse_timestamp(ts)
                
                # 执行分析
                results = self.analyze(
                    input_timestamp=ts,
                    evse_id=input_item.get('evse_id'),
                    sso_id=input_item.get('sso_id'),
                    save_result=save_results
                )
                all_results.extend(results)
                
            except Exception as e:
                logger.error(f"批量分析项 {i+1} 失败: {e}")
                continue
        
        logger.info(f"批量分析完成，共 {len(all_results)} 个结果")
        return all_results


# ================================
# 便捷函数
# ================================

def quick_analyze(
    timestamp: str,
    evse_id: Optional[str] = None,
    sso_id: Optional[str] = None,
    enable_ai: bool = True
) -> List[Dict]:
    """
    快速分析便捷函数
    
    Args:
        timestamp: 时间戳字符串
        evse_id: EVSE ID
        sso_id: SSO ID
        enable_ai: 是否启用AI
        
    Returns:
        分析结果列表
    """
    ts = parse_timestamp(timestamp)
    
    with DirectAnalyzer(enable_ai=enable_ai) as analyzer:
        return analyzer.analyze(ts, evse_id, sso_id)
