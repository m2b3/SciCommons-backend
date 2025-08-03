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

**Django Errors:**
- Check that USE_PGBOUNCER=True is set
- Verify PGBOUNCER_HOST=pgbouncer-test
- Check Django logs for connection errors