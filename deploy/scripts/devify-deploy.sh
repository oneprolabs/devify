#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Two levels up, not one: this script lives at deploy/scripts/ inside the
# merged repository, so the deploy root is the repository root itself.
DEPLOY_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
if [ ! -f "${DEPLOY_ROOT}/deploy/scripts/devify-deploy.sh" ]; then
    echo "Refusing to run: derived DEPLOY_ROOT=${DEPLOY_ROOT}, which is not a" >&2
    echo "  devify checkout (expected deploy/scripts/devify-deploy.sh under it)." >&2
    echo "  Likely cause: this script was moved or symlinked out of deploy/scripts/." >&2
    echo "  Try: run it in place, as <checkout>/deploy/scripts/devify-deploy.sh" >&2
    exit 1
fi
# Captured at file scope, where "$@" is still the script's own arguments,
# so self_update can hand them to the replacement process.
DEVIFY_ARGV=("$@")

CORE_DIR="${DEPLOY_ROOT}/.devify"
ENV_FILE="${DEPLOY_ROOT}/.env"
# The blue/green sample, not the repository-root one: that is the
# standalone installer's and carries no MYSQL_* or STRIPE_* keys.
ENV_SAMPLE="${DEPLOY_ROOT}/deploy/env.sample"

DEVIFY_REPO="${DEVIFY_REPO:-https://github.com/oneprolabs/devify.git}"
DEVIFY_REF="${DEVIFY_REF:-main}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-devify}"
# --local: rehearse against the current .devify working tree + already-present
# images, skipping every git sync and image pull. Lets you dry-run the switch
# on the host without touching git or the registry. Set by the --local flag.
LOCAL_MODE="${LOCAL_MODE:-0}"

log() { echo -e "\033[1;36m[devify-deploy]\033[0m $*"; }
die() { echo -e "\033[1;31m[devify-deploy] ERROR:\033[0m $*" >&2; exit 1; }

DEVIFY_IMAGE_REPO="registry.cn-beijing.aliyuncs.com/oneprolabs/devify"
DEVIFY_UI_IMAGE_REPO="registry.cn-beijing.aliyuncs.com/oneprolabs/devify-ui"
DEVIFY_HOME_IMAGE_REPO="registry.cn-beijing.aliyuncs.com/oneprolabs/devify-home"

# The deploy host runs images, not source. It needs the compose files, the
# nginx/haraka/mysql config those files bind-mount, and this deploy tree —
# not devify/, ui/ or home/, which exist only to build the images. Cone-mode
# sparse checkout always keeps the root files, so the compose YAMLs come
# along; these are the directories on top of them.
CORE_SPARSE_DIRS="docker deploy"

# Every path the deploy reads out of CORE_DIR: the files this script opens
# and the bind-mount sources in the three compose files. Checked after each
# sync so a wrong CORE_SPARSE_DIRS fails here, naming the file, instead of
# somewhere later in a container that will not start.
CORE_REQUIRED_PATHS="
docker-compose.yml
docker-compose.bluegreen.yml
deploy/docker-compose.yml
deploy/docker/nginx/aimychats.com.conf
docker/nginx/default.conf
docker/nginx/bluegreen/default.conf
docker/nginx/bluegreen/active-upstream.conf.default
docker/haraka/config/host_list.prod
docker/haraka/config/plugins.prod
docker/haraka/config/redis.ini
docker/haraka/config/tls.ini
docker/haraka/plugins/raw_email_saver.js
docker/mysql/etc/my.cnf
docker/mysql/initdb.d
"

# Single-flight lock so two mutating runs (a CI retry overlapping a manual run,
# two operators) can't race on .active_color, the colored containers, or the
# nginx switch. `set -o noclobber` makes creation atomic; after MAX_WAIT we take
# over a presumed-stale lock rather than block a deploy forever.
acquire_deploy_lock() {
    local lock_file="/tmp/devify-deploy.lock"
    local max_wait=300 waited=0
    while ! (set -o noclobber; echo "$$ $(date)" > "${lock_file}") 2>/dev/null; do
        if [ "${waited}" -ge "${max_wait}" ]; then
            log "Taking over stale lock ${lock_file} after ${waited}s"
            echo "$$ $(date)" > "${lock_file}"
            break
        fi
        log "Another devify-deploy run holds the lock, waiting... (${waited}s)"
        sleep 5
        waited=$((waited + 5))
    done
    trap 'rm -f "'"${lock_file}"'"' EXIT
}

# Map the git ref to the registry image tag. CI publishes semver tags without
# the leading "v" (docker/metadata-action {{version}}), so v1.1.26 -> 1.1.26;
# non-version refs (e.g. main) fall back to the "latest" image.
image_tag_for_ref() {
    if [[ "${DEVIFY_REF}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "${DEVIFY_REF#v}"
    else
        echo "latest"
    fi
}

# Compose wrapper. Layers three files (base app stack + deploy overlay +
# blue/green overlay); the blue/green file is LAST so its !override/!reset on
# nginx and the colored services win. See docker-compose.bluegreen.yml.
compose() {
    export DEVIFY_DEPLOY_ROOT="${DEPLOY_ROOT}"
    export DEVIFY_RUNTIME_ROOT="${DEPLOY_ROOT}"
    export DEVIFY_ENV_FILE="${ENV_FILE}"
    export DEVIFY_NGINX_CERTS_DIR="${DEPLOY_ROOT}/data/certs/nginx"
    # Respect a caller-preset tag (rollback pins the retired version); default
    # to the tag derived from the deploy ref otherwise.
    export DEVIFY_IMAGE_TAG="${DEVIFY_IMAGE_TAG:-$(image_tag_for_ref)}"

    docker compose \
        --env-file "${ENV_FILE}" \
        --project-directory "${CORE_DIR}" \
        -p "${COMPOSE_PROJECT_NAME}" \
        -f "${CORE_DIR}/docker-compose.yml" \
        -f "${CORE_DIR}/deploy/docker-compose.yml" \
        -f "${CORE_DIR}/docker-compose.bluegreen.yml" \
        "$@"
}

# Blue/green helpers (current_color/other_color/wait_for_healthy/switch_traffic)
DEPLOY_PATH="${DEPLOY_ROOT}"
# shellcheck source=./lib/deploy-common.sh
source "${SCRIPT_DIR}/lib/deploy-common.sh"

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Missing required command: $1" >&2
        exit 1
    fi
}

check_requirements() {
    require_command git
    require_command docker
    docker compose version >/dev/null
}

ensure_env() {
    if [ ! -f "${ENV_FILE}" ]; then
        if [ ! -f "${ENV_SAMPLE}" ]; then
            die "Cannot seed ${ENV_FILE}: ${ENV_SAMPLE} is missing.
  Likely cause: ${DEPLOY_ROOT} is an old devify-deploy checkout, where the
    sample sat at the root, or the clone of the merged repository is
    incomplete.
  Try: clone https://github.com/oneprolabs/devify.git into ${DEPLOY_ROOT},
    keeping .env, data/, .active_color and .rollback_version, then rerun."
        fi
        cp "${ENV_SAMPLE}" "${ENV_FILE}"
        echo "Created ${ENV_FILE} from env.sample."
        echo "Edit ${ENV_FILE} before production use, then rerun this command."
    fi
}

sync_devify() {
    if [ "${LOCAL_MODE}" = "1" ]; then
        [ -f "${CORE_DIR}/docker-compose.yml" ] || die "Local mode needs an existing ${CORE_DIR} checkout; run a normal deploy once first, or clone devify there."
        log "Local mode: using existing ${CORE_DIR} working tree (skipping git sync)"
        return
    fi
    if [ ! -d "${CORE_DIR}/.git" ]; then
        rm -rf "${CORE_DIR}"
        # blob:none fetches file contents on demand; --sparse starts the
        # working tree at the root files only.
        git clone --filter=blob:none --sparse \
            "${DEVIFY_REPO}" "${CORE_DIR}"
    else
        git -C "${CORE_DIR}" remote set-url origin "${DEVIFY_REPO}"
    fi

    # Idempotent: narrows a full checkout made before this existed, and
    # re-asserts the set afterwards.
    #
    # `init --cone` before `set`, not `set --cone`: git only learned the
    # --cone flag on `set` in 2.36, and production runs 2.34, where it is
    # silently taken as a literal path pattern. That lands in non-cone
    # mode, where a bare "docker" matches any directory of that name at any
    # depth — ui/docker and home/docker survive — while the root files
    # match nothing and get removed, taking docker-compose.yml with them.
    git -C "${CORE_DIR}" sparse-checkout init --cone
    # shellcheck disable=SC2086
    git -C "${CORE_DIR}" sparse-checkout set ${CORE_SPARSE_DIRS}
    # Assert the mode rather than trust it. Without this, a git that took
    # --cone as a pattern fails later in verify_core_files, which blames
    # CORE_SPARSE_DIRS for a checkout that is simply in the wrong mode.
    if [ "$(git -C "${CORE_DIR}" config core.sparseCheckoutCone)" != "true" ]; then
        die "Sparse checkout of ${CORE_DIR} is not in cone mode.
  Likely cause: this git ($(git --version)) did not accept \`sparse-checkout
    init --cone\`. Outside cone mode the entries are gitignore patterns, so
    \"docker\" matches any directory of that name at any depth and the root
    files match nothing at all — docker-compose.yml would be deleted.
  Try: upgrade git to 2.25 or newer, or run
    git -C ${CORE_DIR} sparse-checkout disable
    to fall back to a full checkout."
    fi

    git -C "${CORE_DIR}" fetch --tags --force origin
    if git -C "${CORE_DIR}" rev-parse --verify --quiet "origin/${DEVIFY_REF}" >/dev/null; then
        git -C "${CORE_DIR}" checkout --force -B "${DEVIFY_REF}" "origin/${DEVIFY_REF}"
    else
        git -C "${CORE_DIR}" checkout --force "${DEVIFY_REF}"
    fi

    verify_core_files
}

# Guard the sparse set: a directory dropped from CORE_SPARSE_DIRS, or a new
# bind mount added to a compose file without listing it here, would
# otherwise surface as a container refusing to start on a bind-mount error.
verify_core_files() {
    local path missing=""
    for path in ${CORE_REQUIRED_PATHS}; do
        [ -e "${CORE_DIR}/${path}" ] || missing="${missing}    ${path}
"
    done
    [ -z "${missing}" ] && return 0
    die "The deploy checkout is missing files it needs:
${missing}  Likely cause: CORE_SPARSE_DIRS (\"${CORE_SPARSE_DIRS}\") no longer covers
    every path the compose files mount, or a mount was added without
    listing it in CORE_REQUIRED_PATHS.
  Try: add the directory to CORE_SPARSE_DIRS in this script, or run
    git -C ${CORE_DIR} sparse-checkout disable
    for a full checkout while you sort it out."
}

prepare_directories() {
    mkdir -p \
        "${DEPLOY_ROOT}/cache" \
        "${DEPLOY_ROOT}/data/certs/haraka" \
        "${DEPLOY_ROOT}/data/certs/nginx" \
        "${DEPLOY_ROOT}/data/django/staticfiles" \
        "${DEPLOY_ROOT}/data/email_attachments" \
        "${DEPLOY_ROOT}/data/haraka/debug" \
        "${DEPLOY_ROOT}/data/haraka/email_attachments" \
        "${DEPLOY_ROOT}/data/haraka/emails" \
        "${DEPLOY_ROOT}/data/haraka/logs" \
        "${DEPLOY_ROOT}/data/logs/api" \
        "${DEPLOY_ROOT}/data/logs/mysql" \
        "${DEPLOY_ROOT}/data/logs/nginx" \
        "${DEPLOY_ROOT}/data/logs/scheduler" \
        "${DEPLOY_ROOT}/data/logs/worker" \
        "${DEPLOY_ROOT}/data/mysql/data" \
        "${DEPLOY_ROOT}/data/nginx/conf.d" \
        "${DEPLOY_ROOT}/data/redis"
}

# Populate the nginx conf.d directory that the blue/green nginx service mounts.
# The directory (not single files) is mounted so switch_traffic's atomic
# rewrite of active-upstream.conf is visible inside the container.
sync_nginx_confd() {
    local confd="${DEPLOY_ROOT}/data/nginx/conf.d"
    mkdir -p "${confd}"
    # Blue/green app config, versioned with the synced devify repo.
    cp "${CORE_DIR}/docker/nginx/bluegreen/default.conf" \
        "${confd}/default.conf"
    # aimychats.com (devify-home) vhost, from the pinned tag alongside
    # the app config above, so both move together on a rollback.
    cp "${CORE_DIR}/deploy/docker/nginx/aimychats.com.conf" \
        "${confd}/aimychats.com.conf"
    # Runtime switch file: seed from template only if absent so an existing
    # active color is preserved across upgrades.
    if [ ! -f "${confd}/active-upstream.conf" ]; then
        cp "${CORE_DIR}/docker/nginx/bluegreen/active-upstream.conf.default" \
            "${confd}/active-upstream.conf"
    fi
}

ensure_nginx_certs() {
    if [ ! -f "${DEPLOY_ROOT}/data/certs/nginx/aimychats.com.crt" ] ||
       [ ! -f "${DEPLOY_ROOT}/data/certs/nginx/app.aimychats.com.crt" ]; then
        if [ -f "${DEPLOY_ROOT}/docker/nginx/certs/aimychats.com.crt" ] &&
           [ -f "${DEPLOY_ROOT}/docker/nginx/certs/app.aimychats.com.crt" ]; then
            cp "${DEPLOY_ROOT}"/docker/nginx/certs/* "${DEPLOY_ROOT}/data/certs/nginx/"
            echo "Migrated nginx certificates from docker/nginx/certs to data/certs/nginx."
            return
        fi
        # Generating is right on a first install and wrong on a running
        # deployment, where it means real certificates went missing. Say so
        # rather than quietly serving a self-signed pair: this host sits
        # behind a reverse proxy that terminates TLS to the outside, so
        # nothing user-visible changes and nobody would notice until a
        # client checked the chain. .active_color exists only after a
        # deploy has run, which is what separates the two cases.
        if [ -f "${DEPLOY_ROOT}/.active_color" ]; then
            log "WARNING: no nginx certificates in ${DEPLOY_ROOT}/data/certs/nginx,
  generating a self-signed pair on a deployment that has run before.
  Likely cause: the certificates were deleted, the data directory was
    replaced, or a restore missed data/certs/nginx.
  Effect: nginx serves a self-signed certificate from now on. The reverse
    proxy in front terminates TLS for external clients, so this is
    invisible from outside until something validates the chain.
  Try: restore the real certificate and key into
    ${DEPLOY_ROOT}/data/certs/nginx and rerun, before this deploy is
    treated as healthy."
        fi
        "${SCRIPT_DIR}/generate-self-signed-certs.sh"
    fi
}

ensure_stack_files() {
    if [ ! -f "${CORE_DIR}/docker-compose.yml" ]; then
        sync_devify
        prepare_directories
    fi
}

# Blue/green deploy: bring up the idle color, health-gate it, flip nginx, then
# retire the old color. Shared by install and upgrade. Only devify-api/devify-ui
# are colored; mysql/redis/haraka/devify-home/worker/scheduler stay single.
# Pin the version of the color we are about to retire so `rollback` can restore
# exactly that image instead of a moving :latest. Read from the running
# container so no Dockerfile label is required.
record_rollback_version() {
    local color="$1" image tag
    image="$(docker inspect -f '{{.Config.Image}}' \
        "devify-api-${color}" 2>/dev/null || true)"
    tag="${image##*:}"
    if [ -n "${tag}" ] && [ "${tag}" != "${image}" ]; then
        echo "${tag}" > "${DEPLOY_ROOT}/.rollback_version"
        log "Pinned rollback version ${tag} (from devify-api-${color})"
    fi
}

# Prune old image tags, keeping the two newest versions (current + one rollback
# target) plus :latest. The `|| true` guards matter under `set -euo pipefail`:
# grep exits 1 when a repo only has :latest, which would otherwise abort.
prune_old_images() {
    local repo
    for repo in "${DEVIFY_IMAGE_REPO}" "${DEVIFY_UI_IMAGE_REPO}" \
                "${DEVIFY_HOME_IMAGE_REPO}"; do
        docker images "${repo}" --format '{{.Tag}}' \
            | grep -vE '^(latest|<none>)$' \
            | sort -rV | tail -n +3 \
            | while read -r t; do
                docker rmi "${repo}:${t}" >/dev/null 2>&1 || true
            done || true
    done
}

bluegreen_deploy() {
    prepare_directories
    ensure_nginx_certs
    sync_nginx_confd
    # Local mode rehearses against already-present images and skips the pull.
    if [ "${LOCAL_MODE}" != "1" ]; then
        compose pull
    fi

    # Foundational stateful services first (idempotent no-op if already up).
    compose up -d mysql redis haraka

    local current next first_install
    current="$(current_color)"
    if [ "$(docker inspect -f '{{.State.Running}}' \
            "devify-api-${current}" 2>/dev/null)" != "true" ]; then
        # No color is live yet (first blue/green deploy) — deploy the current
        # color directly; there is nothing to switch from or retire.
        next="${current}"
        first_install=1
        log "devify-api-${current} not running — first blue/green deploy to ${next}"
    else
        next="$(other_color "${current}")"
        first_install=0
        log "Active color: ${current}; deploying idle color: ${next}"
    fi

    # Explicitly pull the deploy color: the bare `compose pull` above skips
    # profiled services, and a moving :latest already present locally is not
    # re-pulled otherwise, so a deploy could silently run a stale image.
    if [ "${LOCAL_MODE}" != "1" ]; then
        compose --profile "${next}" pull \
            "devify-api-${next}" "devify-ui-${next}"
    fi

    # Run migrations against the deploy color while it serves no traffic. Single
    # shared mysql, so migrations must stay backward-compatible for the overlap.
    log "Running migrations against devify-api-${next}..."
    compose run --rm --no-deps "devify-api-${next}" \
        python manage.py migrate --noinput

    log "Starting devify-api-${next} / devify-ui-${next}..."
    compose --profile "${next}" up -d \
        "devify-api-${next}" "devify-ui-${next}"

    log "Waiting for devify-api-${next} to report healthy..."
    if ! wait_for_healthy "devify-api-${next}"; then
        compose --profile "${next}" stop \
            "devify-api-${next}" "devify-ui-${next}"
        die "devify-api-${next} never became healthy; deploy aborted, ${current} stays live"
    fi
    log "devify-api-${next} is healthy"

    # devify-home + nginx must be up before switching traffic.
    compose up -d devify-home
    compose up -d nginx

    if [ "${first_install}" = "1" ]; then
        # active-upstream.conf template already points at blue (== next here).
        echo "${next}" > "${DEPLOY_ROOT}/.active_color"
        log "First deploy: nginx serving devify-api-${next} directly"
    else
        switch_traffic "${current}" "${next}"
        echo "${next}" > "${DEPLOY_ROOT}/.active_color"
        # Pin the outgoing color's version for rollback before it is removed.
        record_rollback_version "${current}"
        log "Observing ${POST_SWITCH_OBSERVE_SECONDS}s before retiring ${current}..."
        sleep "${POST_SWITCH_OBSERVE_SECONDS}"
        log "Retiring devify-api-${current} / devify-ui-${current}"
        compose --profile "${current}" stop \
            "devify-api-${current}" "devify-ui-${current}" || true
        compose --profile "${current}" rm -f \
            "devify-api-${current}" "devify-ui-${current}" || true
        # Reclaim disk: keep the two newest versions (+latest); drop the rest.
        prune_old_images
    fi

    # One-time cleanup of legacy pre-blue/green single containers, if present.
    docker rm -f devify-api devify-ui >/dev/null 2>&1 || true

    # Non-colored app services: ordinary rolling restart. Celery graceful-drain
    # settings mean in-flight tasks finish before the old process exits.
    compose up -d devify-worker devify-scheduler
    compose ps
}

install_stack() {
    acquire_deploy_lock
    check_requirements
    ensure_env
    sync_devify
    bluegreen_deploy
}

# Refresh this script from main, then hand over to the version that was
# pulled. Bash defines every function while reading down to the `main` call
# at the bottom of the file, so a running deploy keeps the functions it
# parsed at startup: without the exec, a change to this script is skipped by
# the release that ships it and first runs on the one after. That is not
# only surprising — it means a release can run an old orchestrator against
# the new tag's compose files, with nothing to say so.
#
# Called before acquire_deploy_lock on purpose. exec does not fire EXIT
# traps, so exec-ing while holding the lock would leave it behind for the
# replacement process to wait out.
self_update() {
    [ "${LOCAL_MODE}" = "1" ] && return 0
    [ -n "${DEVIFY_SELF_UPDATED:-}" ] && return 0

    local before after
    before="$(git -C "${DEPLOY_ROOT}" rev-parse HEAD 2>/dev/null || true)"
    if ! git -C "${DEPLOY_ROOT}" pull --ff-only origin main; then
        log "WARNING: could not refresh the orchestrator from main.
  Likely cause: the deploy host cannot reach the git remote right now, or
    ${DEPLOY_ROOT} has local commits that are not a fast-forward.
  Effect: this deploy runs the orchestrator already on disk, which may be
    older than the tag being deployed.
  Try: git -C ${DEPLOY_ROOT} pull --ff-only origin main, by hand."
        return 0
    fi
    after="$(git -C "${DEPLOY_ROOT}" rev-parse HEAD 2>/dev/null || true)"
    [ "${before}" = "${after}" ] && return 0

    log "Orchestrator updated ${before:0:7} -> ${after:0:7}; restarting with it"
    export DEVIFY_SELF_UPDATED=1
    exec "${DEPLOY_ROOT}/deploy/scripts/devify-deploy.sh" \
        ${DEVIFY_ARGV[@]+"${DEVIFY_ARGV[@]}"}
}

upgrade_stack() {
    check_requirements
    self_update
    acquire_deploy_lock
    ensure_env
    sync_devify
    bluegreen_deploy
}

rollback_stack() {
    acquire_deploy_lock
    check_requirements
    ensure_env
    ensure_stack_files
    sync_nginx_confd
    local active target rbfile rbtag
    active="$(current_color)"
    target="$(other_color "${active}")"

    # Pin the previously-retired version so rollback restores the last good
    # image, not a moving :latest (which would just redeploy the bad version).
    rbfile="${DEPLOY_ROOT}/.rollback_version"
    [ -f "${rbfile}" ] || die "No .rollback_version recorded; cannot pin the previous version. Redeploy it instead: DEVIFY_REF=<tag> $0 upgrade"
    rbtag="$(cat "${rbfile}")"
    [ -n "${rbtag}" ] || die ".rollback_version is empty; redeploy instead: DEVIFY_REF=<tag> $0 upgrade"
    if ! docker image inspect "${DEVIFY_IMAGE_REPO}:${rbtag}" >/dev/null 2>&1; then
        die "Image ${DEVIFY_IMAGE_REPO}:${rbtag} is not present locally; cannot roll back to it. Redeploy instead: DEVIFY_REF=v${rbtag} $0 upgrade"
    fi
    export DEVIFY_IMAGE_TAG="${rbtag}"
    log "Active color is ${active}; rolling back to ${target} pinned at version ${rbtag}"
    log "(no pull/build/migrate — uses the locally retained ${rbtag} image)"

    if ! compose --profile "${target}" up -d \
        "devify-api-${target}" "devify-ui-${target}"; then
        die "Could not start ${target}. Redeploy that version instead: DEVIFY_REF=<tag> $0 upgrade"
    fi
    log "Waiting for devify-api-${target} to report healthy..."
    if ! wait_for_healthy "devify-api-${target}"; then
        compose --profile "${target}" stop \
            "devify-api-${target}" "devify-ui-${target}"
        die "devify-api-${target} never became healthy; rollback aborted, ${active} stays live"
    fi
    switch_traffic "${active}" "${target}"
    echo "${target}" > "${DEPLOY_ROOT}/.active_color"

    # The colored services are only half the deploy. Without this the API
    # returns to ${rbtag} and the workers keep running the version being
    # rolled away from, against the same database. DEVIFY_IMAGE_TAG is
    # already exported above, so this recreates them at ${rbtag} too.
    log "Rolling devify-worker / devify-scheduler back to ${rbtag}..."
    compose up -d devify-worker devify-scheduler

    log "Rolled back: active color is now ${target}. ${active} left running for inspection."
}

status_stack() {
    check_requirements
    ensure_env
    ensure_stack_files
    local color; color="$(current_color)"
    log "Active color: ${color}"
    compose ps "devify-api-${color}" "devify-ui-${color}" \
        devify-worker devify-scheduler devify-home nginx 2>/dev/null || true
    if docker exec "devify-api-${color}" \
        curl -fs http://127.0.0.1:8000/health >/dev/null 2>&1; then
        log "devify-api-${color} (active): healthy"
    else
        log "devify-api-${color} (active): NOT healthy"
    fi
}

# Refresh ONLY the devify-home (homepage) service, keeping it compose-managed.
# The devify-home repo's release pipeline calls this instead of a standalone
# `docker run`, so the homepage is never created as an unmanaged container that
# collides with the compose stack on the "devify-home" name (see the deploy
# name-conflict issue). nginx proxies devify-home via a variable proxy_pass, so
# it re-resolves the recreated container at request time — no nginx reload.
update_home() {
    acquire_deploy_lock
    check_requirements
    ensure_env
    ensure_stack_files
    if [ "${LOCAL_MODE}" != "1" ]; then
        log "Pulling devify-home image..."
        compose pull devify-home
    fi
    log "Recreating devify-home under compose management..."
    compose up -d devify-home
    compose ps devify-home
    log "devify-home refreshed."
}

# The blue/green overlay keeps the base API and UI services on the `single`
# profile. Resolve their logical names to whichever color currently serves
# traffic so operational commands do not accidentally target the parked
# single-service definitions.
runtime_service_name() {
    local service="$1" active="$2"
    case "${service}" in
        devify-api)
            echo "devify-api-${active}"
            ;;
        devify-ui)
            echo "devify-ui-${active}"
            ;;
        *)
            echo "${service}"
            ;;
    esac
}

restart_stack() {
    acquire_deploy_lock
    check_requirements
    ensure_env
    ensure_stack_files

    local active service
    local services=()
    active="$(current_color)"
    for service in "$@"; do
        services+=("$(runtime_service_name "${service}" "${active}")")
    done

    if [ "${#services[@]}" -eq 0 ]; then
        compose --profile "${active}" restart
    else
        compose --profile "${active}" restart "${services[@]}"
    fi
}

recreate_stack() {
    acquire_deploy_lock
    check_requirements
    ensure_env
    ensure_stack_files

    local active service
    local services=()
    active="$(current_color)"
    for service in "$@"; do
        services+=("$(runtime_service_name "${service}" "${active}")")
    done

    if [ "${#services[@]}" -eq 0 ]; then
        compose --profile "${active}" up -d --force-recreate
    else
        compose --profile "${active}" up -d --force-recreate "${services[@]}"
    fi
}

show_usage() {
    cat <<'USAGE'
Usage: ./deploy/scripts/devify-deploy.sh <command> [--local] [args]

Commands:
  install      Install the full stack (blue/green) with devify-home
  upgrade      Blue/green deploy: health-gate the idle color, switch, retire old
  update-home  Pull and recreate only the devify-home (homepage) service
  rollback     Flip traffic back to the other color (no pull/build/migrate)
  status       Show the active color, its health, and running services
  pull         Pull images for the deployment stack
  start        Start the deployment stack
  stop         Stop the deployment stack
  restart      Restart the deployment stack
  recreate     Force recreate the deployment stack without removing volumes
  logs         Show logs; extra args are passed to docker compose logs
  manage       Run a Django management command in the devify-api container
               e.g. ./deploy/scripts/devify-deploy.sh manage migrate
               e.g. ./deploy/scripts/devify-deploy.sh manage verify_webhook
  config       Sync devify files and validate the composed deployment config

Flags:
  --local      Rehearse install/upgrade against the current .devify working tree
               and already-present images, skipping all git syncs and image
               pulls. Use it to dry-run the blue/green switch on the host before
               a real deploy (set DEVIFY_REF/DEVIFY_IMAGE_TAG to a locally
               present image tag).

Environment:
  DEVIFY_REPO             Git repository to sync; default https://github.com/oneprolabs/devify.git
  DEVIFY_REF              Branch, tag, or commit to deploy; default main
  DEVIFY_IMAGE_TAG        Override the image tag (else derived from DEVIFY_REF)
  COMPOSE_PROJECT_NAME    Compose project name; default devify
USAGE
}

main() {
    command="${1:-}"
    if [ -n "${command}" ]; then
        shift
    fi

    # Pull the global --local flag out of the remaining args.
    local rest=()
    local arg
    for arg in "$@"; do
        if [ "${arg}" = "--local" ]; then
            LOCAL_MODE=1
        else
            rest+=("${arg}")
        fi
    done
    set -- "${rest[@]+"${rest[@]}"}"
    [ "${LOCAL_MODE}" = "1" ] && log "Local mode: no git sync, no image pull"

    case "${command}" in
        install)
            install_stack
            ;;
        upgrade)
            upgrade_stack
            ;;
        update-home)
            update_home
            ;;
        pull)
            check_requirements
            ensure_env
            sync_devify
            prepare_directories
            compose pull "$@"
            ;;
        start)
            check_requirements
            ensure_env
            ensure_stack_files
            compose up -d "$@"
            ;;
        stop)
            check_requirements
            ensure_env
            ensure_stack_files
            compose stop "$@"
            ;;
        restart)
            restart_stack "$@"
            ;;
        recreate)
            recreate_stack "$@"
            ;;
        status)
            status_stack
            ;;
        rollback)
            rollback_stack
            ;;
        logs)
            check_requirements
            ensure_env
            ensure_stack_files
            compose logs "$@"
            ;;
        manage)
            check_requirements
            ensure_env
            ensure_stack_files
            compose exec devify-api python manage.py "$@"
            ;;
        config)
            check_requirements
            ensure_env
            sync_devify
            prepare_directories
            compose config >/dev/null
            echo "Compose configuration is valid."
            ;;
        *)
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
