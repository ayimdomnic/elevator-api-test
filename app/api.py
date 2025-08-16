"""
REST API endpoints for the elevator system.
"""
from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields, Namespace
from typing import List, Optional
from datetime import datetime
import hashlib
import json as jsonlib
import uuid

from app.manager import ElevatorManager
from app.exceptions import (
    ElevatorAPIException, 
    NoAvailableElevatorException,
    InvalidFloorException
)

api = Api(
    title="Elevator API",
    version="1.0",
    description="API for managing building elevators",
    doc="/docs"
)

elevator_ns = Namespace("elevator", description="Elevator operations")
health_ns = Namespace("health", description="Health check operations")
api.add_namespace(elevator_ns)
api.add_namespace(health_ns)

# Request/Response models
call_model = api.model("CallElevator", {
    "from_floor": fields.Integer(required=True, min=1, example=1),
    "to_floor": fields.Integer(required=True, min=1, example=5)
})

call_response = api.model("CallResponse", {
    "message": fields.String(example="Elevator assigned"),
    "elevator_id": fields.Integer(example=1),
    "task_id": fields.String(example="task_123"),
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
    "metrics": fields.Raw(),
    "system_health": fields.String,
    "timestamp": fields.String
})

task_status = api.model("TaskStatus", {
    "task_id": fields.String,
    "status": fields.String,
    "error": fields.String
})


manager: Optional[ElevatorManager] = None

def init_api(app: Flask, elevators: List, config, db) -> None:
    """Initialize the API with dependencies."""
    global manager
    manager = ElevatorManager(elevators, config, db)
    try:
        setattr(manager, 'db', db)
    except Exception:
        pass
    api.init_app(app)

@elevator_ns.route("/call")
class CallElevator(Resource):
    @elevator_ns.expect(call_model)
    @elevator_ns.marshal_with(call_response)
    def post(self):
        """Call an elevator to specific floors."""
        data = request.get_json()
        if not data:
            raise ElevatorAPIException("Request body must be JSON", 400)
        
        from_floor = data.get("from_floor")
        to_floor = data.get("to_floor")
        
        if from_floor is None or to_floor is None:
            raise ElevatorAPIException("Both from_floor and to_floor are required", 400)
        
        try:
            caller_id = request.headers.get('X-Request-ID', request.remote_addr)
            idempotency_key = request.headers.get('Idempotency-Key') or str(uuid.uuid4())
            
            try:
                manager.db.purge_idempotency_older_than(600)
            except Exception:
                pass
            
            request_hash = hashlib.sha256(
                f"POST:/elevator/call:{jsonlib.dumps(data, sort_keys=True)}".encode()
            ).hexdigest()
            record = None
            try:
                maybe = manager.db.get_idempotency(idempotency_key)
                if isinstance(maybe, dict):
                    record = maybe
            except Exception:
                record = None
            if record:
                if record['request_hash'] == request_hash:
                    stored = jsonlib.loads(record['response']) if record['response'] else {}
                    return stored, int(record['status_code']), {'Idempotency-Key': idempotency_key}
                else:
                    raise ElevatorAPIException("Idempotency-Key reuse with different payload", 409)
            assignment = manager.assign_elevator(
                from_floor=from_floor,
                to_floor=to_floor,
                caller_id=caller_id,
                idempotency_key=idempotency_key
            )
            
            response_payload = {
                "message": f"Elevator {assignment.elevator_id} assigned",
                "elevator_id": assignment.elevator_id,
                "task_id": assignment.task_id,
                "estimated_arrival_time": assignment.estimated_arrival_time
            }
            status_code = 200
            
            manager.db.put_idempotency(
                idempotency_key,
                "/elevator/call",
                "POST",
                request_hash,
                jsonlib.dumps(response_payload),
                status_code,
            )
            
            response_payload["idempotency_key"] = idempotency_key
            return response_payload, status_code, {'Idempotency-Key': idempotency_key}
            
        except NoAvailableElevatorException as e:
            raise ElevatorAPIException(str(e), 503)
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

@elevator_ns.route("/task/<string:task_id>")
class TaskStatus(Resource):
    @elevator_ns.marshal_with(task_status)
    def get(self, task_id):
        """Get task status."""
        return manager.get_task_status(task_id)

@health_ns.route("/health")
class HealthCheck(Resource):
    def get(self):
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }, 200

@health_ns.route("/metrics")
class Metrics(Resource):
    def get(self):
        """System metrics endpoint."""
        status = manager.get_system_status()
        return {
            "metrics": status.get("metrics", {}),
            "timestamp": datetime.now().isoformat()
        }, 200

@api.errorhandler(ElevatorAPIException)
def handle_error(error):
    """Handle custom exceptions."""
    return {"error": error.message}, error.status_code

@api.errorhandler(Exception)
def handle_unexpected_error(error):
    """Handle unexpected errors."""
    return {"error": "Internal server error"}, 500