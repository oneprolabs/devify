# 发布门禁

四道门禁全部通过，才可以把当前分支当作“可发布候选”。CI 由
`.github/workflows/test-gate.yml` 执行同一组命令；本文记录本地怎么跑、通过标准
和当前基线。

## 1. 后端测试（MariaDB）

后端测试只认 MariaDB。SQLite 会在 `threadline` 的 MySQL 专用迁移上失败，因此
不能用 SQLite 结果替代。

本地开发栈已经提供数据库时，在 `devify-api-dev` 容器里执行：

```bash
docker exec devify-api-dev sh -lc 'cd /opt/devify && \
  DJANGO_SETTINGS_MODULE=core.settings /opt/venv/bin/python -m pytest -q -p no:sugar'
```

注意两点：

- 容器只挂载 `./devify` 到 `/opt/devify`，仓库根与 `pyproject.toml` 不在容器内，
  所以必须显式设置 `DJANGO_SETTINGS_MODULE`，并使用 `/opt/venv/bin/python`。
- 不要同时跑两个 pytest 进程：它们会争用同一个测试库，产生成片的 setup error。

通过标准：0 failed、0 error。

## 2. 前端单元测试

```bash
cd ui && npm run test:unit
```

通过标准：全部通过（当前 19 个文件 / 56 项）。

## 3. 生产构建

```bash
cd ui && npm run build
```

通过标准：构建成功且无新增告警。

## 4. 迁移检查

```bash
docker exec devify-api-dev sh -lc 'cd /opt/devify && \
  DJANGO_SETTINGS_MODULE=core.settings /opt/venv/bin/python manage.py check && \
  DJANGO_SETTINGS_MODULE=core.settings /opt/venv/bin/python manage.py \
    makemigrations --check --dry-run'
```

通过标准：系统检查无问题；没有未生成的迁移。迁移演练同时要求空库与存量库都能完成。

## 当前基线（2026-11-03）

| 门禁 | 结果 |
| --- | --- |
| 后端全量（MariaDB） | 1506 passed, 7 skipped, 0 failed |
| 前端单元测试 | 56 passed / 56 |
| 生产构建 | 通过 |
| 迁移检查 | 无问题、无漂移 |

## 已知约定

- 测试缓存默认走 LocMemCache（`devify/conftest.py`），避免与正在运行的开发栈
  共用 Redis 锁；需要 Redis 行为的测试自行 `override_settings`。
- 临时任务锁、调度 guard 依赖缓存，因此本地同时运行 scheduler 时，未隔离缓存的
  测试会出现随机 `skipped` 结果。
- 性能用例保留在套件内，断言的是“明显异常”的耗时阈值，不用于容量评估。
