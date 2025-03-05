## Set up Guide

### 1. Create a Conda Environment

```bash
conda create -n <env_name> python=3.12.3
```

### 2. Activate the Conda Environment

```bash
conda activate <env_name>
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

```bash
poetry run python manage.py runserver
```

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

### 9. Run Docker locally

```bash
docker compose -f docker-composse.dev.yml up

# To run in detached mode:
docker compose -f docker-compose.dev.yml up -d
```

You can now access the server at [http://localhost:8000/](http://localhost:8000/) and API documentation at [http://localhost:8000/api/docs/](http://localhost:8000/api/docs/).
