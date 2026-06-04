#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
用户反馈分析模块

职责：
- 分析用户反馈与OCPP事件的关联
- 生成反馈分析报告
- 支持AI辅助分析

主要接口：
- FeedbackAnalyzer: 反馈分析器
  - analyze(): 分析指定时间范围的用户反馈
"""

import datetime
import json
import logging
import os
from typing import Dict, List, Optional

from ..data.duckdb_client import LegacyDuckDBClient
from ..core.ai_analyzer import AIAnalyzer
from ..utils.json_utils import format_json
from .ocpp_analyzer import OCPPAnalyzer

logger = logging.getLogger(__name__)


class FeedbackAnalyzer:
    """
    用户反馈分析器
    
    分析用户反馈与对应OCPP事件的关联关系。
    """
    
    def __init__(self, enable_ai: bool = False):
        """
        初始化分析器
        
        Args:
            enable_ai: 是否启用AI分析
        """
        self.duckdb_client = LegacyDuckDBClient()
        self.ocpp_analyzer = OCPPAnalyzer(enable_ai=False)
        self.ai_analyzer = AIAnalyzer() if enable_ai else None
        self.enable_ai = enable_ai
    
    def fetch_feedbacks(
        self, 
        start_time: datetime.datetime,
        end_time: datetime.datetime
    ) -> List[Dict]:
        """
        获取指定时间范围的用户反馈
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            用户反馈列表
        """
        query = """
        SELECT 
            f.id,
            f.date_input,
            f.rating,
            f.comment,
            f.category,
            m.attempt_bk,
            m.match_condition
        FROM direct_access_user_feedback f
        LEFT JOIN feedback_attempt_match m ON f.id = m.user_feedback_id
        WHERE f.date_input >= ? AND f.date_input <= ?
        ORDER BY f.date_input ASC
        """
        
        result = self.duckdb_client.query(query, [start_time, end_time])
        
        feedbacks = []
        for row in result:
            feedbacks.append({
                'id': row[0],
                'date_input': row[1],
                'rating': row[2],
                'comment': row[3],
                'category': row[4],
                'attempt_bk': row[5],
                'match_condition': row[6]
            })
        
        logger.info(f"获取到 {len(feedbacks)} 条用户反馈")
        return feedbacks
    
    def generate_feedback_json(self, feedback: Dict) -> str:
        """
        生成单条反馈的JSON
        
        Args:
            feedback: 反馈数据
            
        Returns:
            JSON字符串
        """
        date_input = feedback.get('date_input')
        if isinstance(date_input, datetime.datetime):
            date_input = date_input.isoformat()
        
        data = {
            'id': feedback.get('id'),
            'date_input': date_input,
            'rating': feedback.get('rating'),
            'comment': feedback.get('comment'),
            'category': feedback.get('category'),
            'attempt_bk': feedback.get('attempt_bk'),
            'match_condition': feedback.get('match_condition')
        }
        
        return format_json(data)
    
    def generate_feedback_ocpp_pair(self, feedback: Dict) -> List[str]:
        """
        生成反馈和OCPP事件的配对JSON
        
        Args:
            feedback: 反馈数据
            
        Returns:
            [feedback_json, ocpp_json] 列表
        """
        # 生成反馈JSON
        feedback_json = self.generate_feedback_json(feedback)
        
        # 获取OCPP事件JSON
        attempt_bk = feedback.get('attempt_bk')
        if not attempt_bk:
            return [feedback_json, "null"]
        
        attempt_info, ocpp_events = self.ocpp_analyzer.fetch_attempt_with_events(
            attempt_bk
        )
        
        if attempt_info is None:
            return [feedback_json, "null"]
        
        analysis_json = self.ocpp_analyzer.generate_analysis_json(
            attempt_info, ocpp_events
        )
        ocpp_json = format_json(analysis_json)
        
        return [feedback_json, ocpp_json]
    
    def analyze(
        self, 
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        output_file: Optional[str] = None
    ) -> List[Dict]:
        """
        分析指定时间范围内的用户反馈
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            output_file: 输出文件路径（可选）
            
        Returns:
            分析结果列表
        """
        logger.info(f"分析用户反馈: {start_time} 到 {end_time}")
        
        results = []
        
        try:
            self.duckdb_client.connect()
            self.ocpp_analyzer.duckdb_client = self.duckdb_client
            
            # 获取反馈数据
            feedbacks = self.fetch_feedbacks(start_time, end_time)
            
            if not feedbacks:
                logger.warning("未找到用户反馈数据")
                return []
            
            # 逐条处理
            for idx, feedback in enumerate(feedbacks, 1):
                logger.info(f"处理 {idx}/{len(feedbacks)}")
                
                result_pair = self.generate_feedback_ocpp_pair(feedback)
                
                # AI分析
                ai_result = None
                if self.enable_ai and self.ai_analyzer:
                    ai_result = self.ai_analyzer.analyze_with_feedback(
                        result_pair[0], result_pair[1]
                    )
                
                results.append({
                    'feedback': feedback,
                    'result_pair': result_pair,
                    'ai_result': ai_result
                })
            
        finally:
            self.duckdb_client.close()
        
        # 写入文件
        if output_file:
            self._write_results_to_file(results, output_file)
        
        logger.info(f"分析完成，共 {len(results)} 条记录")
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
            feedback = item['feedback']
            result_pair = item['result_pair']
            ai_result = item.get('ai_result')
            
            lines.append("\n" + "=" * 70)
            lines.append(f"【第 {idx}/{len(results)} 条反馈】")
            lines.append("=" * 70)
            
            lines.append("\n--- 用户反馈 ---")
            lines.append(result_pair[0])
            
            lines.append("\n--- 对应OCPP事件 ---")
            if result_pair[1] != "null":
                lines.append(result_pair[1])
            else:
                attempt_bk = feedback.get('attempt_bk')
                if attempt_bk:
                    lines.append(f"未找到 attempt_bk={attempt_bk} 对应的OCPP事件")
                else:
                    lines.append("该反馈没有匹配的充电尝试记录")
            
            lines.append("\n--- AI 分析结果 ---")
            lines.append(ai_result or "无 AI 分析结果")
        
        lines.append("\n" + "=" * 70)
        lines.append(f"处理完成，共 {len(results)} 条记录")
        lines.append("=" * 70 + "\n")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        
        logger.info(f"结果已写入: {output_file}")
