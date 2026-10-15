import sqlite3
import time
import urllib.parse
import re
import logging
from typing import List, Optional, Tuple
from datetime import datetime

from core.db import DatabaseManager
from .models import BlockRule

logger = logging.getLogger("modules.blocker")

MAX_DURATION_MINUTES = 360  # 6 hours maximum
MIN_DURATION_MINUTES = 1    # 1 minute minimum
MAX_ACTIVE_RULES = 50       # Prevent system resource exhaustion

PROTECTED_SYSTEM_DOMAINS = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1", "local",
    "host.docker.internal", "gateway.docker.internal"
}
try:
    import socket
    _hostname = socket.gethostname().lower()
    if _hostname:
        PROTECTED_SYSTEM_DOMAINS.add(_hostname)
except Exception:
    pass

# RFC 1123 compliant domain regex (letters, digits, hyphens, dots; no leading/trailing hyphens)
VALID_DOMAIN_REGEX = re.compile(
    r'^(?!-)[a-z0-9-]{1,63}(?<!-)(\.[a-z0-9-]{1,63}(?<!-))*\.[a-z]{2,63}$'
)


class HardLockActiveError(Exception):
    """Raised when an attempt is made to delete or modify an active block rule before its timer expires."""
    pass


def normalize_target(raw_url: str) -> Tuple[str, str]:
    """
    Normalizes input URL string and extracts its primary domain.
    Returns (normalized_pattern, domain).
    Enforces strict security checks against host injection and control characters.
    """
    url = raw_url.strip()
    if not url:
        raise ValueError("Đường dẫn (URL) không được để trống.")

    if len(url) > 500:
        raise ValueError("Đường dẫn quá dài (tối đa 500 ký tự).")

    # Reject control characters, newlines, null bytes
    if any(c in url for c in ('\r', '\n', '\0', '\t')):
        raise ValueError("Đường dẫn chứa ký tự điều khiển hoặc xuống dòng không hợp lệ.")

    # Ensure parseable scheme
    test_url = url
    if not re.match(r'^[a-zA-Z]+://', test_url):
        test_url = "https://" + test_url

    parsed = urllib.parse.urlparse(test_url)
    netloc = parsed.netloc.lower()
    if ":" in netloc:
        netloc = netloc.split(":")[0]

    domain = netloc
    if domain.startswith("www."):
        domain = domain[4:]

    # Remove trailing dot if present
    domain = domain.rstrip('.')

    # Reject protected system domains (e.g. localhost, 127.0.0.1)
    if domain in PROTECTED_SYSTEM_DOMAINS:
        raise ValueError(f"Không thể khóa tên miền hệ thống cốt lõi '{domain}' để bảo vệ an toàn máy tính.")

    if not domain or "." not in domain:
        # Default suffix if naked name entered
        domain = f"{domain}.com"

    # Reject protected system domains after suffix
    if domain in PROTECTED_SYSTEM_DOMAINS:
        raise ValueError(f"Không thể khóa tên miền hệ thống cốt lõi '{domain}' để bảo vệ an toàn máy tính.")

    # Strict RFC 1123 domain validation
    if not VALID_DOMAIN_REGEX.match(domain):
        raise ValueError(f"Tên miền '{domain}' không hợp lệ theo chuẩn RFC 1123 (chỉ chứa chữ cái, số, dấu gạch ngang và dấu chấm).")

    # Clean pattern: strip scheme if it was typed as naked domain/path
    cleaned_pattern = url
    cleaned_pattern = re.sub(r'^https?://', '', cleaned_pattern).rstrip('/')
    if cleaned_pattern.startswith("www."):
        cleaned_pattern = cleaned_pattern[4:]

    return cleaned_pattern, domain


def init_blocker_schema(conn: sqlite3.Connection):
    """Schema hook for focus blocker module with indexing."""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocker_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_pattern TEXT NOT NULL,
            domain TEXT NOT NULL,
            match_type TEXT NOT NULL DEFAULT 'domain',
            reason TEXT DEFAULT '',
            duration_minutes INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            blocked_until INTEGER NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocker_blocked_until ON blocker_rules(blocked_until)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocker_is_active ON blocker_rules(is_active)")
    conn.commit()


# Self-register schema into DatabaseManager
DatabaseManager.register_schema(init_blocker_schema)


class BlockerRepository:
    """Repository handling database operations and strict lock enforcement."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        if db_path:
            with DatabaseManager.get_connection(db_path) as conn:
                init_blocker_schema(conn)

    def _conn(self):
        return DatabaseManager.get_connection(self.db_path)

    def add_rule(self, raw_url: str, duration_minutes: int, match_type: str = "domain", reason: str = "") -> BlockRule:
        """
        Adds a new block rule with strict lock duration validation (max 6 hours = 360 mins).
        """
        if duration_minutes < MIN_DURATION_MINUTES:
            raise ValueError(f"Thời gian chặn tối thiểu là {MIN_DURATION_MINUTES} phút.")
        if duration_minutes > MAX_DURATION_MINUTES:
            raise ValueError(f"Thời gian chặn tối đa là 6 tiếng ({MAX_DURATION_MINUTES} phút). Đã đặt là không xóa được!")

        # Enforce maximum active rules limit
        active_rules = self.get_active_rules()
        if len(active_rules) >= MAX_ACTIVE_RULES:
            raise ValueError(f"Đã đạt giới hạn tối đa {MAX_ACTIVE_RULES} quy tắc khóa cùng lúc để bảo vệ tài nguyên hệ thống.")

        url_pattern, domain = normalize_target(raw_url)
        norm_match_type = "exact" if match_type == "exact" else "domain"
        clean_reason = reason.strip() if reason else "Tập trung học tập & tránh xao nhãng"

        now = int(time.time())
        blocked_until = now + (duration_minutes * 60)

        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO blocker_rules (url_pattern, domain, match_type, reason, duration_minutes, created_at, blocked_until, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ''',
                (url_pattern, domain, norm_match_type, clean_reason, duration_minutes, now, blocked_until)
            )
            rule_id = cursor.lastrowid
            conn.commit()

        logger.info(f"Locked rule #{rule_id} created for '{url_pattern}' until {blocked_until} ({duration_minutes}m)")
        return BlockRule(
            id=rule_id,
            url_pattern=url_pattern,
            domain=domain,
            match_type=norm_match_type,
            reason=clean_reason,
            duration_minutes=duration_minutes,
            created_at=now,
            blocked_until=blocked_until,
            is_active=1
        )

    def _sync_expired_status(self, conn: sqlite3.Connection):
        """Internal helper to mark expired rules as is_active = 0."""
        now = int(time.time())
        conn.execute("UPDATE blocker_rules SET is_active = 0 WHERE is_active = 1 AND blocked_until <= ?", (now,))
        conn.commit()

    def get_active_rules(self) -> List[BlockRule]:
        """Returns all rules that are currently locked and not yet expired."""
        with self._conn() as conn:
            self._sync_expired_status(conn)
            cursor = conn.cursor()
            now = int(time.time())
            cursor.execute(
                "SELECT id, url_pattern, domain, match_type, reason, duration_minutes, created_at, blocked_until, is_active FROM blocker_rules WHERE is_active = 1 AND blocked_until > ? ORDER BY blocked_until ASC",
                (now,)
            )
            rows = cursor.fetchall()
            return [
                BlockRule(
                    id=row["id"],
                    url_pattern=row["url_pattern"],
                    domain=row["domain"],
                    match_type=row["match_type"],
                    reason=row["reason"],
                    duration_minutes=row["duration_minutes"],
                    created_at=row["created_at"],
                    blocked_until=row["blocked_until"],
                    is_active=row["is_active"]
                ) for row in rows
            ]

    def get_all_rules(self) -> List[BlockRule]:
        """Returns all rules including expired history."""
        with self._conn() as conn:
            self._sync_expired_status(conn)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, url_pattern, domain, match_type, reason, duration_minutes, created_at, blocked_until, is_active FROM blocker_rules ORDER BY created_at DESC"
            )
            rows = cursor.fetchall()
            return [
                BlockRule(
                    id=row["id"],
                    url_pattern=row["url_pattern"],
                    domain=row["domain"],
                    match_type=row["match_type"],
                    reason=row["reason"],
                    duration_minutes=row["duration_minutes"],
                    created_at=row["created_at"],
                    blocked_until=row["blocked_until"],
                    is_active=row["is_active"]
                ) for row in rows
            ]

    def get_rule_by_id(self, rule_id: int) -> Optional[BlockRule]:
        with self._conn() as conn:
            self._sync_expired_status(conn)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, url_pattern, domain, match_type, reason, duration_minutes, created_at, blocked_until, is_active FROM blocker_rules WHERE id = ?",
                (rule_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return BlockRule(
                id=row["id"],
                url_pattern=row["url_pattern"],
                domain=row["domain"],
                match_type=row["match_type"],
                reason=row["reason"],
                duration_minutes=row["duration_minutes"],
                created_at=row["created_at"],
                blocked_until=row["blocked_until"],
                is_active=row["is_active"]
            )

    def delete_rule(self, rule_id: int) -> bool:
        """
        STRICT HARD-LOCK ENFORCEMENT:
        Deletes a rule ONLY if it has already expired (blocked_until <= now).
        If the rule is still active (blocked_until > now), raises HardLockActiveError!
        """
        rule = self.get_rule_by_id(rule_id)
        if not rule:
            return False

        now = int(time.time())
        if rule.blocked_until > now:
            remaining_mins = max(1, (rule.blocked_until - now + 59) // 60)
            target_dt = datetime.fromtimestamp(rule.blocked_until).strftime('%H:%M:%S %d/%m/%Y')
            raise HardLockActiveError(
                f"Khóa cứng đang hoạt động! Bạn đã đặt lệnh chặn '{rule.url_pattern}' đến {target_dt} "
                f"(còn lại khoảng {remaining_mins} phút). Theo nguyên tắc cam kết, KHÔNG THỂ xóa hoặc mở khóa trước thời hạn!"
            )

        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM blocker_rules WHERE id = ?", (rule_id,))
            conn.commit()
            return True

    def check_url_blocked(self, target_url: str) -> Optional[BlockRule]:
        """
        Checks whether a given URL is currently blocked by any active rule.
        Matches either whole domain or exact prefix pattern.
        """
        active_rules = self.get_active_rules()
        if not active_rules:
            return None

        clean_target = target_url.strip()
        test_url = clean_target if re.match(r'^[a-zA-Z]+://', clean_target) else f"https://{clean_target}"
        parsed = urllib.parse.urlparse(test_url)
        target_domain = parsed.netloc.lower()
        if ":" in target_domain:
            target_domain = target_domain.split(":")[0]
        if target_domain.startswith("www."):
            target_domain = target_domain[4:]

        target_no_scheme = re.sub(r'^https?://', '', clean_target).rstrip('/')
        if target_no_scheme.startswith("www."):
            target_no_scheme = target_no_scheme[4:]

        for rule in active_rules:
            if rule.match_type == "domain":
                # Check domain equality or subdomain
                if target_domain == rule.domain or target_domain.endswith("." + rule.domain):
                    return rule
            elif rule.match_type == "exact":
                # Exact or prefix match
                if target_no_scheme.startswith(rule.url_pattern) or rule.url_pattern in target_no_scheme:
                    return rule

        return None

