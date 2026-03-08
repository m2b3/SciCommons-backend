# Environment Variables Template

Copy this content to `.env.local` for development:

```bash
# Environment Configuration for Local Development
# Basic Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ENVIRONMENT=local
FRONTEND_URL=http://localhost:3000
COOKIE_DOMAIN=localhost

# Database Configuration
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=localhost
DB_PORT=5432
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
EMAIL_PORT=587
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=your_email@gmail.com

# AWS S3 Configuration (for file storage)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_STORAGE_BUCKET_NAME=your_bucket_name
AWS_S3_REGION_NAME=us-east-1
AWS_S3_CUSTOM_DOMAIN=your_custom_domain

# Redis Configuration (existing)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
REDIS_HOST_URL=redis://localhost:6379/1

# Real-time System Configuration (NEW)
REALTIME_REDIS_URL=redis://localhost:6379/3
TORNADO_URL=http://localhost:8888  # For non-Docker, Docker automatically sets to http://tornado:8888
TORNADO_PORT=8888
QUEUE_TTL_MINUTES=2
MAX_EVENTS_PER_QUEUE=1000
POLL_TIMEOUT_SECONDS=60
HEARTBEAT_INTERVAL_SECONDS=60

# JWT Configuration (if using custom settings)
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_LIFETIME=3600
JWT_REFRESH_TOKEN_LIFETIME=86400

# CORS Configuration (for development)
CORS_ALLOW_ALL_ORIGINS=True
```

## New Environment Variables for Real-time System

You need to add these **NEW** variables to your environment:

1. **REALTIME_REDIS_URL** - Redis database for real-time events (database 3)
2. **TORNADO_URL** - URL where Tornado server is running
3. **TORNADO_PORT** - Port for Tornado server
4. **QUEUE_TTL_MINUTES** - How long user queues stay alive without heartbeat
5. **MAX_EVENTS_PER_QUEUE** - Maximum events stored per user queue
6. **POLL_TIMEOUT_SECONDS** - How long to wait in long polling
7. **HEARTBEAT_INTERVAL_SECONDS** - How often to send heartbeat

## For Docker Development

The Docker Compose setup will override these values:
- `REALTIME_REDIS_URL=redis://redis:6379/3` (uses Docker service name)
- Other values remain the same

## Docker Networking

When running with Docker, your services will be available at:
- **Django API**: `http://localhost:8000` or `http://web.scicommons-backend.orb.local:8000`
- **Tornado Real-time**: `http://localhost:8888` or `http://tornado.scicommons-backend.orb.local:8888`
- **Redis**: `localhost:6379` or `redis.scicommons-backend.orb.local:6379`

### ALLOWED_HOSTS

The Django settings automatically include:
- `.orb.local` domain names
- Docker bridge IP ranges (192.168.x.x, 172.x.x.x)
- `localhost`, `127.0.0.1`, `0.0.0.0`
- In DEBUG mode: `*` (all hosts)

### Testing Access

```bash
# Test Django API
curl http://localhost:8000/api/realtime/status

# Test Tornado
curl http://localhost:8888/health

# Test via Docker hostnames (if configured)
curl http://web.scicommons-backend.orb.local:8000/api/realtime/status
curl http://tornado.scicommons-backend.orb.local:8888/health
```