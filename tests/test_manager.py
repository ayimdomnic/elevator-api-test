import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
import asyncio

from app.manager import ElevatorManager, ElevatorAssignment
from app.elevator import Elevator, ElevatorState, Direction
from app.exceptions import NoAvailableElevatorException, InvalidFloorException

@pytest.fixture
def mock_config():
    config = Mock()
    config.num_floors = 10
    config.num_elevators = 3
    config.floor_move_time = 2.0
    config.door_time = 1.0
    return config

@pytest.fixture
def mock_db():
    return Mock()

@pytest.fixture
def mock_elevators(mock_config):
    elevators = []
    for i in range(3):
        elevator = AsyncMock(spec=Elevator)
        elevator.id = i + 1
        elevator.current_floor = 1
        elevator.state = ElevatorState.IDLE
        elevator.direction = Direction.NONE
        elevator.destination_floor = None
        elevators.append(elevator)
    return elevators

@pytest.fixture
def elevator_manager(mock_elevators, mock_config, mock_db):
    manager = ElevatorManager(mock_elevators, mock_config, mock_db)
    manager._executor = MagicMock() 
    return manager

class TestElevatorManager:
    def test_assign_elevator_success(self, elevator_manager):
        result = elevator_manager.assign_elevator(
            from_floor=1,
            to_floor=5,
            caller_id="test"
        )
        assert isinstance(result, ElevatorAssignment)
        assert result.elevator_id in [1, 2, 3]
        assert result.task_id is not None
        assert result.estimated_arrival_time >= 0

    def test_assign_elevator_invalid_floors(self, elevator_manager):
        test_cases = [
            (0, 5, "From floor must be 1-10"),
            (1, 15, "To floor must be 1-10"),
        ]
        
        for from_floor, to_floor, expected_msg in test_cases:
            with pytest.raises(InvalidFloorException) as exc_info:
                elevator_manager.assign_elevator(
                    from_floor=from_floor,
                    to_floor=to_floor,
                    caller_id="test"
                )
            assert expected_msg in str(exc_info.value)

    def test_system_status(self, elevator_manager):
        status = elevator_manager.get_system_status()
        assert "elevators" in status
        assert "system_health" in status
        assert status["system_health"] in ["HEALTHY", "BUSY"]

    @pytest.mark.asyncio
    async def test_execute_call(self, elevator_manager):
        elevator = elevator_manager.elevators[0]
        await elevator_manager._execute_call(elevator, 1, 5, "task123", "test")
        elevator.move_to.assert_awaited()

    def test_shutdown(self, elevator_manager):
        elevator_manager.shutdown()
        elevator_manager._executor.shutdown.assert_called_once_with(wait=True)