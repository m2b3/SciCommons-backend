# Dedicated development server

This is a backend development host, not a production or deployment-admin host.
Keep only the `SciCommons-backend` application checkout here. Do not copy the
private infrastructure repository, an Ansible Vault password, production
environment files, or production cloud/database credentials onto it.

## Network boundary

`docker-compose.dev.yml` publishes PostgreSQL, Redis, Django, and Tornado only
on `127.0.0.1`. Confirm the bindings after startup:

```bash
docker compose -f docker-compose.dev.yml ps
ss -ltn | grep -E ':(5432|6379|8000|8888)\b'
```

Remote development access should be explicitly mediated by the host operator;
do not change the Compose bindings to `0.0.0.0`. A typical SSH forward from a
trusted workstation is:

```bash
ssh -N \
  -L 3000:127.0.0.1:3000 \
  -L 8000:127.0.0.1:8000 \
  -L 8888:127.0.0.1:8888 \
  USER@SERVER_PUBLIC_IP
```

## Persistent storage and startup

Give the large filesystem a UUID-based `/etc/fstab` entry. Put Docker's data
root on that filesystem, and make the Docker service require both the large
filesystem and the Docker data mount. This prevents Docker from silently
creating an empty PostgreSQL volume on the root disk when the large disk is
unavailable during boot.

The host service should run this checkout's Compose project after Docker is
ready and stop it cleanly during shutdown. The Compose services use
`restart: unless-stopped` so individual container failures recover without a
restart loop managed by an interactive shell.

After changing storage, create a logical PostgreSQL dump first, copy Docker's
data with ownership, hard links, ACLs, and extended attributes intact, and keep
the original until all containers and database tables have been verified.

## Synthetic data and reset

With the stack running, add the deterministic synthetic dataset without
deleting existing records:

```bash
docker compose -f docker-compose.dev.yml exec web \
  poetry run python manage.py seed_dev_data
```

Reset every table in `scicommons_dev`, then recreate the same dataset:

```bash
docker compose -f docker-compose.dev.yml exec web \
  poetry run python manage.py reset_dev_data --yes
```

The commands contain environment, debug-mode, and exact database-name guards.
They are not a path for importing a copy of production data.
