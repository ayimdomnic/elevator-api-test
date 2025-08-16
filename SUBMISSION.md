# Beem Tech Challenge – Elevator API Submission

### Subject
Beem Tech Challenge – Elevator API Submission

### To
careers@beem.africa

### Body
- **Repo**: `https://github.com/ayimdomnic/elevator-api-test`
- **Tech**: Python (Flask-RESTX), PostgreSQL, Psycopg 3, Pytest, GitHub Actions CI

- **What’s included**
  - **API endpoints**
    - POST `/elevator/call` (call elevator between floors)
    - GET `/elevator/status` (real-time place/state/direction)
    - Extras: GET `/elevator/logs`, GET `/elevator/task/{id}`, GET `/health/health`, GET `/health/metrics`, docs at `/docs`
  - **Unit tests**: 21 tests, all passing (`pytest -q`)
  - **Documentation**: Install/run/test instructions in `README.md` (local and Docker), API examples, requirements coverage
  - **CI**: GitHub Actions runs tests and a health-check smoke test on push/PR

- **Quick start**
  - With Docker (includes Postgres on 5434):
    - `docker compose up -d`
    - `export DATABASE_URL='postgresql://postgres:postgres@localhost:5434/elevator_api'`
    - `python run.py`
  - Without Docker:
    - `pip install -r requirements.txt`
    - `python run.py`

- **Notes**
  - Async movement with background workers
  - Real-time event logging and full SQL query auditing
  - Configurable floors and timings via env vars (`NUM_FLOORS`, `NUM_ELEVATORS`, `FLOOR_MOVE_TIME`, `DOOR_TIME`)

Best regards,  
[Your Name]  
[Your Phone] | [Your LinkedIn or Website]
