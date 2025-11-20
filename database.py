"""
Database utilities with connection pooling
"""
import logging
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from config import Config

logger = logging.getLogger(__name__)


class DatabasePool:
    """Database connection pool manager"""
    
    _instance = None
    _pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._pool is None:
            try:
                self._pool = psycopg2.pool.ThreadedConnectionPool(
                    Config.DB_POOL_MIN_CONN,
                    Config.DB_POOL_MAX_CONN,
                    **Config.DB_CONFIG
                )
                logger.info("Database connection pool created successfully")
            except psycopg2.Error as e:
                logger.error(f"Failed to create database pool: {e}")
                raise
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool with context manager"""
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
    
    def close_all(self):
        """Close all connections in the pool"""
        if self._pool:
            self._pool.closeall()
            logger.info("Database pool closed")


# Global database pool instance
db_pool = DatabasePool()


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    with db_pool.get_connection() as conn:
        yield conn


def init_db():
    """Initialize database tables"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    context TEXT,
                    response TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_created (user_id, created_at)
                );
                
                CREATE TABLE IF NOT EXISTS general_chat_history (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    response TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_created (user_id, created_at)
                );
                
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    task_description TEXT NOT NULL,
                    due_date TIMESTAMP,
                    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'cancelled')),
                    priority TEXT DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_status (user_id, status),
                    INDEX idx_due_date (due_date)
                );
                
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    email_filters TEXT DEFAULT 'ALL',
                    reminder_preference TEXT DEFAULT 'tasks',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS email_cache (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    email_data TEXT NOT NULL,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_fetched (user_id, fetched_at)
                );
            """)
            
            # Insert default user profile
            cur.execute("""
                INSERT INTO user_profiles (user_id) 
                VALUES (%s) 
                ON CONFLICT (user_id) DO NOTHING
            """, ("abhiram",))
            
            conn.commit()
            logger.info("Database initialized successfully")
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"Database initialization error: {e}")
            raise
        finally:
            cur.close()
