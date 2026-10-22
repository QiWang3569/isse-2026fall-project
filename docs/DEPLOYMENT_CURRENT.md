# 燕渡部署记录与更新清单

核查及发布日期：2026-10-15（北京时间）。资料来源包括服务器运行检查、发布验证和本地 `deployment/aliyun/` 副本。当前发布详情见 [10 月 15 日发布记录](RELEASE_20261015.md)，上一轮结构升级见 [10 月 14 日发布记录](RELEASE_20261014.md)。

> 说明：本文记录的是公开服务器截至 2026-10-15 的发布基线。此后 `main` 分支又加入了 Prometheus/Grafana 监控（`/metrics`、`compose.preview.yaml`、`prometheus.yml`）与管理端商业指标看板（用户增长、访客漏斗、GMV、停留时长），这些改动尚未发布到公开站点，也尚未形成对应的发布批次与验收记录。更新服务器前应以 [修改日志](CHANGELOG.md) 的最新条目为准，按 [公开部署说明](DEPLOYMENT.md) 重新走一遍发布验证。

## 已确认的发布基线

当前公开版本于 2026-10-15 08:29 激活，发布批次 `20261015T002506Z-71c83e13261f`。批次名称中的时间为 UTC，实际激活时间以发布记录为准。旧批次及备份仍保留。

| 项目 | 本地记录 |
| --- | --- |
| 公网入口 | `https://39.106.45.65`，使用 IP 地址作为 HTTPS 站点名 |
| 主机与运行目录 | 阿里云 ECS；`/opt/yandu` |
| Git 提交 | `71c83e13261fc72f433b71c562670c564e381ffb` |
| 应用镜像 | `yandu:71c83e13261f`；上一镜像为 `yandu:888885d3125a` |
| 发布状态 | `release.json` 中为 `active` |
| 当次上线检查 | `public_https=true`、`app_healthy=true`、`production=true`、`secure_cookies=true`、`demo_mode=false` |
| 邮件检查 | `email_auth_ready=true`、`chat_email_ready=true`；新用户默认开启，现有 32 个注册用户已一次性开启，允许自行关闭 |
| 当次恢复验证 | 最新备份逐行核对、22 张图片、重复启动、双账号交易、注册默认开启及关闭后重启保持关闭通过 |

证据位于服务器 `/opt/yandu/deployments/20261015T002506Z-71c83e13261f/`，开发机备份副本位于 `deployment/aliyun/backups/20261015T002506Z-71c83e13261f/`。源码、数据库和应用文件的 SHA-256 校验通过，服务器镜像提交、HTTPS 与服务状态已实查。

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

未读站内信邮件提醒使用 `PUBLIC_APP_URL` 和 `CHAT_EMAIL_ENABLED`。服务器总开关已开启，个人偏好自 10 月 15 日默认开启，用户可自行关闭；当日已对现有 32 个注册用户执行一次性开启，启动迁移不覆盖后续选择。配置、数据升级及回退兼容要求见 [共享需求与邮件提醒更新](FOLLOWUP_FEATURES.md)。

`Caddyfile.public` 配置了 ACME 的 `shortlived` 证书配置和 HSTS。证书持续续期是否成功需要线上检查，不能由旧记录推断。

早期 `compose.preview.yaml` 使用 `yandu:446ecbc` 和 HTTP 预览配置；`start-preview.ps1` 将本机 `127.0.0.1:18000` 经 SSH 转发到服务器 `127.0.0.1:8000`。当前公开版使用 HTTPS、安全 Cookie 与站点来源约束，旧 HTTP 隧道不能替代公开版登录验收。

## 现有发布入口

发布工具目前保存在仓库外的 `deployment/aliyun/`，关键文件为 `release-public.py`、`verify-release.py`、`post-deploy-check.py`、`Dockerfile.preview` 和 `compose.public.yaml`。GitHub 推送与测试通过不会调用这些脚本，也不会自动更新线上。

发布脚本在 ECS 上以 root 运行，保持 `.env` 和持久卷位于 `/opt/yandu`，按以下顺序工作：

1. **准备归档**：完整 Git 提交对应的 `yandu-<40位提交>.tar.gz` 放入 `/opt/yandu/incoming/`，校验 SHA-256。批次名格式为 `YYYYMMDDTHHMMSSZ-<提交前12位>`。
2. **`prepare`**：保存旧 Compose、旧镜像名称，生成 PostgreSQL 自定义格式备份和应用数据卷归档；源码解压到 `/opt/yandu/releases/<批次>/`，写入 `REVISION`。记录存入 `/opt/yandu/deployments/<批次>/`。
3. **`build`**：运行 `npm ci` 和前端构建，再构建 `yandu:<提交前12位>`，写入完整 Git 提交镜像标签。
4. **恢复与升级验证**：`verify-release.py` 和 `verify-release-payload.py` 把最新备份恢复到临时库，用新镜像检查原记录保留、图片、重复启动、查询、交易与聊天，结束后删除临时库。副本禁用邮件和外部模型。
5. **切换**：10 月 15 日默认值与界面更新使用 `release-public.py activate`。10 月 14 日结构升级使用 `safe-cutover.py`，先以维护页阻止写入，停止应用并生成数据库和图片备份，复制到异机，再复核新镜像升级及旧镜像恢复。单独镜像切换入口对 10 月 14 日批次禁用。
6. **上线检查**：`post-deploy-check.py` 验证镜像提交、生产配置、HTTPS、健康接口和求购接口，将结果写入批次目录；随后完成真实浏览器业务验收。

以下是准备和构建接口；结构变更版本随后按本次发布记录执行维护窗口切换：

```sh
cd /opt/yandu
python3 release-public.py prepare --revision <完整提交> --release <批次> --archive-sha256 <源码SHA256>
python3 release-public.py build --revision <完整提交> --release <批次>
python3 verify-release.py --release <批次>
python3 safe-cutover.py rehearse --release <批次>
python3 safe-cutover.py freeze --release <批次>
# 将最终备份复制到异机并校验；再次执行 verify-release.py 和 rehearse。
python3 safe-cutover.py activate --release <批次>
python3 post-deploy-check.py --release <批次>
```

## 备份、恢复与回退

**日常数据库备份**由 `scripts/backup_postgres.sh` 在服务启动时执行一次，此后间隔 24 小时执行；每份归档用 `pg_restore --list` 检查可读取，默认清理超过 14 天的旧备份。这项日常任务只备份 PostgreSQL，不包含上传图片。

**每次发布备份**由 `release-public.py prepare` 同时保存 `database.dump`、`app-data.tar.gz`、`compose.previous.yaml` 和含校验值的 `release.json`。本地存在 10 月 12 日这组完整副本，说明该批次已有服务器之外的副本；现有材料不能证明已经设置持续异机备份。

准备脚本备份时没有停止应用写入，数据库和图片也不是在同一时刻打包。需要完整恢复时，应先安排停止写入的窗口，再形成匹配的数据库与文件备份，并把副本保存到独立存储。恢复演练应验证文件可读、图片归属与数据库引用一致，不能只查看归档目录。

**镜像回退接口**如下；10 月 14 日结构升级批次禁止使用此接口，需配套数据恢复。10 月 15 日切回上一镜像不会撤销本次修改的用户偏好：

```sh
cd /opt/yandu
python3 release-public.py rollback --revision <完整提交> --release <批次>
```

该动作只恢复旧 Compose 和应用镜像，**不会恢复数据库、图片或撤销启动时的数据结构升级**。启用新版本前，必须验证旧镜像能读取升级后的数据库，且不会重新公开已撤回或审核隐藏的商品。如果不兼容，应准备兼容补丁或经过演练的数据恢复方案，不能直接调用镜像回退。

如确需恢复数据，先停止业务写入、保留故障现场的新备份，在隔离环境验证目标备份；恢复匹配的数据库和应用数据卷后再启动对应版本并验收。回到发布前备份会丢失备份之后的新交易与聊天，必须先处理这些增量数据。2026 年 10 月 14 日已在本地恢复 10 月 12 日数据库和图片备份，核对原业务记录、图片可读性及归属，并通过新代码的重复迁移与启动；旧镜像回退和发布时的新快照仍需单独演练。

## 本轮核心交易更新发布清单

产品规则已于 2026-10-13 确认：正式商品撤回后退出公开页面并保留历史记录；进行中交易先处理再撤回；待确认收货时禁止重新上架，成交后通过新发布保留旧交易；所有发布入口统一允许 0–3 张图片。

- [x] 读取服务器镜像、Git 提交标签、Compose 和服务健康状态，记录新发布基线。
- [x] 通过后端回归、前端构建与本地 PostgreSQL 16.15 隔离升级测试；再次启动不重复或破坏迁移，结果见 [验证记录](FOLLOWUP_FEATURES.md#验证记录)。
- [x] 使用 10 月 12 日生产备份副本执行本地升级验证，核对真实业务记录、关联和图片，副本不发送邮件；详细结果见 [验证记录](FOLLOWUP_FEATURES.md#验证记录)。
- [x] 更新服务器验证脚本并针对最终备份和新镜像执行，副本关闭邮件。
- [x] 新镜像隔离双账号流程通过；既有回归覆盖并发、撤回、无图发布、草稿及交易冲突，浏览器覆盖手机布局。
- [x] 固定发布提交，校验源码归档；维护窗口中备份数据库和图片，并在开发机保存完整副本。
- [x] 配套数据库和图片恢复到临时环境，旧镜像启动验证通过；禁用仅切回旧镜像的回退方式。
- [x] 更新后验证生产模式、HTTPS、证书、安全 Cookie、公开页面及搜索；真实收件已确认。邮箱链接登录后跳转与双账号交易在隔离环境完成，未借用生产用户身份。
- [ ] 核对定时数据库备份的新归档，安排上传图片的持续备份，明确备份告警和日常维护负责人。

通用新部署步骤见 [公开部署说明](DEPLOYMENT.md)，数据库迁移说明见 [PostgreSQL 说明](POSTGRESQL.md)。本页描述已有服务器的本地发布证据和后续更新要求。
