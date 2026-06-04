#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AI分析模块

## 面向AI说明

### 业务背景
本模块是OCPP事件分析系统的AI核心，负责调用大语言模型（GPT-5.2）对充电桩OCPP事件
序列进行智能分析，识别充电故障原因、评估事件时序合理性、与用户反馈进行一致性验证。

### 核心职责
1. **提示词管理**: 加载和维护 `config/prompts/ocpp_analysis.md` 提示词模板
2. **数据组装**: 将充电尝试信息和OCPP事件序列组装为AI可理解的JSON结构
3. **API调用**: 封装OpenAI API调用，处理错误和重试
4. **结果返回**: 返回AI生成的结构化分析结果

### 数据流
```
attempt_info + processed_events
       ↓
generate_analysis_json() → 结构化JSON
       ↓
load_prompt_template() → 提示词模板
       ↓
替换 {{ATTEMPT_AND_FEEDBACK_JSON}} 占位符
       ↓
call_api() → OpenAI GPT-5.2
       ↓
AI分析结果（Markdown/JSON格式）
```

### 输入数据结构示例
```python
# attempt_info: 充电尝试基本信息
attempt_info = {
    'attempt_bk': '20260101100000000sebe11000005911',
    'sso_id': 'sebe1100000591',
    'connector_id': 1,
    'attempt_count': 2,
    'consumption_kwh': 2.6,
    'earliest_start': datetime(2026, 1, 1, 10, 0, 0),
    'latest_end': datetime(2026, 1, 1, 10, 30, 0)
}

# processed_events: 已处理的OCPP事件序列（来自OCPPProcessor）
processed_events = [
    {'time_offset_seconds': 0.0, 'ocpp_type': 'StatusNotification', 
     'status_info': {'errorCode': 'NoError', 'status': 'Preparing'}},
    {'time_offset_seconds': 1.5, 'ocpp_type': 'RemoteStartTransaction',
     'request': '...', 'response': '...'},
    ...
]
```

### 提示词模板结构
提示词文件 `config/prompts/ocpp_analysis.md` 包含：
- 系统角色定义（OCPP 1.6 协议专家）
- 分析步骤说明
- 输出格式要求（JSON结构）
- 占位符 `{{ATTEMPT_AND_FEEDBACK_JSON}}` 用于插入实际数据

### 典型调用场景

**场景1：分析单个充电尝试（无用户反馈）**
```python
analyzer = AIAnalyzer()
result = analyzer.analyze_attempt_only(attempt_info, processed_events)
# result: AI返回的分析文本（含故障诊断、时序分析等）
```

**场景2：分析用户反馈关联的充电尝试**
```python
analyzer = AIAnalyzer()
feedback_json = json.dumps(feedback_data)
ocpp_json = json.dumps(ocpp_data)
result = analyzer.analyze_with_feedback(feedback_json, ocpp_json)
# result: AI返回的分析文本（含用户投诉一致性判断）
```

### API配置
- 默认模型: `gpt-5.2`
- API Key: 优先从环境变量 `OPENAI_API_KEY` 读取
- 温度参数: 0.3（偏向确定性输出）
- 最大Token: 2000

### 依赖关系
- 依赖 `OCPPProcessor.process_events_batch()` 的输出
- 依赖 `config/prompts/ocpp_analysis.md` 提示词文件
- 被 `analyzers/*` 模块调用

### 注意事项
- `user_feedback` 可为 None，此时AI跳过投诉一致性分析
- API调用失败返回 None，调用方需处理
- 提示词路径支持新旧两个位置（向后兼容）
"""

import datetime
import json
import logging
import os
from typing import Dict, List, Optional, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """
    AI分析器
    
    使用OpenAI API分析OCPP事件和用户反馈。
    """
    
    # 默认模型
    DEFAULT_MODEL = "gpt-5.2"
    
    # 默认提示词模板路径
    DEFAULT_PROMPT_PATH = "config/prompts/ocpp_analysis.md"
    LEGACY_PROMPT_PATH = "local_database/prompt.md"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        prompt_path: Optional[str] = None
    ):
        """
        初始化AI分析器
        
        Args:
            api_key: OpenAI API Key，默认从环境变量读取
            model: 模型名称，默认为gpt-5.2
            prompt_path: 提示词模板路径
        """
        if OpenAI is None:
            raise ImportError("openai 模块未安装。请运行: pip install openai")
        
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or \
            "OPENAI_API_KEY_PLACEHOLDER"
        self.model = model or self.DEFAULT_MODEL
        self.prompt_path = prompt_path
        self._prompt_template = None
    
    def load_prompt_template(self, path: Optional[str] = None) -> str:
        """
        加载提示词模板
        
        Args:
            path: 模板文件路径
            
        Returns:
            提示词模板字符串
        """
        if self._prompt_template is not None and path is None:
            return self._prompt_template
        
        template_path = path or self.prompt_path or self.DEFAULT_PROMPT_PATH
        
        # 尝试多个路径
        paths_to_try = [template_path, self.LEGACY_PROMPT_PATH]
        
        for p in paths_to_try:
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    self._prompt_template = f.read()
                    logger.info(f"成功加载提示词模板: {p}")
                    return self._prompt_template
        
        raise FileNotFoundError(
            f"提示词模板文件不存在: {paths_to_try}"
        )
    
    def call_api(self, prompt: str) -> Optional[str]:
        """
        调用OpenAI API
        
        Args:
            prompt: 完整的提示词
            
        Returns:
            AI返回的分析结果字符串，失败时返回None
        """
        try:
            client = OpenAI(api_key=self.api_key)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "你是一名精通 OCPP 1.6 协议的高级充电桩技术支持工程师。"
                                   "请严格按照要求输出 JSON 格式的分析结果。"
                                   "重要：请使用英文回复所有分析内容。"
                    },
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=2000,
                temperature=0.3,
            )
            
            content = response.choices[0].message.content
            logger.debug(f"AI 返回内容: {content[:200]}...")
            return content
            
        except Exception as e:
            logger.error(f"调用 OpenAI API 失败: {e}")
            return None
    
    def generate_analysis_json(
        self, 
        attempt_info: Dict, 
        ocpp_events: List[Dict],
        processed_events: Optional[List[Dict]] = None
    ) -> Dict:
        """
        生成分析用的JSON结构
        
        Args:
            attempt_info: 充电尝试基本信息
            ocpp_events: 原始OCPP事件列表
            processed_events: 已处理的事件列表（可选）
            
        Returns:
            完整的分析结果字典
        """
        def format_datetime(dt):
            if dt is None:
                return None
            if isinstance(dt, datetime.datetime):
                return dt.isoformat()
            return str(dt)
        
        # 格式化attempt信息
        formatted_attempt = {
            'sso_id': attempt_info.get('sso_id'),
            'connector_id': attempt_info.get('connector_id'),
            'attempt_count': attempt_info.get('attempt_count'),
            'consumption_kwh': attempt_info.get('consumption_kwh'),
            'attempt_start_time': format_datetime(
                attempt_info.get('attempt_start_time') or 
                attempt_info.get('earliest_start')
            ),
            'attempt_end_time': format_datetime(
                attempt_info.get('attempt_end_time') or 
                attempt_info.get('latest_end')
            )
        }
        
        result = {
            'attempt_bk': attempt_info.get('attempt_bk'),
            'attempt_info': formatted_attempt,
            'event_count': len(processed_events or ocpp_events),
            'events': processed_events or []
        }
        
        return result
    
    def analyze_with_feedback(
        self,
        feedback_json: str,
        ocpp_json: str
    ) -> Optional[str]:
        """
        分析用户反馈和OCPP事件
        
        Args:
            feedback_json: 用户反馈JSON字符串
            ocpp_json: OCPP事件JSON字符串
            
        Returns:
            AI分析结果字符串
        """
        if ocpp_json == "null" or not ocpp_json:
            logger.warning("没有 OCPP 数据，跳过 AI 分析")
            return None
        
        # 组合数据
        combined_data = {
            "user_feedback": json.loads(feedback_json) if feedback_json else None,
            "ocpp_attempt": json.loads(ocpp_json)
        }
        combined_json = json.dumps(combined_data, indent=2, ensure_ascii=False)
        
        # 加载模板并替换占位符
        prompt_template = self.load_prompt_template()
        prompt = prompt_template.replace(
            "{{ATTEMPT_AND_FEEDBACK_JSON}}", 
            combined_json
        )
        
        # 调用API
        logger.info("正在调用 OpenAI API 进行分析...")
        return self.call_api(prompt)
    
    def analyze_attempt_only(
        self,
        attempt_info: Dict,
        processed_events: List[Dict]
    ) -> Optional[str]:
        """
        仅分析充电尝试（无用户反馈）
        
        Args:
            attempt_info: 充电尝试信息
            processed_events: 已处理的OCPP事件列表
            
        Returns:
            AI分析结果字符串
        """
        # 生成分析JSON
        analysis_json = self.generate_analysis_json(
            attempt_info, [], processed_events
        )
        
        # 组合数据
        combined_data = {
            "user_feedback": None,
            "ocpp_attempt": analysis_json
        }
        combined_json = json.dumps(combined_data, indent=2, ensure_ascii=False)
        
        # 加载模板并替换
        prompt_template = self.load_prompt_template()
        prompt = prompt_template.replace(
            "{{ATTEMPT_AND_FEEDBACK_JSON}}", 
            combined_json
        )
        
        logger.info(f"正在调用 OpenAI API 分析 attempt...")
        return self.call_api(prompt)
