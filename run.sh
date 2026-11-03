#!/usr/bin/env bash
set -euo pipefail
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
atlas_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if (($#==0)); then set -- up; fi
usage() {
  cat <<'HELP'
StockNexus-Wiki
  ./run.sh up          Interactive Docker startup; fixed port 8765, one container
  ./run.sh chat setup|start|stop|status  Local signed-in chat bridge
  ./run.sh down        Stop containers (keep all data)
  ./run.sh build       Build the application image
  ./run.sh restart     Restart containers; use up after code changes
  ./run.sh logs        Follow the latest container logs
  ./run.sh status      Show container status
  ./run.sh local [...] Original Python / Tailscale launcher
  ./run.sh             Interactive Docker startup and data-location selection
  ./run.sh --help       Show this help and local launcher options
  ./run.sh up --non-interactive --tailscale off
  ./run.sh up --tailscale on --https-port 8443
  ./run.sh up --data-dir /mnt/disk/news-atlas-data
Docker: fixed project news-atlas, fixed host/container port 8765.
Settings: .env / ATLAS_BIND, ATLAS_DATA_DIR, ATLAS_UID, ATLAS_GID.

Chat first-time setup (run from the repository folder):
  cd /home/nvidia/Desktop/AI_WS/stocknexus-wiki
  ./run.sh chat setup                 Install pinned npm dependencies (npm ci)
  npx --no-install codex login        Only if not already signed in
  ./run.sh up                        Start web UI and integrated chat bridge
  ./run.sh chat status                Check the bridge; logs: data/private/chat.log
Use the Chat Agent tab at http://127.0.0.1:8765/ for news context and UI actions.
The original standalone sample is separate:
  node server.mjs --open              http://127.0.0.1:3210/; no news/UI MCP context
Keep its terminal open. Ctrl+C stops that standalone service.
For a fresh standalone sample folder only: npm install @openai/codex-sdk @openai/codex
For this repository use npm ci (also installs the MCP dependency).
HELP
}
case "${1:-}" in
  chat)
    shift
    if [[ "${1:-}" == setup ]]; then
      command -v node >/dev/null && command -v npm >/dev/null || { echo 'Install Node.js 20+ (includes npm), then run ./run.sh chat setup again.' >&2; exit 1; }
      node -e 'if(Number(process.versions.node.split(".")[0])<20)process.exit(1)' || { echo 'Node.js 20+ is required.' >&2; exit 1; }
      cd -- "$atlas_root"
      npm ci
      printf '\nInstalled in: %s\n' "$atlas_root"
      printf 'Reuse your existing Codex login. If needed: npx --no-install codex login\nStart integrated news chat: ./run.sh chat start\nThen open http://127.0.0.1:8765/ (start the web app with ./run.sh up).\n'
      exit 0
    fi
    exec python3 "$atlas_root/scripts/chat_service.py" "${@:-start}" ;;
  up|down|build|restart|logs|status)
    atlas_action="$1"; shift
    command -v docker >/dev/null || { echo 'Docker Engine and Docker Compose are required.' >&2; exit 1; }
    docker compose version >/dev/null
    # Respect explicit .env IDs; otherwise use the current host user for bind data.
    if ! [[ -f "$atlas_root/.env" ]] || ! grep -Eq '^ATLAS_UID=' "$atlas_root/.env"; then export ATLAS_UID="${ATLAS_UID:-$(id -u)}"; fi
    if ! [[ -f "$atlas_root/.env" ]] || ! grep -Eq '^ATLAS_GID=' "$atlas_root/.env"; then export ATLAS_GID="${ATLAS_GID:-$(id -g)}"; fi
    command -v python3 >/dev/null || { echo 'The Docker launcher requires Python 3.10 or newer.' >&2; exit 1; }
    exec python3 "$atlas_root/scripts/docker_launch.py" "$atlas_action" "$@" ;;
  local) shift ;;
  --help|-h) usage; if ! command -v python3 >/dev/null; then exit 0; fi ;;
  ''|--*) ;;
  *) usage >&2; exit 2 ;;
esac
command -v python3 >/dev/null || { echo 'Python 3.10 or newer is required。' >&2; exit 1; }
exec python3 "$atlas_root/scripts/launch.py" "$@"
