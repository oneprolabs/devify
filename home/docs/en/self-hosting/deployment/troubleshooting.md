# Troubleshooting

## MariaDB crash-loops: "Database is uninitialized and password option is not specified"

`MYSQL_ROOT_PASSWORD` (and the other `MYSQL_*` vars) are not set in your env
file. Set them (see [Development, Step 2](./development.md#step-2-configure-the-database))
and recreate: `docker compose ... up -d`.

## UI container restarts / `sh: vite: not found`

The host `ui/node_modules` is empty or owned by root. Run `npm install` in `ui/`
on the host; if it fails with `EACCES`, fix ownership first:
`sudo chown -R "$USER" ui/node_modules` and re-run `npm install`.

## Custom ports have no effect / `port is already allocated`

You started the dev stack without `--env-file .env.dev`, so port variables fell
back to defaults. Re-run with `--env-file .env.dev`, or change the conflicting
port variable (`DJANGO_HOST_PORT`, `FLOWER_HOST_PORT`, `HARAKA_SMTP_PORT`).

## API stays `unhealthy` for a minute after start

On first boot the API runs database migrations and initialization before the
web server accepts requests; the health check passes once that finishes. Check
progress with `docker logs devify-api-dev` (dev) or `docker logs devify-api`
(production).

## LLM analysis missing tags/summary with no error

Likely output truncation from a too-small `max_tokens` on the bound model
config. Raise `max_tokens` in `/management/llm/config`. Inspect recorded token
usage (`completion_tokens` hitting the ceiling) to confirm. See
[LLM providers](/en/self-hosting/configuration/llm-providers.md#tuning).
