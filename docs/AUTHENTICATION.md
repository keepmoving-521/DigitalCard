# V0.2.0 账户与认证说明

## 会话模型

DigitalCard 使用短期访问令牌与服务端刷新会话组合。V0.3.0 起，访问请求还会实时校验企业状态和租户角色权限：

- 访问令牌为 HS256 JWT，包含签发者、受众、过期时间、账户令牌版本和会话编号；
- 刷新令牌使用密码学安全随机数生成，只通过 HttpOnly Cookie 传输；
- 数据库只保存刷新令牌的 HMAC-SHA256 摘要，不保存原始令牌；
- 每次刷新都会轮换 Cookie 并撤销旧会话，重复使用旧令牌会撤销该用户全部会话；
- 退出登录立即撤销当前会话，停用账户、修改或重置密码会撤销全部会话；
- 每个受保护请求都会检查账户状态、令牌版本和会话状态。
- 企业账户只属于一个企业；企业暂停后，企业账户立即失去访问权限。

密码使用 pwdlib 推荐的 Argon2 算法哈希。密码至少 12 位，必须包含大小写字母、数字和特殊字符，且不能包含邮箱名称。

## API

| 方法 | 路径 | 权限 | 用途 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/login` | 公开 | 邮箱密码登录并设置刷新 Cookie |
| `POST` | `/api/v1/auth/refresh` | 刷新 Cookie | 轮换会话并返回新访问令牌 |
| `POST` | `/api/v1/auth/logout` | 公开 | 撤销当前刷新会话并清理 Cookie |
| `GET` | `/api/v1/auth/me` | 已登录 | 查询当前账户 |
| `PUT` | `/api/v1/auth/me/password` | 已登录 | 修改密码并撤销所有旧会话 |
| `GET` | `/api/v1/admin/users` | 管理员 | 查询账户列表 |
| `POST` | `/api/v1/admin/users` | 管理员 | 创建账户 |
| `PATCH` | `/api/v1/admin/users/{id}/status` | 管理员 | 启用或停用账户 |
| `POST` | `/api/v1/admin/users/{id}/reset-password` | 管理员 | 重置密码并撤销旧会话 |
| `GET` | `/api/v1/admin/login-audits` | 管理员 | 查询登录审计记录 |

## 主要错误码

| HTTP | 错误码 | 含义 |
| --- | --- | --- |
| 401 | `auth_required` | 请求未提供访问令牌 |
| 401 | `token_expired` | 访问令牌已过期 |
| 401 | `invalid_token` | 访问令牌格式或签名无效 |
| 401 | `token_revoked` | 改密、重置等操作已撤销令牌 |
| 401 | `session_revoked` | 当前设备会话已退出或被轮换 |
| 403 | `account_disabled` | 账户已停用 |
| 403 | `company_suspended` | 企业空间已暂停 |
| 403 | `permission_denied` | 当前账户权限不足 |
| 429 | `account_locked` | 连续失败次数达到锁定阈值 |

登录审计只记录账户、结果、原因、IP、User-Agent 和时间，不记录密码、访问令牌或原始刷新令牌。
