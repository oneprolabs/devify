#!/usr/bin/env bash
# Platform smoke tests for install.sh (no Docker/root needed).
# Runs on Linux, macOS, and Windows (Git Bash) and exercises the
# platform-specific branches: detect_os, detect_arch, check_memory,
# port_in_use, configure (domain/timezone), require_root and the
# Git Bash -> Windows path conversion used by run_compose.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

FAILURES=0
ok()   { printf 'ok:   %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1"; FAILURES=$((FAILURES + 1)); }
section() { printf '\n=== %s ===\n' "$1"; }

section "Syntax"
if bash -n install.sh; then ok "bash -n install.sh"; else fail "bash -n install.sh"; fi

section "CLI --help"
if bash install.sh --help 2>&1 | grep -q "Supported platforms"; then
  ok "--help lists supported platforms"
else
  fail "--help lists supported platforms"
fi

section "Platform detection"
# shellcheck disable=SC1091
source ./install.sh || { echo "cannot source install.sh"; exit 1; }
# install.sh sets -Eeuo pipefail; restore safer options for the test harness.
set +eE
set +u
set +o pipefail

uname_s="$(uname -s)"
case "${uname_s}" in
  Darwin)               EXPECT_PLATFORM="macos" ;;
  Linux)                EXPECT_PLATFORM="linux" ;;
  MINGW*|MSYS*|CYGWIN*) EXPECT_PLATFORM="windows" ;;
  *)                    EXPECT_PLATFORM="unknown" ;;
esac
if [[ "${PLATFORM}" == "${EXPECT_PLATFORM}" ]]; then
  ok "PLATFORM=${PLATFORM}"
else
  fail "PLATFORM=${PLATFORM}, expected ${EXPECT_PLATFORM}"
fi

section "detect_os"
detect_os >/dev/null 2>&1
case "${PLATFORM}" in
  macos)
    [[ "${OS_ID}" == "macos" ]] && ok "OS_ID=macos" || fail "OS_ID=${OS_ID}"
    [[ -n "${OS_NAME}" ]] && ok "OS_NAME=${OS_NAME}" || fail "OS_NAME is empty"
    ;;
  windows)
    [[ "${OS_ID}" == "windows" ]] && ok "OS_ID=windows" || fail "OS_ID=${OS_ID}"
    [[ -n "${OS_NAME}" ]] && ok "OS_NAME=${OS_NAME}" || fail "OS_NAME is empty"
    ;;
  linux)
    [[ "${OS_ID}" =~ ^(ubuntu|debian|rocky|alma|centos|unknown)$ ]] \
      && ok "OS_ID=${OS_ID}" || fail "OS_ID=${OS_ID}"
    ;;
esac

section "detect_arch"
detect_arch >/dev/null 2>&1
if [[ "${ARCH}" =~ ^(amd64|arm64)$ ]]; then
  ok "ARCH=${ARCH}"
else
  fail "ARCH=${ARCH}"
fi

section "detect_channel (lowercase, bash 3.2 portable)"
CHANNEL="GitHub"
REGISTRY=""
detect_channel >/dev/null 2>&1
if [[ "${CHANNEL}" == "github" ]]; then
  ok "channel lowercased to github"
else
  fail "channel='${CHANNEL}', expected github"
fi

section "check_memory"
mem_out="$(check_memory 2>&1 || true)"
mem_gb="$(printf '%s\n' "${mem_out}" | sed -n 's/.*Memory: \([0-9][0-9]*\) GB.*/\1/p')"
if [[ -n "${mem_gb}" ]]; then
  if ((mem_gb >= 1)); then
    ok "memory detected: ${mem_gb} GB"
  else
    fail "memory too low: ${mem_gb} GB"
  fi
elif printf '%s\n' "${mem_out}" | grep -q "skipping the memory check"; then
  ok "memory check skipped on this platform (no wmic)"
else
  fail "check_memory produced no usable result: ${mem_out}"
fi

section "port_in_use"
PY=""
for cand in python3 python; do
  if command -v "${cand}" >/dev/null 2>&1; then PY="${cand}"; break; fi
done
if [[ -n "${PY}" ]]; then
  PORT=18765
  SERVER_LOG="${TMPDIR:-/tmp}/devify-test-socket-$$.log"
  (
    sleep 2
    exec "${PY}" -c \
      'import socket, sys, time; sock = socket.socket(); sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); sock.bind(("127.0.0.1", int(sys.argv[1]))); sock.listen(1); time.sleep(30)' \
      "${PORT}"
  ) >"${SERVER_LOG}" 2>&1 &
  SRV_PID=$!
  port_ready=0
  port_attempt=0
  while ((port_attempt < 20)); do
    if port_in_use "${PORT}"; then
      port_ready=1
      break
    fi
    port_attempt=$((port_attempt + 1))
    sleep 0.5
  done
  if ((port_ready)); then
    ok "detects listening port ${PORT}"
  else
    fail "missed listening port ${PORT}"
    if kill -0 "${SRV_PID}" 2>/dev/null; then
      printf 'diagnostic: socket server process %s is still running\n' "${SRV_PID}"
    else
      printf 'diagnostic: socket server process %s exited before the port check\n' "${SRV_PID}"
    fi
    if command -v lsof >/dev/null 2>&1; then
      printf 'diagnostic: lsof path: %s\n' "$(command -v lsof)"
      lsof -nP -iTCP -sTCP:LISTEN 2>&1 | grep -F ":${PORT}" || true
    else
      printf 'diagnostic: lsof is unavailable\n'
    fi
    if [[ -s "${SERVER_LOG}" ]]; then
      sed 's/^/diagnostic: server: /' "${SERVER_LOG}"
    fi
  fi
  if port_in_use "$((PORT + 1))"; then
    fail "false positive on free port $((PORT + 1))"
  else
    ok "free port $((PORT + 1)) not flagged"
  fi
  kill "${SRV_PID}" 2>/dev/null || true
  wait "${SRV_PID}" 2>/dev/null || true
  rm -f "${SERVER_LOG}"
else
  ok "python not available; skipping live-port check"
fi

section "configure (domain/timezone)"
res="$(
  ASSUME_YES=1
  INSTALL_DIR="${TMPDIR:-/tmp}/devify-test-$$"
  DOMAIN=""
  TIMEZONE=""
  ADMIN_EMAIL=""
  EMAIL_DOMAIN=""
  configure >/dev/null 2>&1
  printf '%s\n%s\n' "${DOMAIN}" "${TIMEZONE}"
)"
test_domain="$(printf '%s\n' "${res}" | sed -n '1p')"
test_timezone="$(printf '%s\n' "${res}" | sed -n '2p')"
[[ -n "${test_domain}" ]] && ok "domain=${test_domain}" || fail "domain is empty"
[[ -n "${test_timezone}" ]] && ok "timezone=${test_timezone}" || fail "timezone is empty"

section "require_root"
if [[ "${PLATFORM}" == "windows" ]]; then
  if require_root >/dev/null 2>&1; then
    ok "require_root runs without root on Windows"
  else
    fail "require_root failed on Windows"
  fi
else
  ok "require_root skipped (root/sudo re-exec is host-specific, not run in CI)"
fi

section "final_summary"
summary_out="$(
  VERSION="test"
  INSTALL_DIR="${TMPDIR:-/tmp}/devify-test-$$"
  DATA_DIR="${INSTALL_DIR}/data"
  SCHEME="https"
  DOMAIN="192.0.2.1"
  PORT_SUFFIX=":10443"
  ADMIN_PORT="19443"
  ADMIN_USERNAME="admin"
  ADMIN_PASSWORD="test-password"
  LOG_FILE=""
  HTTPS="true"
  final_summary
)"
expected_admin_url="https://192.0.2.1:19443/admin/"
if printf '%s\n' "${summary_out}" | grep -Fq "Admin panel:      ${expected_admin_url}"; then
  ok "final summary exposes the working admin panel URL"
else
  fail "final summary does not expose ${expected_admin_url}"
fi
if printf '%s\n' "${summary_out}" | grep -Fq "/devify-admin"; then
  fail "final summary still exposes the obsolete /devify-admin path"
else
  ok "final summary omits the obsolete /devify-admin path"
fi

section "installer contracts"
if [[ "${INSTALLER_VERSION}" == "0.2.1" ]]; then
  ok "installer patch version is 0.2.1"
else
  fail "installer patch version is ${INSTALLER_VERSION}, expected 0.2.1"
fi
multiarch_builds="$(grep -Fc "platforms: linux/amd64,linux/arm64" .github/workflows/build_and_deploy.yml)"
if [[ "${multiarch_builds}" == "2" ]]; then
  ok "release workflow builds backend and UI for amd64 and arm64"
else
  fail "release workflow has ${multiarch_builds} multi-architecture build(s), expected 2"
fi
if grep -Fq "Verify published image platforms" .github/workflows/build_and_deploy.yml; then
  ok "release workflow verifies published image platforms"
else
  fail "release workflow does not verify published image platforms"
fi

for compose_file in docker-compose.yml docker-compose.dev.yml; do
  if grep -Fq 'test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]' "${compose_file}"; then
    ok "${compose_file} uses MariaDB's authenticated health check"
  else
    fail "${compose_file} does not use MariaDB's authenticated health check"
  fi
done

for nginx_file in docker/nginx/default.conf docker/nginx/bluegreen/default.conf; do
  if grep -Fq "# Entry URL: /admin/" "${nginx_file}"; then
    ok "${nginx_file} documents the working admin entry URL"
  else
    fail "${nginx_file} does not document the working admin entry URL"
  fi
done

section "health_check"
health_out_file="${TMPDIR:-/tmp}/devify-test-health-$$.log"
curl() {
  local last_arg="${!#}"
  if [[ "${last_arg}" == "http://127.0.0.1:18001/health" ]]; then
    return 0
  fi
  if [[ "${last_arg}" == "https://127.0.0.1:19443/admin/" ]]; then
    printf '302'
    return 0
  fi
  return 1
}
HTTP_PORT="18001"
ADMIN_PORT="19443"
HEALTH_TIMEOUT="1"
health_check >"${health_out_file}" 2>&1
unset -f curl
if grep -Fq "Admin health check passed: https://127.0.0.1:19443/admin/ (HTTP 302)" "${health_out_file}"; then
  ok "health check verifies the dedicated admin URL"
else
  fail "health check did not verify the dedicated admin URL: $(tr '\n' ' ' <"${health_out_file}")"
fi
rm -f "${health_out_file}"

section "verify_app_image_platform"
docker() {
  printf '%s\n' '{"manifests":[{"platform":{"architecture":"amd64","os":"linux"}}]}'
}
APP_NAME="devify"
ARCH="arm64"
DOCKER_DEFAULT_PLATFORM=""
LOG_FILE=""
platform_out="$(verify_app_image_platform "registry.example/devify:1.3.0" 2>&1)"
platform_rc=$?
if [[ "${platform_rc}" == "1" ]] && printf '%s\n' "${platform_out}" | grep -Fq "does not provide a linux/arm64 image"; then
  ok "unsupported application image architecture fails before pull retries"
else
  fail "unsupported application image architecture was not rejected: ${platform_out}"
fi
ARCH="amd64"
if verify_app_image_platform "registry.example/devify-ui:1.3.0" >/dev/null 2>&1; then
  ok "supported application image architecture passes manifest preflight"
else
  fail "supported application image architecture was rejected"
fi
ARCH="arm64"
DOCKER_DEFAULT_PLATFORM="linux/amd64"
if verify_app_image_platform "registry.example/devify:1.3.0" >/dev/null 2>&1; then
  ok "explicit Docker target platform overrides the host architecture"
else
  fail "explicit Docker target platform was ignored"
fi
unset DOCKER_DEFAULT_PLATFORM
unset -f docker

section "run_compose (Windows path conversion)"
if [[ "${PLATFORM}" == "windows" ]]; then
  COMPOSE_CMD=(echo)
  LOG_FILE="${TMPDIR:-/tmp}/devify-test-install.log"
  : >"${LOG_FILE}"
  INSTALL_DIR="${HOME}/devify"
  DATA_DIR="${INSTALL_DIR}"
  out="$(run_compose ps 2>/dev/null)"
  if [[ "${out}" =~ --project-directory\ [A-Za-z]:[\\/] ]]; then
    ok "MSYS path converted for Docker CLI: ${out}"
  else
    fail "path not converted: ${out}"
  fi
else
  ok "run_compose conversion covered by CI on windows-latest"
fi

printf '\n'
if ((FAILURES > 0)); then
  printf '%d test(s) failed\n' "${FAILURES}"
  exit 1
fi
printf 'All platform smoke tests passed\n'
