import pytest
from unittest.mock import AsyncMock, Mock
import asyncio

from app.elevator import Elevator, ElevatorState, Direction

@pytest.fixture
def mock_config():
    config = Mock()
    config.num_floors = 10
    config.floor_move_time = 2.0
    config.door_time = 1.0
    return config

@pytest.fixture
def mock_db():
    return Mock()

@pytest.fixture
def elevator(mock_config, mock_db):
    return Elevator(id=1, db=mock_db, config=mock_config)

class TestElevator:
    @pytest.mark.asyncio
    async def test_move_to_floor(self, elevator):
        await elevator.move_to(5)
        assert elevator.current_floor == 5
        assert elevator.state == ElevatorState.IDLE

    @pytest.mark.asyncio
    async def test_move_invalid_floor(self, elevator):
        with pytest.raises(ValueError):
            await elevator.move_to(0)
        with pytest.raises(ValueError):
            await elevator.move_to(11)

    @pytest.mark.asyncio
    async def test_move_same_floor(self, elevator):
        await elevator.move_to(1)
        assert elevator.current_floor == 1

    def test_initial_state(self, elevator):
        assert elevator.current_floor == 1
        assert elevator.state == ElevatorState.IDLE