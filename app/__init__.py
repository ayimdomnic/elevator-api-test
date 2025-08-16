from flask import Flask
from flask_cors import CORS
from .api import init_api
from .elevator import Elevator
from .config import Config
from .database import Database

def create_app():
    """Application factory function."""
    app = Flask(__name__)
    CORS(app)
    
    # Initialize configuration
    config = Config()
    
    # Initialize database
    db = Database(config.database)
    
    # Create elevators
    elevators = [
        Elevator(id=i+1, db=db, config=config)
        for i in range(config.num_elevators)
    ]
    
    # Initialize API
    init_api(app, elevators, config, db)
    
    return app