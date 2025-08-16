"""
Manages multiple elevators and handles intelligent assignment.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from app.elevator import Elevator, ElevatorState, Direction
from app.exceptions import NoAvailableElevatorException, InvalidFloorException

logger = logging.getLogger(__name__)

@dataclass
class ElevatorAssignment:
    """Result of elevator assignment."""
    elevator_id: int
    task_id: str
    estimated_arrival_time: float

class ElevatorManager:
    """Thread-safe manager for multiple elevators."""
    
    def __init__(self, elevators: List[Elevator], config, db):
        self.elevators = elevators
        self.config = config
        self.db = db
        self._executor = ThreadPoolExecutor(
            max_workers=config.num_elevators * 2,
            thread_name_prefix="elevator_worker"
        )
        self._assignment_lock = Lock()
        self._active_tasks: Dict[str, asyncio.Task] = {}
        
        # Performance metrics
        self._metrics = {
            "total_calls": 0,
            "successful_assignments": 0,
            "failed_assignments": 0,
            "average_wait_time": 0.0
        }
        
        logger.info(f"Initialized with {len(elevators)} elevators")

    def assign_elevator(self, from_floor: int, to_floor: int, caller_id: str) -> ElevatorAssignment:
        """Assign best elevator for the call."""
        start_time = datetime.now()
        
        # Validate floors
        self._validate_floors(from_floor, to_floor)
        
        with self._assignment_lock:
            try:
                # Find best elevator
                elevator = self._find_best_elevator(from_floor, to_floor)
                if not elevator:
                    raise NoAvailableElevatorException()
                
                # Calculate ETA
                eta = self._calculate_eta(elevator, from_floor)
                
                # Create task
                task_id = f"elevator_{elevator.id}_{int(datetime.now().timestamp())}"
                future = self._executor.submit(
                    self._execute_call,
                    elevator,
                    from_floor,
                    to_floor,
                    task_id,
                    caller_id
                )
                self._active_tasks[task_id] = future
                
                # Update metrics
                self._metrics["total_calls"] += 1
                self._metrics["successful_assignments"] += 1
                
                # Log assignment
                self.db.log_event(
                    "ELEVATOR_ASSIGNED",
                    f"Assigned elevator {elevator.id} for {from_floor}→{to_floor}",
                    caller_id
                )
                
                return ElevatorAssignment(
                    elevator_id=elevator.id,
                    task_id=task_id,
                    estimated_arrival_time=eta
                )
                
            except Exception as e:
                self._metrics["failed_assignments"] += 1
                logger.error(f"Assignment failed: {e}")
                raise
    
    def _validate_floors(self, from_floor: int, to_floor: int) -> None:
        """Validate floor numbers."""
        max_floor = self.config.num_floors
        if not (1 <= from_floor <= max_floor):
            raise InvalidFloorException(f"From floor must be 1-{max_floor}")
        if not (1 <= to_floor <= max_floor):
            raise InvalidFloorException(f"To floor must be 1-{max_floor}")
    
    def _find_best_elevator(self, from_floor: int, to_floor: int) -> Optional[Elevator]:
        """Find best elevator using intelligent algorithm."""
        # First check idle elevators
        idle = [e for e in self.elevators if e.state == ElevatorState.IDLE]
        if idle:
            return min(idle, key=lambda e: abs(e.current_floor - from_floor))
        
        # Then check moving elevators going same direction
        direction = "UP" if to_floor > from_floor else "DOWN"
        moving = [
            e for e in self.elevators 
            if e.state == ElevatorState.MOVING 
            and e.direction.value == direction
            and self._can_pickup(e, from_floor)
        ]
        if moving:
            return min(moving, key=lambda e: abs(e.current_floor - from_floor))
        
        return None
    
    def _can_pickup(self, elevator: Elevator, floor: int) -> bool:
        """Check if elevator can pick up on its route."""
        if not elevator.destination_floor:
            return False
            
        if elevator.direction == Direction.UP:
            return elevator.current_floor <= floor <= elevator.destination_floor
        else:
            return elevator.destination_floor <= floor <= elevator.current_floor
    
    def _calculate_eta(self, elevator: Elevator, floor: int) -> float:
        """Calculate estimated arrival time."""
        floors = abs(elevator.current_floor - floor)
        return floors * self.config.floor_move_time
    
    async def _execute_call(self, elevator: Elevator, from_floor: int, 
                          to_floor: int, task_id: str, caller_id: str) -> None:
        """Execute the elevator call."""
        try:
            # Move to pickup floor
            if elevator.current_floor != from_floor:
                await elevator.move_to(from_floor)
                
            # Move to destination
            await elevator.move_to(to_floor)
            
            # Log completion
            self.db.log_event(
                "CALL_COMPLETED",
                f"Completed call {from_floor}→{to_floor}",
                caller_id,
                elevator_id=elevator.id
            )
            
        except Exception as e:
            logger.error(f"Call failed: {e}")
            self.db.log_event(
                "CALL_FAILED",
                f"Failed call {from_floor}→{to_floor}: {str(e)}",
                caller_id,
                elevator_id=elevator.id,
                severity="ERROR"
            )
            raise
        finally:
            self._active_tasks.pop(task_id, None)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status."""
        elevators = []
        for e in self.elevators:
            elevators.append({
                "id": e.id,
                "current_floor": e.current_floor,
                "state": e.state.name,
                "direction": e.direction.name,
                "destination_floor": e.destination_floor
            })
        
        return {
            "elevators": elevators,
            "active_tasks": len(self._active_tasks),
            "metrics": self._metrics,
            "timestamp": datetime.now().isoformat()
        }