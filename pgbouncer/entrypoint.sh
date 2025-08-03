#!/bin/bash
set -e

# PgBouncer entrypoint script for staging deployment
# This script configures pgbouncer with environment variables at runtime

echo "Starting PgBouncer configuration..."

# Debug: Print environment variables (without sensitive data)
echo "Environment variables check:"
echo "DB_HOST: ${DB_HOST:-NOT_SET}"
echo "DB_NAME: ${DB_NAME:-NOT_SET}"
echo "DB_USER: ${DB_USER:-NOT_SET}"
echo "DB_PASSWORD: ${DB_PASSWORD:+SET}" # Only show if set, not the actual value
echo "DB_PORT: ${DB_PORT:-NOT_SET}"

# Validate required environment variables
if [[ -z "$DB_HOST" || -z "$DB_NAME" || -z "$DB_USER" || -z "$DB_PASSWORD" || -z "$DB_PORT" ]]; then
    echo "Error: Required database environment variables are not set"
    echo "Required: DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT"
    exit 1
fi

# Create the userlist.txt file with actual credentials
echo "Generating userlist.txt..."
cat > /etc/pgbouncer/userlist.txt << EOF
"$DB_USER" "md5$(echo -n "$DB_PASSWORD$DB_USER" | md5sum | cut -d' ' -f1)"
EOF

# Update pgbouncer.ini with actual database connection string
echo "Generating pgbouncer.ini..."
cat > /etc/pgbouncer/pgbouncer.ini << 'EOF'
;; pgbouncer configuration for staging deployment
;; Configuration follows best practices for Django applications

[databases]
;; Database connection configuration
scicommons_staging = host=${DB_HOST} port=${DB_PORT} dbname=${DB_NAME} user=${DB_USER} password=${DB_PASSWORD}

[pgbouncer]
;; Connection pooling settings - optimized for Django applications
pool_mode = session
listen_port = 6432
listen_addr = *
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt

;; Connection limits - adjust based on your application needs
max_client_conn = 100
default_pool_size = 20
min_pool_size = 5
reserve_pool_size = 5
reserve_pool_timeout = 5

;; Timeouts and limits
server_reset_query = DISCARD ALL
server_reset_query_always = 0
server_check_delay = 30
server_check_query = select 1
server_lifetime = 3600
server_idle_timeout = 600
client_idle_timeout = 0

;; Logging and monitoring
log_connections = 1
log_disconnections = 1
log_pooler_errors = 1
stats_period = 60

;; Security settings
ignore_startup_parameters = extra_float_digits

;; Administrative settings
admin_users = postgres
stats_users = postgres

;; DNS settings
dns_max_ttl = 15
dns_zone_check_period = 0

;; Application name identification
application_name_add_host = 1
EOF

# Substitute environment variables in the configuration
envsubst < /etc/pgbouncer/pgbouncer.ini > /tmp/pgbouncer.ini && mv /tmp/pgbouncer.ini /etc/pgbouncer/pgbouncer.ini

# Set proper permissions
chown pgbouncer:pgbouncer /etc/pgbouncer/pgbouncer.ini
chown pgbouncer:pgbouncer /etc/pgbouncer/userlist.txt
chmod 600 /etc/pgbouncer/userlist.txt
chmod 644 /etc/pgbouncer/pgbouncer.ini

echo "PgBouncer configuration completed successfully"
echo "Starting PgBouncer as pgbouncer user..."

# Start pgbouncer as the pgbouncer user (not root)
exec su-exec pgbouncer pgbouncer /etc/pgbouncer/pgbouncer.ini