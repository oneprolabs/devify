# 开发环境

开发栈（`docker-compose.dev.yml`）挂载源码实现热重载，UI 跑 Vite dev server，并包含用于 Celery 监控的 Flower。

## 第 1 步 — 创建 `.env.dev`

开发 compose 读取的是 **`.env.dev`**（不是 `.env`）：

```bash
cp env.sample .env.dev
```

## 第 2 步 — 配置数据库

开发栈会启动一个 MariaDB 服务，其容器必须通过健康检查后 API 才会启动。这需要数据库凭据，因此在 `.env.dev` 中设置：

```dotenv
DB_ENGINE=mysql
MYSQL_USER=devify
MYSQL_PASSWORD=devify
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=devify
MYSQL_ROOT_PASSWORD=devify_root
```

> **为什么必须这样：** `env.sample` 默认 `DB_ENGINE=sqlite` 且 MySQL 段被注释。如果 `MYSQL_ROOT_PASSWORD` 未设置，MariaDB 容器会以 *"Database is uninitialized and password option is not specified"* 退出并陷入崩溃重启循环，而 API 因等待数据库健康检查而永远无法启动。

所有引擎选项见[数据库](/zh/self-hosting/configuration/database.md)。

## 第 3 步 — 安装 UI 依赖

开发 compose 会把宿主机的 `ui/node_modules` 挂进 UI 容器，因此必须先在宿主机安装依赖，否则容器会报 `sh: vite: not found`：

```bash
cd ui && npm install && cd ..
```

## 第 4 步 — 构建并启动

```bash
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d --build
```

> **重要 —— `--env-file .env.dev`：** compose 文件里的 `env_file:` 只把变量注入**容器内部**。而端口映射如 `${DJANGO_HOST_PORT}`、`${FLOWER_HOST_PORT}` 的插值来自项目默认的 `.env` 或 shell，**不来自 `env_file`**。加上 `--env-file .env.dev` 才能让你自定义的端口（及其他被插值的值）生效；不加则端口回退到默认值。

## 开发端口

| 服务 | 默认宿主端口 | 变量 |
|------|--------------|------|
| 应用（经 Nginx → UI + API） | `8000` | `DJANGO_HOST_PORT` |
| Flower（Celery 监控） | `5555` | `FLOWER_HOST_PORT` |
| Haraka（入站 SMTP） | `25` | `HARAKA_SMTP_PORT` |

若某端口在宿主机已被占用，改 `.env.dev` 里对应变量，并带 `--env-file .env.dev` 重跑 `up`。

## 验证

```bash
docker compose -f docker-compose.dev.yml ps          # 所有服务 healthy/up
curl -f http://127.0.0.1:8000/health                 # HTTP 200
```

下一步：[首次运行](./first-run.md)。
