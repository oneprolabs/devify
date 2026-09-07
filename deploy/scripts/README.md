# Scripts

## Deployment

Use `devify-deploy.sh` for install, upgrade, and daily operations:

```bash
./scripts/devify-deploy.sh install
./scripts/devify-deploy.sh upgrade
./scripts/devify-deploy.sh status
./scripts/devify-deploy.sh logs
./scripts/devify-deploy.sh restart
./scripts/devify-deploy.sh config
```

Environment overrides:

```bash
DEVIFY_REF=v1.0.3 ./scripts/devify-deploy.sh upgrade
DEVIFY_REPO=https://github.com/cloud2ai/devify.git ./scripts/devify-deploy.sh install
COMPOSE_PROJECT_NAME=devify ./scripts/devify-deploy.sh status
```

## Nginx Certificates

Generate self-signed certificates for testing:

```bash
./scripts/generate-self-signed-certs.sh
```

Generate Let's Encrypt certificates with Docker certbot:

```bash
./scripts/generate-certs-docker.sh
```

Generate Let's Encrypt certificates with system certbot:

```bash
./scripts/generate-letsencrypt-certs.sh
```

Certificate files are written under:

```text
data/certs/nginx/
```

Haraka certificate management is maintained by `devify`, not this repository.
After running install or upgrade, use:

```bash
DEVIFY_RUNTIME_ROOT="$(pwd)" .devify/scripts/manage-haraka-certs.sh status
```
