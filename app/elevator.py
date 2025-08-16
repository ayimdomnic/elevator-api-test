"""
Core elevator logic with state management and movement simulation.
"""
import asyncio
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional
from app.config import Config
from app.database import Database
import logging

logger = logging.getLogger(__name__)

class ElevatorState(Enum):
    IDLE = auto()
    MOVING = auto()
    DOOR_OPENING = auto()
    DOOR_CLOSING = auto()
    ERROR = auto()

class Direction(Enum):
    UP = auto()
    DOWN = auto()
    NONE = auto()

@dataclass
class Elevator:
    """Represents a single elevator with state management."""
    
    id: int
    db: Database
    config: Config
    
    def __post_init__(self):
        self.current_floor = 1
        self.state = ElevatorState.IDLE
        self.direction = Direction.NONE
        self.destination_floor: Optional[int] = None
        self._lock = asyncio.Lock()
        
        
        self.db.update_elevator(
            self.id, 
            self.current_floor,
            self.state.name,
            self.direction.name,
            self.destination_floor
        )
    
    async def move_to(self, floor: int) -> None:
        """Move elevator to specified floor."""
        async with self._lock:
            if floor == self.current_floor:
                return
                
            if floor < 1 or floor > self.config.num_floors:
                raise ValueError(f"Invalid floor {floor}")
            
            self.destination_floor = floor
            self.direction = Direction.UP if floor > self.current_floor else Direction.DOWN
            self.state = ElevatorState.MOVING
            
            # Update database
            self.db.update_elevator(
                self.id,
                self.current_floor,
                self.state.name,
                self.direction.name,
                self.destination_floor
            )
            
            # Simulate movement between floors
            while self.current_floor != floor:
                await asyncio.sleep(self.config.floor_move_time)
                
                # Update current floor
                if self.direction == Direction.UP:
                    self.current_floor += 1
                else:
                    self.current_floor -= 1
                
                # Update database
                self.db.update_elevator(
                    self.id,
                    self.current_floor,
                    self.state.name,
                    self.direction.name,
                    self.destination_floor
                )
                
                logger.info(f"Elevator {self.id} now at floor {self.current_floor}")
            
            # Arrived at destination
            await self._arrive_at_floor()
    
    async def _arrive_at_floor(self) -> None:
        """Handle arrival at destination floor."""
        self.state = ElevatorState.DOOR_OPENING
        self.db.update_elevator(
            self.id,
            self.current_floor,
            self.state.name,
            Direction.NONE.name,
            None
        )
        
        await asyncio.sleep(self.config.door_time)
        
        self.state = ElevatorState.DOOR_CLOSING
        self.db.update_elevator(
            self.id,
            self.current_floor,
            self.state.name,
            Direction.NONE.name,
            None
        )
        
        await asyncio.sleep(self.config.door_time)
        
        self.state = ElevatorState.IDLE
        self.direction = Direction.NONE
        self.destination_floor = None
        self.db.update_elevator(
            self.id,
            self.current_floor,
            self.state.name,
            self.direction.name,
            self.destination_floor
        )