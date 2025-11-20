"""
Database connection pooling and utilities
"""
import logging
from contextlib import contextmanager
from typing import Optional
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database connections with connection pooling"""
    
    _instance = None
    _pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance
    
    def initialize(self, connection_params: dict, min_conn: int = 1, max_conn: int = 5):
        """Initialize connection pool"""
        if self._pool is None:
            try:
                self._pool = psycopg2.pool.ThreadedConnectionPool(
                    min_conn,
                    max_conn,
                    **connection_params
                )
                logger.info("Database connection pool initialized successfully")
            except psycopg2.Error as e:
                logger.error(f"Failed to initialize database pool: {e}")
                raise
    
    @contextmanager
    def get_connection(self):
        """Context manager for getting database connections from pool"""
        if self._pool is None:
            raise RuntimeError("Database pool not initialized. Call initialize() first.")
        
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                self._pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, cursor_factory=None):
        """Context manager for getting database cursor"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
                conn.commit()
            except psycopg2.Error as e:
                conn.rollback()
                logger.error(f"Database cursor error: {e}")
                raise
            finally:
                cursor.close()
    
    def execute_query(self, query: str, params: Optional[tuple] = None, fetch_one: bool = False):
        """Execute a SELECT query and return results"""
        with self.get_cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            if fetch_one:
                return cursor.fetchone()
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: Optional[tuple] = None):
        """Execute an INSERT/UPDATE/DELETE query"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount
    
    def close_all(self):
        """Close all connections in the pool"""
        if self._pool:
            self._pool.closeall()
            logger.info("All database connections closed")
            self._pool = None

def init_database(db_manager: DatabaseManager):
    """Initialize database tables"""
    try:
        with db_manager.get_cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT,
                    query TEXT,
                    context TEXT,
                    response TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_created (user_id, created_at)
                );
                
                CREATE TABLE IF NOT EXISTS general_chat_history (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT,
                    query TEXT,
                    response TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_created (user_id, created_at)
                );
                
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT,
                    task_description TEXT,
                    due_date TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    priority TEXT DEFAULT 'medium',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_status (user_id, status)
                );
                
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    email_filters TEXT DEFAULT 'ALL',
                    reminder_preference TEXT DEFAULT 'tasks',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Insert default user profile if it doesn't exist
            cursor.execute(
                "INSERT INTO user_profiles (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING",
                ("abhiram",)
            )
        
        logger.info("Database initialized successfully")
    except psycopg2.Error as e:
        logger.error(f"Database initialization error: {e}")
        raise
