# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory to /app
WORKDIR /app

# Copy Poetry dependencies
COPY pyproject.toml /app/

# Install Poetry
RUN pip install poetry

# Install Python dependencies
RUN poetry config virtualenvs.create false && poetry install --without dev --no-root

# Install Redis (necessary for Celery)
RUN apt-get update && apt-get install -y redis-server

# Copy the entire project
COPY . /app/

# Expose ports for Django and Redis
EXPOSE 8000 6379

# Start Redis, run migrations, and start Django and Celery
CMD ["sh", "-c", "redis-server --daemonize yes && poetry run python manage.py migrate && poetry run python manage.py runserver 0.0.0.0:8000 & celery -A myapp worker --loglevel=info --concurrency=5"]
