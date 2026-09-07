# 环境变量

所有配置由从 `env.sample` 复制出的环境文件驱动（开发用 `.env.dev`，生产用 `.env`）。**布尔值必须用小写 `true` / `false`。** 本页是分组速查，深入主题各有专页。

## Django / 运行时

| 变量 | 用途 |
|------|------|
| `SECRET_KEY` | Django 密钥——生产务必更换 |
| `DJANGO_DEBUG` | 开发 `true`，生产 `false` |
| `ALLOWED_HOSTS` | 逗号分隔的主机名 |
| `CSRF_TRUSTED_ORIGINS`、`CORS_ALLOWED_ORIGINS` | 允许调用 API 的来源 |
| `SITE_DOMAIN`、`SITE_NAME` | 公开站点域名（不含协议）——用于 OAuth 和 webhook |
| `FRONTEND_URL`、`VITE_API_BASE_URL` | 前端地址、以及前端调用的 API 基址 |
| `DJANGO_SUPERUSER_USERNAME` / `_EMAIL` / `_PASSWORD` | 首次运行自动创建的超级用户 |

## 数据库

用 `DB_ENGINE` 选择引擎，详见[数据库](./database.md)。

## Celery / Redis / 缓存

| 变量 | 用途 |
|------|------|
| `CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND` | 指向 `redis://redis:6379/0` |
| `CELERY_CONCURRENCY`、`CELERY_LOG_LEVEL` | Worker 调优 |
| `CACHE_BACKEND` | `redis` |
| `FLOWER_HOST_PORT` | Flower 监控端口（开发） |

## 邮件 / 通知

见[邮件与通知](./email-notifications.md)。

| 变量 | 用途 |
|------|------|
| `EMAIL_BACKEND` | 生产用 `smtp`，开发可用 `console` |
| `EMAIL_HOST`、`EMAIL_PORT`、`EMAIL_HOST_USER`、`EMAIL_HOST_PASSWORD`、`EMAIL_USE_TLS` | 发送通知的 SMTP |
| `DEFAULT_FROM_EMAIL` | 发件地址 |
| `AUTO_ASSIGN_EMAIL_DOMAIN` | 自动分配入站邮箱的域名（Haraka） |
| `HARAKA_SMTP_PORT`、`HARAKA_EMAIL_BASE_DIR` | 入站 SMTP 设置 |

## OAuth（可选）

见 [OAuth 登录](./oauth.md)。

| 变量 | 用途 |
|------|------|
| `GOOGLE_OAUTH_CLIENT_ID`、`GOOGLE_OAUTH_CLIENT_SECRET` | Google 登录 |
| `ACCOUNT_DEFAULT_HTTP_PROTOCOL` | 开发 `http`，生产 `https` |

## AI 模型 / 提供商

`env.sample` 里保留了历史的 Azure OpenAI 变量（`AZURE_OPENAI_*`），但**模型提供商主要在启动后的管理控制台里配置**，而非 `.env`。见 [模型提供商](./llm-providers.md)。

## 监控（可选）

`SENTRY_*` 与 `VITE_SENTRY_*`——留空即禁用 Sentry。
