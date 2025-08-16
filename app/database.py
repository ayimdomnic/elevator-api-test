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
        self._table_suffix = ""
        try:
            db_name = db_url.rsplit('/', 1)[-1]
            if '_' in db_name:
                
                self._table_suffix = '_' + db_name.split('_', 1)[1]
        except Exception:
            self._table_suffix = ""
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
        """Initialize database schema with environment-aware table names."""
        elevators_table = f"elevators{self._table_suffix}"
        logs_table = f"logs{self._table_suffix}"
        sql_table = f"sql_queries{self._table_suffix}"
        idem_table = f"idempotency_keys{self._table_suffix}"

        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {elevators_table} (
                        id INTEGER PRIMARY KEY,
                        current_floor INTEGER NOT NULL,
                        state TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        destination_floor INTEGER,
                        last_updated TIMESTAMP,
                        trips_completed INTEGER,
                        maintenance_mode BOOLEAN
                    )
                    """
                )
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {logs_table} (
                        id SERIAL PRIMARY KEY,
                        elevator_id INTEGER,
                        event_type TEXT NOT NULL,
                        details TEXT NOT NULL,
                        timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        source TEXT NOT NULL,
                        severity TEXT DEFAULT 'INFO'
                    )
                    """
                )
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {sql_table} (
                        id SERIAL PRIMARY KEY,
                        query TEXT NOT NULL,
                        params TEXT,
                        operation TEXT NOT NULL,
                        source TEXT NOT NULL,
                        execution_time_ms FLOAT,
                        error TEXT,
                        timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS {idem_table} (
                        key TEXT PRIMARY KEY,
                        endpoint TEXT NOT NULL,
                        method TEXT NOT NULL,
                        request_hash TEXT NOT NULL,
                        response TEXT,
                        status_code INTEGER,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    @contextmanager
    def get_connection(self) -> Iterator[psycopg.Connection]:
        """Get a database connection with query tracking."""
        conn = self.pool.getconn()
        try:

            original_cursor = conn.cursor
            
            def tracked_cursor(**kwargs):
                """Create a cursor that tracks all queries."""
                class TrackedCursor:
                    def __init__(self, cursor):
                        self._cursor = cursor
                        self._db = self
                    
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
                wrapper._db = self
                return wrapper
            
            conn.cursor = tracked_cursor
            
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:

            if hasattr(conn, 'cursor') and callable(conn.cursor):
                conn.cursor = original_cursor
            self.pool.putconn(conn)

    def _log_query(self, query: str, params: Any, operation: str, 
                  source: str, exec_time: float, error: str = None) -> None:
        """Log a SQL query to the database."""
        try:
            sql_table = f"sql_queries{self._table_suffix}"
            with self.pool.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        INSERT INTO {sql_table} (
                            query, params, operation, source, 
                            execution_time_ms, error, timestamp
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            query,
                            str(params) if params else None,
                            operation,
                            source,
                            exec_time,
                            error,
                            datetime.now()
                        )
                    )
        except Exception as e:
            logger.error(f"Failed to log query: {e}")

    def update_elevator(self, elevator_id: int, current_floor: int, 
                      state: str, direction: str, destination_floor: Optional[int],
                      trips_completed: int = 0, maintenance_mode: bool = False) -> None:
        """Update elevator state in database."""
        elevators_table = f"elevators{self._table_suffix}"
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {elevators_table} (
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
                    """,
                    (
                        elevator_id,
                        current_floor,
                        state,
                        direction,
                        destination_floor,
                        trips_completed,
                        maintenance_mode,
                    )
                )

    def log_event(self, event_type: str, details: str, source: str, 
                 elevator_id: int = None, severity: str = "INFO") -> None:
        """Log an application event."""
        logs_table = f"logs{self._table_suffix}"
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {logs_table} (
                        elevator_id, event_type, details, source, severity, timestamp
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (elevator_id, event_type, details, source, severity, datetime.now())
                )

    def get_idempotency(self, key: str) -> Optional[Dict[str, Any]]:
        """Fetch idempotency record by key, if present."""
        idem_table = f"idempotency_keys{self._table_suffix}"
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT key, endpoint, method, request_hash, response, status_code, created_at FROM {idem_table} WHERE key = %s",
                    (key,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                cols = [desc[0] for desc in cursor.description]
                return dict(zip(cols, row))

    def put_idempotency(self, key: str, endpoint: str, method: str, request_hash: str, response: str, status_code: int) -> None:
        """Store or upsert an idempotency record."""
        idem_table = f"idempotency_keys{self._table_suffix}"
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {idem_table} (key, endpoint, method, request_hash, response, status_code)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (key) DO UPDATE SET
                        endpoint = EXCLUDED.endpoint,
                        method = EXCLUDED.method,
                        request_hash = EXCLUDED.request_hash,
                        response = EXCLUDED.response,
                        status_code = EXCLUDED.status_code
                    """,
                    (key, endpoint, method, request_hash, response, status_code),
                )

    def get_logs(self, limit: int = 100, offset: int = 0, event_type: str = None) -> List[Dict[str, Any]]:
        """Get system logs with optional filtering."""
        logs_table = f"logs{self._table_suffix}"
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                query = f"""
                    SELECT id, elevator_id, event_type, details, 
                           timestamp, source, severity
                    FROM {logs_table}
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
        elevators_table = f"elevators{self._table_suffix}"
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT 
                        id, 
                        current_floor, 
                        state, 
                        direction, 
                        destination_floor,
                        last_updated,
                        trips_completed,
                        maintenance_mode
                    FROM {elevators_table} 
                    ORDER BY id
                    """
                )
                columns = [desc[0] for desc in cursor.description]
                elevators = []
                for row in cursor.fetchall():
                    elevator = dict(zip(columns, row))
                    
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