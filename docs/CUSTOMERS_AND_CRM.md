# V0.9.0 客户档案、销售跟进与商机说明

## 线索转客户

线索中心可将未作废、未转换的线索转为客户。转换时保留线索与客户关联，并创建主联系人和客户时间线事件。时间线记录原始线索、名片、推荐产品、分享来源和留资时间，确保转化后来源信息不丢失。

客户包含名称、主联系方式、多个联系人、标签、负责人和状态。联系人支持电话、邮箱、微信和其他类型，可调整排序和主联系人；删除主联系人前必须先选择新的主联系人。

## 数据权限

| 权限点 | 用途 |
| --- | --- |
| `customer.read` | 进入客户中心；销售仅能读取本人负责的客户 |
| `customer.self_manage` | 销售维护本人负责客户的联系人、标签、跟进和归档 |
| `customer.all_manage` | 企业管理员查看、转移、合并全部客户 |
| `opportunity.manage` | 在可管理客户下创建和推进商机 |
| `opportunity.stage.manage` | 配置企业商机阶段 |

客户列表、详情、联系人、跟进、时间线和商机接口使用相同负责人范围。管理员转移客户时，客户及其商机负责人同步更新；原负责人立即失去访问权限，新负责人立即获得权限。

## 跟进与提醒

跟进记录包含方式、文本、实际发生时间和可选的下次跟进时间。支持电话、微信、邮件、面谈和其他方式。每次跟进同时写入客户时间线。

## 商机与漏斗

商机包含名称、预计金额、预计成交日期、负责人和阶段。企业预置初步接洽、方案沟通、商务谈判、成交和丢单阶段，管理员可新增、排序、调整概率及停用阶段。

每次创建商机或变更阶段都会写入独立阶段历史，记录原阶段、目标阶段、操作账户和时间，同时写入客户时间线。漏斗按当前用户可见范围统计各阶段商机数量和预计金额。

## 客户转移、归档与合并

- 转移：仅企业管理员可选择本企业启用员工，并同步商机负责人；
- 归档：保留联系人、跟进、时间线和商机，默认列表不展示；
- 合并预览：返回名称和主联系方式冲突，以及待迁移的联系人、跟进和商机数量；
- 确认合并：联系人、跟进、时间线、商机和历史线索引用迁移至目标客户，标签去重，来源客户标记为已合并。

## 主要接口

| 方法与路径 | 用途 |
| --- | --- |
| `POST /api/v1/tenant/leads/{id}/convert` | 线索转客户 |
| `GET/PATCH /api/v1/tenant/customers/{id}` | 查看或维护客户档案 |
| `POST/PATCH/DELETE /api/v1/tenant/customers/{id}/contacts` | 维护联系人 |
| `POST/GET /api/v1/tenant/customers/{id}/follow-ups` | 新增或查询跟进 |
| `GET /api/v1/tenant/customers/{id}/timeline` | 查询客户时间线 |
| `POST /api/v1/tenant/customers/{id}/transfer` | 转移负责人 |
| `POST /api/v1/tenant/customers/{id}/archive` | 归档客户 |
| `POST /api/v1/tenant/customers/{id}/merge-preview` | 预览合并冲突 |
| `POST /api/v1/tenant/customers/{id}/merge` | 确认合并客户 |
| `GET/POST/PATCH /api/v1/tenant/opportunity-stages` | 配置商机阶段 |
| `POST/GET /api/v1/tenant/customers/{id}/opportunities` | 客户商机 |
| `PATCH /api/v1/tenant/opportunities/{id}` | 更新商机和阶段 |
| `GET /api/v1/tenant/opportunities/{id}/history` | 商机阶段历史 |
| `GET /api/v1/tenant/opportunities/funnel/summary` | 简单漏斗 |

## 暂不包含

报价单、合同、回款、复杂销售预测和自动化销售流程。
