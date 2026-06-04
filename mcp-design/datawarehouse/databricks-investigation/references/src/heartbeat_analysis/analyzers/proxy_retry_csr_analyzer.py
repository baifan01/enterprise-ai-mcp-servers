#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
proxy 重连次数与 3 个月 CSR 基础表分析器

## 面向 AI 说明

### 职责
本模块负责生成一张以充电桩为粒度的 POC 基础表，用于后续分析
WebSocket 高频重连设备是否具有更低的长期充电成功率。

### 输入
1. `proxy-11-3.log` 一类的重连统计文件，格式为 `次数 + device_id`
2. Databricks 中的 `kpi_charging_attempts_enriched_v`

### 输出
输出 CSV 包含以下字段：
- `charge_point_id`
- `device_model_prefix`
- `reconnect_count_on_date`
- `attempt_count_3m`
- `success_count_3m`
- `csr_3m`

### 关键约定
- 当前 POC 只聚焦 `suby` 前缀设备
- 近 3 个月窗口固定为 `2025-12-01` 到 `2026-03-15`
- 成功定义为 `session_consumption_kwh > 1`
- 若无充电记录，则 `csr_3m = -1`
- 若设备未出现在重连文件中，但出现在充电聚合结果中，则
  `reconnect_count_on_date = -1`
"""

import csv
import logging
import os
import re
from typing import Dict, List, Optional, Tuple

from ..data.databricks_client import DatabricksClient

logger = logging.getLogger(__name__)


class ProxyRetryCsrAnalyzer:
    """
    proxy 重连与长期 CSR 分析器。

    主流程分为四步：
    1. 读取并聚合重连文件
    2. 从 Databricks 聚合 3 个月充电记录
    3. 合并两侧设备全集
    4. 输出 POC 基础表 CSV
    """

    DEFAULT_MODEL_PREFIX = 'suby'
    DEFAULT_WINDOW_START = '2025-12-01'
    DEFAULT_WINDOW_END = '2026-03-15'
    DEFAULT_ENERGY_THRESHOLD = 1.0
    OUTPUT_HEADERS = [
        'charge_point_id',
        'device_model_prefix',
        'reconnect_count_on_date',
        'attempt_count_3m',
        'success_count_3m',
        'csr_3m',
    ]

    def __init__(
        self,
        input_path: str,
        output_path: str,
        model_prefix: str = DEFAULT_MODEL_PREFIX,
        window_start: str = DEFAULT_WINDOW_START,
        window_end: str = DEFAULT_WINDOW_END,
        energy_threshold: float = DEFAULT_ENERGY_THRESHOLD,
    ):
        """初始化分析器。"""
        self.input_path = input_path
        self.output_path = output_path
        self.model_prefix = model_prefix.lower()
        self.window_start = window_start
        self.window_end = window_end
        self.energy_threshold = energy_threshold
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
        """执行完整分析流程。"""
        retry_map, input_row_count = self._read_retry_file()
        charging_map = self._query_charging_summary_map()
        output_rows = self._build_output_rows(retry_map, charging_map)
        self._write_output_csv(output_rows)
        return self._build_summary(
            input_row_count=input_row_count,
            retry_map=retry_map,
            charging_map=charging_map,
            output_rows=output_rows,
        )

    # ========================
    # 第二部分：重连文件解析
    # ========================

    def _read_retry_file(self) -> Tuple[Dict[str, int], int]:
        """读取重连文件，并按设备聚合重连次数。"""
        if not os.path.exists(self.input_path):
            raise FileNotFoundError(f"输入文件不存在: {self.input_path}")

        retry_map: Dict[str, int] = {}
        input_row_count = 0

        with open(self.input_path, 'r', encoding='utf-8') as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                parsed_row = self._parse_retry_line(raw_line, line_number)
                if parsed_row is None:
                    continue
                input_row_count += 1
                self._merge_retry_row(parsed_row, retry_map)

        logger.info("重连文件解析完成，suby 设备数=%s", len(retry_map))
        return retry_map, input_row_count

    def _parse_retry_line(
        self,
        raw_line: str,
        line_number: int,
    ) -> Optional[Dict[str, object]]:
        """解析单行重连记录。"""
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

        device_id = device_id.strip()
        device_prefix = self._extract_device_model_prefix(device_id)
        if device_prefix != self.model_prefix:
            return None

        return {
            'charge_point_id': device_id,
            'reconnect_count_on_date': retry_count,
        }

    def _merge_retry_row(
        self,
        parsed_row: Dict[str, object],
        retry_map: Dict[str, int],
    ) -> None:
        """将单条重连记录合并到设备映射。"""
        charge_point_id = str(parsed_row['charge_point_id'])
        retry_count = int(parsed_row['reconnect_count_on_date'])
        retry_map[charge_point_id] = retry_map.get(charge_point_id, 0) + retry_count

    def _extract_device_model_prefix(self, charge_point_id: str) -> str:
        """从设备 ID 中提取字母前缀。"""
        matched = re.match(r'^([A-Za-z]+)', charge_point_id)
        if not matched:
            return ''
        return matched.group(1).lower()

    # ========================
    # 第三部分：数仓聚合查询
    # ========================

    def _query_charging_summary_map(self) -> Dict[str, Dict[str, int]]:
        """查询 3 个月充电记录聚合结果。"""
        query = self._build_charging_summary_query()
        columns, rows = self.databricks_client.execute_query(query)
        charging_map: Dict[str, Dict[str, int]] = {}

        for row in rows:
            parsed_row = dict(zip(columns, row))
            charge_point_id = str(parsed_row['charge_point_id'])
            charging_map[charge_point_id] = {
                'attempt_count_3m': int(parsed_row['attempt_count_3m'] or 0),
                'success_count_3m': int(parsed_row['success_count_3m'] or 0),
            }

        logger.info("充电聚合查询完成，设备数=%s", len(charging_map))
        return charging_map

    def _build_charging_summary_query(self) -> str:
        """构建 3 个月充电聚合 SQL。"""
        return f"""
        SELECT
            source_device_id AS charge_point_id,
            COUNT(*) AS attempt_count_3m,
            SUM(
                CASE
                    WHEN COALESCE(session_consumption_kwh, 0) > {self.energy_threshold}
                    THEN 1
                    ELSE 0
                END
            ) AS success_count_3m
        FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.kpi_charging_attempts_enriched_v
        WHERE source_device_id LIKE '{self.model_prefix}%'
          AND DATE(charging_attempt_start) >= DATE('{self.window_start}')
          AND DATE(charging_attempt_start) <= DATE('{self.window_end}')
        GROUP BY source_device_id
        ORDER BY source_device_id ASC
        """

    # ========================
    # 第四部分：结果合并
    # ========================

    def _build_output_rows(
        self,
        retry_map: Dict[str, int],
        charging_map: Dict[str, Dict[str, int]],
    ) -> List[Dict[str, object]]:
        """合并重连与充电聚合结果，生成输出行。"""
        output_rows: List[Dict[str, object]] = []
        all_device_ids = sorted(set(retry_map) | set(charging_map))

        for charge_point_id in all_device_ids:
            retry_count = retry_map.get(charge_point_id, -1)
            charging_summary = charging_map.get(charge_point_id, {})
            attempt_count = int(charging_summary.get('attempt_count_3m', 0))
            success_count = int(charging_summary.get('success_count_3m', 0))
            output_rows.append(
                self._build_single_output_row(
                    charge_point_id=charge_point_id,
                    retry_count=retry_count,
                    attempt_count=attempt_count,
                    success_count=success_count,
                )
            )

        output_rows.sort(
            key=lambda item: (
                -int(item['reconnect_count_on_date']),
                -int(item['attempt_count_3m']),
                str(item['charge_point_id']),
            )
        )
        return output_rows

    def _build_single_output_row(
        self,
        charge_point_id: str,
        retry_count: int,
        attempt_count: int,
        success_count: int,
    ) -> Dict[str, object]:
        """构建单台设备的输出行。"""
        return {
            'charge_point_id': charge_point_id,
            'device_model_prefix': self._extract_device_model_prefix(charge_point_id),
            'reconnect_count_on_date': retry_count,
            'attempt_count_3m': attempt_count,
            'success_count_3m': success_count,
            'csr_3m': self._calculate_csr(attempt_count, success_count),
        }

    def _calculate_csr(self, attempt_count: int, success_count: int) -> float:
        """计算 CSR，若无充电记录则返回 -1。"""
        if attempt_count <= 0:
            return -1
        return round(success_count / attempt_count, 6)

    # ========================
    # 第五部分：结果输出
    # ========================

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
        input_row_count: int,
        retry_map: Dict[str, int],
        charging_map: Dict[str, Dict[str, int]],
        output_rows: List[Dict[str, object]],
    ) -> Dict[str, int]:
        """构建执行摘要。"""
        retry_missing_count = 0
        csr_missing_count = 0

        for row in output_rows:
            if int(row['reconnect_count_on_date']) < 0:
                retry_missing_count += 1
            if float(row['csr_3m']) < 0:
                csr_missing_count += 1

        return {
            'input_row_count': input_row_count,
            'retry_device_count': len(retry_map),
            'charging_device_count': len(charging_map),
            'output_row_count': len(output_rows),
            'retry_missing_count': retry_missing_count,
            'csr_missing_count': csr_missing_count,
        }
