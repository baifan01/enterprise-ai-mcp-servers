#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
proxy 多日重连与 Heartbeat 波动分析器

## 面向 AI 说明

### 职责
本模块负责把一组按天统计的 `proxy_x-y.log` 重连文件，与
Databricks 中 `charger_ocpp_operations_v` 的 Heartbeat 事件聚合结果结合，
生成以下三类输出：

1. 设备-日期粒度的长表
2. 设备粒度的波动摘要表
3. 候选异常设备的宽表

### 核心目标
识别那些“14 天内大部分时间在线（Heartbeat 稳定存在），但 WebSocket
重连次数波动很大”的充电桩。

### 关键约定
- 输入文件命名格式支持 `proxy_16-3.log` 与 `proxy-11-3.log`
- 日期范围从输入文件中解析，以最小日期到最大日期的连续自然日为准
- 如果某天没有对应重连文件，则该天 `reconnect_file_present = 0`
- 如果某天存在重连文件，但设备未出现，则该天 `reconnect_count = 0`
- 如果某天不存在重连文件，则该天 `reconnect_count = -1`
- `heartbeat_day_count >= 12`、`reconnect_max >= 30` 且
  `reconnect_cv >= 0.8` 的设备进入候选集合
- 候选设备按 `reconnect_cv` 从高到低排序
"""

import csv
import datetime as dt
import glob
import logging
import math
import os
import re
from typing import Dict, List, Optional, Tuple

from ..data.databricks_client import DatabricksClient

logger = logging.getLogger(__name__)


class ProxyReconnectHeartbeatAnalyzer:
    """
    proxy 多日重连与 Heartbeat 波动分析器。

    主流程分为三层：
    1. 按设备、按天生成长表
    2. 在长表基础上生成设备级波动摘要
    3. 将候选异常设备展开为宽表，便于人工检查
    """

    DEFAULT_FILE_GLOB = 'proxy*.log'
    DEFAULT_ANALYSIS_YEAR = 2026
    DEFAULT_HEARTBEAT_MIN_DAYS = 12
    DEFAULT_RECONNECT_MAX_THRESHOLD = 30
    DEFAULT_RECONNECT_CV_THRESHOLD = 0.8
    DEFAULT_MODEL_PREFIX = ''
    LONG_TABLE_HEADERS = [
        'charge_point_id',
        'device_model_prefix',
        'date',
        'reconnect_file_present',
        'reconnect_count',
        'heartbeat_count',
    ]
    SUMMARY_HEADERS = [
        'charge_point_id',
        'device_model_prefix',
        'heartbeat_day_count',
        'heartbeat_mean',
        'heartbeat_std',
        'heartbeat_cv',
        'reconnect_file_day_count',
        'reconnect_mean',
        'reconnect_std',
        'reconnect_cv',
        'reconnect_max',
        'reconnect_min',
        'reconnect_range',
        'candidate_flag',
    ]

    def __init__(
        self,
        input_dir: str,
        output_dir: str,
        file_glob: str = DEFAULT_FILE_GLOB,
        analysis_year: int = DEFAULT_ANALYSIS_YEAR,
        heartbeat_min_days: int = DEFAULT_HEARTBEAT_MIN_DAYS,
        reconnect_max_threshold: int = DEFAULT_RECONNECT_MAX_THRESHOLD,
        reconnect_cv_threshold: float = DEFAULT_RECONNECT_CV_THRESHOLD,
        model_prefix: str = DEFAULT_MODEL_PREFIX,
    ):
        """初始化分析器。"""
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.file_glob = file_glob
        self.analysis_year = analysis_year
        self.heartbeat_min_days = heartbeat_min_days
        self.reconnect_max_threshold = reconnect_max_threshold
        self.reconnect_cv_threshold = reconnect_cv_threshold
        self.model_prefix = model_prefix.lower().strip()
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

    def run(self) -> Dict[str, object]:
        """执行完整分析流程。"""
        file_map = self._collect_input_files()
        if not file_map:
            raise FileNotFoundError(
                f"在目录中未找到符合模式的输入文件: {self.input_dir}/{self.file_glob}"
            )

        date_span = self._build_date_span(file_map)
        reconnect_map = self._read_reconnect_files(file_map)
        heartbeat_map = self._query_heartbeat_map(date_span[0], date_span[-1])
        long_rows = self._build_long_rows(date_span, file_map, reconnect_map, heartbeat_map)
        summary_rows = self._build_summary_rows(long_rows)
        wide_rows, wide_headers = self._build_wide_rows(long_rows, summary_rows)
        output_paths = self._build_output_paths()

        self._write_csv(output_paths['long'], self.LONG_TABLE_HEADERS, long_rows)
        self._write_csv(output_paths['summary'], self.SUMMARY_HEADERS, summary_rows)
        self._write_csv(output_paths['wide'], wide_headers, wide_rows)

        return self._build_run_summary(
            file_map=file_map,
            date_span=date_span,
            long_rows=long_rows,
            summary_rows=summary_rows,
            wide_rows=wide_rows,
            output_paths=output_paths,
        )

    # ========================
    # 第二部分：输入文件收集
    # ========================

    def _collect_input_files(self) -> Dict[dt.date, str]:
        """收集并解析输入文件日期。"""
        search_pattern = os.path.join(self.input_dir, self.file_glob)
        candidate_paths = sorted(glob.glob(search_pattern))
        file_map: Dict[dt.date, str] = {}

        for file_path in candidate_paths:
            parsed_date = self._parse_date_from_filename(os.path.basename(file_path))
            if parsed_date is None:
                logger.warning("文件名不符合预期格式，已跳过: %s", file_path)
                continue
            file_map[parsed_date] = file_path

        logger.info("共识别到 %s 个按天重连文件", len(file_map))
        return file_map

    def _parse_date_from_filename(self, filename: str) -> Optional[dt.date]:
        """从文件名中解析日期。"""
        matched = re.match(r'^proxy[-_](\d{1,2})-(\d{1,2})\.log$', filename)
        if not matched:
            return None

        day_text, month_text = matched.groups()
        try:
            return dt.date(self.analysis_year, int(month_text), int(day_text))
        except ValueError:
            logger.warning("文件名日期非法，已跳过: %s", filename)
            return None

    def _build_date_span(self, file_map: Dict[dt.date, str]) -> List[dt.date]:
        """根据最小日期与最大日期生成连续日期列表。"""
        min_date = min(file_map)
        max_date = max(file_map)
        date_span: List[dt.date] = []
        current_date = min_date

        while current_date <= max_date:
            date_span.append(current_date)
            current_date += dt.timedelta(days=1)

        logger.info("分析日期范围: %s 到 %s", min_date, max_date)
        return date_span

    # ========================
    # 第三部分：重连文件解析
    # ========================

    def _read_reconnect_files(
        self,
        file_map: Dict[dt.date, str],
    ) -> Dict[str, Dict[dt.date, int]]:
        """读取全部重连文件，生成设备-日期映射。"""
        reconnect_map: Dict[str, Dict[dt.date, int]] = {}

        for reconnect_date, file_path in sorted(file_map.items()):
            device_counts = self._read_single_reconnect_file(file_path)
            for charge_point_id, reconnect_count in device_counts.items():
                device_map = reconnect_map.setdefault(charge_point_id, {})
                device_map[reconnect_date] = reconnect_count

        logger.info("重连文件解析完成，设备数=%s", len(reconnect_map))
        return reconnect_map

    def _read_single_reconnect_file(self, file_path: str) -> Dict[str, int]:
        """读取单个按天重连文件。"""
        device_counts: Dict[str, int] = {}

        with open(file_path, 'r', encoding='utf-8') as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                parsed_row = self._parse_reconnect_line(raw_line, line_number, file_path)
                if parsed_row is None:
                    continue
                charge_point_id, reconnect_count = parsed_row
                device_counts[charge_point_id] = (
                    device_counts.get(charge_point_id, 0) + reconnect_count
                )

        return device_counts

    def _parse_reconnect_line(
        self,
        raw_line: str,
        line_number: int,
        file_path: str,
    ) -> Optional[Tuple[str, int]]:
        """解析单行重连记录。"""
        stripped_line = raw_line.strip()
        if not stripped_line:
            return None

        parts = stripped_line.split(maxsplit=1)
        if len(parts) != 2:
            logger.warning(
                "文件 %s 第 %s 行格式非法，已跳过: %s",
                file_path,
                line_number,
                stripped_line,
            )
            return None

        reconnect_text, charge_point_id = parts
        try:
            reconnect_count = int(reconnect_text)
        except ValueError:
            logger.warning(
                "文件 %s 第 %s 行次数非法，已跳过: %s",
                file_path,
                line_number,
                stripped_line,
            )
            return None

        charge_point_id = charge_point_id.strip()
        if self.model_prefix and not charge_point_id.lower().startswith(self.model_prefix):
            return None

        return charge_point_id, reconnect_count

    # ========================
    # 第四部分：Heartbeat 聚合查询
    # ========================

    def _query_heartbeat_map(
        self,
        start_date: dt.date,
        end_date: dt.date,
    ) -> Dict[str, Dict[dt.date, int]]:
        """按设备、按天查询 Heartbeat 次数。"""
        query = self._build_heartbeat_query(start_date, end_date)
        columns, rows = self.databricks_client.execute_query(query)
        heartbeat_map: Dict[str, Dict[dt.date, int]] = {}

        for row in rows:
            parsed_row = dict(zip(columns, row))
            charge_point_id = str(parsed_row['charge_point_id'])
            heartbeat_date = self._parse_query_date(parsed_row['event_date'])
            heartbeat_count = int(parsed_row['heartbeat_count'] or 0)
            if heartbeat_date is None:
                continue

            device_map = heartbeat_map.setdefault(charge_point_id, {})
            device_map[heartbeat_date] = heartbeat_count

        logger.info("Heartbeat 聚合查询完成，设备数=%s", len(heartbeat_map))
        return heartbeat_map

    def _build_heartbeat_query(
        self,
        start_date: dt.date,
        end_date: dt.date,
    ) -> str:
        """构建按设备、按天聚合 Heartbeat 的 SQL。"""
        model_prefix_filter = ''
        if self.model_prefix:
            model_prefix_filter = (
                "AND REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) "
                f"LIKE '{self.model_prefix}%'"
            )

        return f"""
        SELECT
            REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) AS charge_point_id,
            CAST(DATE(operation_timestamp) AS STRING) AS event_date,
            COUNT(*) AS heartbeat_count
        FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_ocpp_operations_v
        WHERE DATE(operation_timestamp) >= DATE('{start_date.isoformat()}')
          AND DATE(operation_timestamp) <= DATE('{end_date.isoformat()}')
          AND ocpp_message_type = 'Heartbeat'
          {model_prefix_filter}
        GROUP BY
            REGEXP_EXTRACT(sso_id, '^([^_]+)', 1),
            DATE(operation_timestamp)
        ORDER BY charge_point_id ASC, event_date ASC
        """

    def _parse_query_date(self, value: object) -> Optional[dt.date]:
        """解析查询结果中的日期字段。"""
        if isinstance(value, dt.date):
            return value
        if value is None:
            return None

        try:
            return dt.date.fromisoformat(str(value))
        except ValueError:
            logger.warning("无法解析查询结果日期: %s", value)
            return None

    # ========================
    # 第五部分：长表构建
    # ========================

    def _build_long_rows(
        self,
        date_span: List[dt.date],
        file_map: Dict[dt.date, str],
        reconnect_map: Dict[str, Dict[dt.date, int]],
        heartbeat_map: Dict[str, Dict[dt.date, int]],
    ) -> List[Dict[str, object]]:
        """构建设备-日期粒度长表。"""
        all_device_ids = sorted(set(reconnect_map) | set(heartbeat_map))
        long_rows: List[Dict[str, object]] = []

        for charge_point_id in all_device_ids:
            device_prefix = self._extract_device_model_prefix(charge_point_id)
            for current_date in date_span:
                reconnect_file_present = 1 if current_date in file_map else 0
                reconnect_count = self._resolve_reconnect_count(
                    charge_point_id=charge_point_id,
                    current_date=current_date,
                    reconnect_file_present=reconnect_file_present,
                    reconnect_map=reconnect_map,
                )
                heartbeat_count = heartbeat_map.get(charge_point_id, {}).get(current_date, 0)
                long_rows.append(
                    {
                        'charge_point_id': charge_point_id,
                        'device_model_prefix': device_prefix,
                        'date': current_date.isoformat(),
                        'reconnect_file_present': reconnect_file_present,
                        'reconnect_count': reconnect_count,
                        'heartbeat_count': heartbeat_count,
                    }
                )

        logger.info("长表构建完成，行数=%s", len(long_rows))
        return long_rows

    def _resolve_reconnect_count(
        self,
        charge_point_id: str,
        current_date: dt.date,
        reconnect_file_present: int,
        reconnect_map: Dict[str, Dict[dt.date, int]],
    ) -> int:
        """解析某设备某天的重连次数展示值。"""
        if reconnect_file_present == 0:
            return -1

        return int(reconnect_map.get(charge_point_id, {}).get(current_date, 0))

    def _extract_device_model_prefix(self, charge_point_id: str) -> str:
        """从设备 ID 中提取字母前缀。"""
        matched = re.match(r'^([A-Za-z]+)', charge_point_id)
        if not matched:
            return ''
        return matched.group(1).lower()

    # ========================
    # 第六部分：设备摘要分析
    # ========================

    def _build_summary_rows(
        self,
        long_rows: List[Dict[str, object]],
    ) -> List[Dict[str, object]]:
        """在长表基础上计算设备级统计指标。"""
        rows_by_device: Dict[str, List[Dict[str, object]]] = {}
        for row in long_rows:
            charge_point_id = str(row['charge_point_id'])
            rows_by_device.setdefault(charge_point_id, []).append(row)

        summary_rows: List[Dict[str, object]] = []
        for charge_point_id, device_rows in rows_by_device.items():
            summary_rows.append(self._build_single_summary_row(charge_point_id, device_rows))

        summary_rows.sort(
            key=lambda item: (
                0 if int(item['candidate_flag']) == 1 else 1,
                -float(item['reconnect_cv']),
                -int(item['reconnect_max']),
                str(item['charge_point_id']),
            )
        )
        logger.info("设备摘要构建完成，设备数=%s", len(summary_rows))
        return summary_rows

    def _build_single_summary_row(
        self,
        charge_point_id: str,
        device_rows: List[Dict[str, object]],
    ) -> Dict[str, object]:
        """构建单台设备的波动摘要。"""
        heartbeat_values = [int(row['heartbeat_count']) for row in device_rows]
        heartbeat_day_count = sum(1 for value in heartbeat_values if value > 0)

        reconnect_values = [
            int(row['reconnect_count'])
            for row in device_rows
            if int(row['reconnect_file_present']) == 1
        ]

        reconnect_mean, reconnect_std, reconnect_cv = self._calculate_series_stats(
            reconnect_values
        )
        heartbeat_mean, heartbeat_std, heartbeat_cv = self._calculate_series_stats(
            heartbeat_values
        )
        reconnect_max = max(reconnect_values) if reconnect_values else -1
        reconnect_min = min(reconnect_values) if reconnect_values else -1
        reconnect_range = (
            reconnect_max - reconnect_min
            if reconnect_values
            else -1
        )
        reconnect_file_day_count = len(reconnect_values)
        candidate_flag = 1 if self._is_candidate_device(
            heartbeat_day_count=heartbeat_day_count,
            reconnect_max=reconnect_max,
            reconnect_cv=reconnect_cv,
        ) else 0

        return {
            'charge_point_id': charge_point_id,
            'device_model_prefix': self._extract_device_model_prefix(charge_point_id),
            'heartbeat_day_count': heartbeat_day_count,
            'heartbeat_mean': round(heartbeat_mean, 6),
            'heartbeat_std': round(heartbeat_std, 6),
            'heartbeat_cv': round(heartbeat_cv, 6),
            'reconnect_file_day_count': reconnect_file_day_count,
            'reconnect_mean': round(reconnect_mean, 6),
            'reconnect_std': round(reconnect_std, 6),
            'reconnect_cv': round(reconnect_cv, 6),
            'reconnect_max': reconnect_max,
            'reconnect_min': reconnect_min,
            'reconnect_range': reconnect_range,
            'candidate_flag': candidate_flag,
        }

    def _calculate_series_stats(self, values: List[int]) -> Tuple[float, float, float]:
        """计算均值、标准差与变异系数。"""
        if not values:
            return 0.0, 0.0, -1.0

        mean_value = sum(values) / len(values)
        if len(values) == 1:
            std_value = 0.0
        else:
            variance = sum((value - mean_value) ** 2 for value in values) / len(values)
            std_value = math.sqrt(variance)

        if mean_value <= 0:
            cv_value = -1.0
        else:
            cv_value = std_value / mean_value

        return mean_value, std_value, cv_value

    def _is_candidate_device(
        self,
        heartbeat_day_count: int,
        reconnect_max: int,
        reconnect_cv: float,
    ) -> bool:
        """判断设备是否进入候选异常集合。"""
        return (
            heartbeat_day_count >= self.heartbeat_min_days
            and reconnect_max >= self.reconnect_max_threshold
            and reconnect_cv >= self.reconnect_cv_threshold
        )

    # ========================
    # 第七部分：宽表展开
    # ========================

    def _build_wide_rows(
        self,
        long_rows: List[Dict[str, object]],
        summary_rows: List[Dict[str, object]],
    ) -> Tuple[List[Dict[str, object]], List[str]]:
        """仅对候选设备展开为宽表。"""
        candidate_ids = [
            str(row['charge_point_id'])
            for row in summary_rows
            if int(row['candidate_flag']) == 1
        ]
        long_index = self._build_long_index(long_rows)
        sorted_dates = self._collect_sorted_dates(long_rows)
        wide_headers = self._build_wide_headers(sorted_dates)
        wide_rows: List[Dict[str, object]] = []

        for charge_point_id in candidate_ids:
            row = {
                'charge_point_id': charge_point_id,
                'device_model_prefix': self._extract_device_model_prefix(charge_point_id),
            }
            for date_text in sorted_dates:
                day_data = long_index.get(charge_point_id, {}).get(date_text, {})
                row[f'{date_text}_reconnect_count'] = day_data.get('reconnect_count', -1)
                row[f'{date_text}_heartbeat_count'] = day_data.get('heartbeat_count', 0)
            wide_rows.append(row)

        logger.info("宽表构建完成，候选设备数=%s", len(wide_rows))
        return wide_rows, wide_headers

    def _build_long_index(
        self,
        long_rows: List[Dict[str, object]],
    ) -> Dict[str, Dict[str, Dict[str, object]]]:
        """把长表构建为按设备、按日期索引的映射。"""
        long_index: Dict[str, Dict[str, Dict[str, object]]] = {}

        for row in long_rows:
            charge_point_id = str(row['charge_point_id'])
            date_text = str(row['date'])
            long_index.setdefault(charge_point_id, {})[date_text] = row

        return long_index

    def _collect_sorted_dates(self, long_rows: List[Dict[str, object]]) -> List[str]:
        """收集并排序长表中的日期。"""
        return sorted({str(row['date']) for row in long_rows})

    def _build_wide_headers(self, sorted_dates: List[str]) -> List[str]:
        """构建宽表表头。"""
        headers = ['charge_point_id', 'device_model_prefix']
        for date_text in sorted_dates:
            headers.append(f'{date_text}_reconnect_count')
            headers.append(f'{date_text}_heartbeat_count')
        return headers

    # ========================
    # 第八部分：结果输出
    # ========================

    def _build_output_paths(self) -> Dict[str, str]:
        """构建输出文件路径。"""
        os.makedirs(self.output_dir, exist_ok=True)
        return {
            'long': os.path.join(
                self.output_dir,
                'proxy-reconnect-heartbeat-long.csv',
            ),
            'summary': os.path.join(
                self.output_dir,
                'proxy-reconnect-heartbeat-summary.csv',
            ),
            'wide': os.path.join(
                self.output_dir,
                'proxy-reconnect-heartbeat-wide.csv',
            ),
        }

    def _write_csv(
        self,
        output_path: str,
        headers: List[str],
        rows: List[Dict[str, object]],
    ) -> None:
        """写出 CSV 文件。"""
        with open(output_path, 'w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        logger.info("结果文件已写出: %s", output_path)

    def _build_run_summary(
        self,
        file_map: Dict[dt.date, str],
        date_span: List[dt.date],
        long_rows: List[Dict[str, object]],
        summary_rows: List[Dict[str, object]],
        wide_rows: List[Dict[str, object]],
        output_paths: Dict[str, str],
    ) -> Dict[str, object]:
        """生成执行摘要。"""
        candidate_count = sum(1 for row in summary_rows if int(row['candidate_flag']) == 1)
        return {
            'input_file_count': len(file_map),
            'analysis_start_date': date_span[0].isoformat(),
            'analysis_end_date': date_span[-1].isoformat(),
            'device_count': len(summary_rows),
            'long_row_count': len(long_rows),
            'candidate_count': candidate_count,
            'wide_row_count': len(wide_rows),
            'long_output_path': output_paths['long'],
            'summary_output_path': output_paths['summary'],
            'wide_output_path': output_paths['wide'],
        }
