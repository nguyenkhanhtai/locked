import sqlite3
import os
import time
import datetime
import logging
from logging.handlers import RotatingFileHandler
from schema import (
    TempBlockItem, PermBlockItem, BlockItemsResponse, TopSiteItem, TaskEvent,
    StudyProject, StudyProblem, StudyColumn, StudyRecord, StudyProblemCard,
    ChatSession, ChatMessage
)

# Initalize logger for database
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)

db_logger = logging.getLogger("database_ops")
db_logger.setLevel(logging.INFO)
if not db_logger.handlers:
    fh = RotatingFileHandler(os.path.join(log_dir, "database.log"), maxBytes=20*1024*1024, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    db_logger.addHandler(fh)

from contextlib import contextmanager

class BlockedDatabase:
    def __init__(self, db_path=None):
        """
            Initializes the database for managing blocked websites.
        Args:
            db_path (str, optional): Custom path to the DB file (defaults to db/blocked.db).
        """
        # Khởi tạo database SQLite luôn nằm trong thư mục backend nếu không truyền đường dẫn
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_file = os.path.join(base_dir, "db/blocked.db")
            os.makedirs(base_dir, exist_ok=True)
        else:
            self.db_file = db_path
            
        self.init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_file)
        try:
            yield conn
        except sqlite3.Error as e:
            db_logger.error(f"SQLite error in {self.__class__.__name__}: {e}")
            raise
        finally:
            conn.close()

    def init_db(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS temp_blocks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL,
                        url_hash INTEGER,
                        open_at INTEGER NOT NULL
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS perm_blocks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL,
                        url_hash INTEGER,
                        created_at INTEGER NOT NULL,
                        unlock_at INTEGER NOT NULL DEFAULT 0
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS focus_mode (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        is_active INTEGER DEFAULT 0,
                        end_at INTEGER DEFAULT 0
                    )
                ''')
                cursor.execute("INSERT OR IGNORE INTO focus_mode (id, is_active, end_at) VALUES (1, 0, 0)")
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS focus_list (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL UNIQUE,
                        url_hash INTEGER
                    )
                ''')

                # Migration to Integer Hashes
                try: cursor.execute('ALTER TABLE temp_blocks ADD COLUMN url_hash INTEGER')
                except: pass
                try: cursor.execute('ALTER TABLE perm_blocks ADD COLUMN url_hash INTEGER')
                except: pass
                try: cursor.execute('ALTER TABLE focus_list ADD COLUMN url_hash INTEGER')
                except: pass
                
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_temp_hash ON temp_blocks(url_hash)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_perm_hash ON perm_blocks(url_hash)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_focus_hash ON focus_list(url_hash)')

                conn.commit()
        except Exception as e:
            db_logger.error(f"Failed to initialize BlockedDatabase: {e}")

    def _get_domain(self, url: str) -> str:
        """
        Extracts and normalizes the Root Domain from a full URL.
        (e.g., 'm.facebook.com' -> 'facebook.com')
        """
        try:
            if not url: return ""
            url = url.lower().strip()
            if not url.startswith(('http://', 'https://')):
                url = 'http://' + url
            from urllib.parse import urlparse
            netloc = urlparse(url).netloc
            if netloc.startswith('www.'):
                netloc = netloc[4:]
            
            # Root Domain extraction logic
            parts = netloc.split('.')
            if len(parts) > 2:
                # Handle common multi-level TLDs (.com.vn, .co.uk, etc.)
                if parts[-2] in ['com', 'co', 'edu', 'gov', 'net', 'org', 'ac'] and len(parts[-1]) <= 3:
                    return ".".join(parts[-3:])
                else:
                    return ".".join(parts[-2:])
            return netloc
        except Exception:
            return url.lower()

    def _hash_url(self, url: str) -> int:
        """Helper to create a fast 32-bit integer hash for a normalized Domain."""
        import zlib
        return zlib.crc32(url.encode('utf-8')) & 0xffffffff

    def add_temp_site(self, url: str, open_at: int):
        """Adds a website to the temporary block list with normalized hash."""
        try:
            domain = self._get_domain(url)
            h = self._hash_url(domain)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM temp_blocks WHERE url = ?", (url,))
                cursor.execute("INSERT INTO temp_blocks (url, url_hash, open_at) VALUES (?, ?, ?)", (url, h, open_at))
                conn.commit()
            db_logger.info(f"Added temporary block: '{url}' (domain: {domain}, hash: {h})")
        except Exception as e:
            db_logger.error(f"Error adding temp site {url}: {e}")
        
    def add_perm_site(self, url: str, unlock_at: int = None):
        """Adds a website to the permanent block list with normalized hash."""
        try:
            domain = self._get_domain(url)
            h = self._hash_url(domain)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM perm_blocks WHERE url = ?", (url,))
                now = int(time.time())
                if unlock_at is None:
                    unlock_at = now + 86400
                cursor.execute("INSERT INTO perm_blocks (url, url_hash, created_at, unlock_at) VALUES (?, ?, ?, ?)", (url, h, now, unlock_at))
                conn.commit()
            db_logger.info(f"Added permanent block: '{url}' (domain: {domain}, hash: {h})")
        except Exception as e:
            db_logger.error(f"Error adding perm site {url}: {e}")

    def add_focus_url(self, url: str):
        """Adds a website to the focus list with normalized hash."""
        try:
            domain = self._get_domain(url)
            h = self._hash_url(domain)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO focus_list (url, url_hash) VALUES (?, ?)", (url, h))
                conn.commit()
            db_logger.info(f"Added focus url: '{url}' (domain: {domain}, hash: {h})")
        except Exception as e:
            db_logger.error(f"Error adding focus url {url}: {e}")
        
    def delete_temp_sites(self, keyword: str):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM temp_blocks WHERE url = ?", (keyword,))
                conn.commit()
            db_logger.info(f"Deleted temporary block: '{keyword}'")
        except Exception as e:
            db_logger.error(f"Error deleting temp site {keyword}: {e}")

    def delete_perm_sites(self, keyword: str):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = int(time.time())
                
                cursor.execute("SELECT url, unlock_at FROM perm_blocks WHERE url = ?", (keyword,))
                row = cursor.fetchone()
                if not row:
                    return {"deleted": 0, "message": "Website not found."}
                    
                if row[1] > now:
                    return {"deleted": 0, "message": f"Site '{row[0]}' is still within the minimum lock time."}
                        
                cursor.execute("DELETE FROM perm_blocks WHERE url = ? AND unlock_at <= ?", (keyword, now))
                deleted = cursor.rowcount
                conn.commit()
                db_logger.info(f"Deleted permanent block: '{keyword}'")
                return {"deleted": deleted, "message": "Success"}
        except Exception as e:
            db_logger.error(f"Error deleting perm site {keyword}: {e}")
            return {"deleted": 0, "message": f"System error: {e}"}

    def get_active_sites(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT url FROM temp_blocks WHERE open_at > ?", (int(time.time()),))
                temp_rows = cursor.fetchall()
                
                cursor.execute("SELECT url FROM perm_blocks")
                perm_rows = cursor.fetchall()
            
            return [row[0] for row in temp_rows] + [row[0] for row in perm_rows]
        except Exception as e:
            db_logger.error(f"Error getting active sites: {e}")
            return []

    def get_all_blocks(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT url, open_at FROM temp_blocks WHERE open_at > ?", (int(time.time()),))
                temp_rows = cursor.fetchall()
                
                cursor.execute("SELECT url, created_at, unlock_at FROM perm_blocks")
                perm_rows = cursor.fetchall()
            
            return BlockItemsResponse(
                temporary=[TempBlockItem(url=row[0], open_at=row[1]) for row in temp_rows],
                permanent=[PermBlockItem(url=row[0], created_at=row[1], unlock_at=row[2]) for row in perm_rows]
            )
        except Exception as e:
            db_logger.error(f"Error getting all blocks: {e}")
            return BlockItemsResponse(temporary=[], permanent=[])

    def set_focus_mode(self, is_active: bool, duration_seconds: int = 0):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                end_at = int(time.time()) + duration_seconds if is_active else 0
                cursor.execute("UPDATE focus_mode SET is_active = ?, end_at = ? WHERE id = 1", (1 if is_active else 0, end_at))
                conn.commit()
            db_logger.info(f"Focus mode set to {is_active} (until {end_at})")
        except Exception as e:
            db_logger.error(f"Error setting focus mode: {e}")

    def get_focus_status(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT is_active, end_at FROM focus_mode WHERE id = 1")
                row = cursor.fetchone()
            if row:
                is_active = bool(row[0])
                end_at = row[1]
                if is_active and end_at > 0 and time.time() > end_at:
                    self.set_focus_mode(False)
                    return {"is_active": False, "end_at": 0}
                return {"is_active": is_active, "end_at": end_at}
            return {"is_active": False, "end_at": 0}
        except Exception as e:
            db_logger.error(f"Error getting focus status: {e}")
            return {"is_active": False, "end_at": 0}

    def add_focus_url(self, url: str):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO focus_list (url) VALUES (?)", (url,))
                conn.commit()
        except Exception as e:
            db_logger.error(f"Error adding focus url {url}: {e}")

    def delete_focus_url(self, url: str):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM focus_list WHERE url = ?", (url,))
                conn.commit()
        except Exception as e:
            db_logger.error(f"Error deleting focus url {url}: {e}")

    def get_focus_list(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT url FROM focus_list")
                rows = cursor.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            db_logger.error(f"Error getting focus list: {e}")
            return []

    def _get_domain(self, url: str) -> str:
        try:
            if not url: return ""
            url = url.lower().strip()
            if not url.startswith(('http://', 'https://')):
                url = 'http://' + url
            from urllib.parse import urlparse
            netloc = urlparse(url).netloc
            if netloc.startswith('www.'):
                netloc = netloc[4:]
            
            # Tối ưu: Trích xuất Root Domain (ví dụ: music.youtube.com -> youtube.com)
            parts = netloc.split('.')
            if len(parts) > 2:
                # Xử lý các TLD đa cấp phổ biến
                if parts[-2] in ['com', 'co', 'edu', 'gov', 'net', 'org', 'ac'] and len(parts[-1]) <= 3:
                    return ".".join(parts[-3:])
                else:
                    return ".".join(parts[-2:])
            return netloc
        except Exception:
            return url.lower()

    def _is_match(self, current_url: str, blocked_domain: str) -> bool:
        try:
            current_domain = self._get_domain(current_url)
            blocked_domain = blocked_domain.lower()
            return current_domain == blocked_domain or current_domain.endswith('.' + blocked_domain)
        except Exception:
            return False

    def check_blocked_url(self, current_url: str):
        """
        Checks if the current URL should be blocked.
        TỐI ƯU HÓA: Sử dụng Hash để truy vấn chính xác (Exact Match) trước khi kiểm tra subdomain.
        """
        try:
            focus_status = self.get_focus_status()
            now = int(time.time())
            
            current_domain = self._get_domain(current_url)
            current_hash = self._hash_url(current_domain)

            # print(current_url, current_hash)

            # 1. Kiểm tra Focus Mode
            if focus_status["is_active"]:
                if "127.0.0.1:8765" in current_url or "localhost:8765" in current_url:
                    return {"is_blocked": False}
                    
                # Exact match hash check for allowed list (O(1))
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1 FROM focus_list WHERE url_hash = ?", (current_hash,))
                    if cursor.fetchone():
                        return {"is_blocked": False}
                
                # Subdomain/Pattern fallback check for allowed list
                focus_list = self.get_focus_list()
                for allowed_url in focus_list:
                    if self._is_match(current_url, allowed_url):
                        return {"is_blocked": False}
                
                return {"is_blocked": True, "domain": "Focus Mode Active", "type": "focus", "unlock_at": focus_status["end_at"]}

            # 2. Kiểm tra Blocklists bằng Hash (Exact Match) - Rất nhanh (Indexed)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Check temp blocks by hash
                cursor.execute("SELECT url, open_at FROM temp_blocks WHERE url_hash = ? AND open_at > ?", (current_hash, now))
                row = cursor.fetchone()
                if row: return {"is_blocked": True, "domain": row[0], "type": "temporary", "unlock_at": row[1]}
                
                # Check perm blocks by hash
                cursor.execute("SELECT url, unlock_at FROM perm_blocks WHERE url_hash = ?", (current_hash,))
                row = cursor.fetchone()
                if row: return {"is_blocked": True, "domain": row[0], "type": "permanent", "unlock_at": row[1]}
                
                # # 3. Fallback: Kiểm tra subdomain (Logic cũ nếu hash không khớp hoàn toàn)
                # # Check temporary blocks
                # cursor.execute("SELECT url, open_at FROM temp_blocks WHERE open_at > ?", (now,))
                # temp_rows = cursor.fetchall()
                # for url, open_at in temp_rows:
                #     if self._is_match(current_url, url):
                #         return {"is_blocked": True, "domain": url, "type": "temporary", "unlock_at": open_at}
                    
                # # Check permanent blocks
                # cursor.execute("SELECT url, unlock_at FROM perm_blocks")
                # perm_rows = cursor.fetchall()
                # for url, unlock_at in perm_rows:
                #     if self._is_match(current_url, url):
                #         return {"is_blocked": True, "domain": url, "type": "permanent", "unlock_at": unlock_at}
                
            return {"is_blocked": False}
        except Exception as e:
            db_logger.error(f"Error checking blocked url {current_url}: {e}")
            return {"is_blocked": False}



class ConsumptionDatabase:
    def __init__(self, db_path=None):
        """Initializes the database for tracking screen time."""
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_file = os.path.join(base_dir, "db/consumption.db")
            os.makedirs(base_dir, exist_ok=True)
        else:
            self.db_file = db_path
        self.init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_file)
        try:
            yield conn
        except sqlite3.Error as e:
            db_logger.error(f"SQLite error in ConsumptionDatabase: {e}")
            raise
        finally:
            conn.close()

    def init_db(self):
        """Creates the table for tracking time spent on domains."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS time_tracking (
                        domain TEXT PRIMARY KEY,
                        time_spent INTEGER DEFAULT 0
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                ''')
                conn.commit()
            self.check_weekly_reset()
        except Exception as e:
            db_logger.error(f"Failed to initialize ConsumptionDatabase: {e}")

    def check_weekly_reset(self):
        """
        Checks the current time and automatically resets screen time data every Monday at 0:00 AM.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT value FROM metadata WHERE key = 'last_reset'")
                row = cursor.fetchone()
                
                now = datetime.datetime.now()
                days_since_monday = now.weekday()
                last_monday = now.replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=days_since_monday)
                current_week_start = int(last_monday.timestamp())
                
                if row:
                    last_reset = int(row[0])
                    if last_reset < current_week_start:
                        cursor.execute("DELETE FROM time_tracking")
                        cursor.execute("UPDATE metadata SET value = ? WHERE key = 'last_reset'", (str(current_week_start),))
                        db_logger.info("Weekly reset triggered for time_tracking (Top Sites).")
                else:
                    cursor.execute("INSERT INTO metadata (key, value) VALUES ('last_reset', ?)", (str(current_week_start),))
                
                conn.commit()
        except Exception as e:
            db_logger.error(f"Error checking weekly reset: {e}")

    def add_time(self, domain: str, seconds: int):
        try:
            self.check_weekly_reset()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO time_tracking (domain, time_spent)
                    VALUES (?, ?)
                    ON CONFLICT(domain) DO UPDATE SET time_spent = time_spent + excluded.time_spent
                ''', (domain, seconds))
                conn.commit()
            db_logger.info(f"Cộng thêm {seconds}s thời gian sử dụng cho domain: '{domain}'")
        except Exception as e:
            db_logger.error(f"Error adding time for {domain}: {e}")

    def get_top_sites(self, limit=15):
        try:
            self.check_weekly_reset()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT domain, time_spent FROM time_tracking ORDER BY time_spent DESC LIMIT ?", (limit,))
                rows = cursor.fetchall()
            
            result = []
            for row in rows:
                seconds = row[1]
                h = seconds // 3600
                m = (seconds % 3600) // 60
                s = seconds % 60
                
                time_parts = []
                if h > 0: time_parts.append(f"{h}h")
                if m > 0: time_parts.append(f"{m}m")
                time_parts.append(f"{s}s")
                
                result.append(TopSiteItem(domain=row[0], time_spent=row[1], formatted_time=" ".join(time_parts)))
            return result
        except Exception as e:
            db_logger.error(f"Error getting top sites: {e}")
            return []

class TaskDatabase:
    def __init__(self, db_path=None):
        """Initializes the database for managing Tasks and Events."""
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_file = os.path.join(base_dir, "db/task.db")
            os.makedirs(base_dir, exist_ok=True)
        else:
            self.db_file = db_path
        self.init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_file)
        try:
            yield conn
        except sqlite3.Error as e:
            db_logger.error(f"SQLite error in TaskDatabase: {e}")
            raise
        finally:
            conn.close()

    def init_db(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        start_date INTEGER NOT NULL,
                        end_date INTEGER NOT NULL,
                        priority INTEGER DEFAULT 1,
                        labels TEXT DEFAULT '',
                        done INTEGER DEFAULT 0
                    )
                ''')
                # Check columns
                try: cursor.execute('ALTER TABLE events ADD COLUMN priority INTEGER DEFAULT 1')
                except: pass
                try: cursor.execute("ALTER TABLE events ADD COLUMN labels TEXT DEFAULT ''")
                except: pass
                try: cursor.execute("ALTER TABLE events ADD COLUMN done INTEGER DEFAULT 0")
                except: pass
                conn.commit()
        except Exception as e:
            db_logger.error(f"Failed to initialize TaskDatabase: {e}")

    def add_event(self, name: str, description: str, start_date: int, end_date: int, priority: int, labels: str, done: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO events (name, description, start_date, end_date, priority, labels, done) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                    (name, description, start_date, end_date, priority, labels, done)
                )
                conn.commit()
            db_logger.info(f"Added task: '{name}' (priority: {priority}, done: {done})")
        except Exception as e:
            db_logger.error(f"Error adding event {name}: {e}")

    def update_event(self, event_id: int, name: str, description: str, start_date: int, end_date: int, priority: int, labels: str, done: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE events SET name = ?, description = ?, start_date = ?, end_date = ?, priority = ?, labels = ?, done = ? WHERE id = ?", 
                            (name, description, start_date, end_date, priority, labels, done, event_id))
                conn.commit()
            db_logger.info(f"Updated task ID {event_id}: '{name}'")
        except Exception as e:
            db_logger.error(f"Error updating event {event_id}: {e}")

    def delete_event(self, event_id: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
                conn.commit()
            db_logger.info(f"Deleted task ID {event_id}")
        except Exception as e:
            db_logger.error(f"Error deleting event {event_id}: {e}")

    def get_events(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, description, start_date, end_date, priority, labels, done FROM events ORDER BY end_date ASC")
                rows = cursor.fetchall()
            return [TaskEvent(id=row[0], name=row[1], description=row[2], start_date=row[3], end_date=row[4], priority=row[5], labels=row[6], done=bool(row[7])) for row in rows]
        except Exception as e:
            db_logger.error(f"Error getting events: {e}")
            return []

class StudyDatabase:
    def __init__(self, db_path=None):
        """Initializes the database for studying."""
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_file = os.path.join(base_dir, "db/study.db")
            os.makedirs(base_dir, exist_ok=True)
        else:
            self.db_file = db_path
        self.init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_file)
        try:
            yield conn
        except sqlite3.Error as e:
            db_logger.error(f"SQLite error in StudyDatabase: {e}")
            raise
        finally:
            conn.close()

    def init_db(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS study_projects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        created_at INTEGER,
                        parent_project_id INTEGER,
                        FOREIGN KEY (parent_project_id) REFERENCES study_projects(id)
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS study_problems (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        created_at INTEGER,
                        FOREIGN KEY (project_id) REFERENCES study_projects(id)
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS study_problem_columns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        problem_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        order_index INTEGER DEFAULT 0,
                        FOREIGN KEY (problem_id) REFERENCES study_problems(id)
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS study_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER,
                        title TEXT NOT NULL,
                        body TEXT,
                        created_at INTEGER,
                        updated_at INTEGER,
                        FOREIGN KEY (project_id) REFERENCES study_projects(id)
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS study_problem_cards (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        column_id INTEGER NOT NULL,
                        record_id INTEGER NOT NULL,
                        order_index INTEGER DEFAULT 0,
                        FOREIGN KEY (column_id) REFERENCES study_problem_columns(id),
                        FOREIGN KEY (record_id) REFERENCES study_records(id)
                    )
                ''')
                
                # Migrations
                try: cursor.execute('ALTER TABLE study_projects ADD COLUMN parent_project_id INTEGER REFERENCES study_projects(id)')
                except: pass
                try: cursor.execute('ALTER TABLE study_records ADD COLUMN project_id INTEGER REFERENCES study_projects(id)')
                except: pass

                conn.commit()
        except Exception as e:
            db_logger.error(f"Failed to initialize StudyDatabase: {e}")
            
    # --- Projects ---
    def add_study_project(self, name, description="", parent_project_id=None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = int(time.time())
                
                cursor.execute("SELECT id FROM study_projects WHERE name = ?", (name,))
                exists = cursor.fetchone()
                
                cursor.execute("INSERT INTO study_projects (name, description, created_at, parent_project_id) VALUES (?, ?, ?, ?)", (name, description, now, parent_project_id))
                project_id = cursor.lastrowid
                
                if exists:
                    name = f"[#{project_id}] {name}"
                    cursor.execute("UPDATE study_projects SET name = ? WHERE id = ?", (name, project_id))
                    
                conn.commit()
            db_logger.info(f"Added study project: '{name}'")
            return StudyProject(id=project_id, name=name, description=description, created_at=now, parent_project_id=parent_project_id)
        except Exception as e:
            db_logger.error(f"Error adding study project {name}: {e}")
            return None

    def get_study_projects(self, parent_project_id=None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if parent_project_id is None:
                    cursor.execute("SELECT id, name, description, created_at, parent_project_id FROM study_projects WHERE parent_project_id IS NULL ORDER BY id DESC")
                else:
                    cursor.execute("SELECT id, name, description, created_at, parent_project_id FROM study_projects WHERE parent_project_id = ? ORDER BY id DESC", (parent_project_id,))
                rows = cursor.fetchall()
            return [StudyProject(id=row[0], name=row[1], description=row[2], created_at=row[3] or 0, parent_project_id=row[4]) for row in rows]
        except Exception as e:
            db_logger.error(f"Error getting study projects: {e}")
            return []

    def get_study_project_path(self, project_id):
        try:
            path = []
            current_id = project_id
            with self._get_connection() as conn:
                cursor = conn.cursor()
                while current_id:
                    cursor.execute("SELECT id, name, description, created_at, parent_project_id FROM study_projects WHERE id = ?", (current_id,))
                    row = cursor.fetchone()
                    if not row:
                        break
                    proj = StudyProject(id=row[0], name=row[1], description=row[2], created_at=row[3] or 0, parent_project_id=row[4])
                    path.insert(0, proj)
                    current_id = row[4]
            return path
        except Exception as e:
            db_logger.error(f"Error getting project path for {project_id}: {e}")
            return []

    def delete_study_project(self, project_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Recursive deletion of subprojects not cleanly supported without CTE or multiple queries
                # For now, delete direct child records and problems
                cursor.execute("DELETE FROM study_records WHERE project_id = ?", (project_id,))
                cursor.execute("DELETE FROM study_problem_cards WHERE column_id IN (SELECT id FROM study_problem_columns WHERE problem_id IN (SELECT id FROM study_problems WHERE project_id = ?))", (project_id,))
                cursor.execute("DELETE FROM study_problem_columns WHERE problem_id IN (SELECT id FROM study_problems WHERE project_id = ?)", (project_id,))
                cursor.execute("DELETE FROM study_problems WHERE project_id = ?", (project_id,))
                cursor.execute("DELETE FROM study_projects WHERE id = ?", (project_id,))
                # Let's also set parent_project_id to NULL for any children to avoid orphans that can't be reached
                cursor.execute("UPDATE study_projects SET parent_project_id = NULL WHERE parent_project_id = ?", (project_id,))
                conn.commit()
            db_logger.info(f"Deleted study project ID {project_id}")
        except Exception as e:
            db_logger.error(f"Error deleting study project {project_id}: {e}")

    # --- Problems ---
    def add_study_problem(self, project_id, title, description=""):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = int(time.time())
                
                cursor.execute("SELECT id FROM study_problems WHERE title = ?", (title,))
                exists = cursor.fetchone()
                
                cursor.execute("INSERT INTO study_problems (project_id, title, description, created_at) VALUES (?, ?, ?, ?)", (project_id, title, description, now))
                problem_id = cursor.lastrowid
                
                if exists:
                    title = f"[#{problem_id}] {title}"
                    cursor.execute("UPDATE study_problems SET title = ? WHERE id = ?", (title, problem_id))
                    
                conn.commit()
            db_logger.info(f"Added study problem: '{title}'")
            return StudyProblem(id=problem_id, project_id=project_id, title=title, description=description, created_at=now)
        except Exception as e:
            db_logger.error(f"Error adding study problem {title}: {e}")
            return None

    def get_study_problems(self, project_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, project_id, title, description, created_at FROM study_problems WHERE project_id = ? ORDER BY id DESC", (project_id,))
                rows = cursor.fetchall()
            return [StudyProblem(id=row[0], project_id=row[1], title=row[2], description=row[3] or "", created_at=row[4] or 0) for row in rows]
        except Exception as e:
            db_logger.error(f"Error getting study problems: {e}")
            return []

    def delete_study_problem(self, problem_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM study_problem_cards WHERE column_id IN (SELECT id FROM study_problem_columns WHERE problem_id = ?)", (problem_id,))
                cursor.execute("DELETE FROM study_problem_columns WHERE problem_id = ?", (problem_id,))
                cursor.execute("DELETE FROM study_problems WHERE id = ?", (problem_id,))
                conn.commit()
        except Exception as e:
            db_logger.error(f"Error deleting study problem {problem_id}: {e}")

    def update_study_problem(self, problem_id, title=None, description=None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if title is not None and description is not None:
                    cursor.execute("UPDATE study_problems SET title = ?, description = ? WHERE id = ?", (title, description, problem_id))
                elif title is not None:
                    cursor.execute("UPDATE study_problems SET title = ? WHERE id = ?", (title, problem_id))
                elif description is not None:
                    cursor.execute("UPDATE study_problems SET description = ? WHERE id = ?", (description, problem_id))
                conn.commit()
        except Exception as e:
            db_logger.error(f"Error updating study problem {problem_id}: {e}")

    # --- Columns ---
    def add_study_column(self, problem_id, name, order_index=0):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO study_problem_columns (problem_id, name, order_index) VALUES (?, ?, ?)", (problem_id, name, order_index))
                col_id = cursor.lastrowid
                conn.commit()
            return StudyColumn(id=col_id, problem_id=problem_id, name=name, order_index=order_index)
        except Exception as e:
            db_logger.error(f"Error adding study column: {e}")
            return None

    def get_study_columns(self, problem_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, problem_id, name, order_index FROM study_problem_columns WHERE problem_id = ? ORDER BY order_index ASC", (problem_id,))
                rows = cursor.fetchall()
            return [StudyColumn(id=row[0], problem_id=row[1], name=row[2], order_index=row[3]) for row in rows]
        except Exception as e:
            db_logger.error(f"Error getting columns: {e}")
            return []

    def delete_study_column(self, column_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM study_problem_cards WHERE column_id = ?", (column_id,))
                cursor.execute("DELETE FROM study_problem_columns WHERE id = ?", (column_id,))
                conn.commit()
        except Exception as e:
            db_logger.error(f"Error deleting column {column_id}: {e}")

    def update_study_column(self, column_id, name):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE study_problem_columns SET name = ? WHERE id = ?", (name, column_id))
                conn.commit()
        except Exception as e:
            db_logger.error(f"Error updating column {column_id}: {e}")

    # --- Records ---
    def add_study_record(self, title, body="", project_id=None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = int(time.time())
                
                cursor.execute("SELECT id FROM study_records WHERE title = ?", (title,))
                exists = cursor.fetchone()
                
                cursor.execute("INSERT INTO study_records (title, body, created_at, updated_at, project_id) VALUES (?, ?, ?, ?, ?)", (title, body, now, now, project_id))
                rec_id = cursor.lastrowid
                
                if exists:
                    title = f"[#{rec_id}] {title}"
                    cursor.execute("UPDATE study_records SET title = ? WHERE id = ?", (title, rec_id))
                    
                conn.commit()
            return StudyRecord(id=rec_id, title=title, body=body, created_at=now, updated_at=now, project_id=project_id)
        except Exception as e:
            db_logger.error(f"Error adding record: {e}")
            return None

    def get_study_records(self, limit=50, offset=0, search="", project_id=None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                params = []
                query = "SELECT id, title, body, created_at, updated_at, project_id FROM study_records WHERE 1=1"
                
                if project_id is not None:
                    query += " AND project_id = ?"
                    params.append(project_id)
                else:
                    # Don't show project records when querying all by default unless we specifically want to
                    # Actually, if project_id is None and we want standalone records?
                    # Let's say if search is empty and project_id is None, return all? Or maybe just keep old behavior
                    pass
                
                if search:
                    like = f"%{search}%"
                    query += " AND (title LIKE ? OR body LIKE ?)"
                    params.extend([like, like])
                    
                query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
            return [StudyRecord(id=row[0], title=row[1], body=row[2], created_at=row[3] or 0, updated_at=row[4] or 0, project_id=row[5]) for row in rows]
        except Exception as e:
            db_logger.error(f"Error getting records: {e}")
            return []

    def get_study_record(self, record_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, title, body, created_at, updated_at, project_id FROM study_records WHERE id = ?", (record_id,))
                row = cursor.fetchone()
            if row:
                return StudyRecord(id=row[0], title=row[1], body=row[2], created_at=row[3] or 0, updated_at=row[4] or 0, project_id=row[5])
            return None
        except Exception as e:
            db_logger.error(f"Error getting record {record_id}: {e}")
            return None

    def get_problem_id_for_record(self, record_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT c.problem_id 
                    FROM study_problem_cards card
                    JOIN study_problem_columns c ON card.column_id = c.id
                    WHERE card.record_id = ?
                """, (record_id,))
                row = cursor.fetchone()
                if row:
                    return row[0]
            return None
        except Exception as e:
            db_logger.error(f"Error getting problem_id for record {record_id}: {e}")
            return None

    def update_study_record(self, record_id, title, body):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = int(time.time())
                
                cursor.execute("SELECT id FROM study_records WHERE title = ? AND id != ?", (title, record_id))
                if cursor.fetchone():
                    title = f"[#{record_id}] {title}"
                
                cursor.execute("UPDATE study_records SET title = ?, body = ?, updated_at = ? WHERE id = ?", (title, body, now, record_id))
                conn.commit()
        except Exception as e:
            db_logger.error(f"Error updating record {record_id}: {e}")

    def delete_study_record(self, record_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM study_problem_cards WHERE record_id = ?", (record_id,))
                cursor.execute("DELETE FROM study_records WHERE id = ?", (record_id,))
                conn.commit()
        except Exception as e:
            db_logger.error(f"Error deleting record {record_id}: {e}")

    def search_all_study_items(self, query=""):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                results = []
                like_query = f"%{query}%"

                # Search Projects
                cursor.execute("SELECT id, name, parent_project_id FROM study_projects WHERE name LIKE ?", (like_query,))
                for row in cursor.fetchall():
                    results.append({"type": "project", "id": row[0], "name": row[1], "project_id": row[2] or row[0]})

                # Search Problems
                cursor.execute("SELECT id, title, project_id FROM study_problems WHERE title LIKE ?", (like_query,))
                for row in cursor.fetchall():
                    results.append({"type": "problem", "id": row[0], "name": row[1], "project_id": row[2]})

                # Search Records
                cursor.execute("SELECT id, title, project_id FROM study_records WHERE title LIKE ?", (like_query,))
                for row in cursor.fetchall():
                    results.append({"type": "record", "id": row[0], "name": row[1], "project_id": row[2]})

                return results
        except Exception as e:
            db_logger.error(f"Error searching all study items: {e}")
            return []

    # --- Problem Cards ---
    def add_study_problem_card(self, column_id, record_id, order_index=0):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO study_problem_cards (column_id, record_id, order_index) VALUES (?, ?, ?)", (column_id, record_id, order_index))
                card_id = cursor.lastrowid
                conn.commit()
            return StudyProblemCard(id=card_id, column_id=column_id, record_id=record_id, order_index=order_index)
        except Exception as e:
            db_logger.error(f"Error adding problem card: {e}")
            return None

    def get_study_problem_cards(self, column_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, column_id, record_id, order_index FROM study_problem_cards WHERE column_id = ? ORDER BY order_index ASC", (column_id,))
                rows = cursor.fetchall()
            return [StudyProblemCard(id=row[0], column_id=row[1], record_id=row[2], order_index=row[3]) for row in rows]
        except Exception as e:
            db_logger.error(f"Error getting problem cards: {e}")
            return []

    def delete_study_problem_card(self, card_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM study_problem_cards WHERE id = ?", (card_id,))
                conn.commit()
        except Exception as e:
            db_logger.error(f"Error deleting problem card {card_id}: {e}")


class ChatDatabase:
    def __init__(self, db_path=None):
        """Initializes the database for storing AI Chatbot conversation history (with Session management)."""
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_file = os.path.join(base_dir, "db/chat.db")
            os.makedirs(base_dir, exist_ok=True)
        else:
            self.db_file = db_path
        self.init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_file)
        try:
            yield conn
        except sqlite3.Error as e:
            db_logger.error(f"SQLite error in ChatDatabase: {e}")
            raise
        finally:
            conn.close()

    def init_db(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL,
                        tokens_used INTEGER DEFAULT 0
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at INTEGER NOT NULL
                    )
                ''')
                try: cursor.execute("ALTER TABLE chat_messages ADD COLUMN session_id INTEGER")
                except: pass
                try: cursor.execute("ALTER TABLE chat_sessions ADD COLUMN tokens_used INTEGER DEFAULT 0")
                except: pass

                cursor.execute("SELECT id FROM chat_sessions ORDER BY id ASC LIMIT 1")
                row = cursor.fetchone()
                if row:
                    default_session_id = row[0]
                else:
                    now = int(time.time())
                    cursor.execute("INSERT INTO chat_sessions (title, created_at, updated_at) VALUES (?, ?, ?)", ("Chat 1", now, now))
                    default_session_id = cursor.lastrowid

                cursor.execute("UPDATE chat_messages SET session_id = ? WHERE session_id IS NULL", (default_session_id,))
                conn.commit()
            db_logger.info("Initialized ChatDatabase.")
        except Exception as e:
            db_logger.error(f"Failed to initialize ChatDatabase: {e}")

    def create_session(self, title: str = None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = int(time.time())
                if not title:
                    cursor.execute("SELECT COUNT(*) FROM chat_sessions")
                    session_count = cursor.fetchone()[0]
                    title = f"Chat {session_count + 1}"

                cursor.execute("INSERT INTO chat_sessions (title, created_at, updated_at, tokens_used) VALUES (?, ?, ?, 0)", (title, now, now))
                session_id = cursor.lastrowid
                conn.commit()
            db_logger.info(f"Created chat session: '{title}' (ID {session_id})")
            return ChatSession(id=session_id, title=title, created_at=now, updated_at=now, message_count=0, tokens_used=0)
        except Exception as e:
            db_logger.error(f"Error creating session: {e}")
            return None


    def get_sessions(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT
                        s.id, s.title, s.created_at, s.updated_at,
                        COUNT(m.id) as message_count, s.tokens_used
                    FROM chat_sessions s
                    LEFT JOIN chat_messages m ON m.session_id = s.id
                    GROUP BY s.id, s.title, s.created_at, s.updated_at, s.tokens_used
                    ORDER BY s.updated_at DESC, s.id DESC
                ''')
                rows = cursor.fetchall()
            db_logger.info("Retrieved all chat sessions.")
            return [ChatSession(id=row[0], title=row[1], created_at=row[2], updated_at=row[3], message_count=row[4], tokens_used=row[5] or 0) for row in rows]
        except Exception as e:
            db_logger.error(f"Error getting sessions: {e}")
            return []

    def add_message(self, session_id: int, role: str, content: str):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = int(time.time())
                cursor.execute("INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)", (session_id, role, content, now))
                cursor.execute("UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (now, session_id))
                conn.commit()
            db_logger.info(f"Added {role} message to chat session ID {session_id}.")
        except Exception as e:
            db_logger.error(f"Error adding message to session {session_id}: {e}")

    def add_session_tokens(self, session_id: int, tokens: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE chat_sessions SET tokens_used = tokens_used + ? WHERE id = ?", (tokens, session_id))
                conn.commit()
            db_logger.info(f"Added {tokens} tokens to chat session ID {session_id}.")
        except Exception as e:
            db_logger.error(f"Error adding tokens to session {session_id}: {e}")

    def get_messages(self, session_id: int, limit=50, offset=0):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?", (session_id, limit, offset))
                rows = cursor.fetchall()
            db_logger.info(f"Retrieved messages for chat session ID {session_id}.")
            return [ChatMessage(role=row[0], content=row[1]) for row in reversed(rows)]
        except Exception as e:
            db_logger.error(f"Error getting messages for session {session_id}: {e}")
            return []

    def delete_session(self, session_id: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
                cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
                conn.commit()
            db_logger.info(f"Delete session ID {session_id}")
        except Exception as e:
            db_logger.error(f"Error deleting session {session_id}: {e}")

