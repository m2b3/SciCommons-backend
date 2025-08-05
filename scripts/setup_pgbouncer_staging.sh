#!/bin/bash

# PgBouncer Setup Script for Staging Environment
# This script generates PgBouncer configuration files from templates
# It reads environment variables from .env.test and creates the actual config files

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up PgBouncer for staging environment...${NC}"

# Check if .env.test exists
if [[ ! -f ".env.test" ]]; then
    echo -e "${RED}Error: .env.test file not found!${NC}"
    echo "Please create .env.test with the required database environment variables:"
    echo "  DB_HOST=<your_db_host>"
    echo "  DB_PORT=<your_db_port>"
    echo "  DB_NAME=<your_db_name>"
    echo "  DB_USER=<your_db_user>"
    echo "  DB_PASSWORD=<your_db_password>"
    exit 1
fi

# Load environment variables from .env.test
export $(cat .env.test | grep -v '^#' | grep -v '^$' | xargs)

# Check required environment variables
required_vars=("DB_HOST" "DB_PORT" "DB_NAME" "DB_USER" "DB_PASSWORD")
for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo -e "${RED}Error: Required environment variable $var is not set in .env.test${NC}"
        exit 1
    fi
done

echo -e "${YELLOW}Generating MD5 hash for database password...${NC}"
# Generate MD5 hash for password (format: md5 + md5(username + password))
DB_PASSWORD_HASH=$(echo -n "${DB_USER}${DB_PASSWORD}" | md5sum | cut -d' ' -f1)

echo -e "${YELLOW}Creating pgbouncer-staging.ini...${NC}"
# Generate pgbouncer-staging.ini from template
envsubst < pgbouncer-staging.ini.template > pgbouncer-staging.ini

echo -e "${YELLOW}Creating userlist-staging.txt...${NC}"
# Generate userlist-staging.txt from template
export DB_PASSWORD_HASH
envsubst < userlist-staging.txt.template > userlist-staging.txt

# Set appropriate permissions (readable by container user)
chmod 644 pgbouncer-staging.ini userlist-staging.txt

echo -e "${GREEN}✅ PgBouncer configuration files created successfully!${NC}"
echo -e "${GREEN}Generated files:${NC}"
echo -e "  📄 pgbouncer-staging.ini"
echo -e "  📄 userlist-staging.txt"
echo ""
echo -e "${YELLOW}⚠️  Important:${NC}"
echo -e "  • These files contain sensitive credentials and are excluded from Git"
echo -e "  • After generating config, update your .env.test to use:"
echo -e "    DB_HOST=pgbouncer-test"
echo -e "    DB_PORT=6432"
echo -e "  • Run 'docker-compose -f docker-compose.staging.yml up -d' to start with PgBouncer"
echo ""
echo -e "${GREEN}🎉 Setup complete!${NC}"