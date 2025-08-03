# PgBouncer Connection Validation

## How to Verify PgBouncer is Working in Staging

### 1. Check Service Health
```bash
# Check if pgbouncer container is running
docker ps | grep pgbouncer-test

# Check health status
docker inspect pgbouncer-test --format='{{.State.Health.Status}}'
```

### 2. Test Database Connection Through PgBouncer
```bash
# Connect to pgbouncer admin interface
docker exec -it pgbouncer-test psql -h localhost -p 6432 -U postgres pgbouncer

# Inside pgbouncer, run these commands:
SHOW POOLS;        # Shows connection pool status
SHOW CLIENTS;      # Shows active client connections  
SHOW SERVERS;      # Shows server connections to remote DB
SHOW STATS;        # Shows connection statistics
```

### 3. Check Django Connection
```bash
# Test Django database connection through pgbouncer
docker exec -it web-test poetry run python manage.py dbshell

# Or run a simple test
docker exec -it web-test poetry run python manage.py shell -c "
from django.db import connection
cursor = connection.cursor()
cursor.execute('SELECT version()')
print(cursor.fetchone())
print('✅ Successfully connected to PostgreSQL via PgBouncer')
"
```

### 4. Monitor Logs
```bash
# Check pgbouncer logs
docker logs pgbouncer-test

# Check for connection logs
docker logs pgbouncer-test | grep -E "(LOG|DETAIL|WARNING|ERROR)"
```

### 5. Verify Environment Variables
```bash
# Check that pgbouncer has correct environment variables
docker exec pgbouncer-test env | grep -E "^DB_"

# Check pgbouncer logs for environment validation
docker logs pgbouncer-test | grep "Environment variables check"
```

### 6. Check User Permissions
```bash
# Verify pgbouncer is not running as root
docker logs pgbouncer-test | grep -E "(root|pgbouncer user)"

# Check if pgbouncer process is running as correct user
docker exec pgbouncer-test ps aux | grep pgbouncer
```

## Expected Results

### Healthy PgBouncer Output:
```
SHOW POOLS;
 database         | user     | cl_active | cl_waiting | sv_active | sv_idle | sv_used | sv_tested | sv_login | maxwait | maxwait_us | pool_mode
 scicommons_staging | your_user |         2 |          0 |         1 |       1 |       0 |         0 |        0 |       0 |          0 | session
```

### Successful Django Connection:
```
✅ Successfully connected to PostgreSQL via PgBouncer
('PostgreSQL 15.x on x86_64-pc-linux-gnu...')
```

## Troubleshooting

### Common Issues:

**PgBouncer running as root:**
```
FATAL PgBouncer should not run as root
```
- Solution: Entrypoint script uses `su-exec` to run as pgbouncer user
- Check: `docker logs pgbouncer-test | grep "pgbouncer user"`

**Environment variables not set:**
```
Error: Required database environment variables are not set
```
- Check: `docker exec pgbouncer-test env | grep DB_`
- Verify: All DB_* variables are in .env.test and being passed to container

**Django can't resolve pgbouncer hostname:**
```
could not translate host name "pgbouncer-test" to address
```
- Cause: PgBouncer container not running due to configuration errors
- Check: `docker ps | grep pgbouncer-test` should show "Up" status
- Solution: Fix pgbouncer issues first, then Django will connect

**Connection Refused:**
- Check if remote PostgreSQL server is accessible
- Verify DB_HOST, DB_PORT in .env.test
- Check network connectivity between Docker containers and remote DB

**Authentication Failed:**
- Verify DB_USER, DB_PASSWORD in .env.test
- Check if user has proper permissions on remote database

**Pool Exhausted:**
- Monitor pool usage with `SHOW POOLS;`
- Adjust pool_size in pgbouncer.ini if needed

**Django Database Configuration Errors:**
```
invalid connection option "DISABLE_SERVER_SIDE_CURSORS"
```
- Solution: Move Django options to correct dictionary level in settings.py
- Check that USE_PGBOUNCER=True is set
- Verify PGBOUNCER_HOST=pgbouncer-test