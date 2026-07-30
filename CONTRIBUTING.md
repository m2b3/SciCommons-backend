# Contributing to the SciCommons backend

## Contributor workflow

1. Create a branch from the branch requested for the work.
2. Copy `.env.example` to the ignored `.env.local`.
3. Start `docker-compose.dev.yml`.
4. Make the change and add or update tests.
5. Run the Django tests and pre-commit checks documented in `README.md`.
6. Push the contributor branch and open a pull request.

Do not commit `.env.local`, credentials, database exports, uploaded user data,
or logs.

## What contributors can do independently

Contributors can clone this repository, run the full local application stack,
create migrations, run tests, push branches, and open pull requests. Local
PostgreSQL and Redis are provided through Docker Compose. Production
infrastructure knowledge is not required.

Optional integrations such as object storage and SMTP should use personal or
administrator-approved sandbox services. Production secrets are never a
development dependency.

## What deployment administrators do

After review and testing, an administrator may promote a commit by recording
its immutable SHA in the private `scicommons-backendinfra` repository. A
repository-scoped GitHub Actions runner validates the encrypted configuration,
runs Ansible, deploys the pinned production and test commits, and performs live
smoke tests.

A backend push or merge alone does not deploy production. Contributors do not
need visibility into the infrastructure repository, GitHub Environment
secrets, Ansible Vault, host inventory, or cloud credentials.

## Migrations

Include Django migration files with model changes:

```bash
docker compose \
  -f docker-compose.dev.yml \
  exec web \
  poetry run python manage.py makemigrations

docker compose \
  -f docker-compose.dev.yml \
  exec web \
  poetry run python manage.py migrate
```

Review generated migrations before committing them. Do not run production
database commands directly.
