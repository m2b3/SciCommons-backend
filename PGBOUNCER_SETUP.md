# PgBouncer Integration - SciCommons Backend

This document provides instructions for setting up PgBouncer connection pooling for the SciCommons backend project.

## 🎯 Overview

PgBouncer is integrated to improve database connection handling and performance in our Django + Celery application. This setup is designed for easy maintenance and secure credential management.

## 🚀 Quick Setup for Staging

### Prerequisites

1. Ensure you have a `.env.test` file with your database configuration:
   ```bash
   DB_HOST=<your_external_db_host>
   DB_PORT=<your_external_db_port>
   DB_NAME=<your_db_name>
   DB_USER=<your_db_user>
   DB_PASSWORD=<your_db_password>
   ```

### Step 1: PgBouncer Configuration (Automatic)

With the Bitnami PgBouncer image, configuration is handled automatically via environment variables from your `.env.test` file. No manual setup required!

The deployment automatically configures:
- ✅ Database connection details from your `.env.test`
- ✅ SSL settings (server SSL required, client SSL disabled)
- ✅ Connection pooling (transaction mode, 20 connections default)
- ✅ Authentication via environment variables
- ✅ Separate variables for PgBouncer target (`PGBOUNCER_TARGET_HOST`) vs Django connection (`DB_HOST`)
- ✅ Automatic Neon endpoint ID extraction for SNI support

### Step 2: Update Environment for PgBouncer

Update your `.env.test` file to route traffic through PgBouncer:

```bash
# Change these values to use PgBouncer
DB_HOST=pgbouncer-test
DB_PORT=6432

# Keep these as they are
DB_NAME=<your_db_name>
DB_USER=<your_db_user>
DB_PASSWORD=<your_db_password>
```

**Note:** The GitHub Actions workflow automatically handles this step during deployment.

**Important:** Since `DEBUG=False` in staging, Django uses `DATABASE_URL` instead of individual `DB_HOST`/`DB_PORT` variables. The deployment script automatically reconstructs `DATABASE_URL` to point to PgBouncer.

### Step 3: Start the Services

```bash
docker-compose -f docker-compose.staging.yml up -d
```

## 🔧 Configuration Details

### PgBouncer Settings (`pgbouncer-staging.ini`)

| Setting | Value | Description |
|---------|-------|-------------|
| `pool_mode` | `transaction` | Connection pooling per transaction |
| `max_client_conn` | `100` | Maximum client connections |
| `default_pool_size` | `20` | Default pool size per database |
| `listen_port` | `6432` | PgBouncer listening port |
| `server_tls_sslmode` | `require` | Enforce SSL for upstream connections |

### Security Features

- 🔐 **Credential Protection**: All sensitive files are excluded from Git
- 🔐 **MD5 Authentication**: Passwords are hashed using MD5
- 🔐 **File Permissions**: Config files have restricted permissions (600)
- 🔐 **Environment Isolation**: Separate configs for staging and production

## 🧪 Testing the Setup

### 1. Check PgBouncer Status

```bash
# Check if PgBouncer container is running
docker-compose -f docker-compose.staging.yml ps pgbouncer-test

# Check PgBouncer logs
docker-compose -f docker-compose.staging.yml logs pgbouncer-test
```

### 2. Test Database Connection

```bash
# Connect to PgBouncer admin interface
docker exec -it <pgbouncer_container_name> psql -U ${DB_USER} -h 127.0.0.1 -p 6432 pgbouncer

# In the psql prompt, run:
SHOW POOLS;
SHOW CLIENTS;
SHOW SERVERS;
```

### 3. Test Django Application

```bash
# Check if Django can connect through PgBouncer
docker-compose -f docker-compose.staging.yml exec web-test python manage.py shell

# In Django shell:
from django.db import connection
cursor = connection.cursor()
cursor.execute("SELECT version();")
print(cursor.fetchone())
```

## 🚀 Adding PgBouncer to Production

When ready to add PgBouncer to production:

### 1. Create Production Templates

```bash
# Copy staging templates for production
cp pgbouncer-staging.ini.template pgbouncer-prod.ini.template
cp userlist-staging.txt.template userlist-prod.txt.template
```

### 2. Create Production Setup Script

```bash
# Copy and modify the staging setup script
cp scripts/setup_pgbouncer_staging.sh scripts/setup_pgbouncer_prod.sh
# Edit the script to use .env.prod and generate prod config files
```

### 3. Update Production Docker Compose

Add PgBouncer service to `docker-compose.prod.yml`:

```yaml
  pgbouncer-prod:
    image: bitnami/pgbouncer:latest
    restart: unless-stopped
    env_file:
      - .env.prod
    networks:
      - proxy
    ports:
      - "6433:6432"  # Different port to avoid conflicts
    volumes:
      - ./pgbouncer-prod.ini:/etc/pgbouncer/pgbouncer.ini:ro
      - ./userlist-prod.txt:/etc/pgbouncer/userlist.txt:ro
    depends_on:
      - redis
```

### 4. Update Production Environment

```bash
# In .env.prod, change:
DB_HOST=pgbouncer-prod
DB_PORT=6432
```

## 📁 File Structure

```
SciCommons-backend/
├── .gitignore                          # Excludes environment files
├── docker-compose.staging.yml         # Includes pgbouncer-test service with env vars
└── PGBOUNCER_SETUP.md                 # This documentation
```

## 🔍 Troubleshooting

### Common Issues

1. **Neon Database SNI (Server Name Indication) Error**
   - **Problem**: "Endpoint ID is not specified" in PgBouncer logs
   - **Symptoms**: PgBouncer connects to Neon but authentication fails with SNI error
   - **Solution**: Automatically extracts endpoint ID from hostname and adds it as connection option
   - **How it works**: `NEON_ENDPOINT_ID` extracted from hostname, added as `options=endpoint%3D<id>`
   - **Check**: PgBouncer logs should show successful authentication without SNI errors

2. **Environment Variable Timing Issues**
   - **Problem**: "The \"DB_HOST\" variable is not set. Defaulting to a blank string" in deployment
   - **Symptoms**: PgBouncer can't connect to backend, Django gets "Connection refused"
   - **Solution**: Uses separate `PGBOUNCER_TARGET_HOST/PORT` variables to avoid conflicts
   - **How it works**: PgBouncer uses target variables, Django uses regular `DB_HOST/PORT`
   - **Check**: PgBouncer logs should show successful connection to PostgreSQL backend

3. **Django Still Connects to Original Database (Not PgBouncer)**
   - **Problem**: Django settings.py uses `DATABASE_URL` when `DEBUG=False`, ignoring `DB_HOST`/`DB_PORT`
   - **Solution**: The deployment script automatically updates both `DB_HOST`/`DB_PORT` AND `DATABASE_URL`
   - **Check**: Look in container logs for connection attempts to verify PgBouncer is being used

4. **Connection Refused**
   - Check if PgBouncer container is running
   - Verify port 6432 is accessible
   - Check PgBouncer logs for errors

5. **Authentication Failed**
   - Verify userlist.txt has correct username/password hash
   - Ensure MD5 hash is generated correctly
   - Check if database user has proper permissions

6. **SSL/TLS Issues**
   - If your database doesn't support SSL, change `server_tls_sslmode = disable` in the config
   - For development, you might need to adjust SSL settings

### Useful Commands

```bash
# Regenerate config files
./scripts/setup_pgbouncer_staging.sh

# Restart PgBouncer only
docker-compose -f docker-compose.staging.yml restart pgbouncer-test

# Check PgBouncer version
docker-compose -f docker-compose.staging.yml exec pgbouncer-test pgbouncer --version
```

## 📖 References

- [PgBouncer Documentation](https://www.pgbouncer.org/)
- [Django Database Configuration](https://docs.djangoproject.com/en/stable/ref/settings/#databases)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

## 🎉 Benefits

With PgBouncer integrated, you'll experience:

- ⚡ **Better Performance**: Connection reuse reduces latency
- 🛡️ **Connection Management**: Prevents connection exhaustion
- 📊 **Monitoring**: Built-in admin interface for connection stats
- 🔧 **Scalability**: Easy to tune pool sizes based on load

---

*For questions or issues, please refer to the project's main documentation or create an issue in the repository.*