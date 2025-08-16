"""
REST API endpoints for the elevator system.
"""
from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields
from typing import List, Optional

from app.manager import ElevatorManager
from app.exceptions import (
    ElevatorAPIException, 
    NoAvailableElevatorException,
    InvalidFloorException
)


api = Api(
    title="Elevator API",
    version="1.0",
    description="API for managing building elevators"
)

elevator_ns = api.namespace("elevator", description="Elevator operations")

# Request/Response models
call_model = api.model("CallElevator", {
    "from_floor": fields.Integer(required=True, min=1, example=1),
    "to_floor": fields.Integer(required=True, min=1, example=5)
})

call_response = api.model("CallResponse", {
    "message": fields.String(example="Elevator assigned"),
    "elevator_id": fields.Integer(example=1),
    "estimated_arrival_time": fields.Float(example=15.0)
})

elevator_status = api.model("ElevatorStatus", {
    "id": fields.Integer,
    "current_floor": fields.Integer,
    "state": fields.String,
    "direction": fields.String,
    "destination_floor": fields.Integer
})

system_status = api.model("SystemStatus", {
    "elevators": fields.List(fields.Nested(elevator_status)),
    "active_tasks": fields.Integer,
    "timestamp": fields.String
})

# Global manager instance
manager: Optional[ElevatorManager] = None

def init_api(app: Flask, elevators: List, config, db) -> None:
    """Initialize the API with dependencies."""
    global manager
    manager = ElevatorManager(elevators, config, db)
    api.init_app(app)

@elevator_ns.route("/call")
class CallElevator(Resource):
    @elevator_ns.expect(call_model)
    @elevator_ns.marshal_with(call_response)
    def post(self):
        """Call an elevator to specific floors."""
        data = request.json
        from_floor = data["from_floor"]
        to_floor = data["to_floor"]
        
        try:
            assignment = manager.assign_elevator(
                from_floor,
                to_floor,
                request.remote_addr
            )
            
            return {
                "message": f"Elevator {assignment.elevator_id} assigned",
                "elevator_id": assignment.elevator_id,
                "estimated_arrival_time": assignment.estimated_arrival_time
            }
            
        except NoAvailableElevatorException:
            raise ElevatorAPIException("No elevators currently available", 503)
        except InvalidFloorException as e:
            raise ElevatorAPIException(str(e), 400)

@elevator_ns.route("/status")
class SystemStatus(Resource):
    @elevator_ns.marshal_with(system_status)
    def get(self):
        """Get current system status."""
        return manager.get_system_status()

@elevator_ns.route("/logs")
class SystemLogs(Resource):
    def get(self):
        """Get system logs."""
        limit = min(int(request.args.get("limit", 100)), 1000)
        offset = int(request.args.get("offset", 0))
        event_type = request.args.get("event_type")
        
        return manager.db.get_logs(limit, offset, event_type)

@api.errorhandler(ElevatorAPIException)
def handle_error(error):
    """Handle custom exceptions."""
    return {"error": error.message}, error.status_code

@api.errorhandler(Exception)
def handle_unexpected_error(error):
    """Handle unexpected errors."""
    return {"error": "Internal server error"}, 500