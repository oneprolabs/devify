# 空间标识改为 UUID：迁移与上线说明

`Space.id` 由自增整数改为 UUID，23 个引用 `spaces.Space` 的外键列同步转换，
API 路径与 `relay` 的 `space_id` 查询参数也改为 UUID。迁移文件：
`devify/spaces/migrations/0002_space_uuid_primary_key.py`。

## 迁移做了什么

1. 先把每个整数空间 id 映射到一个新 UUID，写入 `spaces_space_id_map`
   （迁移后保留）。映射在改动任何数据之前落库，重跑必须复用它，否则父子行会
   对不上。
2. 对每张关联表：把外键和涉及 `space_id` 的索引暂存到
   `spaces_space_uuid_refs`（临时表），再按映射把 UUID 写进 `space_id__uuid_tmp`。
3. 替换 `spaces_space` 主键，然后逐表换成 UUID 列并重建索引与外键。
4. 全部完成时删除 `spaces_space_uuid_refs`。

MySQL/MariaDB 的 DDL 不能回滚，所以每一步都先看实际 schema 再执行；中途失败
可以直接再跑一次 `migrate`，它会从断点继续，并复用已有映射与快照。

## 上线步骤

1. **备份数据库**。部署脚本的 `rollback` 只切流量，不会还原数据库，迁移也没有
   逆向操作：

   ```bash
   docker compose exec mysql sh -c \
     'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" \
        --single-transaction --routines --triggers "$MYSQL_DATABASE"' \
     > devify-before-uuid.sql
   ```

2. **进入维护窗口，停掉旧 color 与新任务的写入**。旧版本用整数 id 访问 UUID 列
   会直接报错（404 / `Incorrect uuid value`），迁移期间不应继续服务。
3. 运行迁移：

   ```bash
   python manage.py migrate --noinput
   ```

4. 立即校验（失败会返回非 0）：

   ```bash
   python manage.py verify_space_uuid
   ```

   它会检查主键与 23 个外键列的类型、可空性、外键约束，逐表统计行数和孤儿
   行数，并报告残留的 `*__uuid_tmp` 列或未完成的快照表。
5. 记录迁移前后的行数对比，确认空间、成员、工作流、分析、会话、邮件数量未变。
6. 启动新版本服务，再放开流量；桌面端需要同批发布支持 UUID 的版本。

## 迁移中途失败

- 不要恢复 `django_migrations`，也不要手工删 `*__uuid_tmp` 列。重新执行
  `migrate` 会继续完成转换。
- `spaces_space_uuid_refs` 还在，说明转换未完成；`verify_space_uuid` 会把它列为
  问题。
- 若迁移报「rows were added while the migration was running」，说明还有进程在写
  数据，先停掉写入再重跑。
- 若报 `no constraint snapshot was kept`，说明快照表被清理过，只能从备份恢复。

## 演练结果（2026-11-16）

在从 `spaces 0001` 起步、带数据的草稿库上演练两次，其中一次故意在子表插入一条
指向不存在空间的行，让迁移在转换 22 张表之后中止：

- 删除该行后重跑 `migrate` 直接完成，映射沿用第一次生成的结果，孤儿 0；
- 迁移前后逐表比对 24 张表：67 个外键的名称、列与 delete rule（全为
  `RESTRICT`）、全部索引逐一相同，行数只因删除注入行而变化；
- 空库全量 `migrate`、`verify_space_uuid`、`makemigrations --check` 均通过。

注意：MySQL/MariaDB 的 `DROP FOREIGN KEY` 不会删除支撑该外键的索引，而该索引
与约束同名。迁移在重建约束前会先删掉这类残留索引，否则约束会被跳过。

## 对账

`spaces_space_id_map` 保留 `old_id` → `new_id` 的对应关系，可用于：

- 把历史日志、审计记录、缓存的整数空间 id 翻译成当前 UUID；
- 核对某个空间的转换结果：`SELECT * FROM spaces_space_id_map ORDER BY old_id;`
- 空间后来被删除时，映射行仍保留（`new_id` 在 `spaces_space` 中不再存在），
  `verify_space_uuid` 只统计数量、不视为错误。
