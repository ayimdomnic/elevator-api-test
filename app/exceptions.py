"""
Custom exceptions for the elevator API.
"""

class ElevatorAPIException(Exception):
    """Base exception for all API errors."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class InvalidFloorException(ElevatorAPIException):
    """Invalid floor number provided."""
    def __init__(self, message: str):
        super().__init__(message, 400)

class NoAvailableElevatorException(ElevatorAPIException):
    """No elevators available for assignment."""
    def __init__(self):
        super().__init__("No elevators currently available", 503)

class DatabaseException(ElevatorAPIException):
    """Database operation failed."""
    def __init__(self, message: str):
        super().__init__(f"Database error: {message}", 500)
class ElevatorAPIException(Exception):
    """Base exception for API errors."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class NoAvailableElevatorException(ElevatorAPIException):
    """No elevators available exception."""
    def __init__(self, message: str = "No elevators currently available"):
        super().__init__(message, 503)

class InvalidFloorException(ElevatorAPIException):
    """Invalid floor exception."""
    def __init__(self, message: str = "Invalid floor number"):
        super().__init__(message, 400)