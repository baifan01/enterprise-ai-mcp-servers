#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OCPP事件分析模块

职责：
- 从本地DuckDB读取OCPP事件并分析
- 生成分析用JSON结构
- 调用AI进行分析

主要接口：
- OCPPAnalyzer: OCPP分析器类
  - analyze(): 分析指定attempt的OCPP事件
  - analyze_batch(): 批量分析
"""

import datetime
import json
import logging
import os
from typing import Dict, List, Optional, Tuple

from ..data.duckdb_client import LegacyDuckDBClient
from ..core.ocpp_processor import OCPPProcessor
from ..core.ai_analyzer import AIAnalyzer
from ..utils.json_utils import format_json

logger = logging.getLogger(__name__)


class OCPPAnalyzer:
    """
    OCPP事件分析器
    
    从本地DuckDB读取充电尝试关联的OCPP事件，
    生成结构化JSON供AI分析使用。
    """
    
    def __init__(self, enable_ai: bool = False):
        """
        初始化分析器
        
        Args:
            enable_ai: 是否启用AI分析
        """
        self.duckdb_client = LegacyDuckDBClient()
        self.ocpp_processor = OCPPProcessor()
        self.ai_analyzer = AIAnalyzer() if enable_ai else None
        self.enable_ai = enable_ai
    
    def fetch_attempt_with_events(
        self, 
        attempt_bk: str
    ) -> Tuple[Optional[Dict], List[Dict]]:
        """
        获取充电尝试信息和关联的OCPP事件
        
        Args:
            attempt_bk: 充电尝试业务主键
            
        Returns:
            (attempt_info, ocpp_events) 元组
        """
        query = """
        SELECT 
            a.attempt_bk,
            a.sso_id,
            a.connector_id,
            a.attempt_count,
            a.consumption_kwh,
            a.attempt_start_time,
            a.attempt_end_time,
            e.operation_timestamp,
            e.ocpp_message_type,
            e.ocpp_request_body,
            e.ocpp_response_body
        FROM Charger_Attempts a
        LEFT JOIN OCPP_Events e ON a.attempt_bk = e.charger_attempts_bk
        WHERE a.attempt_bk = ?
        ORDER BY e.operation_timestamp ASC
        """
        
        try:
            result = self.duckdb_client.query(query, [attempt_bk])
            
            if not result:
                logger.warning(f"未找到 attempt_bk={attempt_bk}")
                return None, []
            
            # 提取attempt信息
            first_row = result[0]
            attempt_info = {
                'attempt_bk': first_row[0],
                'sso_id': first_row[1],
                'connector_id': first_row[2],
                'attempt_count': first_row[3],
                'consumption_kwh': first_row[4],
                'attempt_start_time': first_row[5],
                'attempt_end_time': first_row[6]
            }
            
            # 提取OCPP事件
            ocpp_events = []
            for row in result:
                if row[7] is None:
                    continue
                
                event = {
                    'operation_timestamp': row[7],
                    'ocpp_message_type': row[8],
                    'ocpp_request_body': row[9],
                    'ocpp_response_body': row[10]
                }
                ocpp_events.append(event)
            
            logger.info(f"获取到 {len(ocpp_events)} 条OCPP事件")
            return attempt_info, ocpp_events
            
        except Exception as e:
            logger.error(f"查询失败: {e}")
            raise
    
    def generate_analysis_json(
        self, 
        attempt_info: Dict, 
        ocpp_events: List[Dict]
    ) -> Dict:
        """
        生成分析用JSON
        
        Args:
            attempt_info: 充电尝试信息
            ocpp_events: OCPP事件列表
            
        Returns:
            分析JSON字典
        """
        if not ocpp_events:
            return {
                'attempt_bk': attempt_info.get('attempt_bk'),
                'attempt_info': self._format_attempt_info(attempt_info),
                'event_count': 0,
                'events': []
            }
        
        # 处理事件
        _, processed_events = self.ocpp_processor.process_events_batch(ocpp_events)
        
        return {
            'attempt_bk': attempt_info.get('attempt_bk'),
            'attempt_info': self._format_attempt_info(attempt_info),
            'event_count': len(processed_events),
            'events': processed_events
        }
    
    def _format_attempt_info(self, attempt_info: Dict) -> Dict:
        """格式化attempt信息"""
        def format_dt(dt):
            if dt is None:
                return None
            if isinstance(dt, datetime.datetime):
                return dt.isoformat()
            return str(dt)
        
        return {
            'sso_id': attempt_info.get('sso_id'),
            'connector_id': attempt_info.get('connector_id'),
            'attempt_count': attempt_info.get('attempt_count'),
            'consumption_kwh': attempt_info.get('consumption_kwh'),
            'attempt_start_time': format_dt(attempt_info.get('attempt_start_time')),
            'attempt_end_time': format_dt(attempt_info.get('attempt_end_time'))
        }
    
    def analyze(self, attempt_bk: str) -> Optional[Dict]:
        """
        分析指定充电尝试的OCPP事件
        
        Args:
            attempt_bk: 充电尝试业务主键
            
        Returns:
            分析结果字典
        """
        logger.info(f"开始分析 attempt_bk={attempt_bk}")
        
        try:
            self.duckdb_client.connect()
            
            # 获取数据
            attempt_info, ocpp_events = self.fetch_attempt_with_events(attempt_bk)
            
            if attempt_info is None:
                return None
            
            # 生成分析JSON
            result = self.generate_analysis_json(attempt_info, ocpp_events)
            
            # AI分析（可选）
            if self.enable_ai and self.ai_analyzer:
                ocpp_json = format_json(result)
                ai_result = self.ai_analyzer.analyze_attempt_only(
                    attempt_info,
                    result.get('events', [])
                )
                result['ai_analysis'] = ai_result
            
            return result
            
        finally:
            self.duckdb_client.close()
    
    def analyze_batch(
        self, 
        attempt_bks: List[str],
        output_file: Optional[str] = None
    ) -> List[Dict]:
        """
        批量分析多个充电尝试
        
        Args:
            attempt_bks: 充电尝试业务主键列表
            output_file: 输出文件路径（可选）
            
        Returns:
            分析结果列表
        """
        logger.info(f"开始批量分析 {len(attempt_bks)} 个尝试")
        
        results = []
        
        try:
            self.duckdb_client.connect()
            
            for idx, attempt_bk in enumerate(attempt_bks, 1):
                logger.info(f"处理 {idx}/{len(attempt_bks)}: {attempt_bk}")
                
                attempt_info, ocpp_events = self.fetch_attempt_with_events(attempt_bk)
                
                if attempt_info is None:
                    results.append({
                        'attempt_bk': attempt_bk,
                        'error': 'Not found'
                    })
                    continue
                
                analysis_json = self.generate_analysis_json(attempt_info, ocpp_events)
                
                # AI分析
                ai_result = None
                if self.enable_ai and self.ai_analyzer:
                    ai_result = self.ai_analyzer.analyze_attempt_only(
                        attempt_info,
                        analysis_json.get('events', [])
                    )
                
                results.append({
                    'attempt_bk': attempt_bk,
                    'ocpp_json': format_json(analysis_json),
                    'ai_result': ai_result
                })
            
        finally:
            self.duckdb_client.close()
        
        # 写入文件
        if output_file:
            self._write_results_to_file(results, output_file)
        
        return results
    
    def _write_results_to_file(
        self, 
        results: List[Dict], 
        output_file: str
    ) -> None:
        """将结果写入文件"""
        output_dir = os.path.dirname(output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        lines = []
        
        for idx, item in enumerate(results, 1):
            lines.append("\n" + "=" * 70)
            lines.append(f"【第 {idx}/{len(results)} 个尝试】{item['attempt_bk']}")
            lines.append("=" * 70)
            
            if 'error' in item:
                lines.append(f"\n错误: {item['error']}")
            else:
                lines.append("\n--- OCPP 事件 ---")
                lines.append(item.get('ocpp_json', 'N/A'))
                
                lines.append("\n--- AI 分析结果 ---")
                lines.append(item.get('ai_result') or '无AI分析结果')
        
        lines.append("\n" + "=" * 70)
        lines.append(f"处理完成，共 {len(results)} 个尝试")
        lines.append("=" * 70 + "\n")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        
        logger.info(f"结果已写入: {output_file}")
    
    def print_result(self, result: Dict) -> None:
        """打印分析结果"""
        print("\n" + "=" * 60)
        print("OCPP事件分析结果")
        print("=" * 60)
        print(format_json(result))
        print("=" * 60 + "\n")
