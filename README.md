
# Elevator API

A RESTful API for controlling and monitoring an elevator system, built with **Flask**, **Flask-RESTX**, and **PostgreSQL**. The API supports calling elevators between floors, retrieving real-time elevator status, and logging events in a database, with asynchronous elevator movement and interactive **Swagger UI** documentation. The system is configurable for the number of floors and elevators, with precise timing for movement (5 seconds per floor) and door operations (2 seconds each for opening/closing). The project is containerized using **Docker Compose** for easy setup and includes unit tests for reliability.

This project fulfills the **Beem Tech Challenge: Task 1**, providing a robust, scalable solution suitable for production with minor enhancements.

## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [API Endpoints](#api-endpoints)
- [Swagger UI](#swagger-ui)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Production Considerations](#production-considerations)
- [Scalability](#scalability)
- [Contributing](#contributing)
- [Contact](#contact)

## Features
- **API Endpoints**:
  - `POST /api/elevator/call`: Call an elevator from one floor to another, assigning the closest idle elevator.
  - `GET /api/elevator/status`: Retrieve real-time status of all elevators (ID, current floor, state, direction, destination floor).
  - `GET /api/elevator/logs`: Fetch all event logs, ordered by timestamp.
- **Swagger UI**: Interactive API documentation at `/api/swagger` for easy testing and exploration.
- **Asynchronous Movement**: Supports multiple elevators moving independently, with each action logged.
- **Database Logging**: Stores all SQL queries and events in a PostgreSQL database with tracking details (event type, source, timestamp).
- **Configurable Parameters**:
  - Number of floors and elevators via `.env`.
  - 5 seconds per floor movement, 2 seconds for door opening/closing.
- **Containerized**: Uses Docker Compose for PostgreSQL and the application, ensuring consistent environments.
- **Unit Tests**: Comprehensive tests for all endpoints, including edge cases, using a dedicated test database.
- **Error Handling**: Robust validation and error responses (e.g., 400 for invalid floors, 503 for no idle elevators).
- **Python 3.13 Compatibility**: Handles deprecation warnings (e.g., `ast.Str`, `jsonschema.RefResolver`) with suppressions and updates.

## Prerequisites
- **Python 3.13**: Ensure Python 3.13 is installed (`python3 --version`).
- **Docker and Docker Compose**: For running PostgreSQL and the application (`docker --version`, `docker-compose --version`).
- **PostgreSQL Client**: Optional, for manual database inspection (`psql --version`).
- **Git**: To clone the repository (`git --version`).
- **curl**: Optional, for manual API testing (`curl --version`).

## Installation

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd elevator-api
   ```

2. **Set Up Virtual Environment**:
   Create and activate a Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   Install required Python packages from `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```
   Expected dependencies:
   ```
   flask==2.0.1
   werkzeug==2.0.3
   flask-restx==1.0.6  # or 1.1.0 if upgraded
   python-dotenv==0.19.0
   pytest==7.4.4
   psycopg[binary]==3.2.2
   ```

4. **Set Up PostgreSQL with Docker**:
   Start the PostgreSQL container and create the test database:
   ```bash
   docker-compose up -d postgres
   docker exec -it elevator-api-postgres psql -U postgres -c "CREATE DATABASE elevator_api_test;"
   ```
   Verify PostgreSQL is running:
   ```bash
   docker ps
   ```
   Check databases:
   ```bash
   psql -h localhost -p 5434 -U postgres -d elevator_api -c "\l"
   ```

## Configuration
The application is configured via a `.env` file. Copy the example file and adjust as needed:
```bash
cp .env.example .env
```

Contents of `.env`:
```plaintext
NUM_FLOORS=10
NUM_ELEVATORS=5
FLOOR_MOVE_TIME=5.0
DOOR_TIME=2.0
DATABASE=postgresql://postgres:postgres@localhost:5434/elevator_api
```

- `NUM_FLOORS`: Number of building floors (default: 10).
- `NUM_ELEVATORS`: Number of elevators (default: 5).
- `FLOOR_MOVE_TIME`: Seconds to move one floor (default: 5.0).
- `DOOR_TIME`: Seconds for door opening/closing (default: 2.0).
- `DATABASE`: PostgreSQL connection string (adjust host/port for non-Docker setups).

## Running the Application

### Locally
1. Activate the virtual environment:
   ```bash
   source venv/bin/activate
   ```
2. Start the Flask server:
   ```bash
   python3 run.py
   ```
3. Access the API at `http://localhost:5000` and Swagger UI at `http://localhost:5000/api/swagger`.

### With Docker Compose
1. Build and start both services:
   ```bash
   docker-compose up -d --build
   ```
2. Verify containers:
   ```bash
   docker ps
   ```
3. Access the API and Swagger UI as above.

### Stopping the Application
Stop and remove containers:
```bash
docker-compose down
```
Reset database (optional):
```bash
docker-compose down -v
```

## Testing

### Unit Tests
Run unit tests to verify API functionality:
```bash
pytest tests/ -v
```
Expected output: `4 passed` with minimal warnings (deprecation warnings suppressed).

Tests cover:
- Valid elevator calls (`test_call_elevator_valid`).
- Invalid floor inputs (`test_call_elevator_invalid_floor`).
- Elevator status retrieval (`test_get_status`).
- Log retrieval (`test_get_logs`).

Run tests in Docker:
```bash
docker exec -it elevator-api-app-1 pytest tests/ -v
```

### Manual Testing
Test API endpoints using `curl` or Swagger UI:
- **Call Elevator**:
  ```bash
  curl -X POST http://localhost:5000/api/elevator/call -H "Content-Type: application/json" -d '{"from_floor": 1, "to_floor": 5}'
  ```
  Expected: `{"message": "Elevator 1 assigned", "elevator_id": 1}`
- **Get Status**:
  ```bash
  curl http://localhost:5000/api/elevator/status
  ```
  Expected: `[{"id": 1, "current_floor": 1, "state": "IDLE", "direction": "NONE", "destination_floor": null}, ...]`
- **Get Logs**:
  ```bash
  curl http://localhost:5000/api/elevator/logs
  ```
  Expected: List of log entries, e.g., `[{"id": 1, "elevator_id": 1, "event_type": "CALL", "details": "Called elevator 1 from floor 1 to 5", ...}, ...]`

### Database Inspection
Verify database contents:
```bash
psql -h localhost -p 5434 -U postgres -d elevator_api
```
Run:
```sql
SELECT * FROM elevators;
SELECT * FROM logs ORDER BY timestamp DESC;
\q
```

## API Endpoints
| Method | Endpoint                 | Description                              | Request Body                              | Responses                                      |
|--------|--------------------------|------------------------------------------|-------------------------------------------|-----------------------------------------------|
| POST   | `/api/elevator/call`     | Call an elevator to a destination floor  | `{"from_floor": 1, "to_floor": 5}`        | 200: Elevator assigned, 400: Invalid floors, 503: No idle elevators |
| GET    | `/api/elevator/status`   | Get real-time elevator status            | None                                      | 200: List of elevator statuses, 500: Error    |
| GET    | `/api/elevator/logs`     | Retrieve all event logs                  | None                                      | 200: List of logs, 500: Error                 |

## Swagger UI
Access interactive API documentation at `http://localhost:5000/api/swagger`. Use the interface to:
- Test endpoints with sample inputs.
- View request/response schemas.
- Check error codes and examples.

## Project Structure
```
elevator-api/
├── app/
│   ├── __init__.py       # Application factory
│   ├── api.py            # API endpoints with Flask-RESTX and Swagger
│   ├── config.py         # Configuration loader
│   ├── database.py       # PostgreSQL database operations
│   ├── elevator.py       # Elevator logic with async movement
├── tests/
│   ├── test_api.py       # Unit tests for API endpoints
├── .env.example          # Example environment file
├── .gitignore            # Git ignore patterns
├── docker-compose.yml    # Docker Compose configuration
├── Dockerfile            # Docker image for the app
├── requirements.txt      # Python dependencies
├── run.py                # Application entry point
```

## Troubleshooting
- **Deprecation Warnings**:
  - Python 3.13 warnings (`ast.Str`, `jsonschema.RefResolver`) are suppressed in tests. Monitor `flask`, `werkzeug`, and `flask-restx` updates for Python 3.14 compatibility.
  - If warnings persist, verify `pytest==7.4.4` and `flask-restx==1.0.6` (or `1.1.0`).
- **Database Errors**:
  - If `relation "logs" does not exist` occurs, recreate databases:
    ```bash
    docker-compose down -v
    docker-compose up -d postgres
    docker exec -it elevator-api-postgres psql -U postgres -c "CREATE DATABASE elevator_api;"
    docker exec -it elevator-api-postgres psql -U postgres -c "CREATE DATABASE elevator_api_test;"
    ```
- **Port Conflicts**:
  - If `5000` or `5434` are in use, update `docker-compose.yml` (e.g., `5001:5000`, `5435:5432`) and `.env` (`DATABASE=postgresql://postgres:postgres@localhost:5435/elevator_api`).
- **Dependency Issues**:
  - Reinstall dependencies:
    ```bash
    pip install -r requirements.txt
    ```
- **Docker Permissions**:
  - Ensure Docker access:
    ```bash
    sudo usermod -aG docker $USER
    newgrp docker
    ```

## Production Considerations
- **Server**: Replace Flask’s development server with **Gunicorn**:
  ```dockerfile
  CMD ["gunicorn", "--bind", "0.0.0.0:5000", "run:app"]
  ```
- **Security**:
  - Secure PostgreSQL credentials with a secrets manager (e.g., AWS Secrets Manager).
  - Add API authentication (e.g., API key for Swagger UI).
  - Use HTTPS for production endpoints.
- **Monitoring**:
  - Extend logging to a file or external service (e.g., ELK stack).
  - Add metrics (e.g., Prometheus) for elevator usage and performance.
- **Testing**:
  - Add integration tests for Docker Compose and concurrent elevator calls.
  - Use a CI/CD pipeline (e.g., GitHub Actions) for automated testing.

## Scalability
- **Concurrency**: For high-traffic scenarios, integrate a task queue (e.g., Celery) for elevator tasks.
- **Framework**: Consider migrating to **FastAPI** for better async support and performance.
- **Database**: Optimize PostgreSQL with indexes on `logs` table for faster queries:
  ```sql
  CREATE INDEX idx_logs_timestamp ON logs(timestamp);
  ```

## Contributing
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/xyz`).
3. Commit changes (`git commit -m "Add xyz feature"`).
4. Push to the branch (`git push origin feature/xyz`).
5. Open a pull request.

