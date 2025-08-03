#!/bin/bash

# Test script for PgBouncer deployment
echo "🧪 Testing PgBouncer deployment..."

# Stop any existing containers
echo "Stopping existing containers..."
docker compose -f docker-compose.staging.yml down

# Rebuild and start
echo "Building and starting containers..."
docker compose -f docker-compose.staging.yml --env-file .env.test up -d --build

# Wait for containers to start
echo "Waiting for containers to start..."
sleep 10

# Check container status
echo "📋 Container Status:"
docker ps -a | grep -E "(pgbouncer-test|web-test|redis-test|celery-test)"

echo ""
echo "🔍 PgBouncer Health Check:"
docker inspect pgbouncer-test --format='{{.State.Health.Status}}' 2>/dev/null || echo "Health check not available"

echo ""
echo "📝 PgBouncer Logs (last 20 lines):"
docker logs --tail 20 pgbouncer-test

echo ""
echo "🔧 Environment Variables Check:"
docker exec pgbouncer-test env | grep -E "^DB_" 2>/dev/null || echo "Container not running or accessible"

echo ""
echo "👤 User Check:"
docker exec pgbouncer-test ps aux 2>/dev/null | grep pgbouncer || echo "Container not running"

echo ""
echo "🌐 Network Connectivity:"
docker exec web-test nslookup pgbouncer-test 2>/dev/null || echo "Web container not running or can't resolve pgbouncer"

echo ""
echo "📝 Django App Logs (last 10 lines):"
docker logs --tail 10 web-test 2>/dev/null || echo "Web container not running"

echo ""
echo "🚀 Test Complete!"
echo ""
echo "✅ SUCCESS INDICATORS:"
echo "  - All containers show 'Up' status"
echo "  - PgBouncer shows 'healthy' status"
echo "  - PgBouncer logs show 'Detected Neon database' and correct endpoint ID"
echo "  - Django app starts without database connection errors"
echo ""
echo "❌ FAILURE INDICATORS:"
echo "  - 'FATAL: no such database' -> Database name mismatch"
echo "  - 'Endpoint ID not specified' -> Neon SNI configuration issue"
echo "  - 'PgBouncer should not run as root' -> User permission issue"

# Quick deployment command reminder
echo ""
echo "🔄 TO REDEPLOY WITH FIXES:"
echo "docker compose -f docker-compose.staging.yml down && docker compose -f docker-compose.staging.yml --env-file .env.test up -d --build"