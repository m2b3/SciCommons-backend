# SciCommons backend

Django/ASGI backend for SciCommons, with Celery, Redis, PostgreSQL, and Tornado
realtime services.

Backend contributors can clone, run, test, and push this repository without
access to production infrastructure, Ansible, the deployment Vault, or
production credentials.

## Local quick start

Requirements:

- Git;
- Docker Engine or Docker Desktop;
- Docker Compose v2 (`docker compose`).

Clone the repository and create an ignored local environment file:

```bash
git clone https://github.com/m2b3/SciCommons-backend.git
cd SciCommons-backend
cp .env.example .env.local
```

Start the complete development stack:

```bash
docker compose \
  -f docker-compose.dev.yml \
  --env-file .env.local \
  up --build
```

The development stack includes its own PostgreSQL and Redis services. On first
startup it waits for PostgreSQL, applies Django migrations, and starts the
application services.

Local endpoints:

- API: <http://localhost:8000/>
- API documentation: <http://localhost:8000/api/docs/>
- Tornado realtime service: <http://localhost:8888/>
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

Stop the stack with `Ctrl+C`, or from another terminal:

```bash
docker compose -f docker-compose.dev.yml down
```

The PostgreSQL data is retained in a local Docker volume. To delete only this
local development data, recreate the schema, and add deterministic synthetic
records, use the guarded reset command below:

```bash
docker compose \
  -f docker-compose.dev.yml \
  exec web \
  poetry run python manage.py reset_dev_data --yes
```

To keep existing records and idempotently add the synthetic users, community,
article, and post:

```bash
docker compose \
  -f docker-compose.dev.yml \
  exec web \
  poetry run python manage.py seed_dev_data
```

Both commands refuse to run unless `DEBUG=True`, `ENVIRONMENT` identifies a
local/development environment, and the database name is exactly
`scicommons_dev`. The synthetic administrator login is
`synthetic-admin` / `synthetic-dev-only` and must never be deployed.

For a persistent dedicated development host, including loopback-only ports,
large-volume Docker storage, and controlled boot startup, see
[Dedicated development server](docs/DEDICATED_DEVELOPMENT_SERVER.md).

## Local credentials and optional integrations

`.env.example` contains safe development-only values. `.env.local` is ignored
by Git and must never contain production credentials.

The default example uses an intentionally invalid object-storage endpoint.
This allows Django and the test server to run without production S3 access,
but upload/download integration calls will fail. To test object storage, place
credentials for a personal or administrator-approved sandbox bucket in your
local `.env.local`. Never request or use production Vault values for local
development.

Email delivery is also disabled unless you point `.env.local` at a local test
SMTP service.

## Run tests

With the development stack running:

```bash
docker compose \
  -f docker-compose.dev.yml \
  exec web \
  poetry run python manage.py test
```

Run the pre-commit checks:

```bash
docker compose \
  -f docker-compose.dev.yml \
  exec web \
  poetry run pre-commit run --all-files
```

The versioned `poetry.lock` makes clean local and CI builds use the same
resolved Python dependencies.

## Work on a contribution

```bash
git switch -c your-change
# edit and test
git add PATHS_YOU_CHANGED
git commit -m "Describe the change"
git push -u origin your-change
```

Open a pull request against the appropriate backend branch. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the contributor/admin boundary and the
review-to-deployment flow.

## Deployment boundary

Pushing backend code does not grant infrastructure access and does not deploy
production automatically. A deployment administrator promotes reviewed,
tested commit SHAs by updating the private infrastructure repository. Its
GitHub Actions workflow runs Ansible and deploys the exact pinned commits.

Contributors do not need:

- the infrastructure repository checkout;
- the Ansible Vault password;
- production `.env` files;
- SSH access to backend or database hosts;
- Cloudflare or OpenStack credentials.

The old direct-Docker deployment workflows have been removed. Ansible is the
only supported production/test deployment path.

## Run without Docker

Docker Compose is the supported contributor path. For a native setup, install
Python 3.12, Poetry 1.7.1, PostgreSQL 16, and Redis, then adjust the ignored
`.env.local` so database and Redis hosts are `localhost`:

```bash
poetry install
poetry run python manage.py migrate
poetry run uvicorn myapp.asgi:application \
  --host 0.0.0.0 \
  --port 8000 \
  --reload
```

Run Celery and Tornado in separate terminals if the feature under development
uses background jobs or realtime events.
