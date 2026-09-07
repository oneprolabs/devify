# Devify Deploy

`devify-deploy` is the production entrypoint for the hosted Devify stack with
the public homepage enabled.

The application stack itself is maintained by the `devify` repository. This
repository only keeps the homepage deployment delta, certificate helpers, and a
single install/upgrade script.

## Repository Boundary

- `devify`: API, worker, scheduler, UI, MySQL, Redis, Nginx app/API config, and
  Haraka.
- `devify-deploy`: `devify-home`, homepage Nginx config, production `.env`
  sample, and deployment automation.
- `.devify/`: generated local checkout of `devify`; not committed.

## First Install

```bash
git clone https://github.com/cloud2ai/devify-deploy.git
cd devify-deploy
cp env.sample .env
vim .env
./scripts/devify-deploy.sh install
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
./scripts/devify-deploy.sh upgrade
```

Deploy a specific `devify` version:

```bash
DEVIFY_REF=v1.0.3 ./scripts/devify-deploy.sh upgrade
```

Use a custom `devify` repository:

```bash
DEVIFY_REPO=https://github.com/cloud2ai/devify.git DEVIFY_REF=main \
  ./scripts/devify-deploy.sh upgrade
```

## Operations

```bash
./scripts/devify-deploy.sh status
./scripts/devify-deploy.sh logs
./scripts/devify-deploy.sh logs devify-api
./scripts/devify-deploy.sh restart
./scripts/devify-deploy.sh stop
./scripts/devify-deploy.sh start
./scripts/devify-deploy.sh config
```

Update `devify`, `devify-deploy/docker-compose.yml`, or `.env`, then rerun:

```bash
./scripts/devify-deploy.sh config
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
