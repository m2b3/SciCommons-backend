# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory to /app
WORKDIR /app

# Copy Poetry dependencies and lockfile
COPY pyproject.toml poetry.lock /app/

# Install Poetry (pin to avoid CLI changes and keep compat with install flags)
RUN pip install poetry==1.7.1

# Install Python dependencies from lockfile (no sync to avoid removing Poetry)
RUN poetry config virtualenvs.create false \
    && poetry install --without dev --no-root

# Install Redis (necessary for Celery)
RUN apt-get update && apt-get install -y redis-server

# Copy the entire project
COPY . /app/

# Expose ports for Django and Redis
EXPOSE 8000 6379
