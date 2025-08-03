# PgBouncer Dockerfile for staging deployment
# Using Alpine directly for cleaner, lighter image
FROM alpine:3.19

# Install pgbouncer and required tools
RUN apk add --no-cache \
    pgbouncer \
    gettext \
    bash \
    netcat-openbsd \
    postgresql-client \
    su-exec \
    && rm -rf /var/cache/apk/*

# Create pgbouncer user and directories
RUN adduser -D -s /bin/sh pgbouncer && \
    mkdir -p /etc/pgbouncer /var/log/pgbouncer && \
    chown -R pgbouncer:pgbouncer /etc/pgbouncer /var/log/pgbouncer

# Copy configuration files
COPY pgbouncer.ini /etc/pgbouncer/pgbouncer.ini.template
COPY userlist.txt /etc/pgbouncer/userlist.txt.template
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

# Make entrypoint script executable and set ownership
RUN chmod +x /usr/local/bin/entrypoint.sh && \
    chown pgbouncer:pgbouncer /etc/pgbouncer/pgbouncer.ini.template \
                              /etc/pgbouncer/userlist.txt.template \
                              /usr/local/bin/entrypoint.sh

# Expose pgbouncer port
EXPOSE 6432

# Use our custom entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]