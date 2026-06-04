#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
proxy-11-3 固件与配置分析器

## 面向 AI 说明

### 职责
本模块负责处理一条明确的批量分析链路：

1. 读取 `data/input/proxy-11-3.log`
2. 解析出 `retry_count + device_id`
3. 去 Databricks 查询最近一条 `BootNotification`
4. 去 Databricks 查询最近一条 `GetConfiguration`
5. 用正则提取 `firmwareVersion` 与配置字段
6. 输出到 `output/proxy-11-3-analysis.csv`

### 设计约束
本模块不复用 `DirectAnalyzer` 的充电尝试分析流程，因为当前需求只关心
`BootNotification/GetConfiguration -> 固件与配置`，单独实现更短、更清晰。

### 对外接口
- `ProxyFirmwareAnalyzer.run()`: 执行完整分析并返回摘要结果
"""

import csv
import logging
import os
import re
from typing import Dict, List, Optional

from ..data.databricks_client import DatabricksClient

logger = logging.getLogger(__name__)


class ProxyFirmwareAnalyzer:
    """
    proxy-11-3 固件与配置分析器

    负责从输入日志中解析设备列表，批量查询最近一条 BootNotification
    和最近一条 GetConfiguration，提取固件与配置字段，并输出结果 CSV。
    """

    DEFAULT_QUERY_START = '2026-01-01T00:00:00.000+0000'
    DEFAULT_BATCH_SIZE = 500
    OUTPUT_HEADERS = [
        'device_id',
        'number of retry within 10h',
        'firmwareVersion',
        'ConnectorConnetionTimout',
        'HeartbeatInterval',
        'ConnectionTimeout',
        'BootNotification_ocpp_request_body',
        'GetConfiguration_ocpp_response_body',
    ]

    def __init__(
        self,
        input_path: str,
        output_path: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
        query_start: str = DEFAULT_QUERY_START,
    ):
        """初始化分析器。"""
        self.input_path = input_path
        self.output_path = output_path
        self.batch_size = batch_size
        self.query_start = query_start
        self._databricks_client: Optional[DatabricksClient] = None

    # ========================
    # 第一部分：公共入口
    # ========================

    @property
    def databricks_client(self) -> DatabricksClient:
        """懒加载 Databricks 客户端。"""
        if self._databricks_client is None:
            self._databricks_client = DatabricksClient()
            self._databricks_client.connect()
        return self._databricks_client

    def close(self) -> None:
        """关闭外部连接。"""
        if self._databricks_client is not None:
            self._databricks_client.close()
            self._databricks_client = None

    def __enter__(self):
        """上下文管理器入口。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口。"""
        self.close()
        return False

    def run(self) -> Dict[str, int]:
        """
        执行完整分析流程。

        Returns:
            包含输入数量、BootNotification 命中数量、
            GetConfiguration 命中数量与输出数量的摘要信息
        """
        retry_rows = self._read_retry_file()
        device_result_map = self._query_device_result_map(retry_rows)
        output_rows = self._build_output_rows(retry_rows, device_result_map)
        self._write_output_csv(output_rows)
        return self._build_summary(retry_rows, device_result_map, output_rows)

    # ========================
    # 第二部分：输入解析
    # ========================

    def _read_retry_file(self) -> List[Dict[str, object]]:
        """读取并解析重试统计文件。"""
        if not os.path.exists(self.input_path):
            raise FileNotFoundError(f"输入文件不存在: {self.input_path}")

        parsed_rows: List[Dict[str, object]] = []
        with open(self.input_path, 'r', encoding='utf-8') as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                parsed_row = self._parse_retry_line(raw_line, line_number)
                if parsed_row is not None:
                    parsed_rows.append(parsed_row)

        logger.info("输入文件解析完成，共 %s 行有效数据", len(parsed_rows))
        return parsed_rows

    def _parse_retry_line(
        self,
        raw_line: str,
        line_number: int,
    ) -> Optional[Dict[str, object]]:
        """解析单行输入。"""
        stripped_line = raw_line.strip()
        if not stripped_line:
            return None

        parts = stripped_line.split(maxsplit=1)
        if len(parts) != 2:
            logger.warning("第 %s 行格式非法，已跳过: %s", line_number, stripped_line)
            return None

        retry_text, device_id = parts
        try:
            retry_count = int(retry_text)
        except ValueError:
            logger.warning("第 %s 行次数非法，已跳过: %s", line_number, stripped_line)
            return None

        return {
            'device_id': device_id.strip(),
            'retry_count': retry_count,
        }

    # ========================
    # 第三部分：数仓查询
    # ========================

    def _query_device_result_map(
        self,
        retry_rows: List[Dict[str, object]],
    ) -> Dict[str, Dict[str, str]]:
        """查询全部设备的固件与配置结果映射。"""
        device_ids = self._collect_device_ids(retry_rows)
        result_by_device: Dict[str, Dict[str, str]] = {}

        for batch_index, batch_device_ids in enumerate(
            self._build_device_batches(device_ids),
            start=1,
        ):
            logger.info(
                "开始查询第 %s 批设备事件，设备数=%s",
                batch_index,
                len(batch_device_ids),
            )
            batch_rows = self._query_latest_device_events(batch_device_ids)
            self._merge_batch_rows(batch_rows, result_by_device)

        logger.info("设备事件提取完成，共处理 %s 个设备", len(result_by_device))
        return result_by_device

    def _collect_device_ids(
        self,
        retry_rows: List[Dict[str, object]],
    ) -> List[str]:
        """收集去重后的设备列表，同时保持原始顺序。"""
        ordered_device_ids: List[str] = []
        seen_device_ids = set()

        for row in retry_rows:
            device_id = str(row['device_id'])
            if device_id in seen_device_ids:
                continue
            seen_device_ids.add(device_id)
            ordered_device_ids.append(device_id)

        return ordered_device_ids

    def _build_device_batches(self, device_ids: List[str]) -> List[List[str]]:
        """按批次切分设备列表。"""
        if self.batch_size <= 0:
            raise ValueError("batch_size 必须大于 0")

        batches: List[List[str]] = []
        for start_index in range(0, len(device_ids), self.batch_size):
            end_index = start_index + self.batch_size
            batches.append(device_ids[start_index:end_index])
        return batches

    def _query_latest_device_events(
        self,
        device_ids: List[str],
    ) -> List[Dict[str, str]]:
        """查询单批设备最近一条 BootNotification 和 GetConfiguration。"""
        if not device_ids:
            return []

        quoted_device_ids = ', '.join(
            self._quote_sql_string(device_id) for device_id in device_ids
        )
        query = f"""
        WITH ranked_events AS (
            SELECT
                REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) AS device_id,
                ocpp_message_type,
                CAST(operation_timestamp AS STRING) AS operation_timestamp,
                ocpp_request_body,
                ocpp_response_body,
                ROW_NUMBER() OVER (
                    PARTITION BY REGEXP_EXTRACT(sso_id, '^([^_]+)', 1), ocpp_message_type
                    ORDER BY operation_timestamp DESC
                ) AS row_num
            FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_ocpp_operations_v
            WHERE REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) IN ({quoted_device_ids})
              AND operation_timestamp > '{self.query_start}'
              AND ocpp_message_type IN ('BootNotification', 'GetConfiguration')
        )
        SELECT
            device_id,
            ocpp_message_type,
            operation_timestamp,
            ocpp_request_body,
            ocpp_response_body
        FROM ranked_events
        WHERE row_num = 1
        ORDER BY device_id ASC, ocpp_message_type ASC
        """

        columns, rows = self.databricks_client.execute_query(query)
        return [dict(zip(columns, row)) for row in rows]

    def _quote_sql_string(self, value: str) -> str:
        """对 SQL 字符串字面量做简单转义。"""
        escaped_value = value.replace("'", "''")
        return f"'{escaped_value}'"

    # ========================
    # 第四部分：字段提取
    # ========================

    def _merge_batch_rows(
        self,
        batch_rows: List[Dict[str, str]],
        result_by_device: Dict[str, Dict[str, str]],
    ) -> None:
        """将单批查询结果合并到最终映射。"""
        for row in batch_rows:
            device_id = row.get('device_id')
            event_type = row.get('ocpp_message_type')
            if not device_id or not event_type:
                continue

            device_result = self._ensure_device_result(result_by_device, device_id)
            self._merge_single_event(row, device_result, event_type)

    def _ensure_device_result(
        self,
        result_by_device: Dict[str, Dict[str, str]],
        device_id: str,
    ) -> Dict[str, str]:
        """确保设备结果字典存在。"""
        if device_id not in result_by_device:
            result_by_device[device_id] = {
                'firmwareVersion': '',
                'ConnectorConnetionTimout': '',
                'HeartbeatInterval': '',
                'ConnectionTimeout': '',
                'BootNotification_ocpp_request_body': '',
                'GetConfiguration_ocpp_response_body': '',
            }
        return result_by_device[device_id]

    def _merge_single_event(
        self,
        row: Dict[str, str],
        device_result: Dict[str, str],
        event_type: str,
    ) -> None:
        """根据事件类型提取需要的字段。"""
        if event_type == 'BootNotification':
            request_body = row.get('ocpp_request_body')
            device_result['BootNotification_ocpp_request_body'] = request_body or ''
            device_result['firmwareVersion'] = self._extract_named_value(
                request_body,
                ['firmwareVersion'],
            )
            return

        if event_type == 'GetConfiguration':
            response_body = row.get('ocpp_response_body')
            device_result['GetConfiguration_ocpp_response_body'] = response_body or ''
            device_result['ConnectorConnetionTimout'] = self._extract_named_value(
                response_body,
                ['ConnectorConnetionTimout', 'ConnectorConnectionTimeout'],
            )
            device_result['HeartbeatInterval'] = self._extract_named_value(
                response_body,
                ['HeartbeatInterval'],
            )
            device_result['ConnectionTimeout'] = self._extract_named_value(
                response_body,
                ['ConnectionTimeout', 'ConnectionTimeOut'],
            )

    def _extract_named_value(
        self,
        body_text: Optional[str],
        candidate_keys: List[str],
    ) -> str:
        """通过正则从 OCPP 文本中提取指定 key 的 value。"""
        if not body_text:
            return ''

        for key in candidate_keys:
            extracted_value = self._extract_key_value_pair(body_text, key)
            if extracted_value:
                return extracted_value

        return ''

    def _extract_key_value_pair(self, body_text: str, key: str) -> str:
        """提取单个 key 对应的字符串值。"""
        escaped_key = re.escape(key)
        pair_pattern = (
            r'"key"\s*:\s*"'
            + escaped_key
            + r'"\s*,\s*"readonly"\s*:\s*(?:true|false)\s*,\s*"value"\s*:\s*"([^"]*)"'
        )
        pair_matched = re.search(pair_pattern, body_text)
        if pair_matched:
            return pair_matched.group(1).strip()

        direct_pattern = r'"' + escaped_key + r'"\s*:\s*"([^"]*)"'
        direct_matched = re.search(direct_pattern, body_text)
        if direct_matched:
            return direct_matched.group(1).strip()

        return ''

    # ========================
    # 第五部分：结果输出
    # ========================

    def _build_output_rows(
        self,
        retry_rows: List[Dict[str, object]],
        result_map: Dict[str, Dict[str, str]],
    ) -> List[Dict[str, object]]:
        """组装输出结果并排序。"""
        output_rows: List[Dict[str, object]] = []

        for row in retry_rows:
            device_id = str(row['device_id'])
            device_result = result_map.get(device_id, {})
            output_rows.append({
                'device_id': device_id,
                'number of retry within 10h': row['retry_count'],
                'firmwareVersion': device_result.get('firmwareVersion', ''),
                'ConnectorConnetionTimout': device_result.get(
                    'ConnectorConnetionTimout',
                    '',
                ),
                'HeartbeatInterval': device_result.get('HeartbeatInterval', ''),
                'ConnectionTimeout': device_result.get('ConnectionTimeout', ''),
                'BootNotification_ocpp_request_body': device_result.get(
                    'BootNotification_ocpp_request_body',
                    '',
                ),
                'GetConfiguration_ocpp_response_body': device_result.get(
                    'GetConfiguration_ocpp_response_body',
                    '',
                ),
            })

        output_rows.sort(
            key=lambda item: (-int(item['number of retry within 10h']), item['device_id'])
        )
        return output_rows

    def _write_output_csv(self, output_rows: List[Dict[str, object]]) -> None:
        """写出最终结果 CSV。"""
        output_dir = os.path.dirname(self.output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(self.output_path, 'w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=self.OUTPUT_HEADERS)
            writer.writeheader()
            writer.writerows(output_rows)

        logger.info("结果文件已写出: %s", self.output_path)

    def _build_summary(
        self,
        retry_rows: List[Dict[str, object]],
        result_map: Dict[str, Dict[str, str]],
        output_rows: List[Dict[str, object]],
    ) -> Dict[str, int]:
        """生成执行摘要。"""
        firmware_found_count = 0
        get_configuration_found_count = 0

        for device_result in result_map.values():
            if device_result.get('firmwareVersion'):
                firmware_found_count += 1

            if (
                device_result.get('ConnectorConnetionTimout')
                or device_result.get('HeartbeatInterval')
                or device_result.get('ConnectionTimeout')
            ):
                get_configuration_found_count += 1

        return {
            'input_row_count': len(retry_rows),
            'firmware_found_count': firmware_found_count,
            'get_configuration_found_count': get_configuration_found_count,
            'output_row_count': len(output_rows),
        }
