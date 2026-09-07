# 故障排查

## MariaDB 崩溃重启："Database is uninitialized and password option is not specified"

环境文件里没设 `MYSQL_ROOT_PASSWORD`（及其他 `MYSQL_*`）。补上（见[开发环境第 2 步](./development.md#第-2-步-配置数据库)）后重建：`docker compose ... up -d`。

## UI 容器不断重启 / `sh: vite: not found`

宿主机 `ui/node_modules` 为空或属主是 root。在宿主机 `ui/` 下执行 `npm install`；若报 `EACCES`，先修属主：`sudo chown -R "$USER" ui/node_modules` 再重装。

## 自定义端口不生效 / `port is already allocated`

启动开发栈时没带 `--env-file .env.dev`，端口变量回退成默认值。带上 `--env-file .env.dev` 重跑，或修改冲突的端口变量（`DJANGO_HOST_PORT`、`FLOWER_HOST_PORT`、`HARAKA_SMTP_PORT`）。

## API 启动后 unhealthy 持续约一分钟

首次启动时 API 会先跑数据库迁移与初始化，之后 web 服务才接受请求；完成后健康检查即通过。用 `docker logs devify-api-dev`（开发）或 `docker logs devify-api`（生产）查看进度。

## LLM 分析缺少标签/摘要且无报错

多半是所绑定模型配置的 `max_tokens` 过小导致输出截断。在 `/management/llm/config` 调高 `max_tokens`；查看已记录的 token 用量（`completion_tokens` 是否顶到上限）可确认。见 [模型提供商](/zh/self-hosting/configuration/llm-providers.md#调优)。
