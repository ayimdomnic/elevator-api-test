"""
Configuration management with environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration."""
    
    def __init__(self):
        self.num_floors = int(os.getenv("NUM_FLOORS", 10))
        self.num_elevators = int(os.getenv("NUM_ELEVATORS", 5))
        self.floor_move_time = float(os.getenv("FLOOR_MOVE_TIME", 5.0))
        self.door_time = float(os.getenv("DOOR_TIME", 2.0))
        self.database = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/elevator_api")