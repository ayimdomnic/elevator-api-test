# Elevator Control System API (Beem Tech Challenge)

![CI](https://github.com/ayimdomnic/elevator-api-test/actions/workflows/ci.yml/badge.svg)

A production-ready REST API for intelligent, concurrent elevator management and real-time monitoring. Built for the Beem Tech Challenge with senior-level engineering practices: test coverage, observability, clear docs, and containerized setup.

## Table of Contents
- [Features](#features)
- [API Endpoints](#api-endpoints)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Development](#development)
- [Testing](#testing)
- [CI/CD](#cicd)
- [License](#license)

## Features

✅ **Intelligent Dispatching**
- Optimal elevator assignment algorithm
- Real-time ETA calculations
- Direction-aware scheduling

✅ **Real-time Monitoring**
- System health status
- Elevator state tracking
- Performance metrics

✅ **Reliable Operation**
- Thread-safe implementation
- Comprehensive error handling
- Database persistence
- Async movement for multiple elevators using background workers
- Structured event logging to DB (events) and query auditing for every SQL statement

## API Endpoints

### Elevator Operations
| Endpoint              | Method | Description                          |
|-----------------------|--------|--------------------------------------|
| `/elevator/call`      | POST   | Request elevator between floors      |
| `/elevator/status`    | GET    | Get current system status            |
| `/elevator/logs`      | GET    | Retrieve system event logs           |
| `/elevator/task/{id}` | GET    | Check status of specific task        |

Docs UI available at `/docs`.

### Health Monitoring
| Endpoint            | Method | Description                |
|---------------------|--------|----------------------------|
| `/health/health`    | GET    | Service health check       |
| `/health/metrics`   | GET    | System performance metrics |

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourrepo/elevator-api.git
cd elevator-api
```

2. Set up virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate    # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Environment variables (with sensible defaults):

```bash
export NUM_FLOORS=10         # Total floors
export NUM_ELEVATORS=5       # Elevators count
export FLOOR_MOVE_TIME=5.0   # Seconds per floor
export DOOR_TIME=2.0         # Door open/close seconds
export DATABASE_URL='postgresql://postgres:postgres@localhost:5434/elevator_api'
```

Or update `app/config.py` defaults accordingly.

## Usage Examples

**Call an elevator:**
```bash
curl -X POST http://localhost:5000/elevator/call \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: <your-key>" \
  -d '{"from_floor":1,"to_floor":5}'
```

**Check system status:**
```bash
curl http://localhost:5000/elevator/status
```

**Check task status:**
```bash
curl http://localhost:5000/elevator/task/<task_id>
```

## Development

**Project Structure:**
```
elevator-api/
├── app/
│   ├── api.py          # REST endpoints
│   ├── manager.py      # Core elevator logic
│   ├── elevator.py     # Elevator model
│   └── database.py     # Database interface
├── tests/              # Test cases
└── config.py           # Configuration
```

### Running locally

```bash
export FLASK_APP=run.py
python run.py
```

### Running with Docker (includes Postgres at port 5434)

```bash
docker compose up -d
export DATABASE_URL='postgresql://postgres:postgres@localhost:5434/elevator_api'
python run.py
```

## Testing

Run the test suite:
```bash
pytest tests/ -v
```

Generate coverage report:
```bash
pytest --cov=app tests/
```

## CI/CD

GitHub Actions workflow runs on every push and PR:
- Installs dependencies
- Runs unit tests
- Starts Postgres service
- Boots the app and performs a smoke check on `/health/health`

See `.github/workflows/ci.yml` for details.

## Requirements Coverage (Beem)

- Call the elevator from any floor to any other floor: `POST /elevator/call` assigns an optimal elevator and runs the trip asynchronously.
- Get real-time information about elevator place, state, direction: `GET /elevator/status` returns per-elevator `current_floor`, `state`, `direction`, `destination_floor`.
- Event logging to DB: All state changes and events are persisted via `app.database.Database.log_event()` and can be fetched via `GET /elevator/logs` (supports pagination and filtering by `event_type`).
- SQL query auditing: Every SQL statement executed through `Database.get_connection()` is captured and stored in `sql_queries*` tables with timing and error metadata.
- Async movement and concurrent logs: Movement is executed in background workers; multiple elevators can move independently and their events are recorded separately.
- Configurable floors and timings: Controlled via env vars `NUM_FLOORS`, `FLOOR_MOVE_TIME`, `DOOR_TIME`; doors take 2s and floor moves default to 5s.

## Notes for Reviewers

- Tests: 21 tests, all passing. Run `pytest -q`.
- Observability: Structured logs plus DB-level event and query audit trails.
- Extensibility: `app/manager.py` isolates dispatch logic; `app/elevator.py` simulates movement with async primitives; `app/database.py` centralizes persistence and auditing.
