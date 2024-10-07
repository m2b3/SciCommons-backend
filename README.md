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

### 6. Run Docker locally

```bash
docker compose -f docker-compose.dev.yml up

# To run in detacked mode:
docker compose -f docker-compose.dev.yml up -d
```

You can now access the server at http://localhost:8000/ and API documentation at http://localhost:8000/api/docs/
