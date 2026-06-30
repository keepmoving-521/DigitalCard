# V0.6.0 H5 名片与分享说明

## 公开地址与数据边界

公开名片地址格式为 `PUBLIC_CARD_BASE_URL/{card_id}?source={source}`。本地默认地址示例：

```text
http://localhost:5174/card/9c08d5d2-44b8-4f99-82dc-39ee6a68f63c?source=wechat
```

只有状态为“已发布”、员工在职且企业启用的名片可以访问。公开响应来自发布快照，并按员工选择的公开字段生成，因此不会返回草稿、后台编号或未选择公开的联系方式。

名片下线返回 `card_offline`，员工停用返回 `employee_inactive`，企业停用返回 `company_suspended`。H5 会显示对应的不可用状态页。

## 分享与二维码

H5 支持复制带来源参数的链接、系统分享和二维码分享。二维码由后端离线生成 SVG，不依赖第三方二维码服务；二维码内容与响应头 `X-QR-Content` 是同一规范化分享地址。

管理端已发布名片页面展示公开链接、二维码、访问次数和关键操作次数。生产环境的 `PUBLIC_CARD_BASE_URL` 与 `VITE_PUBLIC_CARD_BASE_URL` 应指向相同 H5 `/card` 路径。

## 联系操作

公开页支持 `tel:` 一键拨号、`mailto:` 发送邮件、复制微信号、下载 vCard 3.0 通讯录，以及打开员工公开配置的社交账号。对应字段未公开时，操作入口不会出现。

## 事件与去重

公开事件包括 `view`、`call`、`email`、`wechat_copy`、`vcard_download`、`share_copy` 和 `qr_open`。

H5 在浏览器本地生成匿名访客编号，服务端只保存其 SHA-256 摘要。页面访问按“名片、事件、来源、访客、30 分钟时间窗口”去重；按钮操作采用 10 秒窗口去重。数据库唯一约束作为并发兜底，重复事件返回 `recorded=false`。

## 主要接口

| 接口 | 用途 |
| --- | --- |
| `GET /api/v1/public/cards/{card_id}` | 获取允许公开的已发布名片快照 |
| `GET /api/v1/public/cards/{card_id}/qr.svg` | 生成带来源参数的分享二维码 |
| `POST /api/v1/public/cards/{card_id}/events` | 记录去重后的访问和按钮事件 |
| `GET /api/v1/tenant/cards/me/analytics` | 查看本人名片基础统计 |
| `GET /api/v1/tenant/cards/{employee_id}/analytics` | 企业管理员查看员工名片统计 |
