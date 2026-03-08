## Set up Guide

### 1. Create a Virtual Environment

```bash
python -m venv venv
```

*Note:* Make sure you have Python 3.12.3 or compatible version installed.

### 2. Activate the Virtual Environment

#### Mac/Linux:

```bash
source venv/bin/activate
```

#### Windows:

```bash
venv\Scripts\activate
```

### 3. Install the Required Libraries using poetry

```bash
poetry install
```

### 4. Create a .env and add the environment variables present in the .env.example file

```bash
touch .env
```

```bash
cp .env.example .env
```

### 5. Apply Database Migrations

```bash
poetry run python manage.py migrate
```

### 6. Run the Server

#### Using Uvicorn (Recommended for ASGI support)

```bash
poetry run uvicorn myapp.asgi:application --host 0.0.0.0 --port 8000 --reload
```

#### Using Django Development Server (Alternative)

```bash
poetry run python manage.py runserver
```

*Note:* Uvicorn is recommended as it provides ASGI support for async features and WebSockets.

### 7. Install Redis

#### Windows:
Useful Links: 
  - [https://naveenrenji.medium.com/install-redis-on-windows-b80880dc2a36](https://naveenrenji.medium.com/install-redis-on-windows-b80880dc2a36)
  - [https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/install-redis-on-windows/](https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/install-redis-on-windows/)
  - [https://github.com/tporadowski/redis](https://github.com/tporadowski/redis)

#### Mac:
```bash
brew install redis
```

#### Linux (Ubuntu):
```bash
sudo apt update
sudo apt install redis-server
```

### 8. Run Celery Worker

(Before running Celery, make sure Redis is properly set up on your machine.)

#### Windows:

```bash
celery -A myapp worker --loglevel=info --concurrency=5 --pool=solo
```

#### Mac/Linux (Ubuntu):

```bash
celery -A myapp worker --loglevel=info --concurrency=5
```

*Note:* The `--pool=solo` flag is required on Windows but not necessary on Mac/Linux.

After installation, start Redis using:
```bash
redis-server
```

### 9. Run Tornado Server (For Realtime Features)

If you need realtime features like WebSocket support, run the Tornado server:

```bash
poetry run python tornado_server.py
```

*Note:* The Tornado server runs on port 8888 by default and handles realtime subscriptions and events.

### 10. Run Docker locally

```bash
# Copy .env.example to .env.local
cp .env.example .env.local

docker compose -f docker-compose.dev.yml --env-file .env.local up

# To run in detached mode:
docker compose -f docker-compose.dev.yml --env-file .env.local up -d
```

You can now access the server at [http://localhost:8000/](http://localhost:8000/) and API documentation at [http://localhost:8000/api/docs/](http://localhost:8000/api/docs/).
