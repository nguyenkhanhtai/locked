import sqlite3
import os
import time
import datetime
import logging
from logging.handlers import RotatingFileHandler

# Initalize logger for database
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)

db_logger = logging.getLogger("database_ops")
db_logger.setLevel(logging.INFO)
if not db_logger.handlers:
    fh = RotatingFileHandler(os.path.join(log_dir, "database.log"), maxBytes=20*1024*1024, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    db_logger.addHandler(fh)

class BlockedDatabase:
    def __init__(self, db_path=None):
        # Khởi tạo database SQLite luôn nằm trong thư mục backend nếu không truyền đường dẫn
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_file = os.path.join(base_dir, "db/blocked.db")
        else:
            self.db_file = db_path
            
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS temp_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                open_at INTEGER NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS perm_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                unlock_at INTEGER NOT NULL DEFAULT 0
            )
        ''')
        try:
            cursor.execute('ALTER TABLE perm_blocks ADD COLUMN unlock_at INTEGER NOT NULL DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        conn.commit()
        conn.close()

    def add_temp_site(self, url: str, open_at: int):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM temp_blocks WHERE url = ?", (url,))
        cursor.execute("INSERT INTO temp_blocks (url, open_at) VALUES (?, ?)", (url, open_at))
        conn.commit()
        conn.close()
        db_logger.info(f"Added temporary block: '{url}' (until {open_at})")
        
    def add_perm_site(self, url: str, unlock_at: int = None):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM perm_blocks WHERE url = ?", (url,))
        now = int(time.time())
        if unlock_at is None:
            unlock_at = now + 86400  # Mặc định 1 ngày nếu không truyền
        cursor.execute("INSERT INTO perm_blocks (url, created_at, unlock_at) VALUES (?, ?, ?)", (url, now, unlock_at))
        conn.commit()
        conn.close()
        db_logger.info(f"Added permanent block: '{url}' (unlock at {unlock_at})")
        
    def delete_temp_sites(self, keyword: str):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM temp_blocks WHERE url LIKE ?", (f"%{keyword}%",))
        conn.commit()
        conn.close()
        db_logger.info(f"Deleted temporary blocks containing: '{keyword}'")

    def delete_perm_sites(self, keyword: str):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        now = int(time.time())
        
        cursor.execute("SELECT url, unlock_at FROM perm_blocks WHERE url LIKE ?", (f"%{keyword}%",))
        rows = cursor.fetchall()
        if not rows:
            conn.close()
            return {"deleted": 0, "message": "Website not found."}
        if not rows:
            conn.close()
            return {"deleted": 0, "message": "Website not found."}
            
        for row in rows:
            if row[1] > now:
                conn.close()
                return {"deleted": 0, "message": f"Site '{row[0]}' is still within the minimum lock time; you cannot remove it yet."}
            if row[1] > now:
                conn.close()
                return {"deleted": 0, "message": f"Trang '{row[0]}' chưa hết thời gian khoá tối thiểu, bạn chưa thể gỡ lúc này!"}
                
        cursor.execute("DELETE FROM perm_blocks WHERE url LIKE ? AND unlock_at <= ?", (f"%{keyword}%", now))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        db_logger.info(f"Deleted permanent blocks containing: '{keyword}' (count: {deleted})")
        return {"deleted": deleted, "message": "Success"}

    def get_active_sites(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM temp_blocks WHERE open_at > ?", (int(time.time()),))
        temp_rows = cursor.fetchall()
        
        cursor.execute("SELECT url FROM perm_blocks")
        perm_rows = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in temp_rows] + [row[0] for row in perm_rows]

    def get_all_blocks(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT url, open_at FROM temp_blocks WHERE open_at > ?", (int(time.time()),))
        temp_rows = cursor.fetchall()
        
        cursor.execute("SELECT url, created_at, unlock_at FROM perm_blocks")
        perm_rows = cursor.fetchall()
        conn.close()
        
        return {
            "temporary": [{"url": row[0], "open_at": row[1]} for row in temp_rows],
            "permanent": [{"url": row[0], "created_at": row[1], "unlock_at": row[2]} for row in perm_rows]
        }

class ConsumptionDatabase:
    def __init__(self, db_path=None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_file = os.path.join(base_dir, "db/consumption.db")
        else:
            self.db_file = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS time_tracking (
                domain TEXT PRIMARY KEY,
                time_spent INTEGER DEFAULT 0
            )
        ''')
        conn.commit()
        conn.close()
        self.check_weekly_reset()

    def check_weekly_reset(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("SELECT value FROM metadata WHERE key = 'last_reset'")
        row = cursor.fetchone()
        
        now = datetime.datetime.now()
        # now.weekday(): Thứ 2 = 0, Chủ nhật = 6
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
        conn.close()

    def add_time(self, domain: str, seconds: int):
        self.check_weekly_reset()
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO time_tracking (domain, time_spent)
            VALUES (?, ?)
            ON CONFLICT(domain) DO UPDATE SET time_spent = time_spent + excluded.time_spent
        ''', (domain, seconds))
        conn.commit()
        conn.close()
        db_logger.info(f"Cộng thêm {seconds}s thời gian sử dụng cho domain: '{domain}'")

    def get_top_sites(self, limit=15):
        self.check_weekly_reset()
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT domain, time_spent FROM time_tracking ORDER BY time_spent DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        
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
            
            result.append({"domain": row[0], "time_spent": row[1], "formatted_time": " ".join(time_parts)})
        return result

class TaskDatabase:
    
    def __init__(self, db_path=None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_file = os.path.join(base_dir, "db/task.db")
        else:
            self.db_file = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                start_date INTEGER NOT NULL,
                end_date INTEGER NOT NULL,
                priority INTEGER DEFAULT 1,
                labels TEXT DEFAULT ''
            )
        ''')
        try:
            cursor.execute('ALTER TABLE events ADD COLUMN priority INTEGER DEFAULT 1')
            cursor.execute("ALTER TABLE events ADD COLUMN labels TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE events ADD COLUMN done INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        conn.commit()
        conn.close()

    def add_event(self, name: str, description: str, start_date: int, end_date: int, priority: int, labels: str, done: int):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (name, description, start_date, end_date, priority, labels, done) VALUES (?, ?, ?, ?, ?, ?, ?)", 
            (name, description, start_date, end_date, priority, labels, done)
        )
        conn.commit()
        conn.close()
        db_logger.info(f"Added task: '{name}' (priority: {priority}, done: {done})")

    def update_event(self, event_id: int, name: str, description: str, start_date: int, end_date: int, priority: int, labels: str, done: int):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("UPDATE events SET name = ?, description = ?, start_date = ?, end_date = ?, priority = ?, labels = ?, done = ? WHERE id = ?", 
                       (name, description, start_date, end_date, priority, labels, done, event_id))
        conn.commit()
        conn.close()
        

    def delete_event(self, event_id: int):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()
        conn.close()
        db_logger.info(f"Deleted task ID {event_id}")

    def get_events(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description, start_date, end_date, priority, labels, done FROM events ORDER BY end_date ASC")
        rows = cursor.fetchall()
        conn.close()
        return [{"id": row[0], "name": row[1], "description": row[2], "start_date": row[3], "end_date": row[4], "priority": row[5], "labels": row[6], "done": bool(row[7])} for row in rows]

class StudyDatabase:
    def __init__(self, db_path=None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_file = os.path.join(base_dir, "db/study.db")
        else:
            self.db_file = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_file)
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
                FOREIGN KEY (project_id) REFERENCES thinking_projects(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS thinking_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                FOREIGN KEY (project_id) REFERENCES thinking_projects(id)
            )
        ''')
        conn.commit()
        conn.close()
        
        # Tự động đồng bộ/chuyển đổi dữ liệu cũ sang kiến trúc mới (nếu bạn đã có dữ liệu từ trước)
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO project_flashcards (project_id, flashcard_id) SELECT project_id, id FROM flashcards WHERE project_id IS NOT NULL")
            conn.commit()
            conn.close()
        except sqlite3.OperationalError:
            pass
        
    def add_study_project(self, name, description=""):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO study_projects (name, description) VALUES (?, ?)", (name, description))
        conn.commit()
        conn.close()
        db_logger.info(f"Added flashcard project: '{name}'")

    def get_study_projects(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description FROM study_projects")
        rows = cursor.fetchall()
        conn.close()
        return [{"id": row[0], "name": row[1], "description": row[2]} for row in rows]

    def delete_study_project(self, project_id):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM project_flashcards WHERE project_id = ?", (project_id,))
        cursor.execute("DELETE FROM study_projects WHERE id = ?", (project_id,))
        conn.commit()
        conn.close()
        db_logger.info(f"Deleted study project ID {project_id}. Các flashcard vẫn được giữ lại trong kho tổng.")

    def delete_flashcard(self, card_id):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM project_flashcards WHERE flashcard_id = ?", (card_id,))
        cursor.execute("DELETE FROM flashcards WHERE id = ?", (card_id,))
        conn.commit()
        conn.close()
        db_logger.info(f"Deleted flashcard ID {card_id}")

    def add_flashcard(self, word, meaning, label, other_info, project_id=None):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO flashcards (word, meaning, label, other_info) VALUES (?, ?, ?, ?)", 
                       (word, meaning, label, other_info))
        flashcard_id = cursor.lastrowid
        
        if project_id:
            cursor.execute("INSERT INTO project_flashcards (project_id, flashcard_id) VALUES (?, ?)", (project_id, flashcard_id))
        conn.commit()
        conn.close()
        db_logger.info(f"Added flashcard: '{word}' to project ID {project_id}")

    def get_flashcards(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT f.id, pf.project_id, f.word, f.meaning, f.label, f.other_info 
            FROM flashcards f
            LEFT JOIN project_flashcards pf ON f.id = pf.flashcard_id
        ''')
        rows = cursor.fetchall()
        conn.close()
        return [{"id": row[0], "project_id": row[1], "word": row[2], "meaning": row[3], "label": row[4], "other_info": row[5]} for row in rows]

    # --- THINKING ROOM METHODS ---
    def add_thinking_project(self, name, problem_statement):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO thinking_projects (name, problem_statement) VALUES (?, ?)", (name, problem_statement))
        conn.commit()
        conn.close()
        db_logger.info(f"Added thinking project: '{name}'")

    def update_thinking_project(self, project_id, problem_statement):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("UPDATE thinking_projects SET problem_statement = ? WHERE id = ?", (problem_statement, project_id))
        conn.commit()
        conn.close()
        db_logger.info(f"Cập nhật Problem Statement cho Thinking Project ID {project_id}")

    def get_thinking_projects(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, problem_statement FROM thinking_projects")
        rows = cursor.fetchall()
        conn.close()
        return [{"id": row[0], "name": row[1], "problem_statement": row[2]} for row in rows]

    def delete_thinking_project(self, project_id):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM thinking_knowledge WHERE project_id = ?", (project_id,))
        cursor.execute("DELETE FROM thinking_inferences WHERE project_id = ?", (project_id,))
        cursor.execute("DELETE FROM thinking_questions WHERE project_id = ?", (project_id,))
        cursor.execute("DELETE FROM thinking_projects WHERE id = ?", (project_id,))
        conn.commit()
        conn.close()
        db_logger.info(f"Deleted thinking project ID {project_id} and all items inside")

    def delete_thinking_item(self, item_type, item_id):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        if item_type == "knowledge":
            cursor.execute("DELETE FROM thinking_knowledge WHERE id = ?", (item_id,))
        elif item_type == "inference":
            cursor.execute("DELETE FROM thinking_inferences WHERE id = ?", (item_id,))
        elif item_type == "question":
            cursor.execute("DELETE FROM thinking_questions WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()
        db_logger.info(f"Deleted thinking item ({item_type}) ID {item_id}")

    def add_thinking_knowledge(self, project_id, name, description):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO thinking_knowledge (project_id, name, description) VALUES (?, ?, ?)", (project_id, name, description))
        conn.commit()
        conn.close()
        db_logger.info(f"Added knowledge: '{name}' to thinking project ID {project_id}")

    def add_thinking_inference(self, project_id, name, description, source_ids):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO thinking_inferences (project_id, name, description, source_ids) VALUES (?, ?, ?, ?)", (project_id, name, description, source_ids))
        conn.commit()
        conn.close()
        db_logger.info(f"Added inference: '{name}' to thinking project ID {project_id}")

    def add_thinking_question(self, project_id, name, description):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO thinking_questions (project_id, name, description) VALUES (?, ?, ?)", (project_id, name, description))
        conn.commit()
        conn.close()
        db_logger.info(f"Added question: '{name}' to thinking project ID {project_id}")

    def update_thinking_item(self, item_type, item_id, name, description, source_ids=None):
        conn = sqlite3.connect(self.db_file)
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
        conn.close()
        db_logger.info(f"Cập nhật Thinking Item ({item_type}): '{name}' ID {item_id}")

    def get_thinking_items(self, project_id):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name, description FROM thinking_knowledge WHERE project_id = ?", (project_id,))
        knowledge = [{"id": row[0], "name": row[1], "description": row[2]} for row in cursor.fetchall()]
        
        cursor.execute("SELECT id, name, description, source_ids FROM thinking_inferences WHERE project_id = ?", (project_id,))
        inferences = [{"id": row[0], "name": row[1], "description": row[2], "source_ids": row[3]} for row in cursor.fetchall()]
        
        cursor.execute("SELECT id, name, description FROM thinking_questions WHERE project_id = ?", (project_id,))
        questions = [{"id": row[0], "name": row[1], "description": row[2]} for row in cursor.fetchall()]
        
        conn.close()
        return {"knowledge": knowledge, "inferences": inferences, "questions": questions}

class ChatDatabase:
    def __init__(self, db_path=None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_file = os.path.join(base_dir, "db/chat.db")
        else:
            self.db_file = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

    def add_message(self, role: str, content: str):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_messages (role, content, created_at) VALUES (?, ?, ?)", 
                       (role, content, int(time.time())))
        conn.commit()
        conn.close()

    def get_messages(self, limit=50):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT role, content FROM chat_messages ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        # Sắp xếp lại theo thời gian từ cũ tới mới để làm context
        return [{"role": row[0], "content": row[1]} for row in reversed(rows)]


class ChatDatabase:
    def __init__(self, db_path=None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_file = os.path.join(base_dir, "db/chat.db")
        else:
            self.db_file = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
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
        try:
            cursor.execute("ALTER TABLE chat_messages ADD COLUMN session_id INTEGER")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE chat_sessions ADD COLUMN tokens_used INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        cursor.execute("SELECT id FROM chat_sessions ORDER BY id ASC LIMIT 1")
        row = cursor.fetchone()
        if row:
            default_session_id = row[0]
        else:
            now = int(time.time())
            cursor.execute(
                "INSERT INTO chat_sessions (title, created_at, updated_at) VALUES (?, ?, ?)",
                ("Chat 1", now, now)
            )
            default_session_id = cursor.lastrowid

        cursor.execute(
            "UPDATE chat_messages SET session_id = ? WHERE session_id IS NULL",
            (default_session_id,)
        )
        conn.commit()
        conn.close()

    def create_session(self, title: str = None):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        now = int(time.time())
        if not title:
            cursor.execute("SELECT COUNT(*) FROM chat_sessions")
            session_count = cursor.fetchone()[0]
            title = f"Chat {session_count + 1}"

        cursor.execute(
            "INSERT INTO chat_sessions (title, created_at, updated_at) VALUES (?, ?, ?)",
            (title, now, now)
        )
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {"id": session_id, "title": title, "created_at": now, "updated_at": now}

    def get_sessions(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                s.id,
                s.title,
                s.created_at,
                s.updated_at,
                COUNT(m.id) as message_count,
                s.tokens_used
            FROM chat_sessions s
            LEFT JOIN chat_messages m ON m.session_id = s.id
            GROUP BY s.id, s.title, s.created_at, s.updated_at, s.tokens_used
            ORDER BY s.updated_at DESC, s.id DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": row[0],
                "title": row[1],
                "created_at": row[2],
                "updated_at": row[3],
                "message_count": row[4],
                "tokens_used": row[5] or 0
            }
            for row in rows
        ]

    def add_message(self, session_id: int, role: str, content: str):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        now = int(time.time())
        cursor.execute(
            "INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now)
        )
        cursor.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
            (now, session_id)
        )
        conn.commit()
        conn.close()

    def add_session_tokens(self, session_id: int, tokens: int):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE chat_sessions SET tokens_used = tokens_used + ? WHERE id = ?",
            (tokens, session_id)
        )
        conn.commit()
        conn.close()

    def get_messages(self, session_id: int, limit=50, offset=0):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (session_id, limit, offset)
        )
        rows = cursor.fetchall()
        conn.close()
        return [{"role": row[0], "content": row[1]} for row in reversed(rows)]

    def delete_session(self, session_id: int):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
        conn.commit()
        conn.close()
        db_logger.info(f"Delete session ID {session_id}")
