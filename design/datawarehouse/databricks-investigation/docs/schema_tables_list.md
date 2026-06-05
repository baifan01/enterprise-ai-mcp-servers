# curated-emob-ubitricity-core 表清单与提示词生成优先级

**Schema**：`emobility-uc-prd`.`curated-emob-ubitricity-core`  
**排除**：以 `gcp_` 开头的表（历史数据，已停用，不生成提示词）。

---

## 一、排除的表（gcp_ 开头，共 21 张）

- gcp_sync_cables_v
- gcp_sync_chargepoint_availability_v
- gcp_sync_chargepoint_installations_v
- gcp_sync_chargepoint_sockets_v
- gcp_sync_chargepoint_sockets_without_events_v
- gcp_sync_chargepoints_v
- gcp_sync_charging_attempts_v
- gcp_sync_charging_events_directaccess_with_payment_data_v
- gcp_sync_charging_events_meter_readings_v
- gcp_sync_charging_events_mobilemetering_export_v
- gcp_sync_charging_events_unified_v
- gcp_sync_charging_events_with_payment_values_and_roaming_rates_v
- gcp_sync_ocpp_operations_v
- gcp_sync_ocpp_status_notifications_v
- gcp_sync_pipedrive_monthly_stats_v
- gcp_sync_reporting_portal_charging_events_v
- gcp_sync_reporting_portal_charging_events_without_private_filter_v
- gcp_sync_socket_daily_stats_v
- gcp_sync_socket_daily_stats_with_ghost_attempts_v
- gcp_sync_socket_visits_v
- gcp_sync_sockets_v

---

## 二、保留表（按前缀/域分组）

| 前缀/域 | 表名 |
|---------|------|
| **account** | account_roaming_emsp_active_contracts_v |
| **billing** | billing_salesforce_juston_invoice_item_v |
| **charger_customer_driivz** | charger_customer_driivz_charger_charger_group_v, charger_customer_driivz_charger_group_plan_v, charger_customer_driivz_charger_group_v, charger_customer_driivz_contract_v, charger_customer_driivz_plan_tariff_v, charger_customer_driivz_plan_v, charger_customer_driivz_tariff_v |
| **charger_group** | charger_group_to_tariff_v |
| **charger_information** | charger_information_latest_v |
| **charger_location** | charger_location_charger_v, charger_location_v |
| **charger_location_sitetracker** | charger_location_sitetracker_activity_v, charger_location_sitetracker_case_v, charger_location_sitetracker_checklist_item_v, charger_location_sitetracker_field_asset_v, charger_location_sitetracker_item_v, charger_location_sitetracker_job_task_required_v, charger_location_sitetracker_job_v, charger_location_sitetracker_program_v, charger_location_sitetracker_reactive_maintenance_v, charger_location_sitetracker_shipment_v, charger_location_sitetracker_site_v |
| **charger_ocpp** | charger_ocpp_operations_v, charger_ocpp_status_notifications_v |
| **charger_session** | charger_session_for_revenue_dashboard_v, charger_session_mv, charger_session_v |
| **crm_pipedrive** | crm_pipedrive_deal_probability_periods_v, crm_pipedrive_deal_products_v, crm_pipedrive_deals_v, crm_pipedrive_dealupdates_v, crm_pipedrive_monthly_stats_v, crm_pipedrive_monthly_stats_with_history_v, crm_pipedrive_products_v, crm_pipedrive_stages_v |
| **customer_interaction** | customer_interaction_call_eva_v, customer_interaction_email_eva_v |
| **issuetracking** | issuetracking_issue_all_changes_laufzettel_v, issuetracking_issue_all_changes_support_uk_v, issuetracking_issue_status_periods_laufzettel_v, issuetracking_issue_status_periods_support_uk_v, issuetracking_issues_laufzettel_v, issuetracking_issues_support_uk_v |
| **kpi** | kpi_charging_attempts_enriched_v, kpi_connector_daily_stats_v, kpi_device_daily_stats_mv, kpi_device_daily_stats_v |
| **rp** | rp_charger_session_all_v |

---

## 三、按域 + 表名排列的生成优先级

同一域内表关联度高，建议**按域批量生成**：每域一次性提供业务信息，域内表按表名字母序依次或成批生成，便于复用上下文。

**域顺序**（按与当前业务“充电尝试 / OCPP / 设备·位置 / 会话·KPI”的关联度与依赖关系排序；域内表按**表名字母序**排列）：

| 顺序 | 域 | 表数 | 说明 |
|------|-----|------|------|
| 1 | **kpi** | 4 | 充电尝试/KPI；kpi_charging_attempts_enriched_v 已完成 |
| 2 | **charger_ocpp** | 2 | OCPP 事件与状态通知，与尝试分析配套 |
| 3 | **charger_location** | 2 | 设备与位置主数据（不含 sitetracker） |
| 4 | **charger_information** | 1 | 充电桩最新信息 |
| 5 | **charger_session** | 3 | 充电会话与收入看板 |
| 6 | **charger_group** | 1 | 充电桩组与资费关联 |
| 7 | **charger_customer_driivz** | 7 | 客户/合同/套餐/资费，关联度高可一批生成 |
| 8 | **account** | 1 | 漫游合同 |
| 9 | **billing** | 1 | 发票明细 |
| 10 | **rp** | 1 | 报表用会话视图 |
| 11 | **crm_pipedrive** | 8 | CRM 商机/阶段/产品等，域内关联高 |
| 12 | **customer_interaction** | 2 | 客服通话/邮件 |
| 13 | **issuetracking** | 6 | 工单/问题跟踪，域内关联高 |
| 14 | **charger_location_sitetracker** | 11 | 现场维护/站点/任务等，域内关联高 |

---

## 四、各域表名单（域内按表名字母序）

每域内按**表名字母序**排列；生成时可按域一次性提供业务信息，再按本列表依次或成批生成提示词。

### 1. kpi（4）
- kpi_charging_attempts_enriched_v ✅ 已完成
- kpi_connector_daily_stats_v
- kpi_device_daily_stats_mv
- kpi_device_daily_stats_v

### 2. charger_ocpp（2）
- charger_ocpp_operations_v
- charger_ocpp_status_notifications_v

### 3. charger_location（2）
- charger_location_charger_v
- charger_location_v

### 4. charger_information（1）
- charger_information_latest_v

### 5. charger_session（3）
- charger_session_for_revenue_dashboard_v
- charger_session_mv
- charger_session_v

### 6. charger_group（1）
- charger_group_to_tariff_v

### 7. charger_customer_driivz（7）
- charger_customer_driivz_charger_charger_group_v
- charger_customer_driivz_charger_group_plan_v
- charger_customer_driivz_charger_group_v
- charger_customer_driivz_contract_v
- charger_customer_driivz_plan_tariff_v
- charger_customer_driivz_plan_v
- charger_customer_driivz_tariff_v

### 8. account（1）
- account_roaming_emsp_active_contracts_v

### 9. billing（1）
- billing_salesforce_juston_invoice_item_v

### 10. rp（1）
- rp_charger_session_all_v

### 11. crm_pipedrive（8）
- crm_pipedrive_deal_probability_periods_v
- crm_pipedrive_deal_products_v
- crm_pipedrive_deals_v
- crm_pipedrive_dealupdates_v
- crm_pipedrive_monthly_stats_v
- crm_pipedrive_monthly_stats_with_history_v
- crm_pipedrive_products_v
- crm_pipedrive_stages_v

### 12. customer_interaction（2）
- customer_interaction_call_eva_v
- customer_interaction_email_eva_v

### 13. issuetracking（6）
- issuetracking_issue_all_changes_laufzettel_v
- issuetracking_issue_all_changes_support_uk_v
- issuetracking_issue_status_periods_laufzettel_v
- issuetracking_issue_status_periods_support_uk_v
- issuetracking_issues_laufzettel_v
- issuetracking_issues_support_uk_v

### 14. charger_location_sitetracker（11）
- charger_location_sitetracker_activity_v
- charger_location_sitetracker_case_v
- charger_location_sitetracker_checklist_item_v
- charger_location_sitetracker_field_asset_v
- charger_location_sitetracker_item_v
- charger_location_sitetracker_job_task_required_v
- charger_location_sitetracker_job_v
- charger_location_sitetracker_program_v
- charger_location_sitetracker_reactive_maintenance_v
- charger_location_sitetracker_shipment_v
- charger_location_sitetracker_site_v

---

后续生成时：先选定域（或指定表），提供该域/表的业务信息后，按上表域内顺序依次生成各表提示词及 all_tables_summary 条目。
