#!/usr/bin/env bash
# Locked Focus Blocker - Systemd Service Uninstaller (Linux)
set -e

if [ "$EUID" -ne 0 ]; then
    echo "❌ Lỗi: Vui lòng chạy script này với quyền sudo:"
    echo "👉 sudo bash scripts/uninstall_service.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DAEMON_SCRIPT="$ROOT_DIR/scripts/blocker_daemon.py"
SERVICE_FILE="/etc/systemd/system/locked-blocker.service"

echo "=================================================="
echo "🛡️  GỠ BỎ LOCKED FOCUS BLOCKER SYSTEMD SERVICE"
echo "=================================================="

if systemctl is-active --quiet locked-blocker.service 2>/dev/null; then
    echo "[*] Đang dừng service locked-blocker..."
    systemctl stop locked-blocker.service || true
fi

if systemctl is-enabled --quiet locked-blocker.service 2>/dev/null; then
    echo "[*] Đang vô hiệu hóa tự khởi động..."
    systemctl disable locked-blocker.service || true
fi

if [ -f "$SERVICE_FILE" ]; then
    echo "[*] Đang xóa file service $SERVICE_FILE..."
    rm -f "$SERVICE_FILE"
    systemctl daemon-reload
fi

# Clean up /etc/hosts
if [ -f "$DAEMON_SCRIPT" ]; then
    echo "[*] Đang khôi phục file /etc/hosts..."
    if [ -f "$ROOT_DIR/.venv/bin/python" ]; then
        "$ROOT_DIR/.venv/bin/python" "$DAEMON_SCRIPT" --clear || true
    else
        python3 "$DAEMON_SCRIPT" --clear || true
    fi
fi

echo ""
echo "✅ ĐÃ GỠ BỎ TOÀN BỘ SERVICE VÀ KHÔI PHỤC HỆ THỐNG AN TOÀN!"

