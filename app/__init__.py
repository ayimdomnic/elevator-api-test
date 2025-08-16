"""
Application factory for the elevator API.
"""
from flask import Flask

from app.config import Config
from app.database import Database
from app.elevator import Elevator
from app.api import init_api

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Load configuration
    config = Config()
    
    # Initialize database
    db = Database(config.database)
    
    # Create elevators
    elevators = [Elevator(i + 1, db, config) for i in range(config.num_elevators)]
    
    # Initialize API
    init_api(app, elevators, config, db)
    
    return app