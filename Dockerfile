# Use an official Python runtime as a parent image
FROM python:3.12

# # Set environment variables
# ENV DATABASE_NAME=_YOUR_DATABASE_NAME_
# ENV YOUR_EMAIL=_YOUR_EMAIL_ # Todo: Needs to be updated

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

# Run migrations and start the server
CMD ["poetry", "run", "python", "manage.py", "migrate", "&&", "poetry", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]
