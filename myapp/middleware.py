# middleware file
import logging
import time

from django.conf import settings
from django.db import connection
from django.db.backends.base.base import BaseDatabaseWrapper

logger = logging.getLogger(__name__)


class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip timing in production when DEBUG is False
        if not settings.DEBUG:
            return self.get_response(request)
        # Start timing
        start_time = time.time()

        # Get initial database queries count
        initial_queries = len(connection.queries)

        # Process the request
        response = self.get_response(request)

        # Calculate timing
        total_time = time.time() - start_time

        # Get final database queries
        final_queries = len(connection.queries)
        query_count = final_queries - initial_queries

        # Calculate database time
        db_time = sum(float(q["time"]) for q in connection.queries[initial_queries:])

        # Log the timing information
        logger.info(
            f"Request: {request.method} {request.path}\n"
            f"Total Time: {total_time:.2f}s\n"
            f"Database Time: {db_time:.2f}s\n"
            f"Database Queries: {query_count}\n"
            f"Application Time: {total_time - db_time:.2f}s"
        )

        return response
