# 生产环境

生产栈（`docker-compose.yml`）使用预构建镜像，并由 Nginx 承接前端流量。

## 第 1 步 — 创建 `.env`

```bash
cp env.sample .env
```

至少设置这些生产值：

- `DJANGO_DEBUG=false`、强随机 `SECRET_KEY`
- `ALLOWED_HOSTS`、`SITE_DOMAIN`、`FRONTEND_URL`、`VITE_API_BASE_URL`、`CSRF_TRUSTED_ORIGINS`、`CORS_ALLOWED_ORIGINS`
- 数据库：`DB_ENGINE=mysql`，`MYSQL_HOST=mysql`，并设强 `MYSQL_ROOT_PASSWORD` / `MYSQL_PASSWORD`
- `EMAIL_*` 用于发送通知
- 若使用入站邮件，设 `AUTO_ASSIGN_EMAIL_DOMAIN`
- `ACCOUNT_DEFAULT_HTTP_PROTOCOL=https`

完整变量参考见[配置](/zh/self-hosting/configuration/environment.md)章节。

## 第 2 步 — 构建并启动

```bash
docker compose build
docker compose up -d
```

生产栈包含：API（gunicorn）、worker、scheduler、UI、Nginx、MariaDB、Redis、Haraka。

## 生产端口

Nginx 对外发布应用；请在其前面放置你自己的 HTTPS 反向代理。

| 变量 | 默认 | 用途 |
|------|------|------|
| `NGINX_HTTP_PORT` | `10080` | HTTP 入口 |
| `NGINX_HTTPS_PORT` | `10443` | HTTPS 入口 |
| `NGINX_ADMIN_PORT` | `19443` | 管理端口 |
| `HARAKA_SMTP_PORT` | `25` | 入站 SMTP |

## HTTPS

HTTPS 建议在反向代理（**Nginx Proxy Manager**、**Traefik**、**Caddy** 等）处终止 TLS，再转发到 `NGINX_HTTP_PORT`。

下一步：[入站邮件（Haraka）](./haraka.md) 与 [首次运行](./first-run.md)。
