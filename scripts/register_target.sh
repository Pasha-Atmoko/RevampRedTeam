#!/usr/bin/env bash
#
# register_target.sh — register (add) an IP or domain + port into the Tier2
# scope allowlist (SSM StringList /tier2/scope-allowlist).
#
# The allowlist is FAIL-CLOSED: a scan is only allowed against host:port entries
# present here. This script ADDS an entry (append + dedupe) rather than
# overwriting the whole list (use set_scope.ps1 to replace everything).
#
# Usage:
#   ./register_target.sh <ip-or-domain> <port>     # add host:port
#   ./register_target.sh <ip-or-domain> <port> --remove
#   ./register_target.sh --list
#   ./register_target.sh --help
#
# Examples:
#   ./register_target.sh 54.84.126.64 80
#   ./register_target.sh sandbox-defender.example.com 443
#   ./register_target.sh 10.0.0.5 8080 --remove
#
# Env:
#   AWS_REGION / AWS_DEFAULT_REGION   (default: us-east-1)
#   SCOPE_PARAM_NAME                  (default: /tier2/scope-allowlist)
#
# Requires: awscli v2, configured credentials.
set -euo pipefail

# Git Bash on Windows rewrites leading-slash args (e.g. /tier2/...) into Windows
# paths. Disable that so the SSM parameter name is passed through verbatim.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

PARAM="${SCOPE_PARAM_NAME:-/tier2/scope-allowlist}"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"

die()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo "$*" >&2; }

usage() {
  cat >&2 <<'EOF'
register_target.sh — add an IP or domain + port to the Tier2 scope allowlist
(SSM StringList /tier2/scope-allowlist). The allowlist is FAIL-CLOSED: a scan is
only allowed against host:port entries present here. This ADDS (append + dedupe).

Usage:
  ./register_target.sh <ip-or-domain> <port>            add host:port
  ./register_target.sh <ip-or-domain> <port> --remove   remove host:port
  ./register_target.sh --list                           show current allowlist
  ./register_target.sh --help

Examples:
  ./register_target.sh 54.84.126.64 80
  ./register_target.sh sandbox-defender.example.com 443
  ./register_target.sh 10.0.0.5 8080 --remove

Env: AWS_REGION/AWS_DEFAULT_REGION (default us-east-1),
     SCOPE_PARAM_NAME (default /tier2/scope-allowlist). Requires awscli v2.
EOF
  exit "${1:-0}"
}

command -v aws >/dev/null 2>&1 || die "awscli not found on PATH."

# --- read current allowlist -> newline-separated entries (empty if unset) ----
read_entries() {
  local raw
  raw="$(aws ssm get-parameter --name "$PARAM" --region "$REGION" \
          --query 'Parameter.Value' --output text 2>/dev/null || true)"
  # StringList comes back comma-joined; scope_guard also accepts newlines.
  printf '%s' "$raw" | tr ',\n' '\n\n' | sed '/^[[:space:]]*$/d'
}

write_entries() {  # args: newline-separated entries -> SSM StringList (comma-joined)
  local joined
  joined="$(printf '%s' "$1" | sed '/^[[:space:]]*$/d' | paste -sd, -)"
  [ -n "$joined" ] || die "Refusing to write an empty allowlist (fail-closed). \
Add an entry or use set_scope.ps1."
  aws ssm put-parameter --name "$PARAM" --region "$REGION" \
      --type StringList --overwrite --value "$joined" >/dev/null
  info "Allowlist for $PARAM is now:"
  printf '%s' "$1" | sed '/^[[:space:]]*$/d' | sed 's/^/  - /' >&2
}

# --- validation --------------------------------------------------------------
valid_ipv4() {
  local ip="$1" o IFS=.
  [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || return 1
  read -ra parts <<<"$ip"
  for o in "${parts[@]}"; do (( o >= 0 && o <= 255 )) || return 1; done
  return 0
}
valid_domain() {
  [[ "$1" =~ ^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$ ]]
}
valid_port() { [[ "$1" =~ ^[0-9]+$ ]] && (( $1 >= 1 && $1 <= 65535 )); }

# --- arg parsing -------------------------------------------------------------
[ $# -ge 1 ] || usage 1
case "${1:-}" in
  -h|--help) usage 0 ;;
  --list)
    info "Scope allowlist ($PARAM, region $REGION):"
    entries="$(read_entries)"
    [ -n "$entries" ] && printf '%s\n' "$entries" | sed 's/^/  - /' || info "  (empty — fail-closed)"
    exit 0 ;;
esac

HOST="${1:-}"; PORT="${2:-}"; ACTION="add"
[ "${3:-}" = "--remove" ] && ACTION="remove"
[ -n "$HOST" ] && [ -n "$PORT" ] || die "Need <ip-or-domain> <port>. See --help."

if ! valid_ipv4 "$HOST" && ! valid_domain "$HOST"; then
  die "'$HOST' is not a valid IPv4 address or domain name."
fi
valid_port "$PORT" || die "Port '$PORT' must be an integer 1-65535."

ENTRY="${HOST}:${PORT}"

# --- apply -------------------------------------------------------------------
current="$(read_entries)"
exists=0
while IFS= read -r e; do [ "$e" = "$ENTRY" ] && exists=1; done <<<"$current"

if [ "$ACTION" = "remove" ]; then
  [ "$exists" -eq 1 ] || die "'$ENTRY' is not in the allowlist; nothing to remove."
  new="$(printf '%s\n' "$current" | grep -vxF "$ENTRY" || true)"
  info "Removing $ENTRY ..."
  write_entries "$new"
else
  if [ "$exists" -eq 1 ]; then
    info "'$ENTRY' is already registered; nothing to do."
    exit 0
  fi
  new="$(printf '%s\n%s\n' "$current" "$ENTRY" | sed '/^[[:space:]]*$/d')"
  info "Registering $ENTRY ..."
  write_entries "$new"
fi
