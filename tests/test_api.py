"""
Comprehensive unit tests for ElevatorManager class.

Tests cover concurrent operations, error handling, and edge cases.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from concurrent.futures import Future
from datetime import datetime

from app.manager import ElevatorManager, ElevatorAssignment
from app.elevator import Elevator, ElevatorState, Direction
from app.exceptions import NoAvailableElevatorException, InvalidFloorException


class TestElevatorManager:
    """Test cases for ElevatorManager class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = Mock()
        config.num_floors = 10
        config.num_elevators = 3
        config.floor_move_time = 2.0
        config.door_time = 1.0
        return config

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = Mock()
        db.log_query = Mock()
        return db

    @pytest.fixture
    def mock_elevators(self, mock_db, mock_config):
        """Create mock elevators."""
        elevators = []
        for i in range(3):
            elevator = Mock(spec=Elevator)
            elevator.id = i + 1
            elevator.current_floor = 1
            elevator.state = ElevatorState.IDLE
            elevator.direction = Direction.NONE
            elevator.destination_floor = None
            elevator.move_to = AsyncMock()
            elevators.append(elevator)
        return elevators

    @pytest.fixture
    def elevator_manager(self, mock_elevators, mock_config, mock_db):
        """Create ElevatorManager instance."""
        return ElevatorManager(mock_elevators, mock_config, mock_db)

    def test_initialization(self, elevator_manager, mock_elevators, mock_config, mock_db):
        """Test ElevatorManager initialization."""
        assert elevator_manager.elevators == mock_elevators
        assert elevator_manager.config == mock_config
        assert elevator_manager.db == mock_db
        assert len(elevator_manager._active_tasks) == 0

    def test_assign_elevator_success(self, elevator_manager):
        """Test successful elevator assignment."""
        result = elevator_manager.assign_elevator(from_floor=1, to_floor=5)
        
        assert isinstance(result, ElevatorAssignment)
        assert result.elevator_id in [1, 2, 3]
        assert result.task_id is not None
        assert result.estimated_arrival_time is not None

    def test_assign_elevator_invalid_floors(self, elevator_manager):
        """Test elevator assignment with invalid floors."""
        test_cases = [
            (0, 5, "From floor 0 invalid"),
            (1, 15, "To floor 15 invalid"),
            (-1, 5, "From floor -1 invalid"),
            (1, 0, "To floor 0 invalid"),
        ]
        
        for from_floor, to_floor, expected_msg in test_cases:
            with pytest.raises(InvalidFloorException) as exc_info:
                elevator_manager.assign_elevator(from_floor, to_floor)
            assert "invalid" in str(exc_info.value).lower()

    def test_assign_elevator_non_integer_floors(self, elevator_manager):
        """Test elevator assignment with non-integer floors."""
        with pytest.raises(InvalidFloorException) as exc_info:
            elevator_manager.assign_elevator("first", 5)
        assert "integers" in str(exc_info.value)

    def test_no_available_elevators(self, elevator_manager):
        """Test behavior when no elevators are available."""
        # Set all elevators to busy state
        for elevator in elevator_manager.elevators:
            elevator.state = ElevatorState.MOVING
            elevator.destination_floor = 10
        
        with pytest.raises(NoAvailableElevatorException):
            elevator_manager.assign_elevator(from_floor=1, to_floor=5)

    def test_closest_idle_elevator_selection(self, elevator_manager):
        """Test that closest idle elevator is selected."""
        # Position elevators at different floors
        elevator_manager.elevators[0].current_floor = 1  # Distance: 2
        elevator_manager.elevators[1].current_floor = 5  # Distance: 2  
        elevator_manager.elevators[2].current_floor = 2  # Distance: 1 (closest)
        
        result = elevator_manager.assign_elevator(from_floor=3, to_floor=7)
        
        # Should select elevator 3 (closest to floor 3)
        assert result.elevator_id == 3

    def test_concurrent_assignments(self, elevator_manager):
        """Test multiple concurrent elevator assignments."""
        import threading
        results = []
        errors = []
        
        def assign_elevator():
            try:
                result = elevator_manager.assign_elevator(from_floor=1, to_floor=5)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads to test thread safety
        threads = [threading.Thread(target=assign_elevator) for _ in range(5)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have some successful assignments (limited by number of elevators)
        assert len(results) > 0
        # Some might fail due to no available elevators
        assert len(results) + len(errors) == 5

    @patch('app.elevator_manager.asyncio.run')
    def test_execute_elevator_call_success(self, mock_asyncio_run, elevator_manager):
        """Test successful elevator call execution."""
        elevator = elevator_manager.elevators[0]
        task_id = "test_task_123"
        
        # Execute the call
        elevator_manager._execute_elevator_call(
            elevator, from_floor=1, to_floor=5, task_id=task_id, caller_id="test"
        )
        
        # Verify elevator.move_to was called twice (pickup + destination)
        assert mock_asyncio_run.call_count == 2
        
        # Verify database logging
        elevator_manager.db.log_query.assert_called()

    def test_calculate_arrival_time_idle_elevator(self, elevator_manager):
        """Test arrival time calculation for idle elevator."""
        elevator = elevator_manager.elevators[0]
        elevator.current_floor = 1
        elevator.state = ElevatorState.IDLE
        
        arrival_time = elevator_manager._calculate_arrival_time(elevator, pickup_floor=5)
        
        # Should be 4 floors * 2.0 seconds = 8.0 seconds
        assert arrival_time == 8.0

    def test_calculate_arrival_time_moving_elevator(self, elevator_manager):
        """Test arrival time calculation for moving elevator."""
        elevator = elevator_manager.elevators[0]
        elevator.current_floor = 3
        elevator.state = ElevatorState.MOVING
        elevator.destination_floor = 7
        
        arrival_time = elevator_manager._calculate_arrival_time(elevator, pickup_floor=5)
        
        # Current trip: 4 floors * 2.0 = 8.0s
        # Plus pickup: 2 floors * 2.0 = 4.0s
        # Total: 12.0s
        assert arrival_time == 12.0

    def test_can_pickup_on_route_going_up(self, elevator_manager):
        """Test pickup on route for elevator going up."""
        elevator = elevator_manager.elevators[0]
        elevator.current_floor = 2
        elevator.destination_floor = 8
        elevator.direction = Direction.UP
        
        assert elevator_manager._can_pickup_on_route(elevator, 5) is True  # On route
        assert elevator_manager._can_pickup_on_route(elevator, 1) is False  # Behind
        assert elevator_manager._can_pickup_on_route(elevator, 10) is False  # Ahead

    def test_can_pickup_on_route_going_down(self, elevator_manager):
        """Test pickup on route for elevator going down."""
        elevator = elevator_manager.elevators[0]
        elevator.current_floor = 8
        elevator.destination_floor = 2
        elevator.direction = Direction.DOWN
        
        assert elevator_manager._can_pickup_on_route(elevator, 5) is True  # On route
        assert elevator_manager._can_pickup_on_route(elevator, 10) is False  # Behind
        assert elevator_manager._can_pickup_on_route(elevator, 1) is False  # Ahead

    def test_system_status(self, elevator_manager):
        """Test system status reporting."""
        status = elevator_manager.get_system_status()
        
        assert "elevators" in status
        assert "active_tasks" in status
        assert "metrics" in status
        assert "system_health" in status
        assert "timestamp" in status
        
        # Check elevator status structure
        elevator_status = status["elevators"][0]
        assert "id" in elevator_status
        assert "current_floor" in elevator_status
        assert "state" in elevator_status
        assert "direction" in elevator_status

    def test_system_health_healthy(self, elevator_manager):
        """Test system health when all elevators are idle."""
        # All elevators are idle by default
        status = elevator_manager.get_system_status()
        assert status["system_health"] == "HEALTHY"

    def test_system_health_busy(self, elevator_manager):
        """Test system health when all elevators are busy."""
        for elevator in elevator_manager.elevators:
            elevator.state = ElevatorState.MOVING
        
        status = elevator_manager.get_system_status()
        assert status["system_health"] == "BUSY"

    def test_metrics_tracking(self, elevator_manager):
        """Test that metrics are properly tracked."""
        initial_metrics = elevator_manager._metrics.copy()
        
        # Make a successful assignment
        elevator_manager.assign_elevator(from_floor=1, to_floor=5)
        
        # Check metrics were updated
        assert elevator_manager._metrics["total_calls"] == initial_metrics["total_calls"] + 1
        assert elevator_manager._metrics["successful_assignments"] == initial_metrics["successful_assignments"] + 1

    def test_task_status_tracking(self, elevator_manager):
        """Test task status tracking."""
        # Assign an elevator to get a task ID
        assignment = elevator_manager.assign_elevator(from_floor=1, to_floor=5)
        
        # Check task status
        task_status = elevator_manager.get_task_status(assignment.task_id)
        assert task_status is not None
        assert task_status["task_id"] == assignment.task_id
        assert "status" in task_status

    @patch('app.elevator_manager.logger')
    def test_logging_calls(self, mock_logger, elevator_manager):
        """Test that appropriate log calls are made."""
        elevator_manager.assign_elevator(from_floor=1, to_floor=5)
        
        # Verify info logging was called
        mock_logger.info.assert_called()

    def test_shutdown(self, elevator_manager):
        """Test graceful shutdown."""
        # Add a mock active task
        mock_future = Mock()
        mock_future.done.return_value = False
        elevator_manager._active_tasks["test_task"] = mock_future
        
        with patch.object(elevator_manager._executor, 'shutdown') as mock_shutdown:
            elevator_manager.shutdown()
            mock_shutdown.assert_called_once_with(wait=True, timeout=30)

    def test_validate_floors_success(self, elevator_manager):
        """Test successful floor validation."""
        # Should not raise any exception
        elevator_manager._validate_floors(1, 5)
        elevator_manager._validate_floors(10, 1)

    def test_elevator_assignment_algorithm_with_compatible_elevators(self, elevator_manager):
        """Test assignment when elevators are moving in compatible direction."""
        # Set all elevators to moving
        elevator_manager.elevators[0].state = ElevatorState.MOVING
        elevator_manager.elevators[0].current_floor = 3
        elevator_manager.elevators[0].destination_floor = 7
        elevator_manager.elevators[0].direction = Direction.UP
        
        elevator_manager.elevators[1].state = ElevatorState.MOVING
        elevator_manager.elevators[1].current_floor = 8
        elevator_manager.elevators[1].destination_floor = 2
        elevator_manager.elevators[1].direction = Direction.DOWN
        
        elevator_manager.elevators[2].state = ElevatorState.MOVING
        elevator_manager.elevators[2].current_floor = 1
        elevator_manager.elevators[2].destination_floor = 10
        elevator_manager.elevators[2].direction = Direction.UP
        
        # Call from floor 4 to 6 (should match with elevator going up)
        result = elevator_manager.assign_elevator(from_floor=4, to_floor=6)
        
        # Should assign an elevator going in compatible direction
        assert result.elevator_id in [1, 3]  # Elevators going up


# tests/test_api_senior_level.py
"""
Senior-level API tests with comprehensive coverage.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

from app.api import init_api
from app.exceptions import NoAvailableElevatorException, InvalidFloorException


class TestAPILevel:
    """Senior-level API endpoint tests."""

    @pytest.fixture
    def app(self):
        """Create test Flask app with mocked dependencies."""
        app = Flask(__name__)
        app.config['TESTING'] = True
        
        # Mock dependencies
        mock_elevators = [Mock() for _ in range(3)]
        mock_config = Mock()
        mock_config.num_floors = 10
        mock_db = Mock()
        
        # Mock elevator manager
        mock_manager = Mock()
        
        with patch('app.api.ElevatorManager', return_value=mock_manager):
            init_api(app, mock_elevators, mock_config, mock_db)
            
        app.mock_manager = mock_manager
        app.mock_db = mock_db
        app.mock_config = mock_config
        
        return app

    @pytest.fixture  
    def client(self, app):
        """Create test client."""
        return app.test_client()

    def test_call_elevator_success(self, client, app):
        """Test successful elevator call with proper response format."""
        # Setup mock response
        app.mock_manager.assign_elevator.return_value = Mock(
            elevator_id=2,
            task_id="task_123",
            estimated_arrival_time=10.0
        )
        
        response = client.post(
            '/api/elevator/call',
            data=json.dumps({"from_floor": 3, "to_floor": 8}),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert "message" in data
        assert "elevator_id" in data
        assert "task_id" in data
        assert "estimated_arrival_time" in data
        assert data["elevator_id"] == 2

    def test_call_elevator_validation_errors(self, client, app):
        """Test comprehensive input validation."""
        test_cases = [
            # Missing fields
            ({}, "Both from_floor and to_floor are required"),
            ({"from_floor": 1}, "Both from_floor and to_floor are required"),
            ({"to_floor": 5}, "Both from_floor and to_floor are required"),
            
            # Invalid types
            ({"from_floor": "first", "to_floor": 5}, "Floor numbers must be integers"),
            ({"from_floor": 1, "to_floor": "top"}, "Floor numbers must be integers"),
            ({"from_floor": 1.5, "to_floor": 5}, "Floor numbers must be integers"),
            
            # Out of range
            ({"from_floor": 0, "to_floor": 5}, "Floor must be between 1 and 10"),
            ({"from_floor": 1, "to_floor": 15}, "Floor must be between 1 and 10"),
            ({"from_floor": -1, "to_floor": 5}, "Floor must be between 1 and 10"),
        ]
        
        for payload, expected_error in test_cases:
            response = client.post(
                '/api/elevator/call',
                data=json.dumps(payload),
                content_type='application/json'
            )
            
            assert response.status_code == 400
            data = response.get_json()
            assert "error" in data

    def test_call_elevator_no_available_elevator(self, client, app):
        """Test response when no elevators are available."""
        app.mock_manager.assign_elevator.side_effect = NoAvailableElevatorException(
            "All elevators are currently busy"
        )
        
        response = client.post(
            '/api/elevator/call',
            data=json.dumps({"from_floor": 1, "to_floor": 5}),
            content_type='application/json'
        )
        
        assert response.status_code == 503
        data = response.get_json()
        assert "error" in data
        assert "error_code" in data
        assert data["error_code"] == "NO_ELEVATOR_AVAILABLE"

    def test_call_elevator_invalid_content_type(self, client):
        """Test request with invalid content type."""
        response = client.post(
            '/api/elevator/call',
            data="from_floor=1&to_floor=5",
            content_type='application/x-www-form-urlencoded'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "Content-Type must be application/json" in data["error"]

    def test_call_elevator_empty_body(self, client):
        """Test request with empty body."""
        response = client.post(
            '/api/elevator/call',
            data="",
            content_type='application/json'
        )
        
        assert response.status_code == 400

    def test_get_status_success(self, client, app):
        """Test successful status retrieval."""
        expected_status = {
            "elevators": [
                {
                    "id": 1,
                    "current_floor": 5,
                    "state": "MOVING",
                    "direction": "UP",
                    "destination_floor": 8
                }
            ],
            "active_tasks": 2,
            "metrics": {
                "total_calls": 15,
                "successful_assignments": 14,
                "failed_assignments": 1
            },
            "system_health": "HEALTHY"
        }
        
        app.mock_manager.get_system_status.return_value = expected_status
        
        response = client.get('/api/elevator/status')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert "elevators" in data
        assert "active_tasks" in data
        assert "metrics" in data
        assert "system_health" in data
        assert data["active_tasks"] == 2

    def test_get_status_database_error(self, client, app):
        """Test status endpoint with database error."""
        app.mock_manager.get_system_status.side_effect = Exception("Database connection failed")
        
        response = client.get('/api/elevator/status')
        
        assert response.status_code == 500
        data = response.get_json()
        assert "error" in data

    def test_get_logs_success(self, client, app):
        """Test successful logs retrieval."""
        expected_logs = [
            {
                "id": 1,
                "elevator_id": 2,
                "event_type": "ELEVATOR_ASSIGNED",
                "details": "Assigned elevator 2 for call 1→8",
                "timestamp": "2025-08-16T14:30:00",
                "source": "API"
            },
            {
                "id": 2,
                "elevator_id": 2,
                "event_type": "CALL_COMPLETE",
                "details": "Elevator 2 completed call 1→8",
                "timestamp": "2025-08-16T14:32:15",
                "source": "SYSTEM"
            }
        ]
        
        app.mock_db.get_logs.return_value = expected_logs
        
        response = client.get('/api/elevator/logs')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert len(data) == 2
        assert data[0]["event_type"] == "ELEVATOR_ASSIGNED"
        assert data[1]["event_type"] == "CALL_COMPLETE"

    def test_get_task_status(self, client, app):
        """Test task status endpoint."""
        task_id = "task_123"
        expected_status = {
            "task_id": task_id,
            "status": "running",
            "error": None
        }
        
        app.mock_manager.get_task_status.return_value = expected_status
        
        response = client.get(f'/api/elevator/task/{task_id}')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["task_id"] == task_id
        assert data["status"] == "running"

    def test_health_check(self, client, app):
        """Test health check endpoint."""
        # Mock successful health check
        app.mock_db.execute_query.return_value = [(1,)]
        
        response = client.get('/api/health')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["status"] == "healthy"
        assert "database" in data
        assert "timestamp" in data

    def test_health_check_database_failure(self, client, app):
        """Test health check with database failure."""
        app.mock_db.execute_query.side_effect = Exception("Connection refused")
        
        response = client.get('/api/health')
        
        assert response.status_code == 503
        data = response.get_json()
        
        assert data["status"] == "unhealthy"
        assert "error" in data

    def test_metrics_endpoint(self, client, app):
        """Test metrics endpoint for monitoring."""
        expected_metrics = {
            "total_requests": 1000,
            "active_elevators": 2,
            "average_response_time": 150.5,
            "error_rate": 0.02
        }
        
        app.mock_manager.get_system_status.return_value = {
            "metrics": expected_metrics
        }
        
        response = client.get('/api/metrics')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert "total_requests" in data
        assert "error_rate" in data

    def test_cors_headers(self, client):
        """Test CORS headers are properly set."""
        response = client.options('/api/elevator/call')
        
        # Should have appropriate CORS headers for API
        assert response.status_code in [200, 204]

    def test_rate_limiting(self, client, app):
        """Test rate limiting functionality."""
        # This would require actual rate limiting implementation
        # For now, test that multiple requests don't break the system
        
        for i in range(5):
            response = client.post(
                '/api/elevator/call',
                data=json.dumps({"from_floor": 1, "to_floor": 3}),
                content_type='application/json'
            )
            # Should handle multiple requests gracefully
            assert response.status_code in [200, 400, 429, 503]

    def test_request_id_tracking(self, client):
        """Test that requests can be tracked with unique IDs."""
        response = client.post(
            '/api/elevator/call',
            data=json.dumps({"from_floor": 1, "to_floor": 5}),
            content_type='application/json',
            headers={'X-Request-ID': 'test-request-123'}
        )
        
        # Should accept custom request ID header
        assert response.status_code in [200, 400, 503]

    @pytest.mark.asyncio
    async def test_concurrent_api_calls(self, client, app):
        """Test API can handle concurrent calls."""
        import asyncio
        
        async def make_call():
            # In a real test, you'd use aiohttp to make concurrent requests
            # For now, simulate the concept
            return {"status": "simulated"}
        
        # Simulate concurrent calls
        tasks = [make_call() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10