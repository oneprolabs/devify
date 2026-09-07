#!/usr/bin/env bash
# Shared blue/green helpers for devify-deploy (issue #17), ported from the
# newshub deployment. Not run directly — sourced by devify-deploy.sh after it
# has set DEPLOY_PATH and defined log()/die() and the compose() wrapper.
#
# Runtime state lives under the deploy root (git-ignored):
#   ${DEPLOY_PATH}/.active_color            which color serves traffic
#   ${DEPLOY_PATH}/data/nginx/conf.d/active-upstream.conf   nginx switch file
#
# Only devify-api / devify-ui are colored; everything else is single.

GRACE_HEALTH_RETRIES="${GRACE_HEALTH_RETRIES:-40}"
GRACE_HEALTH_INTERVAL="${GRACE_HEALTH_INTERVAL:-3}"
POST_SWITCH_OBSERVE_SECONDS="${POST_SWITCH_OBSERVE_SECONDS:-5}"

UPSTREAM_CONF="${DEPLOY_PATH}/data/nginx/conf.d/active-upstream.conf"

current_color() {
    cat "${DEPLOY_PATH}/.active_color" 2>/dev/null || echo "blue"
}

other_color() {
    [ "$1" = "green" ] && echo "blue" || echo "green"
}

# Poll a color's devify-api /health endpoint. Returns 0 once healthy, 1 on
# timeout — never raises; callers decide what to do on failure.
wait_for_healthy() {
    local container="$1"
    local i
    for i in $(seq 1 "${GRACE_HEALTH_RETRIES}"); do
        if docker exec "${container}" \
            curl -fs http://127.0.0.1:8000/health >/dev/null 2>&1; then
            return 0
        fi
        sleep "${GRACE_HEALTH_INTERVAL}"
    done
    return 1
}

# Flip nginx's active-upstream.conf from color $1 to color $2, validate, reload.
# Atomic replace (sed writes a temp file then mv) so the directory-mounted
# conf is seen inside the container. Does not touch .active_color or start/stop
# containers — callers own that.
switch_traffic() {
    local from="$1" to="$2"
    log "Switching nginx upstream: ${from} -> ${to}"
    [ -f "${UPSTREAM_CONF}" ] || die "Missing ${UPSTREAM_CONF}"
    sed \
        -e "s/devify-api-${from}/devify-api-${to}/g" \
        -e "s/devify-ui-${from}/devify-ui-${to}/g" \
        "${UPSTREAM_CONF}" > "${UPSTREAM_CONF}.tmp"
    mv "${UPSTREAM_CONF}.tmp" "${UPSTREAM_CONF}"
    compose exec -T nginx nginx -t
    compose exec -T nginx nginx -s reload
    log "Traffic switched to ${to}"
}
