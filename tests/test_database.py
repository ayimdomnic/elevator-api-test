import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from app.database import Database

@pytest.fixture
def db():
    with patch('psycopg_pool.ConnectionPool') as mock_pool:
        db = Database("postgresql://postgres:postgres@localhost:5434/elevator_api_test")
        db.pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        db.pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.execute.return_value = None
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = [('id',), ('elevator_id',), ('event_type',), 
                                 ('details',), ('timestamp',), ('source',), ('severity',)]
        return db


class TestDatabase:
    def test_init(self, db):
        mock_cursor = db.pool.getconn().cursor()
        mock_cursor.execute.side_effect = [None, None, None] 
        
        db._init_db()
        
        assert mock_cursor.execute.call_count >= 3
        assert "CREATE TABLE IF NOT EXISTS elevators_api_test" in mock_cursor.execute.call_args_list[0][0][0]

    def test_update_elevator(self, db):
        db.update_elevator(1, 5, "MOVING", "UP", 8)
        mock_cursor = db.pool.getconn().cursor()
        mock_cursor.execute.assert_called_once()

    def test_log_event(self, db):
        db.log_event("TEST", "Test event", "TEST", 1)
        mock_cursor = db.pool.getconn().cursor()
        mock_cursor.execute.assert_called_once()

    def test_get_logs(self, db):
        test_log = (1, 1, "TEST", "Test log", datetime.now(), "TEST", "INFO")
        columns = ['id', 'elevator_id', 'event_type', 'details', 'timestamp', 'source', 'severity']
        db.pool.getconn().cursor().fetchall.return_value = [test_log]
        db.pool.getconn().cursor().description = [(col,) for col in columns]
        
        logs = db.get_logs()
        assert len(logs) == 1
        assert logs[0]["event_type"] == "TEST"

    def test_close(self, db):
        db.close()
        db.pool.close.assert_called_once()