# Inbound Email (Haraka)

Devify bundles [Haraka](https://haraka.github.io/) so users can receive mail at
auto-assigned addresses:

```text
{username}@{AUTO_ASSIGN_EMAIL_DOMAIN}
```

Haraka listens on SMTP port 25, writes raw messages under
`data/haraka/emails`, and the worker/scheduler picks them up into the normal
email workflow.

## Configure the mail domain

For production, configure the mail domain in **three** places:

1. `.env`: `AUTO_ASSIGN_EMAIL_DOMAIN=example.com`
2. `docker/haraka/config/host_list.prod`: add `example.com`
3. DNS: an **MX** record for `example.com` pointing to the Haraka host.

## Recommended DNS records

```text
example.com.        MX   10 mail.example.com.
mail.example.com.   A    <server-public-ip>
example.com.        TXT  "v=spf1 mx -all"
_dmarc.example.com. TXT  "v=DMARC1; p=quarantine; rua=mailto:admin@example.com"
```

Port 25 must be reachable from the public internet.

## STARTTLS

```bash
HARAKA_DOMAIN=mail.example.com HARAKA_CERT_EMAIL=admin@example.com \
  ./scripts/manage-haraka-certs.sh apply
```

See [`docker/haraka/README.md`](https://github.com/cloud2ai/devify/blob/main/docker/haraka/README.md) for details.
