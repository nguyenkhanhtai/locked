import sqlite3
import os
import time
import datetime
import logging
from logging.handlers import RotatingFileHandler
from schema import (
    TempBlockItem, PermBlockItem, BlockItemsResponse, TopSiteItem, TaskEvent,
    StudyProject, FlashcardItem, ThinkingProject, ThinkingItem, ThinkingItemsResponse,
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

    def _hash_url(self, url: str) -> int:
        """Helper to create a fast 32-bit integer hash for a URL/Domain."""
        import zlib
        return zlib.crc32(url.lower().strip().encode('utf-8')) & 0xffffffff

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

    def add_temp_site(self, url: str, open_at: int):
        """
        Adds a website to the temporary block list.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM temp_blocks WHERE url = ?", (url,))
                cursor.execute("INSERT INTO temp_blocks (url, open_at) VALUES (?, ?)", (url, open_at))
                conn.commit()
            db_logger.info(f"Added temporary block: '{url}' (until {open_at})")
        except Exception as e:
            db_logger.error(f"Error adding temp site {url}: {e}")
        
    def add_perm_site(self, url: str, unlock_at: int = None):
        """
        Adds a website to the permanent/long-term block list.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM perm_blocks WHERE url = ?", (url,))
                now = int(time.time())
                if unlock_at is None:
                    unlock_at = now + 86400  # Default 1 day
                cursor.execute("INSERT INTO perm_blocks (url, created_at, unlock_at) VALUES (?, ?, ?)", (url, now, unlock_at))
                conn.commit()
            db_logger.info(f"Added permanent block: '{url}' (unlock at {unlock_at})")
        except Exception as e:
            db_logger.error(f"Error adding perm site {url}: {e}")
        
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
            if not url.startswith(('http://', 'https://')):
                url = 'http://' + url
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain.lower()
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
        """Initializes the database for studying (Flashcards and Thinking Room)."""
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
                # Memorize
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS study_projects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS flashcards (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        word TEXT NOT NULL,
                        meaning TEXT NOT NULL,
                        label TEXT,
                        other_info TEXT
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS project_flashcards (
                        project_id INTEGER NOT NULL,
                        flashcard_id INTEGER NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES study_projects(id),
                        FOREIGN KEY (flashcard_id) REFERENCES flashcards(id),
                        PRIMARY KEY (project_id, flashcard_id)
                    )
                ''')
                
                # Thinking
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS thinking_projects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        problem_statement TEXT
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS thinking_knowledge (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT,
                        is_global INTEGER DEFAULT 0,
                        FOREIGN KEY (project_id) REFERENCES thinking_projects(id)
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS thinking_inferences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT,
                        source_ids TEXT,
                        is_global INTEGER DEFAULT 0,
                        FOREIGN KEY (project_id) REFERENCES thinking_projects(id)
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS thinking_questions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT,
                        is_global INTEGER DEFAULT 0,
                        FOREIGN KEY (project_id) REFERENCES thinking_projects(id)
                    )
                ''')
                conn.commit()
            
            # Sync architecture
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO project_flashcards (project_id, flashcard_id) SELECT project_id, id FROM flashcards WHERE project_id IS NOT NULL")
                try: cursor.execute("ALTER TABLE thinking_knowledge ADD COLUMN is_global INTEGER DEFAULT 0")
                except: pass
                try: cursor.execute("ALTER TABLE thinking_inferences ADD COLUMN is_global INTEGER DEFAULT 0")
                except: pass
                try: cursor.execute("ALTER TABLE thinking_questions ADD COLUMN is_global INTEGER DEFAULT 0")
                except: pass
                conn.commit()
        except Exception as e:
            db_logger.error(f"Failed to initialize StudyDatabase: {e}")
        
    def add_study_project(self, name, description=""):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO study_projects (name, description) VALUES (?, ?)", (name, description))
                project_id = cursor.lastrowid
                conn.commit()
            db_logger.info(f"Added flashcard project: '{name}'")
            return StudyProject(id=project_id, name=name, description=description)
        except Exception as e:
            db_logger.error(f"Error adding study project {name}: {e}")
            return None

    def get_study_projects(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, description FROM study_projects")
                rows = cursor.fetchall()
            return [StudyProject(id=row[0], name=row[1], description=row[2]) for row in rows]
        except Exception as e:
            db_logger.error(f"Error getting study projects: {e}")
            return []

    def delete_study_project(self, project_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM project_flashcards WHERE project_id = ?", (project_id,))
                cursor.execute("DELETE FROM study_projects WHERE id = ?", (project_id,))
                conn.commit()
            db_logger.info(f"Deleted study project ID {project_id}")
        except Exception as e:
            db_logger.error(f"Error deleting study project {project_id}: {e}")

    def delete_flashcard(self, card_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM project_flashcards WHERE flashcard_id = ?", (card_id,))
                cursor.execute("DELETE FROM flashcards WHERE id = ?", (card_id,))
                conn.commit()
            db_logger.info(f"Deleted flashcard ID {card_id}")
        except Exception as e:
            db_logger.error(f"Error deleting flashcard {card_id}: {e}")

    def add_flashcard(self, word, meaning, label, other_info, project_id=None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO flashcards (word, meaning, label, other_info) VALUES (?, ?, ?, ?)", 
                            (word, meaning, label, other_info))
                flashcard_id = cursor.lastrowid
                
                if project_id:
                    cursor.execute("INSERT INTO project_flashcards (project_id, flashcard_id) VALUES (?, ?)", (project_id, flashcard_id))
                conn.commit()
            db_logger.info(f"Added flashcard: '{word}' to project ID {project_id}")
            return FlashcardItem(id=flashcard_id, project_id=project_id, word=word, meaning=meaning, label=label, other_info=other_info)
        except Exception as e:
            db_logger.error(f"Error adding flashcard {word}: {e}")
            return None

    def add_flashcards_bulk(self, cards, project_id=None, default_label="", default_other_info=""):
        if not cards:
            return []

        try:
            normalized = []
            for idx, card in enumerate(cards):
                word = (card.get("word") or "").strip()
                meaning = (card.get("meaning") or "").strip()
                if not word or not meaning:
                    continue
                label = (card.get("label") if card.get("label") is not None else default_label) or ""
                other_info = (card.get("other_info") if card.get("other_info") is not None else default_other_info) or ""
                normalized.append((word, meaning, label, other_info))

            created = []
            with self._get_connection() as conn:
                cursor = conn.cursor()
                for word, meaning, label, other_info in normalized:
                    cursor.execute(
                        "INSERT INTO flashcards (word, meaning, label, other_info) VALUES (?, ?, ?, ?)",
                        (word, meaning, label, other_info),
                    )
                    flashcard_id = cursor.lastrowid
                    if project_id:
                        cursor.execute(
                            "INSERT INTO project_flashcards (project_id, flashcard_id) VALUES (?, ?)",
                            (project_id, flashcard_id),
                        )
                    created.append(FlashcardItem(id=flashcard_id, project_id=project_id, word=word, meaning=meaning, label=label, other_info=other_info))
                conn.commit()
            db_logger.info(f"Bulk added {len(created)} flashcards to project ID {project_id}")
            return created
        except Exception as e:
            db_logger.error(f"Error bulk adding flashcards: {e}")
            return []

    def get_flashcards(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT f.id, pf.project_id, f.word, f.meaning, f.label, f.other_info 
                    FROM flashcards f
                    LEFT JOIN project_flashcards pf ON f.id = pf.flashcard_id
                ''')
                rows = cursor.fetchall()
            return [FlashcardItem(id=row[0], project_id=row[1], word=row[2], meaning=row[3], label=row[4], other_info=row[5]) for row in rows]
        except Exception as e:
            db_logger.error(f"Error getting flashcards: {e}")
            return []

    # --- THINKING ROOM METHODS ---
    def add_thinking_project(self, name, problem_statement):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO thinking_projects (name, problem_statement) VALUES (?, ?)", (name, problem_statement))
                conn.commit()
            db_logger.info(f"Added thinking project: '{name}'")
        except Exception as e:
            db_logger.error(f"Error adding thinking project {name}: {e}")

    def update_thinking_project(self, project_id, problem_statement):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE thinking_projects SET problem_statement = ? WHERE id = ?", (problem_statement, project_id))
                conn.commit()
            db_logger.info(f"Updated Thinking Project ID {project_id}")
        except Exception as e:
            db_logger.error(f"Error updating thinking project {project_id}: {e}")

    def get_thinking_projects(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, problem_statement FROM thinking_projects")
                rows = cursor.fetchall()
            return [ThinkingProject(id=row[0], name=row[1], problem_statement=row[2]) for row in rows]
        except Exception as e:
            db_logger.error(f"Error getting thinking projects: {e}")
            return []

    def delete_thinking_project(self, project_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM thinking_knowledge WHERE project_id = ?", (project_id,))
                cursor.execute("DELETE FROM thinking_inferences WHERE project_id = ?", (project_id,))
                cursor.execute("DELETE FROM thinking_questions WHERE project_id = ?", (project_id,))
                cursor.execute("DELETE FROM thinking_projects WHERE id = ?", (project_id,))
                conn.commit()
            db_logger.info(f"Deleted thinking project ID {project_id}")
        except Exception as e:
            db_logger.error(f"Error deleting thinking project {project_id}: {e}")

    def delete_thinking_item(self, item_type, item_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                table = f"thinking_{item_type}"
                if item_type in ["knowledge", "inference", "question"]:
                    cursor.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
                    conn.commit()
            db_logger.info(f"Deleted thinking item ({item_type}) ID {item_id}")
        except Exception as e:
            db_logger.error(f"Error deleting thinking item {item_type}/{item_id}: {e}")

    def add_thinking_knowledge(self, project_id, name, description, is_global=0):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO thinking_knowledge (project_id, name, description, is_global) VALUES (?, ?, ?, ?)", (project_id, name, description, is_global))
                item_id = cursor.lastrowid
                conn.commit()
            db_logger.info(f"Added knowledge: '{name}' to thinking project ID {project_id}")
            return ThinkingItem(id=item_id, project_id=project_id, name=name, description=description, is_global=bool(is_global), type='knowledge')
        except Exception as e:
            db_logger.error(f"Error adding thinking knowledge {name}: {e}")
            return None

    def add_thinking_inference(self, project_id, name, description, source_ids, is_global=0):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO thinking_inferences (project_id, name, description, source_ids, is_global) VALUES (?, ?, ?, ?, ?)", (project_id, name, description, source_ids, is_global))
                item_id = cursor.lastrowid
                conn.commit()
            db_logger.info(f"Added inference: '{name}' to thinking project ID {project_id}")
            return ThinkingItem(id=item_id, project_id=project_id, name=name, description=description, source_ids=source_ids, is_global=bool(is_global), type='inference')
        except Exception as e:
            db_logger.error(f"Error adding thinking inference {name}: {e}")
            return None

    def add_thinking_question(self, project_id, name, description, is_global=0):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO thinking_questions (project_id, name, description, is_global) VALUES (?, ?, ?, ?)", (project_id, name, description, is_global))
                item_id = cursor.lastrowid
                conn.commit()
            db_logger.info(f"Added question: '{name}' to thinking project ID {project_id}")
            return ThinkingItem(id=item_id, project_id=project_id, name=name, description=description, is_global=bool(is_global), type='question')
        except Exception as e:
            db_logger.error(f"Error adding thinking question {name}: {e}")
            return None

    def update_thinking_item(self, item_type, item_id, name, description, source_ids=None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if item_type == "knowledge":
                    cursor.execute("UPDATE thinking_knowledge SET name = ?, description = ? WHERE id = ?", (name, description, item_id))
                elif item_type == "inference":
                    if source_ids is not None:
                        cursor.execute("UPDATE thinking_inferences SET name = ?, description = ?, source_ids = ? WHERE id = ?", (name, description, source_ids, item_id))
                    else:
                        cursor.execute("UPDATE thinking_inferences SET name = ?, description = ? WHERE id = ?", (name, description, item_id))
                elif item_type == "question":
                    cursor.execute("UPDATE thinking_questions SET name = ?, description = ? WHERE id = ?", (name, description, item_id))
                conn.commit()
            
            # Fetch back
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if item_type == "knowledge":
                    cursor.execute("SELECT id, project_id, name, description, is_global FROM thinking_knowledge WHERE id = ?", (item_id,))
                elif item_type == "inference":
                    cursor.execute("SELECT id, project_id, name, description, source_ids, is_global FROM thinking_inferences WHERE id = ?", (item_id,))
                elif item_type == "question":
                    cursor.execute("SELECT id, project_id, name, description, is_global FROM thinking_questions WHERE id = ?", (item_id,))
                row = cursor.fetchone()
                
            if row:
                if item_type == 'inference':
                    return ThinkingItem(id=row[0], project_id=row[1], name=row[2], description=row[3], source_ids=row[4], is_global=bool(row[5]), type=item_type)
                return ThinkingItem(id=row[0], project_id=row[1], name=row[2], description=row[3], is_global=bool(row[4]), type=item_type)
            return None
        except Exception as e:
            db_logger.error(f"Error updating thinking item {item_type}/{item_id}: {e}")
            return None

    def toggle_global_thinking_item(self, item_type, item_id, is_global):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                table = f"thinking_{item_type}"
                if item_type in ["knowledge", "inference", "question"]:
                    cursor.execute(f"UPDATE {table} SET is_global = ? WHERE id = ?", (is_global, item_id))
                    conn.commit()
            db_logger.info(f"Set is_global={is_global} for {item_type} ID {item_id}")
        except Exception as e:
            db_logger.error(f"Error toggling global for {item_type}/{item_id}: {e}")

    def get_all_thinking_knowledge(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT k.id, k.project_id, k.name, k.description, p.name, 'knowledge' as type 
                    FROM thinking_knowledge k LEFT JOIN thinking_projects p ON k.project_id = p.id WHERE k.is_global = 1
                    UNION
                    SELECT k.id, k.project_id, k.name, k.description, p.name, 'inference' as type 
                    FROM thinking_inferences k LEFT JOIN thinking_projects p ON k.project_id = p.id WHERE k.is_global = 1
                    UNION
                    SELECT k.id, k.project_id, k.name, k.description, p.name, 'question' as type 
                    FROM thinking_questions k LEFT JOIN thinking_projects p ON k.project_id = p.id WHERE k.is_global = 1
                ''')
                rows = cursor.fetchall()
            return [ThinkingItem(id=row[0], project_id=row[1], name=row[2], description=row[3], project_name=row[4], type=row[5], is_global=True) for row in rows]
        except Exception as e:
            db_logger.error(f"Error getting all global knowledge: {e}")
            return []

    def get_thinking_items(self, project_id):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, description, is_global FROM thinking_knowledge WHERE project_id = ?", (project_id,))
                knowledge = [ThinkingItem(id=row[0], project_id=project_id, name=row[1], description=row[2], is_global=bool(row[3]), type='knowledge') for row in cursor.fetchall()]
                
                cursor.execute("SELECT id, name, description, source_ids, is_global FROM thinking_inferences WHERE project_id = ?", (project_id,))
                inferences = [ThinkingItem(id=row[0], project_id=project_id, name=row[1], description=row[2], source_ids=row[3], is_global=bool(row[4]), type='inference') for row in cursor.fetchall()]
                
                cursor.execute("SELECT id, name, description, is_global FROM thinking_questions WHERE project_id = ?", (project_id,))
                questions = [ThinkingItem(id=row[0], project_id=project_id, name=row[1], description=row[2], is_global=bool(row[3]), type='question') for row in cursor.fetchall()]
            
            return ThinkingItemsResponse(knowledge=knowledge, inferences=inferences, questions=questions)
        except Exception as e:
            db_logger.error(f"Error getting thinking items for project {project_id}: {e}")
            return ThinkingItemsResponse(knowledge=[], inferences=[], questions=[])

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

