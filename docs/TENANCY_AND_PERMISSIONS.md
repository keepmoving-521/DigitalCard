# V0.3.0 租户隔离与权限说明

## 权限边界

DigitalCard V0.3.0 使用单企业归属模型。除平台管理员外，每个账户只属于一个企业，并可选归属一个部门。当前版本不支持集团多企业切换。

- 平台管理员负责创建、暂停和恢复企业空间，以及创建初始企业账户；
- 企业用户只能通过令牌关联的 `company_id` 访问本企业数据；
- 企业接口不接受客户端传入的租户编号作为查询边界；
- 部门编号只需在企业内部唯一，不同企业可以使用相同编号；
- 企业暂停、账户停用、改密和重置密码都会让相关旧会话失效。

## 预置角色

| 角色 | 默认能力 |
| --- | --- |
| 平台管理员 | 管理企业生命周期与平台账户，不能作为企业角色使用 |
| 企业管理员 | 企业资料、部门、角色权限和审计的完整管理能力 |
| 内容管理员 | 查看企业与部门，管理名片模板、产品和素材 |
| 销售 | 查看企业、部门、产品和素材，管理自己的资料与名片 |
| 普通员工 | 查看企业、部门和产品，管理自己的资料与名片 |

企业管理员角色权限受保护，避免企业失去管理能力。其他企业角色可由企业管理员调整权限，修改即时生效。

## 权限点

| 分类 | 权限点 |
| --- | --- |
| 企业 | `company.read`、`company.update` |
| 组织 | `department.read`、`department.create`、`department.update`、`department.move`、`department.disable` |
| 权限 | `role.read`、`role.update` |
| 审计 | `audit.read` |
| 名片 | `card.read`、`card.edit_self`、`card.publish_self`、`card.template.manage`、`card.manage` |
| 产品 | `product.read`、`product.manage` |
| 素材 | `material.read`、`material.manage` |
| 线索 | `lead.read`、`lead.manage`、`lead.claim` |
| 通知 | `notification.read` |
| 业务预留 | `content.manage`、`customer.manage` |

后端权限依赖会在每次请求时读取当前企业角色绑定，因此角色权限更新无需用户重新登录。前端菜单与路由守卫用于改善体验，不能替代后端校验。

## API

### 平台接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/v1/platform/companies` | 查询企业空间 |
| `POST` | `/api/v1/platform/companies` | 创建企业并初始化四类企业角色 |
| `PATCH` | `/api/v1/platform/companies/{id}/status` | 暂停或恢复企业 |
| `GET/POST` | `/api/v1/admin/users` | 查询或创建平台及企业账户 |

### 企业接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET/PUT` | `/api/v1/tenant/company` | 查看或维护本企业资料 |
| `GET/POST` | `/api/v1/tenant/departments` | 查询部门树或创建部门 |
| `PATCH` | `/api/v1/tenant/departments/{id}` | 编辑部门 |
| `POST` | `/api/v1/tenant/departments/{id}/move` | 移动和排序部门 |
| `POST` | `/api/v1/tenant/departments/{id}/status` | 启用或停用部门 |
| `GET` | `/api/v1/tenant/roles` | 查询企业角色及权限 |
| `PUT` | `/api/v1/tenant/roles/{code}/permissions` | 更新角色权限 |
| `GET` | `/api/v1/tenant/audits` | 查询企业变更审计 |

## 部门约束

- 上级部门必须属于同一企业；
- 移动部门时检查自身引用和祖先循环；
- 停用部门前检查活跃子部门和仍归属该部门的启用账户；
- 重新启用子部门前，上级部门必须处于启用状态；
- 使用其他企业的部门编号访问时统一返回未找到，不泄露跨租户数据是否存在。

## 初始化流程

1. 使用 `scripts/create-admin.ps1` 创建首个平台管理员；
2. 平台管理员登录后，在“企业管理”创建企业空间；
3. 在“账户管理”创建该企业的企业管理员；
4. 企业管理员登录并维护企业资料、部门与角色权限；
5. 企业管理员可继续维护员工档案、名片模板、产品和素材；普通员工按角色权限使用个人资料、名片和只读产品中心。

企业资料、部门、企业状态和角色权限变更会写入租户审计日志。日志记录操作人、动作、对象、变更摘要与时间，不保存密码或令牌。
