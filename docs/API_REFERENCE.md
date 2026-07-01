# DigitalCard V1.4 API 使用说明

服务启动后访问 `/docs` 查看 Swagger UI，访问 `/openapi.json` 获取机器可读的 OpenAPI 文档。业务接口统一使用 `/api/v1` 前缀。

## 认证与错误

管理接口使用 `Authorization: Bearer <access_token>`，刷新令牌存储在 HttpOnly Cookie。公开名片、产品、素材和留资接口不要求登录，但只返回已发布且允许公开的数据。

错误统一返回 `error.code`、`error.message`、可选 `error.details` 和 `error.request_id`。响应头 `X-Request-ID` 可用于日志定位。`401` 表示未认证或会话失效，`403` 表示账户状态或权限不足，`404` 同时用于不存在和无权读取的租户数据，`409` 表示状态冲突，`422` 表示输入或发布校验失败。

## 接口分组

| 分组 | 主要前缀 | 说明 |
| --- | --- | --- |
| 系统 | `/health`、`/ready` | 存活和数据库就绪检查 |
| 认证 | `/auth` | 登录、刷新、退出、密码 |
| 平台 | `/platform`、`/admin` | 企业与平台账户 |
| 企业 | `/tenant/company`、`/tenant/departments`、`/tenant/roles` | 企业、组织和权限 |
| 员工 | `/tenant/employees` | 员工档案、导入和邀请 |
| 名片 | `/tenant/cards`、`/public/cards` | 模板、草稿、发布和公开访问 |
| 产品 | `/tenant/products`、`/tenant/materials`、`/public/products` | 产品与素材 |
| 线索 | `/tenant/leads`、`/public/cards/{id}/leads` | 留资、分配和领取 |
| CRM | `/tenant/customers`、`/tenant/opportunities` | 客户、跟进、商机和漏斗 |
| 运维 | `/tenant/onboarding`、`/tenant/monitoring` | 初始化进度和运行指标 |
| 经营分析 | `/tenant/analytics` | 指标、趋势、排行、漏斗、抽样事件和报表导出 |
| 营销活动 | `/tenant/marketing`、`/public/campaigns` | 表单、活动、报名、统计、导出和线索转换 |
| SaaS 运营 | `/platform/saas` | 套餐、订阅、用量、注销、运营日志和临时授权 |
| 知识与 AI | `/tenant/knowledge`、`/tenant/ai`、`/public/ai` | 知识索引、配置、来源问答、草稿和审计 |

## 经营分析

- `GET /tenant/analytics/dashboard`：按日期、部门、员工、名片、产品和渠道筛选，返回指标、日趋势、排行、漏斗、数据质量、事件样本及最后更新时间；日期跨度最大 366 天；
- `GET /tenant/analytics/export`：导出当前权限和筛选范围内的有效事件 CSV，最多 100,000 行，仅具有 `analytics.export` 权限的角色可用；
- `ranking_dimension` 支持 `department`、`employee`、`card`、`product`、`channel`，企业本身由当前租户范围确定。

字段、枚举、请求示例及响应结构以当前版本 `/openapi.json` 为准，禁止客户端依赖未声明字段。
