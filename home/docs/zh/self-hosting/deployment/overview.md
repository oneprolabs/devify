# 部署概览

Devify 开源、可自托管。本章带你从零（克隆代码）到运行起整套服务——涵盖本地开发与自托管生产两种场景，默认你对 Docker 和命令行有基本了解。

## 前置条件

- **Docker** 与 **Docker Compose v2**（`docker compose`，而非旧版 `docker-compose`）。
- **Node.js 18+** 与 **npm**——仅开发环境需要（UI 通过 Vite dev server 运行，依赖宿主机的 `node_modules`）。
- **Git**。
- 至少一个受支持的 **LLM 提供商**账号及 API 凭据，且需包含一个**多模态**模型（图像理解与意图识别必需）。
- 用于发送通知的 **SMTP 服务器**。

## 宿主机最低资源

| 资源 | 最低 |
|------|------|
| CPU | 2 核 |
| 内存 | 4 GB |
| 存储 | 20 GB |

## 获取代码

```bash
git clone https://github.com/cloud2ai/devify.git
cd devify
```

仓库顶层结构：

```text
devify/                 # Django 后端（应用代码在此）
ui/                     # Vue 3 前端（Vite）
docker/                 # 服务配置（Haraka、Nginx、MySQL）
docker-compose.yml      # 生产栈
docker-compose.dev.yml  # 开发栈
env.sample              # 环境变量模板
```

## 选择部署栈

所有配置由从 `env.sample` 复制出的环境文件驱动，不同栈文件名不同：

| 栈 | 环境文件 | Compose 文件 | 指南 |
|----|----------|--------------|------|
| 开发 | `.env.dev` | `docker-compose.dev.yml` | [开发环境](./development.md) |
| 生产 | `.env` | `docker-compose.yml` | [生产环境](./production.md) |

> **布尔值必须用小写 `true` / `false`。**

栈跑起来后，继续[首次运行](./first-run.md)创建管理员并接入模型。全部环境变量见[配置](/zh/self-hosting/configuration/environment.md)章节。
