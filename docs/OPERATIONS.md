# V1.0 运维、监控与备份恢复

## 健康与监控

- `/api/v1/health`：进程存活、版本和环境；
- `/api/v1/ready`：数据库连接就绪；
- 管理端“运行监控”：请求量、5xx 错误率、P95、名片发布成功率、公开访问成功率、留资成功率和线索首次处理时长。

建议基线：核心管理接口 P95 小于 500 ms，公开名片接口 P95 小于 300 ms，系统 5xx 错误率低于 1%。进程内指标在重启后清零，生产环境应由外部监控持续抓取健康状态并保存历史。

## 日志

请求日志包含方法、路径、状态、耗时和请求编号，不记录密码、访问令牌、刷新令牌和留资表单正文。排障时先记录页面错误和 `X-Request-ID`，再关联服务日志和审计日志。

## SQLite 备份

```powershell
.\scripts\backup.ps1
```

备份默认写入 `data/backups`，包含数据库文件和同名 JSON 清单。清单记录版本、时间、大小和 SHA-256。工具使用 SQLite 在线备份 API，并在完成后执行完整性检查。

## 隔离恢复演练

在隔离目录复制备份及清单，设置测试数据库地址，停止测试 API 后执行：

```powershell
$env:DATABASE_URL="sqlite:///./data/restore-drill.db"
.\scripts\restore.ps1 -Backup ".\data\backups\digitalcard-时间.db"
uv run alembic -c backend/alembic.ini upgrade head
```

恢复工具验证清单校验和及 SQLite 完整性。覆盖现有目标必须显式传入 `-Force`，并自动保留一份 `pre-restore` 安全副本。恢复后检查 ready、管理员登录、企业数量、已发布名片和客户记录。

## 定期任务建议

- 每日备份并异地保留；
- 每周检查磁盘、上传目录和备份可读性；
- 每月执行隔离恢复演练；
- 发布前后各创建一次备份；
- 依据隐私和合同要求设置日志、线索、客户及备份保留期限。
