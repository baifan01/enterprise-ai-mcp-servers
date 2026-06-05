#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
充电桩掉线分析程序 (Databricks版)

该程序用于分析电动车充电桩的在线状态，识别充电桩在某一时间段内是否"掉线"。
掉线的判断依据是心跳数据的时间间隔：如果两个连续心跳之间的时间间隔超过设定时间（默认1小时），
并且在两个心跳事件之间没有其他OCPP事件/消息，视为中间存在掉线。

数据从Databricks中获取，分析指定日期之后的OCPP事件信息。
"""

import os
import csv
import datetime
from typing import Dict, List, Tuple, Set, Iterator
from databricks import sql
import pandas as pd
from collections import defaultdict


class ChargerHeartbeatAnalyzerDB:
    """充电桩心跳数据分析器 (Databricks版)"""

    # Databricks连接参数
    static_fan_tocken = 'DATABRICKS_TOKEN_PLACEHOLDER'
    static_server_hostname = 'shell-prj2778928-674688609822-eu-west-1-prd.cloud.databricks.com'
    static_http_path = '/sql/1.0/warehouses/d0ba8f87b62d10f2'

    def __init__(self, output_dir: str, offline_threshold_seconds: int = 3600):
        """
        初始化分析器

        Args:
            output_dir: 输出结果文件目录
            offline_threshold_seconds: 判断掉线的时间阈值（秒），默认为3600秒（1小时）
        """
        self.output_dir = output_dir
        self.offline_threshold_seconds = offline_threshold_seconds

        # 掉线记录，每个元素为(sso_id, 掉线开始时间, 掉线结束时间)
        self.offline_periods = []

        # 特殊异常记录，每个元素为(sso_id, 最后OCPP事件类型, 最后OCPP事件时间戳, 未报告持续小时数)
        self.special_exceptions = []

        # 设备状态跟踪
        self.device_state = {}

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

    # 第一部分：数据获取与预处理

    def get_connection_params(self) -> Dict:
        """获取Databricks连接参数"""
        return {
            "server_hostname": self.static_server_hostname,
            "http_path": self.static_http_path,
            "access_token": self.static_fan_tocken
        }

    def stream_ocpp_data(self, analysis_start_date: str, batch_size: int = 100000) -> Iterator[pd.DataFrame]:
        """
        从Databricks流式获取OCPP事件数据

        Args:
            analysis_start_date: 分析起始日期，格式为'YYYY-MM-DD'
            batch_size: 每批获取的数据行数

        Yields:
            包含OCPP事件数据的DataFrame批次
        """
        print(f"开始从Databricks流式获取OCPP事件数据，起始日期: {analysis_start_date}")

        connection_params = self.get_connection_params()

        try:
            # 建立连接
            print("正在连接到Databricks SQL...")
            with sql.connect(**connection_params) as connection:
                print("连接成功，正在执行查询...")

                # 创建游标
                with connection.cursor() as cursor:
                    # 执行SQL查询，获取数据，使用CAST 时间戳到String是因为有些时间戳没有毫秒，造成Connector获取数据时报错。
                    # 使用REGEXP_EXTRACT或SPLIT提取sso_id的基本部分，忽略后缀
                    query = f"""
                    SELECT
                        -- 提取sso_id的基本部分，忽略"_disabled_xyz"等后缀
                        REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) as sso_id,
                        CAST(operation_timestamp AS STRING) as operation_timestamp,
                        ocpp_message_type
                    FROM `curated-emob-ubitricity-core`.charger_ocpp_operations_v
                    WHERE DATE(operation_timestamp) >= Date('{analysis_start_date}')
                    ORDER BY sso_id, operation_timestamp
                    """
                    print(query)
                    cursor.execute(query)

                    # 获取列名
                    columns = [desc[0] for desc in cursor.description]

                    # 分批获取数据
                    print("开始流式处理数据...")
                    total_rows = 0

                    while True:
                        batch = cursor.fetchmany(batch_size)
                        if not batch:
                            break

                        total_rows += len(batch)
                        print(f"已获取 {total_rows} 行数据...")

                        # 创建DataFrame并预处理
                        df_batch = pd.DataFrame(batch, columns=columns)
                        df_batch = self.preprocess_data(df_batch)

                        yield df_batch

                    print(f"数据获取完成，共 {total_rows} 行")
        except Exception as e:
            print(f"获取数据出错: {e}")
            raise

    def preprocess_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        预处理OCPP事件数据

        Args:
            df: 原始OCPP事件数据DataFrame

        Returns:
            预处理后的DataFrame
        """
        # 转换时间戳格式 - 使用更健壮的方法
        def parse_timestamp(ts):
            """解析各种格式的时间戳"""
            if not isinstance(ts, str):
                return ts

            # 如果包含'T'，将其替换为空格
            ts = ts.replace('T', ' ')

            # 尝试不同的格式
            formats = [
                '%Y-%m-%d %H:%M:%S',      # 无毫秒
                '%Y-%m-%d %H:%M:%S.%f',   # 带毫秒
                '%Y-%m-%d'                # 仅日期
            ]

            for fmt in formats:
                try:
                    return datetime.datetime.strptime(ts, fmt)
                except ValueError:
                    continue

            # 如果所有格式都失败，打印错误并返回None
            print(f"无法解析时间戳: {ts}")
            return None

        # 应用解析函数
        df['operation_timestamp'] = df['operation_timestamp'].apply(parse_timestamp)

        # 删除时间戳为None的行
        df = df.dropna(subset=['operation_timestamp'])

        # 确保数据按sso_id和时间戳排序
        df = df.sort_values(by=['sso_id', 'operation_timestamp'])

        return df

    # 第二部分：掉线分析

    def process_data_batch(self, df_batch: pd.DataFrame, analysis_start_date: datetime.datetime, current_time: datetime.datetime) -> None:
        """
        处理一批数据

        Args:
            df_batch: 预处理后的OCPP事件数据DataFrame批次
            analysis_start_date: 分析起始时间
            current_time: 当前时间
        """
        # 按设备ID分组
        device_groups = df_batch.groupby('sso_id')

        # 遍历每个设备
        for sso_id, device_df in device_groups:
            # 更新设备状态并分析掉线情况
            self.update_device_state(sso_id, device_df, analysis_start_date, current_time)

    def update_device_state(self, sso_id: str, device_df: pd.DataFrame, analysis_start_date: datetime.datetime, current_time: datetime.datetime) -> None:
        """
        更新设备状态并分析掉线情况

        Args:
            sso_id: 设备ID
            device_df: 该设备的OCPP事件数据
            analysis_start_date: 分析起始时间
            current_time: 当前时间
        """
        # 如果是新设备，初始化状态
        if sso_id not in self.device_state:
            self.device_state[sso_id] = {
                'last_heartbeat_time': None,
                'last_event_time': None,
                'last_event_type': None,
                'first_heartbeat_seen': False,
                'first_event_type': None
            }

        state = self.device_state[sso_id]

        # 遍历设备的所有事件
        for _, row in device_df.iterrows():
            event_time = row['operation_timestamp']
            event_type = row['ocpp_message_type']

            # 记录第一个事件类型
            if state['first_event_type'] is None:
                state['first_event_type'] = event_type
            # 如果是心跳事件
            if event_type == 'Heartbeat':
                # 如果有上一次心跳事件
                if state['last_heartbeat_time'] is not None:
                    # 检查两次心跳之间的时间间隔
                    time_diff = (event_time - state['last_heartbeat_time']).total_seconds()

                    # 如果时间间隔超过阈值，并且两次心跳之间没有其他OCPP事件
                    if time_diff > self.offline_threshold_seconds and state['last_heartbeat_time'] == state['last_event_time']:
                        self.offline_periods.append((sso_id, state['last_heartbeat_time'], event_time))

                # 更新最后一次心跳时间
                state['last_heartbeat_time'] = event_time
            # 更新最后一次事件时间和类型
            state['last_event_time'] = event_time
            state['last_event_type'] = event_type

    def finalize_analysis(self, current_time: datetime.datetime) -> None:
        """
        完成分析，处理结束边界判断

        Args:
            current_time: 当前时间
        """
        print("完成分析，处理结束边界判断...")

        # 遍历所有设备状态
        for sso_id, state in self.device_state.items():
            # 如果设备有最后一次事件
            if state['last_event_time'] is not None:
                time_diff = (current_time - state['last_event_time']).total_seconds()
                # 如果距离当前时间超过24小时，记录为特殊异常
                if time_diff > 24 * 3600:
                    hours_offline = time_diff / 3600
                    days_offline = int(hours_offline / 24)
                    self.special_exceptions.append((sso_id, state['last_event_type'], state['last_event_time'], hours_offline, days_offline))




        print(f"分析完成，共发现 {len(self.offline_periods)} 个掉线区间，{len(self.special_exceptions)} 个特殊异常")

    # 第三部分：结果输出

    def write_results(self) -> None:
        """将分析结果写入CSV文件"""
        # 1. 写入掉线区间结果
        offline_output_path = os.path.join(self.output_dir, 'offline_periods.csv')
        with open(offline_output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            # 写入表头
            writer.writerow([
                'sso_id', 'offline_start', 'offline_restore', 'duration_min'
            ])

            # 写入数据
            for sso_id, start_time, end_time in self.offline_periods:
                # 计算掉线时长（分钟）
                offline_duration = (end_time - start_time).total_seconds() / 60

                writer.writerow([
                    sso_id,
                    start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    end_time.strftime('%Y-%m-%d %H:%M:%S'),
                    round(offline_duration, 2)
                ])

        print(f"掉线区间结果已写入 {offline_output_path}")

        # 2. 写入特殊异常结果
        exception_output_path = os.path.join(self.output_dir, 'special_exceptions.csv')
        with open(exception_output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            # 写入表头
            writer.writerow([
                'sso_id', 'last_event_type', 'last_event_time', 'hours_offline', 'days_offline'
            ])

            # 写入数据
            for sso_id, event_type, event_time, hours_offline, days_offline in self.special_exceptions:
                writer.writerow([
                    sso_id,
                    event_type,
                    event_time.strftime('%Y-%m-%d %H:%M:%S'),
                    round(hours_offline, 2),
                    days_offline
                ])

        print(f"特殊异常结果已写入 {exception_output_path}")

    # 主流程

    def run(self, days_to_analyze: int = 30, batch_size: int = 100000) -> None:
        """
        运行分析流程

        Args:
            days_to_analyze: 要分析的天数，默认为30天
            batch_size: 每批处理的数据行数，默认为100000
        """
        print(f"开始充电桩掉线分析，分析过去 {days_to_analyze} 天的数据...")

        # 1. 计算分析起始日期
        current_time = datetime.datetime.now()
        analysis_start_date = current_time - datetime.timedelta(days=days_to_analyze)
        analysis_start_date_str = analysis_start_date.strftime('%Y-%m-%d')

        # 2. 流式获取并处理数据
        for batch_idx, df_batch in enumerate(self.stream_ocpp_data(analysis_start_date_str, batch_size)):
            print(f"处理第 {batch_idx + 1} 批数据...")
            self.process_data_batch(df_batch, analysis_start_date, current_time)
            # 释放内存
            del df_batch

        # 3. 完成分析
        self.finalize_analysis(current_time)

        # 4. 输出结果
        self.write_results()

        print("分析完成")


def main():
    """主函数"""
    # 配置输出目录
    output_dir = 'output'

    # 创建分析器
    analyzer = ChargerHeartbeatAnalyzerDB(output_dir, offline_threshold_seconds=3600)

    # 运行分析，分析过去30天的数据，每批处理100000行
    analyzer.run(days_to_analyze=30, batch_size=100000)


if __name__ == "__main__":
    # 执行测试连接方法
    # ChargerHeartAnalysisDB.test_connection()

    # 执行主函数
    main()
