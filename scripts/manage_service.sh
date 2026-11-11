#!/bin/bash
# ==============================================================================
# Sound OS - Systemd User Service Management Tool (Owner: Yassin)
# Usage:
#   ./scripts/manage_service.sh install    - Install, enable & start the service
#   ./scripts/manage_service.sh status     - Check service status
#   ./scripts/manage_service.sh logs       - Follow real-time logs via journalctl
#   ./scripts/manage_service.sh restart    - Restart the service
#   ./scripts/manage_service.sh stop       - Stop the service
#   ./scripts/manage_service.sh uninstall  - Disable & remove service
# ==============================================================================

SERVICE_NAME="soundos.service"
USER_SYSTEMD_DIR="${HOME}/.config/systemd/user"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_SRC="${REPO_DIR}/scripts/${SERVICE_NAME}"
SERVICE_DEST="${USER_SYSTEMD_DIR}/${SERVICE_NAME}"

case "$1" in
  install)
    echo "[Sound OS] Installing systemd user service..."
    mkdir -p "${USER_SYSTEMD_DIR}"
    # Replace placeholder with current repo directory if needed
    sed "s|%h/Sound-OS|${REPO_DIR}|g" "${SERVICE_SRC}" > "${SERVICE_DEST}"
    systemctl --user daemon-reload
    systemctl --user enable "${SERVICE_NAME}"
    systemctl --user restart "${SERVICE_NAME}"
    echo "[Sound OS] Service installed and started successfully!"
    echo "Check status with: ./scripts/manage_service.sh status"
    ;;

  status)
    systemctl --user status "${SERVICE_NAME}" --no-pager
    ;;

  logs)
    echo "[Sound OS] Tailing real-time journalctl logs (Ctrl+C to exit)..."
    journalctl --user -u soundos -f
    ;;

  restart)
    echo "[Sound OS] Restarting service..."
    systemctl --user restart "${SERVICE_NAME}"
    echo "[Sound OS] Restarted."
    ;;

  stop)
    echo "[Sound OS] Stopping service..."
    systemctl --user stop "${SERVICE_NAME}"
    echo "[Sound OS] Stopped."
    ;;

  uninstall)
    echo "[Sound OS] Uninstalling service..."
    systemctl --user stop "${SERVICE_NAME}" 2>/dev/null
    systemctl --user disable "${SERVICE_NAME}" 2>/dev/null
    rm -f "${SERVICE_DEST}"
    systemctl --user daemon-reload
    echo "[Sound OS] Service uninstalled cleanly."
    ;;

  *)
    echo "Usage: $0 {install|status|logs|restart|stop|uninstall}"
    exit 1
    ;;
esac
