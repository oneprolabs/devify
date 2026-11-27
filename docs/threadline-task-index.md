# Threadline conversation task index

Migration `threadline.0044_index_conversation_tasks` adds a virtual
conversation key and a composite index to the AgentCore task-execution
table. Existing rows are indexed from their JSON metadata. Application
writers keep using the AgentCore model. The migration requires no data
backfill.

Run the migration before switching the API to the new code. The
migration adds the column and index separately, requests online DDL
without a table copy, and bounds lock acquisition to five seconds.
Run it on a representative MariaDB copy first. Measure index build
time, free disk space, and lock waits under concurrent load. The
server still scans the task table once while building the index.
An unsupported DDL algorithm or lock mode fails the migration.

For an application rollback, restore the previous API code first. The
column and index can remain in place. To remove them later, reverse
this migration during maintenance after checking the migration plan.
