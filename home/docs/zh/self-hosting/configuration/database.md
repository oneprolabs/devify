# 数据库

用 `DB_ENGINE` 选择数据库引擎。两个 compose 栈都自带 **MariaDB** 服务，因此推荐 `DB_ENGINE=mysql` 并设 `MYSQL_HOST=mysql`（服务名）。

## 引擎

| 引擎 | 变量 |
|------|------|
| `sqlite` | `SQLITE_PATH` |
| `mysql` | `MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_DATABASE`、`MYSQL_ROOT_PASSWORD` |
| `postgresql` | `POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_HOST`、`POSTGRES_PORT`、`POSTGRES_DB` |

## 推荐（MySQL / MariaDB）

```dotenv
DB_ENGINE=mysql
MYSQL_USER=devify
MYSQL_PASSWORD=devify
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=devify
MYSQL_ROOT_PASSWORD=devify_root
```

> 内置的 MariaDB 容器**必须设 `MYSQL_ROOT_PASSWORD`**。未设则容器会以 *"Database is uninitialized and password option is not specified"* 崩溃重启，API 也永远起不来（它等数据库健康检查）。生产请用强密码。

## SQLite

`DB_ENGINE=sqlite` 配 `SQLITE_PATH` 适合快速试用，但 compose 栈是围绕 MariaDB 服务构建的——任何正式部署都优先用 MySQL。
