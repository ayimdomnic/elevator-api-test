import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from app.exceptions import InvalidFloorException

@pytest.fixture
def app():
    from flask import Flask
    from app.api import api, init_api
    
    app = Flask(__name__)
    app.config['TESTING'] = True
    
    # Mock dependencies
    mock_elevators = [Mock() for _ in range(3)]
    mock_config = Mock()
    mock_config.num_floors = 10
    mock_db = Mock()
    
    # Initialize API with mocks
    with patch('app.api.ElevatorManager') as mock_manager:
        mock_manager.return_value = MagicMock()
        init_api(app, mock_elevators, mock_config, mock_db)
        app.mock_manager = mock_manager.return_value
        app.mock_db = mock_db
    
    return app

@pytest.fixture
def client(app):
    return app.test_client()

class TestElevatorAPI:
    def test_call_elevator_success(self, client, app):
        app.mock_manager.assign_elevator.return_value = Mock(
            elevator_id=2,
            task_id="task_123",
            estimated_arrival_time=10.0
        )
        
        response = client.post(
            '/elevator/call',
            data=json.dumps({"from_floor": 3, "to_floor": 8}),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["elevator_id"] == 2

    def test_call_elevator_validation(self, client, app):
        test_cases = [
            ({}, "Request body must be JSON"),
            ({"from_floor": 1}, "Both from_floor and to_floor are required"),
            ({"from_floor": "first", "to_floor": 5}, "Invalid floor number"),
        ]
        
        # Mock the validation to raise exceptions
        app.mock_manager.assign_elevator.side_effect = [
            InvalidFloorException("Invalid floor number"),
            ValueError("Both from_floor and to_floor are required"),
            ValueError("Request body must be JSON")
        ]
        
        for payload, expected_error in test_cases:
            response = client.post(
                '/elevator/call',
                data=json.dumps(payload),   
                content_type='application/json'
            )
            assert response.status_code == 400
        assert expected_error.lower() in response.get_json()["error"].lower()

    def test_call_elevator_no_available(self, client, app):
        from app.exceptions import NoAvailableElevatorException
        app.mock_manager.assign_elevator.side_effect = NoAvailableElevatorException()
        
        response = client.post(
            '/elevator/call',
            data=json.dumps({"from_floor": 1, "to_floor": 5}),
            content_type='application/json'
        )
        
        assert response.status_code == 503
        assert "No elevators currently available" in response.get_json()["error"]

    def test_get_status(self, client, app):
        app.mock_manager.get_system_status.return_value = {
            "elevators": [],
            "active_tasks": 0,
            "metrics": {},
            "system_health": "HEALTHY",
            "timestamp": datetime.now().isoformat()
        }
        
        response = client.get('/elevator/status')
        assert response.status_code == 200
        assert response.get_json()["system_health"] == "HEALTHY"

    def test_get_logs(self, client, app):
        test_log = {
            "id": 1,
            "elevator_id": 1,
            "event_type": "TEST",
            "details": "Test log",
            "timestamp": datetime.now().isoformat(),
            "source": "TEST",
            "severity": "INFO"
        }
        
       
        app.mock_db.get_logs.return_value = [dict(test_log)] 
        
        response = client.get('/elevator/logs')
        assert response.status_code == 200
        assert response.get_json()[0]["event_type"] == "TEST"

    def test_health_check(self, client, app):
        response = client.get('/health/health')
        assert response.status_code == 200
        assert response.get_json()["status"] == "healthy"

    def test_metrics_endpoint(self, client, app):
        app.mock_manager.get_system_status.return_value = {
            "metrics": {"total_calls": 10},
            "timestamp": datetime.now().isoformat()
        }
        
        response = client.get('/health/metrics')
        assert response.status_code == 200
        assert response.get_json()["metrics"]["total_calls"] == 10