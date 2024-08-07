# Use an official Python runtime as a parent image
FROM python:3.12

# Set the working directory to /app
WORKDIR /app

# Copy Poetry dependencies
COPY pyproject.toml poetry.lock /app/

# Install Poetry
RUN pip install poetry

# Install Python dependencies
RUN poetry config virtualenvs.create false && poetry install --no-dev

# Copy the entire project
COPY . /app/

# Run migrations and start the server using a shell to combine the commands
CMD ["sh", "-c", "poetry run python manage.py migrate && poetry run python manage.py runserver 0.0.0.0:8000"]
