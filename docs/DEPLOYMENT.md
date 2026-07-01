# V1.0 部署与升级

## 发布前配置

复制 `.env.example` 为 `.env`，至少替换 `SECRET_KEY`、浏览器允许来源、邀请地址和公开名片地址。生产环境设置 `APP_ENV=production`；系统会拒绝默认密钥和任何包含 `localhost` 或 `127.0.0.1` 的浏览器地址。

敏感配置不得写入镜像、Git 或前端构建变量。TLS 应在负载均衡或 Nginx 层终止。

## Docker Compose

```powershell
docker compose build
docker compose up -d
docker compose ps
```

API 容器启动时先执行数据库迁移，再启动服务。就绪检查为 `/api/v1/ready`，管理端默认端口 `8080`，H5 默认端口 `8081`，API 默认端口 `8000`。

## 手工升级

1. 停止写入或进入维护窗口；
2. 执行 `scripts/backup.ps1` 并保存数据库和 JSON 校验清单；
3. 部署新代码并安装锁定依赖；
4. 执行 `alembic -c backend/alembic.ini upgrade head`；
5. 启动服务并检查 health、ready、登录、名片公开页和留资；
6. 观察运行监控和错误日志。

SQLite 适合首批企业和单实例试用。多实例或更高并发生产环境应迁移到受支持的集中式数据库，并改用数据库厂商的在线备份方案。

## 回滚

优先回滚应用镜像且保持向后兼容的数据库结构。确需数据库回退时，停止 API，保存当前备份，按 [发布、回滚与缺陷响应](RELEASE_AND_INCIDENTS.md) 执行迁移回退或恢复发布前备份。禁止在 API 运行期间覆盖 SQLite 文件。
