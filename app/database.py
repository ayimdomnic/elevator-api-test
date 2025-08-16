"""
Database module with connection pooling and query tracking.
"""
import psycopg
import psycopg_pool
from datetime import datetime
from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Iterator, Callable
import logging
import time

logger = logging.getLogger(__name__)

class Database:
    """Database manager with connection pooling and query tracking."""
    
    def __init__(self, db_url: str, pool_size: int = 5, max_pool_size: int = 10):
        """Initialize database connection pool."""
        self.db_url = db_url
        try:
            self.pool = psycopg_pool.ConnectionPool(
                db_url,
                min_size=pool_size,
                max_size=max_pool_size,
                open=True
            )
            self._init_db()
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def _init_db(self) -> None:
        """Initialize database schema with robust column creation."""
        with self.pool.connection() as conn:
            with conn.cursor() as cursor:
                # Create tables if they don't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS elevators (
                        id INTEGER PRIMARY KEY,
                        current_floor INTEGER NOT NULL,
                        state TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        destination_floor INTEGER,
                        last_updated TIMESTAMP,
                        trips_completed INTEGER,
                        maintenance_mode BOOLEAN
                    )
                """)
                
                # Ensure all columns exist with proper types
                cursor.execute("""
                    DO $$
                    BEGIN
                        -- Add missing columns with proper types
                        BEGIN
                            ALTER TABLE elevators ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP;
                        EXCEPTION WHEN duplicate_column THEN -- Do nothing
                        END;
                        
                        BEGIN
                            ALTER TABLE elevators ADD COLUMN IF NOT EXISTS trips_completed INTEGER DEFAULT 0;
                        EXCEPTION WHEN duplicate_column THEN -- Do nothing
                        END;
                        
                        BEGIN
                            ALTER TABLE elevators ADD COLUMN IF NOT EXISTS maintenance_mode BOOLEAN DEFAULT FALSE;
                        EXCEPTION WHEN duplicate_column THEN -- Do nothing
                        END;
                        
                        -- Set default values for existing columns if needed
                        BEGIN
                            ALTER TABLE elevators ALTER COLUMN last_updated SET DEFAULT CURRENT_TIMESTAMP;
                        EXCEPTION WHEN undefined_column THEN -- Do nothing
                        END;
                    END $$;
                """)
                
                # Create other tables
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS logs (
                        id SERIAL PRIMARY KEY,
                        elevator_id INTEGER,
                        event_type TEXT NOT NULL,
                        details TEXT NOT NULL,
                        timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        source TEXT NOT NULL,
                        severity TEXT DEFAULT 'INFO'
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sql_queries (
                        id SERIAL PRIMARY KEY,
                        query TEXT NOT NULL,
                        params TEXT,
                        operation TEXT NOT NULL,
                        source TEXT NOT NULL,
                        execution_time_ms FLOAT,
                        error TEXT,
                        timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()

    @contextmanager
    def get_connection(self) -> Iterator[psycopg.Connection]:
        """Get a database connection with query tracking."""
        conn = self.pool.getconn()
        try:
            # Store original cursor method
            original_cursor = conn.cursor
            
            def tracked_cursor(**kwargs):
                """Create a cursor that tracks all queries."""
                class TrackedCursor:
                    def __init__(self, cursor):
                        self._cursor = cursor
                        self._db = self  # Will be set after creation
                    
                    def __getattr__(self, name):
                        return getattr(self._cursor, name)
                    
                    def execute(self, query, params=None, **execute_kwargs):
                        start = time.time()
                        try:
                            result = self._cursor.execute(query, params, **execute_kwargs)
                            self._db._log_query(
                                query,
                                params,
                                query.split()[0].upper(),
                                "API",
                                (time.time() - start) * 1000
                            )
                            return result
                        except Exception as e:
                            self._db._log_query(
                                query,
                                params,
                                query.split()[0].upper(),
                                "API",
                                (time.time() - start) * 1000,
                                str(e)
                            )
                            raise
                    
                    # Context manager protocol
                    def __enter__(self):
                        self._cursor.__enter__()
                        return self
                    
                    def __exit__(self, exc_type, exc_val, exc_tb):
                        return self._cursor.__exit__(exc_type, exc_val, exc_tb)
                
                cursor = original_cursor(**kwargs)
                wrapper = TrackedCursor(cursor)
                wrapper._db = self  # Pass the Database instance to the wrapper
                return wrapper
            
            # Replace cursor method with our tracked version
            conn.cursor = tracked_cursor
            
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            # Restore original cursor method before returning connection to pool
            if hasattr(conn, 'cursor') and callable(conn.cursor):
                conn.cursor = original_cursor
            self.pool.putconn(conn)

    def _log_query(self, query: str, params: Any, operation: str, 
                  source: str, exec_time: float, error: str = None) -> None:
        """Log a SQL query to the database."""
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO sql_queries (
                            query, params, operation, source, 
                            execution_time_ms, error, timestamp
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        query,
                        str(params) if params else None,
                        operation,
                        source,
                        exec_time,
                        error,
                        datetime.now()
                    ))
        except Exception as e:
            logger.error(f"Failed to log query: {e}")

    def update_elevator(self, elevator_id: int, current_floor: int, 
                      state: str, direction: str, destination_floor: Optional[int],
                      trips_completed: int = 0, maintenance_mode: bool = False) -> None:
        """Update elevator state in database."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO elevators (
                        id, current_floor, state, direction, 
                        destination_floor, trips_completed, maintenance_mode,
                        last_updated
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        current_floor = EXCLUDED.current_floor,
                        state = EXCLUDED.state,
                        direction = EXCLUDED.direction,
                        destination_floor = EXCLUDED.destination_floor,
                        trips_completed = EXCLUDED.trips_completed,
                        maintenance_mode = EXCLUDED.maintenance_mode,
                        last_updated = CURRENT_TIMESTAMP
                """, (
                    elevator_id, current_floor, state, direction, 
                    destination_floor, trips_completed, maintenance_mode
                ))

    def log_event(self, event_type: str, details: str, source: str, 
                 elevator_id: int = None, severity: str = "INFO") -> None:
        """Log an application event."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO logs (
                        elevator_id, event_type, details, source, severity, timestamp
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (elevator_id, event_type, details, source, severity, datetime.now()))

    def get_logs(self, limit: int = 100, offset: int = 0, event_type: str = None) -> List[Dict[str, Any]]:
        """Get system logs with optional filtering."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    SELECT id, elevator_id, event_type, details, 
                           timestamp, source, severity
                    FROM logs
                """
                params = []
                
                if event_type:
                    query += " WHERE event_type = %s"
                    params.append(event_type)
                
                query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                columns = [desc[0] for desc in cursor.description]
                logs = []
                for row in cursor.fetchall():
                    log = dict(zip(columns, row))
                    # Convert datetime to ISO format string
                    if 'timestamp' in log and isinstance(log['timestamp'], datetime):
                        log['timestamp'] = log['timestamp'].isoformat()
                    logs.append(log)
                return logs

    def get_elevator_status(self) -> List[Dict[str, Any]]:
        """Get current status of all elevators."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        id, 
                        current_floor, 
                        state, 
                        direction, 
                        destination_floor,
                        last_updated,
                        trips_completed,
                        maintenance_mode
                    FROM elevators 
                    ORDER BY id
                """)
                columns = [desc[0] for desc in cursor.description]
                elevators = []
                for row in cursor.fetchall():
                    elevator = dict(zip(columns, row))
                    # Convert datetime to ISO format string
                    if 'last_updated' in elevator and isinstance(elevator['last_updated'], datetime):
                        elevator['last_updated'] = elevator['last_updated'].isoformat()
                    elevators.append(elevator)
                return elevators

    def close(self) -> None:
        """Close the connection pool."""
        self.pool.close()
        logger.info("Database connection pool closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()