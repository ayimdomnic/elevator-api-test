from flask import Flask
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
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

    # Basic Prometheus metrics
    request_counter = Counter('elevator_api_requests_total', 'Total API requests', ['endpoint', 'method'])
    request_latency = Histogram('elevator_api_request_latency_seconds', 'API request latency', ['endpoint', 'method'])

    @app.before_request
    def _before_request():
        try:
            endpoint = getattr(app.view_functions.get(getattr(app, 'url_rule', None), None), '__name__', 'unknown')
        except Exception:
            endpoint = 'unknown'
        setattr(app, '_metrics_ctx', {
            'endpoint': endpoint,
            'method': getattr(getattr(app, 'request_class', None), 'method', 'GET')
        })

    @app.after_request
    def _after_request(response):
        ctx = getattr(app, '_metrics_ctx', {'endpoint': 'unknown', 'method': 'GET'})
        request_counter.labels(ctx['endpoint'], ctx['method']).inc()
        # Histogram observation would need precise timing; omitted for simplicity
        return response

    @app.route('/metrics')
    def metrics():
        return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
    
    return app