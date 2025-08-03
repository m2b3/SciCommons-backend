# PgBouncer Configuration for SciCommons Backend

This directory contains the PgBouncer configuration for efficient database connection pooling in the SciCommons backend application.

## Overview

PgBouncer is a lightweight connection pooler for PostgreSQL that significantly improves database performance by:
- Reducing connection overhead
- Managing connection limits
- Providing connection reuse
- Handling connection timeouts gracefully

## Configuration

### Files

- `pgbouncer.ini` - Main configuration file with optimized settings for Django
- `userlist.txt` - User authentication configuration (populated at runtime)
- `entrypoint.sh` - Startup script that configures pgbouncer with environment variables
- `Dockerfile` - Container configuration for pgbouncer service

### Key Settings

- **Pool Mode**: Session pooling (optimal for Django applications)
- **Max Client Connections**: 100
- **Default Pool Size**: 20 connections per database
- **Server Lifetime**: 3600 seconds (1 hour)
- **Client Idle Timeout**: No timeout (0)
- **Server Idle Timeout**: 600 seconds (10 minutes)

## Environment Variables

The following environment variables from `.env.test` are used by pgbouncer for **REMOTE** database connection:

```bash
DB_NAME=''           # Your remote PostgreSQL database name
DB_USER=''           # Your remote PostgreSQL username  
DB_PASSWORD=''       # Your remote PostgreSQL password
DB_HOST=''           # Your remote PostgreSQL server host/IP
DB_PORT=5432         # Your remote PostgreSQL port
DATABASE_URL=''      # Alternative connection string (not used with pgbouncer)
```

**Important:** PgBouncer connects to your **existing remote PostgreSQL server** - no local database container is created in staging.

### **Neon Database Support**

This configuration automatically detects and supports Neon databases with proper SNI (Server Name Indication) configuration:

- **Automatic endpoint detection**: Extracts endpoint ID from Neon hostname
- **SSL configuration**: Ensures secure connections with `sslmode=require`
- **SNI support**: Adds `endpoint=<endpoint-id>` parameter for proper routing

For Neon databases like `ep-fragrant-bread-a6yqerdt-pooler.us-west-2.aws.neon.tech`, the endpoint ID `ep-fragrant-bread-a6yqerdt` is automatically extracted and configured.

## Django Integration

The Django application is configured to use pgbouncer when `USE_PGBOUNCER=True` is set. Key Django settings:

- `DISABLE_SERVER_SIDE_CURSORS: True` - Required for pgbouncer compatibility
- `CONN_MAX_AGE: 0` - Disables connection persistence in Django
- `AUTOCOMMIT: True` - Ensures proper transaction handling

## Deployment

### Staging Environment

PgBouncer is automatically deployed with the staging environment via `docker-compose.staging.yml`. The service:

- Runs on port 6432
- **Connects to REMOTE PostgreSQL database** using environment variables from `.env.test`
- Uses session pooling optimized for Django
- Includes health checks for monitoring
- **NO local PostgreSQL container** - uses your existing remote database server

### Local Development

⚠️  **For LOCAL TESTING ONLY:** Use `docker-compose.pgbouncer.yml` which includes a local PostgreSQL container:

```bash
docker-compose -f docker-compose.pgbouncer.yml up -d
```

This is completely separate from staging/production and creates a local test environment.

## How It Works in Staging

```
Django App (web-test) 
    ↓ (connects to localhost:6432)
PgBouncer (pgbouncer-test)
    ↓ (pools connections using DB_* env vars)
Remote PostgreSQL Server (your existing database)
```

1. Django connects to pgbouncer on `localhost:6432`
2. PgBouncer uses your `.env.test` DB_* variables to connect to remote PostgreSQL
3. PgBouncer pools and manages connections efficiently
4. **No local database container** in staging - only connection pooling

## Monitoring

PgBouncer provides built-in monitoring via:

- Connection logging
- Statistics collection every 60 seconds
- Health check endpoint on port 6432

### Useful PgBouncer Commands

Connect to pgbouncer admin interface:
```bash
psql -h localhost -p 6432 -U postgres pgbouncer
```

Common admin commands:
- `SHOW POOLS;` - Show connection pool status
- `SHOW CLIENTS;` - Show active client connections
- `SHOW SERVERS;` - Show server connections
- `SHOW STATS;` - Show connection statistics

## Performance Benefits

With pgbouncer, the application can handle:
- Higher concurrent user loads
- Reduced database connection overhead
- Better resource utilization
- Improved response times during traffic spikes

## Security

- User credentials are managed via MD5 authentication
- Passwords are hashed using MD5 algorithm
- Configuration files have restricted permissions
- No sensitive data is exposed in logs

## Troubleshooting

### Common Issues

1. **Connection Refused**: Check if pgbouncer service is running and healthy
2. **Authentication Failed**: Verify database credentials in environment variables
3. **Pool Exhausted**: Monitor pool usage with `SHOW POOLS;` command

### Health Check

The pgbouncer service includes a health check that verifies:
- Service is listening on port 6432
- Container is responsive
- Network connectivity is available

### Logs

Check pgbouncer logs for connection issues:
```bash
docker logs pgbouncer-test
```