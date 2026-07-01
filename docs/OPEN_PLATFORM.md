# 开放平台开发者文档

## 认证与凭据

Open API 当前稳定版本为 V1，前缀 `/api/v1/open/v1`。请求必须携带 `X-App-Key` 和 `X-App-Secret`。Secret 只在应用创建或轮换时完整返回，服务端仅保存 SHA-256 摘要；轮换成功后旧 Secret 立即失效。应用可随时停用。

## 权限、隔离和限流

可用作用域为 `leads.write`、`customers.read` 和 `customers.write`。每次调用先校验应用状态、密钥、分钟限流和作用域，再将查询固定在应用所属企业；调用方提供其他企业的资源编号时统一返回未找到。调用日志记录应用、方法、路径、状态和错误码，不记录 Secret。

### 创建线索

`POST /api/v1/open/v1/leads`，需要 `leads.write`。请求体包含 `card_id`、姓名、联系方式、可选需求与 `idempotency_key`。相同应用和幂等键重复提交返回第一次结果，不重复创建线索。

### 更新客户

`PATCH /api/v1/open/v1/customers/{id}`，需要 `customers.write`。只允许更新声明字段，且客户必须属于应用企业。

## Webhook

支持 `lead.created` 和 `customer.updated`。请求头包括：

- `X-DigitalCard-Signature: sha256=<hex>`：对规范 JSON 请求体执行 HMAC-SHA256；
- `X-DigitalCard-Event`：事件类型；
- `Idempotency-Key`：订阅、事件类型和业务事件编号组成的稳定键。

消费方必须以 `Idempotency-Key` 去重。非 2xx、连接错误或超时会进入指数退避，最多尝试五次；管理员可查看失败原因并人工重试。签名密钥只在订阅创建时返回。

部署环境应每分钟由受保护的计划任务调用 `POST /api/v1/tenant/open/deliveries/process-due`，批量处理首次投递和到期重试；单次最多处理 100 条，公开业务请求不等待外部回调。

## 版本和废弃策略

V1 内只增加向后兼容的可选字段，不删除或改变已有字段含义。不兼容变化发布新的 URL 主版本。接口废弃至少提前 90 天公告，并在响应中提供 `Deprecation`、`Sunset` 和迁移文档链接；迁移期内旧版本继续可用。安全漏洞修复可缩短周期，但会提供明确影响说明。
