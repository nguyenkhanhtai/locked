#!/usr/bin/env python3
"""
Locked Focus Blocker - OS-level DNS/hosts Daemon (Linux)
Syncs active domain-level block rules to /etc/hosts to enforce system-wide website blocking.

Usage:
    sudo python3 scripts/blocker_daemon.py             # Run in continuous daemon mode
    sudo python3 scripts/blocker_daemon.py --sync-once # Run a single sync and exit
    sudo python3 scripts/blocker_daemon.py --clear     # Clear all blocker entries from /etc/hosts
"""

import sys
import os
import time
import argparse
import sqlite3
import signal
import subprocess
import re
from typing import List, Set

HOSTS_PATH = os.environ.get("HOSTS_PATH", "/etc/hosts")
MARKER_START = "### LOCKED FOCUS BLOCKER - BEGIN ###"
MARKER_END = "### LOCKED FOCUS BLOCKER - END ###"

# Locate default DB
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("LOCKED_DB_PATH", os.path.join(BASE_DIR, "backend", "db", "locked.db"))


def check_root_permission():
    if os.path.exists(HOSTS_PATH) and not os.access(HOSTS_PATH, os.W_OK):
        print(f"❌ LỖI: Không có quyền ghi vào file {HOSTS_PATH}.")
        print("👉 Vui lòng chạy lại với quyền sudo hoặc chạy qua Docker:")
        print("   sudo python3 scripts/blocker_daemon.py")
        sys.exit(1)


def get_active_blocked_domains(db_path: str = DB_PATH) -> Set[str]:
    """Queries SQLite directly for currently locked domains."""
    if not os.path.exists(db_path):
        return set()

    try:
        conn = sqlite3.connect(db_path)
        now = int(time.time())
        cursor = conn.cursor()
        # Find active rules where match_type is domain (or domain extracted from exact)
        cursor.execute(
            "SELECT domain FROM blocker_rules WHERE is_active = 1 AND blocked_until > ?",
            (now,)
        )
        domains = set()
        for row in cursor.fetchall():
            d = row[0].strip().lower()
            if d:
                bare = d[4:] if d.startswith("www.") else d
                domains.add(bare)
                domains.add(f"www.{bare}")
                if bare in ("facebook.com", "fb.com"):
                    domains.add("m.facebook.com")
                    domains.add("web.facebook.com")
                elif bare in ("youtube.com", "youtu.be"):
                    domains.add("m.youtube.com")
                    domains.add("music.youtube.com")
                elif bare in ("reddit.com",):
                    domains.add("old.reddit.com")
                    domains.add("m.reddit.com")
                elif bare in ("twitter.com", "x.com"):
                    domains.add("mobile.twitter.com")
                    domains.add("mobile.x.com")
        conn.close()
        return domains
    except Exception as e:
        print(f"⚠️ Không thể đọc database ({db_path}): {e}")
        return set()


def read_hosts_file() -> str:
    if not os.path.exists(HOSTS_PATH):
        return ""
    with open(HOSTS_PATH, "r", encoding="utf-8") as f:
        return f.read()


def write_hosts_file(content: str):
    with open(HOSTS_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    flush_dns()


def flush_dns():
    """Flushes local DNS resolver caches if systemd-resolved is active."""
    cmds = [
        ["resolvectl", "flush-caches"],
        ["systemd-resolve", "--flush-caches"],
    ]
    for cmd in cmds:
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            break
        except Exception:
            pass


VALID_DOMAIN_REGEX = re.compile(
    r'^(?!-)[a-z0-9-]{1,63}(?<!-)(\.[a-z0-9-]{1,63}(?<!-))*\.[a-z]{2,63}$'
)
PROTECTED_SYSTEM_DOMAINS = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1", "local",
    "host.docker.internal", "gateway.docker.internal"
}


def update_hosts(domains: Set[str]):
    content = read_hosts_file()

    # Strip existing locked block
    if MARKER_START in content and MARKER_END in content:
        before = content.split(MARKER_START)[0]
        after = content.split(MARKER_END)[1]
        content = (before.rstrip() + "\n\n" + after.lstrip()).strip() + "\n"

    # Strictly filter domains to prevent hosts injection attacks
    valid_domains = set()
    for d in domains:
        clean_d = d.strip().lower()
        if clean_d and clean_d not in PROTECTED_SYSTEM_DOMAINS and VALID_DOMAIN_REGEX.match(clean_d):
            valid_domains.add(clean_d)

    if valid_domains:
        lines = [MARKER_START]
        for d in sorted(valid_domains):
            lines.append(f"0.0.0.0 {d}")
            lines.append(f"127.0.0.1 {d}")
            lines.append(f"::1 {d}")
        lines.append(MARKER_END)
        block = "\n".join(lines)
        new_content = content.rstrip() + "\n\n" + block + "\n"
    else:
        new_content = content.rstrip() + "\n"

    write_hosts_file(new_content)


def clear_hosts():
    content = read_hosts_file()
    if MARKER_START in content and MARKER_END in content:
        before = content.split(MARKER_START)[0]
        after = content.split(MARKER_END)[1]
        cleaned = (before.rstrip() + "\n\n" + after.lstrip()).strip() + "\n"
        write_hosts_file(cleaned)
        print("✅ Đã dọn dẹp toàn bộ các mục Locked Blocker trong /etc/hosts.")
    else:
        print("ℹ️ Không tìm thấy mục Locked Blocker nào trong /etc/hosts.")


def main():
    parser = argparse.ArgumentParser(description="Locked Focus Blocker - OS Hosts Daemon")
    parser.add_argument("--sync-once", action="store_true", help="Sync /etc/hosts once and exit")
    parser.add_argument("--clear", action="store_true", help="Clear all entries from /etc/hosts")
    parser.add_argument("--interval", type=int, default=5, help="Check interval in seconds (default: 5)")
    args = parser.parse_args()

    check_root_permission()

    if args.clear:
        clear_hosts()
        return

    if args.sync_once:
        domains = get_active_blocked_domains()
        update_hosts(domains)
        print(f"✅ Đã đồng bộ {len(domains)} tên miền vào {HOSTS_PATH}.")
        return

    # Continuous Daemon Mode
    print("=" * 60)
    print("🛡️  LOCKED FOCUS BLOCKER — OS HOSTS DAEMON")
    print("=" * 60)
    print(f"[*] Database: {DB_PATH}")
    print(f"[*] Hosts:    {HOSTS_PATH}")
    print(f"[*] Interval: {args.interval}s")
    print("[*] Đang lắng nghe các quy tắc khóa cứng. Nhấn Ctrl+C để dừng.")
    print("-" * 60)

    last_synced_domains = None

    def handle_exit(sig, frame):
        print("\n[!] Nhận tín hiệu dừng. Đang dọn dẹp...")
        clear_hosts()
        print("✅ Đã khôi phục /etc/hosts an toàn. Tạm biệt!")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    while True:
        try:
            active_domains = get_active_blocked_domains()
            if active_domains != last_synced_domains:
                update_hosts(active_domains)
                last_synced_domains = active_domains
                if active_domains:
                    print(f"[{time.strftime('%H:%M:%S')}] 🔒 Đang chặn {len(active_domains)} tên miền: {', '.join(sorted(active_domains))}")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] 🟢 Không còn liên kết nào bị khóa.")
        except Exception as e:
            print(f"[!] Lỗi đồng bộ: {e}")

        time.sleep(args.interval)


if __name__ == "__main__":
    main()

