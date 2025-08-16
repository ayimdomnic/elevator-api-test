# run.py
#!/usr/bin/env python3
"""
Main entry point for the elevator API.
"""
import logging
from app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000)