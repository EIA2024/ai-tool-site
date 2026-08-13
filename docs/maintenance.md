# AI Tool Site — 运维维护手册

> 面向项目维护者，涵盖 Docker 管理、依赖更新、数据库运维、生产部署、监控排查等日常运维操作。

---

## Table of Contents

1. [日常运维概览](#1-日常运维概览)
2. [Docker 运维](#2-docker-运维)
3. [依赖管理](#3-依赖管理)
4. [数据库运维](#4-数据库运维)
5. [Redis 运维](#5-redis-运维)
6. [生产环境部署](#6-生产环境部署)
7. [日志与监控](#7-日志与监控)
8. [备份与恢复](#8-备份与恢复)
9. [安全维护](#9-安全维护)
10. [故障排查速查](#10-故障排查速查)

---

## 1. 日常运维概览

### 项目依赖关系

```
Frontend (React/Vite, port 5173)
    ↕ HTTP / WebSocket
Backend (FastAPI, port 8000)
    ↕ SQL / RESP
PostgreSQL (port 5432)    Redis (port 6379)
```

### 关键端口

| 服务 | 端口 | 环境变量 |
|---|---|---|
| Frontend | 5173 | `FRONTEND_PORT` |
| Backend | 8000 | `BACKEND_PORT` |
| PostgreSQL | 5432 | `POSTGRES_PORT` |
| Redis | 6379 | `REDIS_PORT` |

### 目录结构（运维相关）

```text
ai-tool-site/
├── docker-compose.yml        # 全栈编排
├── .env.example              # 环境变量模板
├── backend/
│   ├── Dockerfile            # 后端容器镜像
│   ├── .dockerignore         # 构建上下文排除
│   ├── .gitignore            # git 排除规则
│   ├── .env.example          # 后端环境变量
│   ├── alembic/              # 数据库迁移
│   └── pyproject.toml        # Python 依赖 & 工具配置
└── frontend/
    ├── Dockerfile            # 前端容器镜像 (multi-stage)
    ├── .dockerignore
    ├── .gitignore
    └── package.json          # Node 依赖
```

---

## 2. Docker 运维

### 基础命令

```bash
# 构建并启动所有服务
docker compose up --build

# 后台启动
docker compose up --build -d

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f          # 所有服务
docker compose logs -f backend  # 仅后端
docker compose logs -f frontend # 仅前端

# 停止服务
docker compose down

# 停止并删除数据卷（⚠️ 会丢失数据库数据）
docker compose down -v

# 重启单个服务
docker compose restart backend

# 重新构建单个服务
docker compose build backend
```

### 数据卷管理

Docker Compose 定义了两个命名数据卷：

| 卷名 | 挂载路径 | 用途 | 备份建议 |
|---|---|---|---|
| `pgdata` | `/var/lib/postgresql/data` | PostgreSQL 数据文件 | ✅ 必须定期备份 |
| `redisdata` | `/data` | Redis 持久化数据 | 可选 |

```bash
# 查看数据卷列表
docker volume ls

# 查看数据卷详情
docker volume inspect ai-tool-site_pgdata

# 手动备份数据卷
docker run --rm -v ai-tool-site_pgdata:/source -v $(pwd)/backup:/backup \
  alpine tar czf /backup/pgdata-$(date +%Y%m%d).tar.gz -C /source .
```

### 容器健康检查

All services configured with health checks. Check status:

```bash
docker compose ps
# "healthy" = OK, "starting" = booting up

# Check specific health log
docker inspect --format='{{json .State.Health}}' $(docker compose ps -q postgres)
```

### 后端启动流程（Docker）

每次 `docker compose up --build` 时，后端容器启动顺序：

1. `alembic upgrade head` — 自动运行所有待执行的数据库迁移
   - 使用环境变量 `DATABASE_URL` 连接 PostgreSQL（Docker 内部 hostname `postgres`）
   - 同步驱动使用 `psycopg2-binary`（运行时用 `asyncpg`）
   - `alembic/env.py` 优先读取 `DATABASE_URL` 环境变量，否则回退到 `alembic.ini`
2. `uvicorn app.main:app --host 0.0.0.0 --port 8000`

### 前端 Docker 架构说明

Docker 模式下，前端由 `serve` 静态文件服务器托管（非 Vite dev server），因此没有反向代理功能。前端通过构建时注入的 `VITE_API_BASE` 直接请求后端：

- **Docker 模式**：`VITE_API_BASE=http://localhost:8000/api`（`docker-compose.yml` 的 `build.args` 传入）
- **Dev 模式**（`npm run dev`）：`VITE_API_BASE` 未设置，默认 `/api`，由 Vite proxy 转发

```yaml
# docker-compose.yml
frontend:
  build:
    context: ./frontend
    args:
      VITE_API_BASE: http://localhost:8000/api
    target: runner
```

---

## 3. 依赖管理

### 后端 (Python)

```bash
cd backend

# 查看已安装包及版本
pip list

# 查看过时的包
pip list --outdated

# 更新单个依赖
pip install --upgrade fastapi

# 更新后锁定版本（当前使用 loose pinning >=）
# 建议测试通过后收紧版本号
```

当前核心依赖及最低版本：

| 包 | 最低版本 | 用途 |
|---|---|---|
| `fastapi` | 0.115.0 | Web 框架 |
| `uvicorn[standard]` | 0.30.0 | ASGI 服务器 |
| `sqlalchemy` | 2.0 | ORM |
| `asyncpg` | 0.30.0 | PostgreSQL 异步驱动 |
| `psycopg2-binary` | 2.9.0 | PostgreSQL 同步驱动（Alembic 迁移用） |
| `alembic` | 1.13.0 | 数据库迁移 |
| `redis` | 5.1.0 | Redis 客户端 |
| `pydantic` | 2.0 | 数据验证 |
| `pydantic-settings` | 2.0 | 配置管理 |

```bash
# 更新依赖版本的推荐流程
# 1. 更新 pyproject.toml 中的版本号
# 2. 重新安装
pip install -e .
# 3. 运行测试
pytest
# 4. 确认启动正常
python -c "from app.main import app; print('OK')"
```

其中 dev 依赖（pytest, ruff, httpx）仅在开发环境中使用，生产环境不应安装。

### 前端 (Node.js)

```bash
cd frontend

# 检查过时的包
npm outdated

# 更新所有补丁版本
npm update

# 更新指定包到最新
npm install react-router-dom@latest

# 检查安全漏洞
npm audit

# 修复安全漏洞
npm audit fix

# 完全重建 node_modules
rm -rf node_modules package-lock.json
npm install
```

```bash
# 更新依赖版本的推荐流程
# 1. 更新 package.json 中的版本号
npm install package@latest
# 2. 构建验证
npm run build
# 3. 确认无类型错误
npx tsc --noEmit
```

### 依赖更新策略

| 更新类型 | 频率 | 操作 |
|---|---|---|
| 安全补丁 | 发现即修复 | `npm audit fix` / `pip audit` |
| 补丁版本 | 每月 | `npm update` / `pip install --upgrade` |
| 次版本 | 每季度 | 更新 pyproject.toml / package.json 后测试 |
| 主版本 | 按需 | 需评估 breaking changes |

---

## 4. 数据库运维

### 连接数据库

```bash
# 通过 Docker
docker compose exec postgres psql -U postgres -d ai_tool_site

# 本地（如果 PostgreSQL 运行在本机）
psql -h localhost -U postgres -d ai_tool_site
```

### 常用 SQL 查询

```sql
-- 查看所有表
\dt

-- 查看表结构
\d chat_sessions
\d chat_messages
\d tool_call_records
\d agent_practice_records

-- 查看练习记录
SELECT * FROM agent_practice_records ORDER BY created_at DESC LIMIT 20;

-- 统计各阶段的练习次数
SELECT stage_key, COUNT(*) FROM agent_practice_records GROUP BY stage_key ORDER BY COUNT(*) DESC;

-- 查看聊天会话数
SELECT COUNT(*) FROM chat_sessions;

-- 查看最近的消息
SELECT s.title, m.role, LEFT(m.content, 50), m.created_at
FROM chat_messages m
JOIN chat_sessions s ON s.id = m.session_id
ORDER BY m.created_at DESC
LIMIT 20;

-- 查看工具调用统计
SELECT tool_id, COUNT(*), SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count
FROM tool_call_records
GROUP BY tool_id;

-- 清理超过30天的聊天历史
DELETE FROM chat_sessions
WHERE created_at < NOW() - INTERVAL '30 days';
```

### Alembic 迁移管理

```bash
cd backend

# 查看迁移历史
alembic history

# 查看当前版本
alembic current

# 自动生成新迁移（检测模型变更）
alembic revision --autogenerate -m "description of change"

# 手动创建空迁移
alembic revision -m "add user_preferences table"

# 升级到最新
alembic upgrade head

# 升级/降级到指定版本
alembic upgrade abc123
alembic downgrade abc123

# 回退一步
alembic downgrade -1

# 查看待执行的 SQL（不实际执行）
alembic upgrade head --sql
```

迁移文件位于 `backend/alembic/versions/`，命名格式为 `{revision_id}_description.py`。

**生产环境迁移注意事项：**

```bash
# 1. 先在本地测试迁移
alembic upgrade head

# 2. 备份数据库（见第8章）

# 3. 在生产环境执行迁移
alembic upgrade head

# 4. 验证表结构正确
alembic check  # Alembic 1.12+ 支持
```

### 数据库迁移回退

若生产环境迁移出现问题：

```bash
# 1. 回退迁移
alembic downgrade -1

# 2. 修复迁移脚本

# 3. 重新升级
alembic upgrade head
```

---

## 5. Redis 运维

### 连接与检查

```bash
# 通过 Docker
docker compose exec redis redis-cli

# 常用 Redis 命令
# 查看所有 key
KEYS *

# 查看 key 的 TTL
TTL <key>

# 查看内存使用
INFO memory

# 查看客户端连接
CLIENT LIST

# 清空所有缓存（⚠️ 谨慎）
FLUSHALL
```

### Redis 配置

当前 Redis 使用默认配置运行在端口 6379。生产环境建议：

```ini
# docker-compose.yml 中可增加的 Redis 生产配置
redis:
  image: redis:7-alpine
  command: redis-server --requirepass ${REDIS_PASSWORD:-} --maxmemory 256mb --maxmemory-policy allkeys-lru
  environment:
    - REDIS_PASSWORD=${REDIS_PASSWORD}
```

### 缓存键命名约定

| 键模式 | 用途 | TTL |
|---|---|---|
| `rl:{key}` | 限流计数器（rate limiter） | 60s |
| 自定义键 | 插件/服务通过 `cache_get`/`cache_set` 的缓存 | 调用方指定 |

---

## 6. 生产环境部署

### 从开发到生产的变更清单

开发环境使用默认密码、无认证。生产环境必须修改以下配置：

```diff
# docker-compose.yml 生产环境调整
- POSTGRES_PASSWORD=postgres       # 默认密码
+ POSTGRES_PASSWORD=${POSTGRES_PASSWORD}  # 从环境变量读取

- POSTGRES_PORT=5432:5432          # 默认端口
+ POSTGRES_PORT=${POSTGRES_PORT:-5432}:5432

# 前端 CORS 限制
- APP_CORS_ORIGINS=http://localhost:5173
+ APP_CORS_ORIGINS=https://your-domain.com
```

### 生产环境部署文件

```yaml
# docker-compose.prod.yml
services:
  postgres:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - internal

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    restart: always
    volumes:
      - redisdata:/data
    networks:
      - internal

  backend:
    build: ./backend
    restart: always
    ports:
      - "127.0.0.1:8000:8000"  # 仅本地监听，前面有反向代理
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      APP_CORS_ORIGINS: https://your-domain.com
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - internal

  frontend:
    build:
      context: ./frontend
      args:
        VITE_API_BASE: https://your-domain.com/api
      target: runner
      dockerfile: Dockerfile
    restart: always
    ports:
      - "127.0.0.1:5173:5173"
    depends_on:
      - backend
    networks:
      - internal

  # 可选：反向代理
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - frontend
      - backend
    networks:
      - internal

networks:
  internal:

volumes:
  pgdata:
  redisdata:
```

### Nginx 反向代理配置

```nginx
# nginx.conf
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # Frontend
    location / {
        proxy_pass http://frontend:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### Linux 服务器常用操作

```bash
# 上传项目到服务器
rsync -avz --exclude 'node_modules' --exclude '.venv' --exclude '__pycache__' \
  ./ user@your-server:/opt/ai-tool-site/

# SSH 到服务器
ssh user@your-server

# 启动生产环境
cd /opt/ai-tool-site
docker compose -f docker-compose.prod.yml up --build -d

# 查看日志
docker compose -f docker-compose.prod.yml logs -f

# 更新服务
git pull
docker compose -f docker-compose.prod.yml up --build -d
```

---

## 7. 日志与监控

### 日志位置

| 服务 | Docker 方式 | 非 Docker 方式 |
|---|---|---|
| Backend | `docker compose logs backend` | 终端 stdout |
| Frontend | `docker compose logs frontend` | 终端 stdout / 浏览器控制台 |
| PostgreSQL | `docker compose logs postgres` | `/var/log/postgresql/` |
| Redis | `docker compose logs redis` | Redis 配置中的 logfile |

### 后端日志级别

默认日志级别为 WARNING。需要调试时可以临时调整：

```python
# backend/app/main.py 中添加
import logging
logging.basicConfig(level=logging.INFO)  # 或 DEBUG
```

### 健康检查端点

```bash
# 后端健康检查
curl http://localhost:8000/api/health
# 返回示例: {"status":"ok","version":"0.1.0"}

# 用脚本监控
#!/bin/bash
if ! curl -sf http://localhost:8000/api/health > /dev/null; then
    echo "Backend is down! Restarting..."
    docker compose restart backend
fi
```

### 资源监控

```bash
# 容器资源使用
docker stats

# 查看单个容器资源
docker stats backend

# 磁盘使用
docker system df

# 清理未使用的资源
docker system prune -f        # 清理停止的容器、网络、悬空镜像
docker system prune -a -f     # 清理所有未使用的镜像（谨慎）

# 查看数据卷占用
docker system df -v
```

---

## 8. 备份与恢复

### PostgreSQL 备份

```bash
# 通过 Docker 备份
docker compose exec -T postgres pg_dump -U postgres ai_tool_site > backup_$(date +%Y%m%d_%H%M%S).sql

# 压缩备份
docker compose exec -T postgres pg_dump -U postgres ai_tool_site | gzip > backup_$(date +%Y%m%d).sql.gz

# 备份指定表
docker compose exec -T postgres pg_dump -U postgres -t chat_sessions -t chat_messages ai_tool_site > chat_backup.sql
```

### PostgreSQL 恢复

```bash
# 从 SQL 文件恢复
cat backup_20260725.sql | docker compose exec -T postgres psql -U postgres -d ai_tool_site

# 从压缩文件恢复
gunzip -c backup_20260725.sql.gz | docker compose exec -T postgres psql -U postgres -d ai_tool_site

# 恢复前清空数据库（谨慎！）
docker compose exec -T postgres psql -U postgres -d ai_tool_site -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

### Redis 备份

```bash
# Redis 数据保存在数据卷中，备份数据卷即可
# 手动触发 RDB 快照
docker compose exec redis redis-cli SAVE

# RDB 文件位置
docker compose exec redis ls -la /data/

# 备份 dump.rdb
docker run --rm -v ai-tool-site_redisdata:/source -v $(pwd)/backup:/backup \
  alpine cp /source/dump.rdb /backup/redis_$(date +%Y%m%d).rdb
```

### 备份策略建议

| 数据 | 备份频率 | 保留时间 | 方法 |
|---|---|---|---|
| PostgreSQL 全量 | 每日 | 7 天 | `pg_dump` |
| PostgreSQL 全量（周） | 每周 | 30 天 | `pg_dump` + 压缩 |
| Redis RDB | 可选 | — | 数据卷快照 |
| docker-compose.yml | 每次变更 | 永久 | Git 版本控制 |
| .env 文件 | 每次变更 | 永久 | 安全存储（不提交 Git） |

---

## 9. 安全维护

### 环境变量安全

```bash
# 创建 .env 文件（永远不要提交到 Git）
cp .env.example .env

# .env 已包含在 .gitignore 中
# 确保以下文件不被提交：
#   - backend/.env
#   - frontend/.env
#   - .env

# 在 Linux 服务器上设置权限
chmod 600 .env
```

### 依赖安全

```bash
# 后端安全审计
pip install pip-audit
pip-audit

# 前端安全审计
cd frontend && npm audit

# 定期运行安全审计（建议集成到 CI）
```

### API 密钥管理

```python
# 绝不要硬编码 API 密钥 ✋
# backend/app/core/config.py
class Settings(BaseSettings):
    deepseek_api_key: str = ""    # 通过 .env 或环境变量注入
```

```bash
# Linux 生产环境通过 systemd 或 Docker 环境变量注入
export DEEPSEEK_API_KEY=sk-...
docker compose up -d
```

### 网络安全

| 配置 | 开发环境 | 生产环境 |
|---|---|---|
| CORS origins | `http://localhost:5173` | `https://your-domain.com` |
| 数据库端口暴露 | 是（方便本地调试） | 否（仅内部网络） |
| Redis 密码 | 无 | 必须设置 |
| PostgreSQL 密码 | 默认值 | 必须修改强密码 |
| TLS/SSL | 无 | 必须配置（Nginx + Let's Encrypt） |

---

## 10. 故障排查速查

### 容器无法启动

```bash
# 查看详细日志
docker compose logs backend

# 检查端口占用
netstat -ano | grep 8000

# 检查环境变量
docker compose config

# 验证 Dockerfile
docker compose build --no-cache backend
```

### 数据库连接失败

```bash
# 验证 PostgreSQL 是否健康
docker compose ps postgres

# 测试连接
docker compose exec postgres pg_isready -U postgres

# 查看连接池状态
docker compose exec postgres psql -U postgres -c "SELECT * FROM pg_stat_activity;"

# 常见原因
# - PostgreSQL 尚未就绪（等待 healthcheck 通过）
# - 密码不匹配（检查 .env 和 docker-compose.yml）
# - 端口冲突（宿主机已有 PostgreSQL 在运行）
```

### Redis 连接失败

```bash
# 验证 Redis 是否健康
docker compose ps redis

# 测试连接
docker compose exec redis redis-cli ping
# 应返回 PONG

# 检查 Redis 是否需要密码
docker compose exec redis redis-cli AUTH yourpassword
```

### 前端无法连接后端

```bash
# Docker 模式
# 1. 检查后端是否运行
curl http://localhost:8000/api/health

# 2. 检查 docker compose 网络
docker compose ps

# 3. 检查前端容器能否访问后端
docker compose exec frontend wget -qO- http://backend:8000/api/health

# 非 Docker 模式
# 1. 确保后端在 8000 端口运行
# 2. 检查 Vite proxy 配置（vite.config.ts）
# 3. 浏览器开发者工具 → Network 标签 → 查看请求是否被代理
```

### WebSocket 连接断开

```bash
# 检查后端 WebSocket 日志
docker compose logs backend | grep -i ws

# 检查 proxy 配置
# vite.config.ts 中 /ws 必须有 ws: true
# Nginx 必须有 Upgrade/Connection header 转发

# 常见原因
# - 连接空闲超时（默认无超时限制）
# - Nginx 的 proxy_read_timeout 太短
# - 后端重启导致连接断开（前端会自动重连）
```

### 磁盘空间不足

```bash
# 查看 Docker 磁盘占用
docker system df

# 清理未使用的镜像、容器、网络
docker system prune -f

# 清理构建缓存
docker builder prune -f

# 清理所有未使用的镜像（包括无标签的 dangling 镜像）
docker image prune -a -f

# 查看数据卷大小
du -sh /var/lib/docker/volumes/ai-tool-site_pgdata/

# 清理旧备份
find ./backup -name "*.sql.gz" -mtime +30 -delete
```

### 性能问题排查

```bash
# 后端响应慢
# 1. 检查 AI API 调用耗时
# 2. 检查数据库查询性能
docker compose exec postgres psql -U postgres -c "
    SELECT query, calls, total_time/calls as avg_time
    FROM pg_stat_statements
    ORDER BY total_time DESC LIMIT 10;"

# 3. 检查 Redis 缓存命中率
docker compose exec redis redis-cli INFO stats | grep hits

# 前端加载慢
# 1. 检查构建产物大小
du -sh frontend/dist/
# 2. 浏览器 DevTools → Network 查看资源加载
# 3. 考虑代码分割 (React.lazy + Suspense)
```

### 清理维护脚本

将以下脚本保存为 `scripts/maintenance.sh` 定期执行：

```bash
#!/bin/bash
# 项目维护脚本

set -e

echo "=== 备份数据库 ==="
docker compose exec -T postgres pg_dump -U postgres ai_tool_site | \
  gzip > "backups/db_$(date +%Y%m%d).sql.gz"

echo "=== 清理旧备份（30天以上） ==="
find ./backups -name "*.sql.gz" -mtime +30 -delete

echo "=== Docker 系统清理 ==="
docker system prune -f

echo "=== 检查容器健康状态 ==="
docker compose ps

echo "=== 维护完成 ==="
```

---

## 附录

### 常用命令速查

| 目的 | 命令 |
|---|---|
| 启动（前台） | `docker compose up --build` |
| 启动（后台） | `docker compose up --build -d` |
| 停止 | `docker compose down` |
| 查看日志 | `docker compose logs -f [service]` |
| 重启服务 | `docker compose restart [service]` |
| 数据库备份 | `docker compose exec -T postgres pg_dump -U postgres ai_tool_site > backup.sql` |
| 数据库恢复 | `cat backup.sql \| docker compose exec -T postgres psql -U postgres -d ai_tool_site` |
| 运行迁移 | `alembic upgrade head` |
| 查看迁移历史 | `alembic history` |
| 检查过时依赖 | `pip list --outdated` / `npm outdated` |
| 安全审计 | `pip-audit` / `npm audit` |

### 环境变量参考

| 变量 | 默认值 | 说明 |
|---|---|---|
| `APP_NAME` | AI Tool Site | 应用名称 |
| `APP_VERSION` | 0.1.0 | 版本号 |
| `APP_CORS_ORIGINS` | http://localhost:5173 | 允许的跨域来源（逗号分隔） |
| `DATABASE_URL` | postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tool_site | 数据库连接字符串 |
| `POSTGRES_USER` | postgres | 数据库用户名 |
| `POSTGRES_PASSWORD` | postgres | 数据库密码 |
| `POSTGRES_DB` | ai_tool_site | 数据库名 |
| `REDIS_URL` | redis://localhost:6379/0 | Redis 连接字符串 |
| `AUDIT_OPERATOR_TOKEN` | 空 | 读取审计原始输入/输出详情所需的 bearer token；为空时禁用详情读取 |
| `RATE_LIMIT_ENABLED` | true | 是否启用调用频率限制 |
| `RATE_LIMIT_PER_MINUTE` | 20 | 每 IP 每分钟允许的调用次数 |
| `RATE_LIMIT_GLOBAL_PER_MINUTE` | 200 | 全站每分钟总调用预算（上限 DeepSeek 花费） |
| `TRUST_PROXY_HEADERS` | false | 仅在反向代理之后设为 true，信任 `X-Forwarded-For` |
| `BACKEND_PORT` | 8000 | 后端端口 |
| `FRONTEND_PORT` | 5173 | 前端端口 |
| `VITE_API_BASE` | `/api` | 前端 API 基础 URL（Docker 构建时设为 `http://localhost:8000/api`） |

---

*Last updated: 2026-07-25*
*Maintainer: EIA2024*

---

## 11. 已知问题

### Docker 模式下首次迁移失败

如果首次 `docker compose up --build` 时后端日志出现 `alembic upgrade head` 错误，常见原因：

1. `DATABASE_URL` 环境变量未正确设置 → 检查 `docker compose config`
2. PostgreSQL 尚未就绪 → 检查 `docker compose ps postgres` 状态
3. 缺少 `psycopg2-binary` → 确认 `pyproject.toml` 包含该依赖

### 非 Docker 开发模式

优先从项目根目录运行 `./start.sh`（macOS）或 `start.bat`（Windows），脚本会使用 SQLite 启动后端并同时启动 Vite。手动运行 `npm run dev` 时，Vite dev server 自带 proxy，不需要 `VITE_API_BASE` 环境变量。如果前端无法连接后端，检查：

1. 后端是否运行在 `localhost:8000`
2. `vite.config.ts` 中的 proxy 配置是否正确
3. 浏览器控制台是否有 CORS 错误
