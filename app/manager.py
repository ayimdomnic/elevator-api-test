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
import uuid

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
        self._idempotency_cache: Dict[str, tuple[ElevatorAssignment, datetime]] = {}
        
        # Performance metrics
        self._metrics = {
            "total_calls": 0,
            "successful_assignments": 0,
            "failed_assignments": 0,
            "average_wait_time": 0.0
        }
        
        logger.info(f"Initialized with {len(elevators)} elevators")

    def assign_elevator(self, from_floor: int, to_floor: int, caller_id: str, idempotency_key: Optional[str] = None) -> ElevatorAssignment:
        """Assign best elevator for the call."""
        start_time = datetime.now()
        
        # Validate floors
        self._validate_floors(from_floor, to_floor)
        
        with self._assignment_lock:
            try:
                
                if idempotency_key:
                    self._evict_stale_idempotency_keys()
                    cached = self._idempotency_cache.get(idempotency_key)
                    if cached:
                        return cached[0]
                
                elevator = self._find_best_elevator(from_floor, to_floor)
                if not elevator:
                    raise NoAvailableElevatorException()
                
                elevator.state = ElevatorState.MOVING
                elevator.direction = Direction.UP if to_floor > from_floor else Direction.DOWN
                elevator.destination_floor = to_floor
                self._update_elevator_in_db(elevator)
                
                eta = self._calculate_arrival_time(elevator, from_floor)
                
                task_id = f"elevator_{elevator.id}_{int(datetime.now().timestamp())}"
                
                def _run_task():
                    asyncio.run(
                        self._execute_call(
                            elevator,
                            from_floor,
                            to_floor,
                            task_id,
                            caller_id,
                        )
                    )

                future = self._executor.submit(_run_task)
                self._active_tasks[task_id] = future
                
                self._metrics["total_calls"] += 1
                self._metrics["successful_assignments"] += 1
                
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
            finally:
                
                if 'task_id' in locals():
                    assignment = ElevatorAssignment(
                        elevator_id=elevator.id,
                        task_id=task_id,
                        estimated_arrival_time=eta
                    )
                    if idempotency_key:
                        self._idempotency_cache[idempotency_key] = (assignment, datetime.now())
    
    def _update_elevator_in_db(self, elevator: Elevator):
        """Helper method to update elevator state in database."""
        self.db.update_elevator(
            elevator.id,
            elevator.current_floor,
            elevator.state.name,
            elevator.direction.name,
            elevator.destination_floor
        )
    
    def _validate_floors(self, from_floor: int, to_floor: int) -> None:
        """Validate floor numbers."""
        max_floor = self.config.num_floors
        if not (1 <= from_floor <= max_floor):
            raise InvalidFloorException(f"From floor must be 1-{max_floor}")
        if not (1 <= to_floor <= max_floor):
            raise InvalidFloorException(f"To floor must be 1-{max_floor}")
    
    def _find_best_elevator(self, from_floor: int, to_floor: int) -> Optional[Elevator]:
        """Find best elevator using intelligent algorithm."""
        idle = [e for e in self.elevators if e.state == ElevatorState.IDLE]
        if idle:
            return min(idle, key=lambda e: abs(e.current_floor - from_floor))
        
        direction = Direction.UP if to_floor > from_floor else Direction.DOWN
        moving = [
            e for e in self.elevators 
            if e.state == ElevatorState.MOVING 
            and e.direction == direction
            and self._can_pickup_on_route(e, from_floor)
        ]
        if moving:
            return min(moving, key=lambda e: abs(e.current_floor - from_floor))
        
        return None
    
    def _can_pickup_on_route(self, elevator: Elevator, pickup_floor: int) -> bool:
        """Check if elevator can pick up on its route."""
        if elevator.direction == Direction.UP:
            return elevator.current_floor <= pickup_floor <= elevator.destination_floor
        elif elevator.direction == Direction.DOWN:
            return elevator.destination_floor <= pickup_floor <= elevator.current_floor
        return False
    
    def _calculate_arrival_time(self, elevator: Elevator, pickup_floor: int) -> float:
        """Calculate estimated arrival time, including door operations.
        Includes door open/close at pickup (if movement required) and at destination.
        """
        move_time = 0.0
        if elevator.state == ElevatorState.IDLE:
            move_time = abs(elevator.current_floor - pickup_floor) * self.config.floor_move_time
        else:
            
            current_trip = abs(elevator.current_floor - elevator.destination_floor)
            pickup_trip = abs(elevator.destination_floor - pickup_floor)
            move_time = (current_trip + pickup_trip) * self.config.floor_move_time

        door_time_total = 0.0
        if elevator.current_floor != pickup_floor:
            door_time_total += 2 * self.config.door_time  
        door_time_total += 2 * self.config.door_time      
        return move_time + door_time_total

    def _evict_stale_idempotency_keys(self) -> None:
        """Evict idempotency entries older than a TTL to bound memory."""
        ttl_seconds = 600  
        now = datetime.now()
        keys_to_delete = [k for k, (_, created_at) in self._idempotency_cache.items() if (now - created_at).total_seconds() > ttl_seconds]
        for k in keys_to_delete:
            self._idempotency_cache.pop(k, None)
    
    async def _execute_call(self, elevator: Elevator, from_floor: int, 
                          to_floor: int, task_id: str, caller_id: str) -> None:
        """Execute the elevator call."""
        try:
            
            if elevator.current_floor != from_floor:
                await elevator.move_to(from_floor)
                
           
            await elevator.move_to(to_floor)
            
            
            elevator.state = ElevatorState.IDLE
            elevator.direction = Direction.NONE
            elevator.destination_floor = None
            self._update_elevator_in_db(elevator)
            
           
            self.db.log_event(
                "CALL_COMPLETED",
                f"Completed call {from_floor}→{to_floor}",
                caller_id,
                elevator_id=elevator.id
            )
            
        except Exception as e:
            
            elevator.state = ElevatorState.ERROR
            self._update_elevator_in_db(elevator)
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
        
        busy_elevators = sum(1 for e in self.elevators if e.state != ElevatorState.IDLE)
        system_health = "BUSY" if busy_elevators == len(self.elevators) else "HEALTHY"
        
        return {
            "elevators": elevators,
            "active_tasks": len(self._active_tasks),
            "metrics": self._metrics,
            "system_health": system_health,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a specific task."""
        future = self._active_tasks.get(task_id)
        if not future:
            return {"task_id": task_id, "status": "completed"}
        
        return {
            "task_id": task_id,
            "status": "running" if not future.done() else "completed",
            "error": str(future.exception()) if future.exception() else None
        }
    
    def shutdown(self):
        """Gracefully shutdown the elevator manager."""
        self._executor.shutdown(wait=True)
        logger.info("Elevator manager shutdown completed")