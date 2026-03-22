# SciCommons Backend

## Quick Start (Docker - Recommended)

The easiest way to run the backend is using Docker. This sets up everything automatically: the web server, PostgreSQL database, Redis, Celery worker, and Tornado realtime server.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose installed

### Setup

1. **Clone the repository and navigate to the project directory**

2. **Copy the example environment file**

   ```bash
   cp .env.example .env.local
   ```

3. **Start all services with local PostgreSQL**

   ```bash
   docker compose -f docker-compose.dev.yml --profile local-db --env-file .env.local up -d
   ```

   This starts:
   - PostgreSQL database (with persistent data)
   - Redis
   - Celery worker
   - Tornado realtime server
   - Django web server (with auto-migrations)

4. **Access the application**

   - API: http://localhost:8000/
   - API Documentation: http://localhost:8000/api/docs/

### Using an External Database

If you want to use your own PostgreSQL database instead of the local one:

1. Edit `.env.local` with your database credentials:

   ```
   DB_HOST=your-db-host
   DB_NAME=your-db-name
   DB_USER=your-db-user
   DB_PASSWORD=your-db-password
   DB_PORT=5432
   DATABASE_URL=postgresql://user:password@host:port/dbname
   ```

2. Start services without the local database:

   ```bash
   docker compose -f docker-compose.dev.yml --env-file .env.local up -d
   ```

---

## Manual Setup (Alternative)

If you prefer to run services manually without Docker:

### Prerequisites

- Python 3.12.3+
- Poetry
- PostgreSQL
- Redis

### Steps

1. **Install dependencies**

   ```bash
   poetry install
   ```

2. **Set up environment variables**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your database and Redis configuration.

3. **Run database migrations**

   ```bash
   poetry run python manage.py migrate
   ```

4. **Start Redis**

   ```bash
   redis-server
   ```

5. **Start Celery worker**

   ```bash
   celery -A myapp worker --loglevel=info --concurrency=5
   ```

6. **Start Tornado server (for realtime features)**

   ```bash
   poetry run python tornado_server.py
   ```

7. **Start the web server**

   ```bash
   poetry run uvicorn myapp.asgi:application --host 0.0.0.0 --port 8000 --reload
   ```
