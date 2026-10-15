#!/usr/bin/env bash
# Locked Focus Blocker - Systemd Service Installer (Linux)
set -e

if [ "$EUID" -ne 0 ]; then
    echo "❌ Lỗi: Vui lòng chạy script này với quyền sudo:"
    echo "👉 sudo bash scripts/install_service.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DAEMON_SCRIPT="$ROOT_DIR/scripts/blocker_daemon.py"
SERVICE_FILE="/etc/systemd/system/locked-blocker.service"

# Use system python3 or project virtualenv python if available
if [ -f "$ROOT_DIR/.venv/bin/python" ]; then
    PYTHON_EXEC="$ROOT_DIR/.venv/bin/python"
else
    PYTHON_EXEC="$(which python3)"
fi

echo "=================================================="
echo "🛡️  CÀI ĐẶT LOCKED FOCUS BLOCKER SYSTEMD SERVICE"
echo "=================================================="
echo "[*] Thư mục dự án: $ROOT_DIR"
echo "[*] Python:         $PYTHON_EXEC"
echo "[*] Script Daemon:  $DAEMON_SCRIPT"
echo "[*] File Service:   $SERVICE_FILE"
echo "--------------------------------------------------"

# Ensure daemon script is executable
chmod +x "$DAEMON_SCRIPT"

# Write systemd service file
cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Locked Focus Blocker Daemon (System-wide website blocker)
After=network.target

[Service]
Type=simple
ExecStart=$PYTHON_EXEC $DAEMON_SCRIPT
Restart=always
RestartSec=3
WorkingDirectory=$ROOT_DIR
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload and enable
systemctl daemon-reload
systemctl enable locked-blocker.service
systemctl restart locked-blocker.service

echo ""
echo "✅ ĐÃ CÀI ĐẶT VÀ KHỞI ĐỘNG THÀNH CÔNG!"
echo "👉 Từ bây giờ, daemon sẽ tự động chạy ngầm cùng máy tính với quyền root."
echo "👉 Bất kỳ trang web nào bạn khóa trên web http://127.0.0.1:8765/blocker sẽ được tự động chặn trên MỌI trình duyệt!"
echo ""
systemctl status locked-blocker.service --no-pager

