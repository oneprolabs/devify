# Blue/green first go-live runbook (issue #17)

Concrete steps to switch aimychats production from the old single-container
deploy to single-node blue/green, and to prove the zero-downtime switch and
rollback afterwards. Run everything on the production host as the deploy user,
from `~/devify-deploy`.

Terms: **active color** = the color nginx currently routes to; **idle color** =
the other one. Only `devify-api` / `devify-ui` are colored.

---

## Topology (important — there is an edge proxy in front)

```
Internet
  → Nginx Proxy Manager (NPM): public HTTPS termination + free (Let's Encrypt)
                               certs + host/port mapping. UNCHANGED by this work.
    → devify-nginx (this stack, ports 10080/10443/19443, already mapped by NPM)
        → active color: devify-api-<color> / devify-ui-<color>
        → devify-home  (aimychats.com)
```

Consequences that shape this runbook:

- **The blue/green switch is internal, behind NPM.** `switch_traffic` does a
  `nginx -s reload` inside the *running* devify-nginx container — the container
  never stops, so NPM's upstream never drops. Steady-state deploys are
  **zero-downtime end-to-end (through NPM)**.
- **NPM needs no change.** This work preserves devify-nginx's ports
  (10080/10443/19443), its 443 server blocks, and the internal self-signed
  cert. Verified against the merged compose/nginx config.
- **The ONE exception is the first cutover** (§2): it *recreates* the
  devify-nginx container (single-file mount → conf.d directory mount), so NPM's
  upstream is down for ~1–2s and users get a brief **502 through NPM**. This is
  one-time; every deploy after it is a reload (no recreate, no 502).

---

## 0. Pre-flight (no traffic impact)

1. Merge both PRs: `cloud2ai/devify#18` and `cloud2ai/devify-deploy#1`.
2. On the host: `cd ~/devify-deploy && git pull --ff-only origin main`.
3. Record the current running version (your fallback) and back up MySQL:
   ```bash
   docker inspect -f '{{.Config.Image}}' devify-api        # note the tag
   # take your usual MySQL backup here
   ```
4. Validate the merged compose without changing anything (safe, no-op):
   ```bash
   ./scripts/devify-deploy.sh config      # expect: "Compose configuration is valid."
   ```
5. **Keep CI auto-deploy OFF during the transition.** In the devify repo's
   GitHub → Settings → Variables, leave `DEVIFY_AUTO_DEPLOY` unset (or `false`).
   A `v*` tag then still builds/pushes images but does **not** deploy to the
   host, so you control the first cutover manually (§1). Set it to `true` only
   after §3 proves the zero-downtime switch, to get hands-off releases.

> There is no fully side-effect-free rehearsal of the cutover on this single
> host (shared MySQL, one set of ports). The confidence for step 2 comes from:
> the `config` check above, the local zero-downtime switch tests (2000/2000
> non-error across a blue↔green flip on api+ui), and the fallback in §2.
> `--local` is **not** a dry run — it performs a real deploy from the local
> working tree/images (see §5); do not use it expecting a no-op.

## 1. First cutover (one-time ~1–2s 502 through NPM — maintenance window)

Do this in a low-traffic / maintenance window and, if possible, put NPM into
maintenance or expect a brief 502.

```bash
DEVIFY_REF=v<VERSION> ./scripts/devify-deploy.sh upgrade
```
Expected log sequence: single-flight lock acquired → first-install detected
(no color running) → migrate (no-op if already applied) → start **blue** →
**healthy** → devify-home up → **nginx recreated** onto the conf.d dir mount
(the one-time blip) → old single `devify-api`/`devify-ui` removed → serving
**blue**. Because blue is health-gated up *before* nginx is recreated, the blip
is just the nginx container restart.

> First install has **no previous color to fall back to**. If blue never becomes
> healthy the deploy aborts before touching nginx; your fallback is the recorded
> single-container image — re-run your previous deploy method. Keep those images
> on the host until §3 passes.

## 2. Verify

```bash
./scripts/devify-deploy.sh status                          # active=blue, healthy
curl -fsS -o /dev/null -w '%{http_code}\n' https://app.aimychats.com/swagger  # backend/color -> 200
curl -fsS https://aimychats.com/                           # devify-home still served
```
`https://app.aimychats.com/health` (no `/api`) only proves the NPM→nginx edge is
up (nginx returns a static "healthy" and never reaches a backend). Use a route
that actually proxies to the active color, e.g. **`/swagger` (200)** or
**`/api/v1/threadlines` (401, which still proves the backend was reached)** —
the container's own health path is `:8000/health` (bypasses nginx). Also
spot-check by hand: a UI page, the admin port, an `/attachments/...` URL, and
send a test mail through haraka.

## 3. Prove the switch + rollback (next deploy — the real payoff, zero-downtime)

The **second** deploy exercises the true zero-downtime path (blue→green via an
nginx *reload*, not a recreate — invisible to NPM). Trigger via a normal tag
release (CI runs `devify-deploy.sh upgrade`) or manually:

```bash
DEVIFY_REF=v<NEXT_VERSION> ./scripts/devify-deploy.sh upgrade
```
While it runs, from another shell hit a **backend** route (so the loop actually
exercises the color switch, not just the edge) and expect **zero** non-200s:
```bash
while :; do curl -fsS -o /dev/null https://app.aimychats.com/swagger \
  || echo "FAIL $(date)"; sleep 0.2; done
```
After it lands, drill rollback — must return to the previous version without a
rebuild, using the pinned `.rollback_version`:
```bash
./scripts/devify-deploy.sh status                          # active=green
./scripts/devify-deploy.sh rollback                        # -> blue, pinned version
./scripts/devify-deploy.sh status                          # active=blue
```
Roll forward again when satisfied.

## 4. Steady state

- Turn on hands-off releases: set `DEVIFY_AUTO_DEPLOY=true` in the devify repo's
  GitHub Variables.
- Releases: push a `v*` tag; CI builds/pushes images and runs
  `devify-deploy.sh upgrade` = a health-gated zero-downtime switch (reload).
- Rollback anytime: `./scripts/devify-deploy.sh rollback` (seconds, no rebuild).
- Runtime state on the host (git-ignored): `.active_color`, `.rollback_version`,
  `data/nginx/conf.d/active-upstream.conf`.

## 5. `--local` (host-side deploy without git/registry)

`--local` runs install/upgrade against the current `~/devify-deploy/.devify`
checkout and the images already present on the host, skipping every git sync
and image pull. Use it to deploy a locally-built hotfix or when the registry is
unreachable:

```bash
DEVIFY_REF=v<VERSION> ./scripts/devify-deploy.sh upgrade --local
```
It is a **real deploy** (migrate → start idle color → health-gate → switch →
retire), not a no-op — the only difference from a normal upgrade is where the
code/images come from. Set `DEVIFY_REF`/`DEVIFY_IMAGE_TAG` to an image tag that
is actually present on the host.

## Notes / limits

- Single shared MySQL: keep migrations expand/contract (backward-compatible for
  the observe window) — see the compose overlay comments and playbook §5.3.
- Single-node only. `devify-home` and stateful services are not colored.
- The one-time first-cutover blip (§1, a ~1–2s 502 through NPM) is the only
  non-zero-downtime moment; every subsequent deploy is a reload.
