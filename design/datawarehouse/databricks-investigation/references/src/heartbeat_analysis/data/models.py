#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据模型定义

职责：
- 定义项目中使用的数据结构和模型
- 提供数据验证和转换方法

主要模型：
- MergedAttempt: 合并后的充电尝试模型
- OCPPEvent: OCPP事件模型
- UserFeedback: 用户反馈模型
- ChargerLocation: 充电桩位置模型
"""

import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class MergedAttempt:
    """
    合并后的充电尝试模型
    
    表示将多个原始充电尝试记录合并后的结果。
    每个connector_id对应一条记录。
    """
    sso_id: str
    connector_id: int
    attempt_count: int
    consumption_kwh: float
    earliest_start: datetime.datetime
    latest_end: datetime.datetime
    original_records: List[Dict] = field(default_factory=list)
    attempt_bk: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'sso_id': self.sso_id,
            'connector_id': self.connector_id,
            'attempt_count': self.attempt_count,
            'consumption_kwh': self.consumption_kwh,
            'earliest_start': self.earliest_start,
            'latest_end': self.latest_end,
            'original_records': self.original_records,
            'attempt_bk': self.attempt_bk
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MergedAttempt':
        """从字典创建实例"""
        return cls(
            sso_id=data['sso_id'],
            connector_id=data['connector_id'],
            attempt_count=data['attempt_count'],
            consumption_kwh=data.get('consumption_kwh', 0.0),
            earliest_start=data['earliest_start'],
            latest_end=data['latest_end'],
            original_records=data.get('original_records', []),
            attempt_bk=data.get('attempt_bk')
        )


@dataclass
class OCPPEvent:
    """
    OCPP事件模型
    
    表示一条OCPP协议事件记录。
    """
    sso_id: str
    operation_timestamp: datetime.datetime
    ocpp_message_type: str
    ocpp_request_body: Optional[str] = None
    ocpp_response_body: Optional[str] = None
    connector_id: Optional[int] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'sso_id': self.sso_id,
            'operation_timestamp': self.operation_timestamp,
            'ocpp_message_type': self.ocpp_message_type,
            'ocpp_request_body': self.ocpp_request_body,
            'ocpp_response_body': self.ocpp_response_body,
            'connector_id': self.connector_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'OCPPEvent':
        """从字典创建实例"""
        return cls(
            sso_id=data.get('sso_id', ''),
            operation_timestamp=data['operation_timestamp'],
            ocpp_message_type=data['ocpp_message_type'],
            ocpp_request_body=data.get('ocpp_request_body'),
            ocpp_response_body=data.get('ocpp_response_body'),
            connector_id=data.get('connector_id')
        )


@dataclass
class UserFeedback:
    """
    用户反馈模型
    
    表示Direct Access系统中的一条用户反馈。
    """
    id: int
    date_input: datetime.datetime
    rating: int
    comment: Optional[str] = None
    session_id: Optional[str] = None
    country_code: Optional[str] = None
    postal_code: Optional[str] = None
    category: Optional[str] = None
    evse_id: Optional[str] = None
    attempt_bk: Optional[str] = None
    match_condition: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'date_input': self.date_input,
            'rating': self.rating,
            'comment': self.comment,
            'session_id': self.session_id,
            'country_code': self.country_code,
            'postal_code': self.postal_code,
            'category': self.category,
            'evse_id': self.evse_id,
            'attempt_bk': self.attempt_bk,
            'match_condition': self.match_condition
        }


@dataclass
class ChargerLocation:
    """
    充电桩位置模型
    
    表示充电桩的地理位置和设备信息。
    """
    id: int
    sso_id: str
    evse_id: Optional[str] = None
    evse_count: Optional[int] = None
    unique_location_id: Optional[str] = None
    source_location_id: Optional[str] = None
    country_code: Optional[str] = None
    district_name: Optional[str] = None
    city: Optional[str] = None
    postcode: Optional[str] = None
    street: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    socket_hardware_serial_number: Optional[str] = None
    socket_manufacturer_serial_number: Optional[str] = None
    socket_last_contact_firmware_version: Optional[str] = None
    model_type: Optional[str] = None
    project_name: Optional[str] = None
    project_number: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'sso_id': self.sso_id,
            'evse_id': self.evse_id,
            'evse_count': self.evse_count,
            'unique_location_id': self.unique_location_id,
            'source_location_id': self.source_location_id,
            'country_code': self.country_code,
            'district_name': self.district_name,
            'city': self.city,
            'postcode': self.postcode,
            'street': self.street,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'socket_hardware_serial_number': self.socket_hardware_serial_number,
            'socket_manufacturer_serial_number': self.socket_manufacturer_serial_number,
            'socket_last_contact_firmware_version': self.socket_last_contact_firmware_version,
            'model_type': self.model_type,
            'project_name': self.project_name,
            'project_number': self.project_number
        }


@dataclass
class AIAnalysisResult:
    """
    AI分析结果模型
    
    表示AI对充电尝试和OCPP事件的分析结果。
    """
    attempt_bk: str
    analysis_time: datetime.datetime
    ocpp_json: Optional[str] = None
    ai_result: Optional[str] = None
    feedback_id: Optional[int] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'attempt_bk': self.attempt_bk,
            'analysis_time': self.analysis_time,
            'ocpp_json': self.ocpp_json,
            'ai_result': self.ai_result,
            'feedback_id': self.feedback_id
        }


@dataclass
class DirectMergedAttempt:
    """
    直连查询合并后的充电尝试模型
    
    用于直连Databricks数据仓库分析场景。
    与MergedAttempt的区别在于包含更多直连分析所需的字段。
    """
    evse_id: Optional[str]
    sso_id: str
    connector_id: int
    attempt_start: datetime.datetime
    attempt_end: datetime.datetime
    total_consumption_kwh: float
    attempt_count: int
    duration_seconds: int
    original_records: List[Dict] = field(default_factory=list)
    raw_ocpp_events: List[Dict] = field(default_factory=list)
    processed_events: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'evse_id': self.evse_id,
            'sso_id': self.sso_id,
            'connector_id': self.connector_id,
            'attempt_start': self.attempt_start,
            'attempt_end': self.attempt_end,
            'total_consumption_kwh': self.total_consumption_kwh,
            'attempt_count': self.attempt_count,
            'duration_seconds': self.duration_seconds,
            'original_records': self.original_records,
            'raw_ocpp_events': self.raw_ocpp_events,
            'processed_events': self.processed_events
        }
    
    @classmethod
    def from_records(
        cls, 
        records: List[Dict], 
        evse_id: Optional[str],
        sso_id: str,
        connector_id: int
    ) -> 'DirectMergedAttempt':
        """
        从原始记录创建合并后的尝试
        
        Args:
            records: 原始充电尝试记录列表
            evse_id: EVSE ID
            sso_id: SSO ID
            connector_id: Connector ID
            
        Returns:
            合并后的DirectMergedAttempt实例
        """
        if not records:
            raise ValueError("records不能为空")
        
        # 计算各项汇总值
        attempt_start = min(r['charging_attempt_start'] for r in records)
        attempt_end = max(r['charging_attempt_end'] for r in records)
        
        consumption_values = [
            r.get('session_consumption_kwh', 0) or 0 
            for r in records
        ]
        total_consumption = sum(consumption_values)
        
        duration = int((attempt_end - attempt_start).total_seconds())
        
        return cls(
            evse_id=evse_id,
            sso_id=sso_id,
            connector_id=connector_id,
            attempt_start=attempt_start,
            attempt_end=attempt_end,
            total_consumption_kwh=total_consumption,
            attempt_count=len(records),
            duration_seconds=duration,
            original_records=records
        )


@dataclass
class DirectAnalysisResult:
    """
    直连分析结果模型
    
    用于存储直连数据仓库分析的结果。
    """
    id: Optional[int] = None
    analysis_timestamp: datetime.datetime = field(
        default_factory=datetime.datetime.now
    )
    input_timestamp: Optional[datetime.datetime] = None
    evse_id: Optional[str] = None
    sso_id: Optional[str] = None
    connector_id: Optional[int] = None
    attempt_start: Optional[datetime.datetime] = None
    attempt_end: Optional[datetime.datetime] = None
    total_consumption_kwh: Optional[float] = None
    attempt_count: Optional[int] = None
    ocpp_event_count: Optional[int] = None
    ai_analysis_result: Optional[str] = None
    raw_ocpp_events: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'analysis_timestamp': self.analysis_timestamp,
            'input_timestamp': self.input_timestamp,
            'evse_id': self.evse_id,
            'sso_id': self.sso_id,
            'connector_id': self.connector_id,
            'attempt_start': self.attempt_start,
            'attempt_end': self.attempt_end,
            'total_consumption_kwh': self.total_consumption_kwh,
            'attempt_count': self.attempt_count,
            'ocpp_event_count': self.ocpp_event_count,
            'ai_analysis_result': self.ai_analysis_result,
            'raw_ocpp_events': self.raw_ocpp_events
        }
    
    @classmethod
    def from_merged_attempt(
        cls,
        attempt: 'DirectMergedAttempt',
        input_timestamp: datetime.datetime,
        ai_result: Optional[str] = None
    ) -> 'DirectAnalysisResult':
        """从合并后的尝试创建分析结果"""
        import json
        
        return cls(
            analysis_timestamp=datetime.datetime.now(),
            input_timestamp=input_timestamp,
            evse_id=attempt.evse_id,
            sso_id=attempt.sso_id,
            connector_id=attempt.connector_id,
            attempt_start=attempt.attempt_start,
            attempt_end=attempt.attempt_end,
            total_consumption_kwh=attempt.total_consumption_kwh,
            attempt_count=attempt.attempt_count,
            ocpp_event_count=len(attempt.processed_events),
            ai_analysis_result=ai_result,
            raw_ocpp_events=json.dumps(
                attempt.raw_ocpp_events, 
                default=str, 
                ensure_ascii=False
            ) if attempt.raw_ocpp_events else None
        )
