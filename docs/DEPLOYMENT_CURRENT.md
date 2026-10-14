# 燕渡部署记录与更新清单

核查日期：2026-10-13（北京时间）。资料来源为本地 `deployment/aliyun/` 的脚本、配置与发布元数据，以及仓库的部署文件。

## 已确认的发布基线

本地保存了 **2026-10-12 已激活公开版本**的记录。发布批次 `20261012T004247Z-e50aef549d47` 中的时间为 UTC，对应北京时间 10 月 12 日 08:42:47；这是批次命名时间，不是精确的上线完成时间。

| 项目 | 本地记录 |
| --- | --- |
| 公网入口 | `https://39.106.45.65`，使用 IP 地址作为 HTTPS 站点名 |
| 主机与运行目录 | 阿里云 ECS；`/opt/yandu` |
| Git 提交 | `e50aef549d47a2d5db8b48dc0527f0a8b9862996`，提交说明为 `feat(wanted): add responsive keyword search` |
| 应用镜像 | `yandu:e50aef549d47`；上一镜像为 `yandu:446ecbc` |
| 发布状态 | `release.json` 中为 `active` |
| 当次上线检查 | `public_https=true`、`app_healthy=true`、`production=true`、`secure_cookies=true`、`demo_mode=false` |
| 邮件检查 | 当次记录 `email_auth_ready=true`、`smtp_configured=true`；这些字段确认配置状态，未记录真实收件结果 |
| 当次恢复验证 | `restore_ok=true`、`upgrade_ok=true`、`wanted_search_ok=true`；记录检查了新增表与升级前后数据条数一致 |

证据位于开发机 `D:\University\智能化软件系统与工程\deployment\aliyun\backups\20261012T004247Z-e50aef549d47\` 的 `release.json`、`verification.json`、`post-deploy-checks.json`。本次重新计算了源码归档、`database.dump`、`app-data.tar.gz` 的 SHA-256，三者均与发布记录一致；未打开数据库或用户上传文件的内容。

上述记录说明该版本曾通过公开部署检查。本次未连接服务器，服务器当前镜像、证书、服务状态和新增数据仍需在下一次发布前复核。

## 运行拓扑与持久数据

```text
用户 HTTPS :443 / HTTP :80
          │
          ▼
  Caddy 2.11.7
          │ 容器网络 app:8000
          ▼
  FastAPI + 已构建的 React 页面 ── PostgreSQL 16 + pgvector
          │                             │
     yandu_app_data              yandu_postgres_data
                                        │
                                  backup 服务
                                        ▼
                         /opt/yandu/data/backups/postgres
```

实际发布编排为 `/opt/yandu/compose.public.yaml`，Compose 项目名 `yandu`。其本地副本在 `deployment/aliyun/compose.public.yaml`，与仓库提供的新部署模板 `compose.production.yaml` 有差异，更新现有服务器时应以实际编排为基础。

| 服务 | 镜像 / 端口 | 保存位置 |
| --- | --- | --- |
| `app` | `yandu:<提交前12位>`；宿主机仅绑定 `127.0.0.1:8000` | `yandu_app_data` → `/app/data`，含上传图片 |
| `postgres` | `pgvector/pgvector:pg16`；未向宿主机发布数据库端口 | `yandu_postgres_data` → `/var/lib/postgresql/data` |
| `caddy` | `yandu-caddy:2.11.7`；宿主机 80、443 | `yandu_caddy_data`、`yandu_caddy_config`；配置 `/opt/yandu/Caddyfile.public` |
| `backup` | `pgvector/pgvector:pg16`；无公开端口 | `/opt/yandu/data/backups/postgres`，绑定容器 `/backups` |

应用镜像以 Python 3.12 为基础，使用 UID 10001 运行；前端由 Node.js 22 构建。Uvicorn 只运行一个进程，当前后台匹配任务不支持直接增加多个 worker。四个服务的本地公开编排均设置日志轮转：单文件 10 MB，最多 3 份。

运行配置保存在服务器 `/opt/yandu/.env`。公开编排启用安全 Cookie、单个 HTTPS 来源和 `DEMO_MODE=false`；`APP_ENV` 从环境取值且默认回退为 `local`，因此发布检查必须明确验证最终值为 `production`。密码、模型密钥和邮件凭据不写入本页。

新版本的未读站内信邮件提醒需要额外配置 `PUBLIC_APP_URL` 和 `CHAT_EMAIL_ENABLED`，默认关闭，并要求用户自行开启个人偏好。已配置验证码 SMTP 不会自动启用聊天提醒。配置、数据升级及回退兼容要求见 [共享需求与邮件提醒更新](FOLLOWUP_FEATURES.md)。

`Caddyfile.public` 配置了 ACME 的 `shortlived` 证书配置和 HSTS。证书持续续期是否成功需要线上检查，不能由旧记录推断。

早期 `compose.preview.yaml` 使用 `yandu:446ecbc` 和 HTTP 预览配置；`start-preview.ps1` 将本机 `127.0.0.1:18000` 经 SSH 转发到服务器 `127.0.0.1:8000`。当前公开版使用 HTTPS、安全 Cookie 与站点来源约束，旧 HTTP 隧道不能替代公开版登录验收。

## 现有发布入口

发布工具目前保存在仓库外的 `deployment/aliyun/`，关键文件为 `release-public.py`、`verify-release.py`、`post-deploy-check.py`、`Dockerfile.preview` 和 `compose.public.yaml`。GitHub 推送与测试通过不会调用这些脚本，也不会自动更新线上。

发布脚本在 ECS 上以 root 运行，保持 `.env` 和持久卷位于 `/opt/yandu`，按以下顺序工作：

1. **准备归档**：完整 Git 提交对应的 `yandu-<40位提交>.tar.gz` 放入 `/opt/yandu/incoming/`，校验 SHA-256。批次名格式为 `YYYYMMDDTHHMMSSZ-<提交前12位>`。
2. **`prepare`**：保存旧 Compose、旧镜像名称，生成 PostgreSQL 自定义格式备份和应用数据卷归档；源码解压到 `/opt/yandu/releases/<批次>/`，写入 `REVISION`。记录存入 `/opt/yandu/deployments/<批次>/`。
3. **`build`**：运行 `npm ci` 和前端构建，再构建 `yandu:<提交前12位>`，写入完整 Git 提交镜像标签。
4. **恢复与升级验证**：`verify-release.py` 把发布前数据库备份恢复到临时库，使用新镜像启动应用检查后删除临时库。现有脚本主要覆盖求购搜索和旧版本新增表，本轮还需补充新的交易规则、商品撤回和重复启动检查。
5. **`activate`**：确认运行 Compose 未在准备后变化，只替换应用镜像与构建目录，等待应用健康。启动失败时自动恢复旧编排和旧应用镜像。
6. **上线检查**：`post-deploy-check.py` 验证镜像提交、生产配置、HTTPS、健康接口和求购接口，将结果写入批次目录；随后完成真实浏览器业务验收。

以下为脚本接口示例，参数需替换为此次已审查的发布值；本次文档整理未执行它们：

```sh
cd /opt/yandu
python3 release-public.py prepare --revision <完整提交> --release <批次> --archive-sha256 <源码SHA256>
python3 release-public.py build --revision <完整提交> --release <批次>
python3 verify-release.py --release <批次>
python3 release-public.py activate --revision <完整提交> --release <批次>
python3 post-deploy-check.py --release <批次>
```

## 备份、恢复与回退

**日常数据库备份**由 `scripts/backup_postgres.sh` 在服务启动时执行一次，此后间隔 24 小时执行；每份归档用 `pg_restore --list` 检查可读取，默认清理超过 14 天的旧备份。这项日常任务只备份 PostgreSQL，不包含上传图片。

**每次发布备份**由 `release-public.py prepare` 同时保存 `database.dump`、`app-data.tar.gz`、`compose.previous.yaml` 和含校验值的 `release.json`。本地存在 10 月 12 日这组完整副本，说明该批次已有服务器之外的副本；现有材料不能证明已经设置持续异机备份。

准备脚本备份时没有停止应用写入，数据库和图片也不是在同一时刻打包。需要完整恢复时，应先安排停止写入的窗口，再形成匹配的数据库与文件备份，并把副本保存到独立存储。恢复演练应验证文件可读、图片归属与数据库引用一致，不能只查看归档目录。

**应用回退**接口为：

```sh
cd /opt/yandu
python3 release-public.py rollback --revision <完整提交> --release <批次>
```

该动作只恢复旧 Compose 和应用镜像，**不会恢复数据库、图片或撤销启动时的数据结构升级**。启用新版本前，必须验证旧镜像能读取升级后的数据库，且不会重新公开已撤回或审核隐藏的商品。如果不兼容，应准备兼容补丁或经过演练的数据恢复方案，不能直接调用镜像回退。

如确需恢复数据，先停止业务写入、保留故障现场的新备份，在隔离环境验证目标备份；恢复匹配的数据库和应用数据卷后再启动对应版本并验收。回到发布前备份会丢失备份之后的新交易与聊天，必须先处理这些增量数据。本地记录没有显示做过完整的数据库加图片恢复演练。

## 本轮核心交易更新发布清单

产品规则已于 2026-10-13 确认：正式商品撤回后退出公开页面并保留历史记录；进行中交易先处理再撤回；待确认收货时禁止重新上架，成交后通过新发布保留旧交易；所有发布入口统一允许 0–3 张图片。

- [ ] 发布前读取服务器当前镜像、Git 提交标签、Compose 和服务健康状态，确认与本页基线是否一致；记录新的发布基线。
- [ ] 通过后端回归、前端构建与隔离 PostgreSQL 升级测试；再次启动不重复或破坏迁移。
- [ ] 在测试环境用买卖双方完成发布、搜索、聊天、申请和确认预订、售出、确认收货，覆盖手机视口与两位买家竞争场景。
- [ ] 验证无图新建、编辑、草稿发布，以及撤回后的搜索、详情权限、旧会话访问；审核隐藏商品不会公开出现。
- [ ] 验证待收货商品不能重新上架、完成交易的新发布保留旧记录，重复提交与取消预订不会产生冲突状态。
- [ ] 固定发布提交，校验源码归档；备份数据库和图片，并在独立存储保存副本。
- [ ] 对新版本备份恢复和旧镜像兼容性进行演练，明确回退是否需要数据处理；保留可用的旧镜像。
- [ ] 更新后验证生产模式、HTTPS、证书有效期、安全 Cookie、真实邮件收件和双账号关键流程；记录结果与时间。
- [ ] 核对定时数据库备份的新归档，安排上传图片的持续备份，明确备份告警和日常维护负责人。

通用新部署步骤见 [公开部署说明](DEPLOYMENT.md)，数据库迁移说明见 [PostgreSQL 说明](POSTGRESQL.md)。本页描述已有服务器的本地发布证据和后续更新要求。
