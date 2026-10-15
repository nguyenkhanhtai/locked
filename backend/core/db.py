import sqlite3
import os
import logging
from contextlib import contextmanager
from typing import Callable, List, Optional

logger = logging.getLogger("core.db")

class DatabaseManager:
    """
    Centralized SQLite database manager with Schema Registration support.
    Modules can register their own table initialization hooks to ensure
    modular schema definition while operating on a unified SQLite database.
    """
    _db_path: Optional[str] = None
    _schema_hooks: List[Callable[[sqlite3.Connection], None]] = []

    @classmethod
    def get_default_path(cls) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_dir = os.path.join(base_dir, "db")
        os.makedirs(db_dir, exist_ok=True)
        return os.path.join(db_dir, "locked.db")

    @classmethod
    @property
    def DEFAULT_DB(cls) -> str:
        return cls.get_default_path()

    @classmethod
    def set_db_path(cls, db_path: str):
        """Overrides database path (useful for testing and custom environments)."""
        cls._db_path = db_path
        db_dir = os.path.dirname(os.path.abspath(db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    @classmethod
    def get_db_path(cls) -> str:
        if cls._db_path is None:
            cls._db_path = cls.get_default_path()
        return cls._db_path

    @classmethod
    def register_schema(cls, init_fn: Callable[[sqlite3.Connection], None]):
        """Registers a schema initialization hook from any feature module."""
        if init_fn not in cls._schema_hooks:
            cls._schema_hooks.append(init_fn)

    @classmethod
    @contextmanager
    def get_connection(cls, db_path: Optional[str] = None):
        """Context manager yielding a thread-safe SQLite connection with foreign keys enabled."""
        target_path = db_path or cls.get_db_path()
        target_dir = os.path.dirname(os.path.abspath(target_path))
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)

        conn = sqlite3.connect(target_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database error on {target_path}: {e}")
            raise
        finally:
            conn.close()

    @classmethod
    def init_all(cls, db_path: Optional[str] = None):
        """Initializes all registered schemas on the database."""
        with cls.get_connection(db_path) as conn:
            for hook in cls._schema_hooks:
                try:
                    hook(conn)
                except Exception as e:
                    logger.error(f"Error executing schema hook {hook}: {e}")
                    raise
            conn.commit()
        logger.info(f"Initialized all ({len(cls._schema_hooks)}) module schemas on {db_path or cls.get_db_path()}.")

    @classmethod
    def reset(cls):
        """Clears registered hooks (used mainly in tests)."""
        cls._schema_hooks.clear()
        cls._db_path = None
