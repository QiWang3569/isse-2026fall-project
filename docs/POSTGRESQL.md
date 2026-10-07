# 本机 PostgreSQL + pgvector 接入

本项目可以在本机 Docker 中运行 PostgreSQL 16 和 pgvector。容器只监听 `127.0.0.1:5432`；数据库数据保存在 Docker 卷中，重启容器不会清空。应用仍需以**单个后端进程**运行，因为匹配任务使用进程内 worker。

## 1. 准备配置

安装并启动 Docker Desktop。在项目根目录创建 `.env`（已有文件直接编辑），设置下面两项。`POSTGRES_PASSWORD` 请自行生成足够长的随机密码；`DATABASE_URL` 中使用完全相同的密码。如果密码含 `@`、`:`、`/` 等 URL 特殊字符，先对密码进行 URL 编码。

```dotenv
POSTGRES_PASSWORD=<你的随机数据库密码>
DATABASE_URL=postgresql+psycopg://yandu:<同一个密码>@127.0.0.1:5432/yandu
```

保留 `.env` 中已有的邮件和模型配置。`.env` 已被 Git 忽略，不要把它提交到仓库。若希望关闭演示账号，再设置 `DEMO_MODE=false`；它与数据库类型无关。

## 2. 启动数据库

```sh
docker compose up -d postgres
docker compose ps
```

等待 `postgres` 显示 `healthy`。这一步只启动数据库，不启动网页服务。
迁移并检查完成后，执行 `docker compose up -d --build app backup`，即可在 `http://127.0.0.1:8000` 运行本机容器版网页并开启每 24 小时一次的 PostgreSQL 自动备份。此容器版强制关闭演示登录；不要同时运行另一份占用 8000 端口的后端。可用 `python3 scripts/verify_postgres_restore.py` 将最新备份恢复到临时数据库进行验证。备份保存在 `data/backups/postgres`，仍需定期复制到独立存储。

## 3. 迁移现有 SQLite 数据

如果以前使用 `data/yandu.db`，先停止燕渡后端，避免复制期间产生新写入，然后运行：

```sh
# macOS / Linux
.venv/bin/python scripts/migrate_sqlite_to_postgres.py --apply
```

```powershell
# Windows PowerShell
.\.venv\Scripts\python.exe scripts\migrate_sqlite_to_postgres.py --apply
```

脚本先通过 SQLite 在线备份接口生成 `data/backups/` 下的快照并检查完整性，再在一个 PostgreSQL 事务内导入所有项目表、保留原 ID 和时间戳，并核对各表行数。目标表必须为空；导入失败会回滚本次数据写入，原 SQLite 数据不会删除。`data/` 不进入 Git。如果是全新项目，没有 SQLite 数据，可跳过这一步；应用首次启动会建表。

## 4. 启动与检查

照 README 的对应系统启动后端，打开 `http://127.0.0.1:8000`。检查接口：

```sh
curl http://127.0.0.1:8000/api/v1/health
docker compose exec postgres psql -U yandu -d yandu -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
```

服务在 PostgreSQL 中使用 `vector(1536)` 字段，并建立商品向量 HNSW 索引。只有配置 `EMBEDDING_MODE=remote` 和有效的 `EMBEDDING_API_KEY` 后，新商品与新代蹲任务才会生成向量并使用向量召回；旧数据需要用同一个 embedding 模型回填后才能参与向量匹配。保持 `EMBEDDING_MODE=local` 时，应用继续使用本地关键词匹配。

## 回退与边界

若要暂时回到 SQLite，先停止后端，将 `.env` 中的 `DATABASE_URL` 改回 `sqlite:///./data/yandu.db`，再启动。迁移后的 PostgreSQL 新写入不会自动同步回 SQLite；迁移前快照可用于人工恢复。不要运行 `docker compose down -v`，那会删除数据库卷。

本机容器已验证建表、扩展、HNSW 索引、数据迁移和接口访问。公开部署仍需要独立的备份策略、版本化数据库迁移、监控和多进程任务队列；目前的本机容器不等于已上线的托管数据库。
