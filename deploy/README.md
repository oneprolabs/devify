# Devify Deploy

The production entrypoint for the hosted Devify stack with the public homepage
enabled. It lives in the `devify` repository now; `devify-deploy` was merged in
and archived.

## What lives where on the deploy host

Two checkouts of this one repository, at two different refs:

- **the deploy root** — tracks `main`, and holds the runtime state the release
  must not touch: `.env`, `data/`, `cache/`, `.active_color`,
  `.rollback_version`. Only `deploy/` is checked out.
- **`.devify/`** — pinned to the release tag, re-synced by every deploy. Only
  `docker/` and `deploy/` are checked out, alongside the root files.

Neither carries `devify/`, `ui/` or `home/`. Those build the images; the deploy
host runs the images. `sync_devify` sets `.devify`'s sparse checkout itself, so
it converges on its own — including narrowing a full checkout made before this
was introduced.

## First install

```bash
git clone --filter=blob:none --sparse \
    https://github.com/oneprolabs/devify.git devify-deploy
cd devify-deploy
git sparse-checkout init --cone
git sparse-checkout set deploy

cp deploy/env.sample .env
vim .env
./deploy/scripts/devify-deploy.sh install
```

`init --cone` comes first because git only learned `--cone` on
`sparse-checkout set` in 2.36. Before that — production runs 2.34 — the flag
is taken as a literal path pattern, which lands the checkout in non-cone mode
and deletes the root files, `docker-compose.yml` included.

### Narrowing an existing deploy root

A deploy root cloned in full needs no re-clone — the runtime state stays put:

```bash
cd /path/to/deploy/root
git sparse-checkout init --cone
git sparse-checkout set deploy
```

The script will:

- fetch `devify` into `.devify/`
- create runtime directories under `data/`
- pull images
- start the full stack

## Upgrade

```bash
cd devify-deploy
git pull
./deploy/scripts/devify-deploy.sh upgrade
```

Deploy a specific `devify` version:

```bash
DEVIFY_REF=v1.0.3 ./deploy/scripts/devify-deploy.sh upgrade
```

Use a custom `devify` repository:

```bash
DEVIFY_REPO=https://github.com/oneprolabs/devify.git DEVIFY_REF=main \
  ./deploy/scripts/devify-deploy.sh upgrade
```

## Operations

```bash
./deploy/scripts/devify-deploy.sh status
./deploy/scripts/devify-deploy.sh logs
./deploy/scripts/devify-deploy.sh logs devify-api
./deploy/scripts/devify-deploy.sh restart
./deploy/scripts/devify-deploy.sh stop
./deploy/scripts/devify-deploy.sh start
./deploy/scripts/devify-deploy.sh config
```

Update `devify`, `devify-deploy/docker-compose.yml`, or `.env`, then rerun:

```bash
./deploy/scripts/devify-deploy.sh config
```

## Ports

| Service | Default Port |
| --- | --- |
| HTTP | `80` |
| HTTPS | `443` |
| Admin HTTPS | `19443` |
| Haraka SMTP | `25` |

Change ports in `.env`:

```bash
NGINX_HTTP_PORT=8080
NGINX_HTTPS_PORT=8443
NGINX_ADMIN_PORT=19443
HARAKA_SMTP_PORT=25
```

## Inbound Email DNS

The full Haraka integration is maintained by `devify` and included by this
deployment script. For production auto-assigned email addresses, make these
values consistent:

- `.env`: `AUTO_ASSIGN_EMAIL_DOMAIN=aimychats.com`
- synced Haraka host list: `.devify/docker/haraka/config/host_list.prod`
- DNS: MX record for the same domain pointing to this server

Example:

```text
aimychats.com.        MX   10 mail.aimychats.com.
mail.aimychats.com.   A    <server-public-ip>
aimychats.com.        TXT  "v=spf1 mx -all"
_dmarc.aimychats.com. TXT  "v=DMARC1; p=quarantine; rua=mailto:admin@aimychats.com"
```

Port 25 must be open to the public internet. Detailed Haraka notes live in:

```bash
.devify/docker/haraka/README.md
```

## Certificates

Homepage and app certificates are mounted from:

```text
data/certs/nginx/
```

The existing certificate helper scripts remain available:

```bash
./scripts/generate-self-signed-certs.sh
./scripts/generate-certs-docker.sh
./scripts/generate-letsencrypt-certs.sh
```

Haraka certificate management now belongs to the `devify` repository and is
available inside the synced checkout after install:

```bash
DEVIFY_RUNTIME_ROOT="$(pwd)" .devify/scripts/manage-haraka-certs.sh status
```

## Important Files

- `scripts/devify-deploy.sh`: install, upgrade, and operations wrapper.
- `docker-compose.yml`: homepage-only Compose override.
- `docker/nginx/aimychats.com.conf`: homepage Nginx routing.
- `env.sample`: production environment template for the whole stack.

## Upgrading MariaDB

The database is a single shared service — blue/green does not cover it, so a
version change is real downtime. Locally, an in-place 11.6.2 → 11.8.9 upgrade
was ready in 7 seconds on an empty schema; production carries 2.2 GB, so
expect tens of seconds rather than minutes.

```bash
# 1. back up first, and check the backup before going further
TS=$(date +%Y%m%d-%H%M%S)
docker exec devify-mariadb sh -c \
  'exec mariadb-dump -uroot -p"$MYSQL_ROOT_PASSWORD" --all-databases \
     --single-transaction --routines --events --triggers' \
  | gzip > /apps/devify/backups/devify-full-$TS.sql.gz
gzip -t /apps/devify/backups/devify-full-$TS.sql.gz

# 2. point .env at the new image, then deploy
#    DEVIFY_MYSQL_IMAGE=mariadb:11.8
#    MARIADB_AUTO_UPGRADE=1
```

`MARIADB_AUTO_UPGRADE` runs `mariadb-upgrade` **on the system tables only** —
its own log says so: *"The --upgrade-system-tables option was used, user
tables won't be touched."* The user tables have to be checked separately, and
this is the step that is easy to assume happened:

```bash
docker exec devify-mariadb sh -c \
  'mariadb-check -uroot -p"$MYSQL_ROOT_PASSWORD" --check-upgrade --all-databases'
```

Every table must report `OK`. Then confirm the schema still matches the code:

```bash
docker exec devify-api-blue python manage.py migrate --check   # expect 0
```

Rolling back means restoring the dump onto the previous image. `mariadb-upgrade`
rewrites system tables, so the running data directory does not go backwards —
the backup from step 1 is the only way back.
