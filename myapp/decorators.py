import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)


def timing_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()

        # Get the function name and module
        func_name = func.__name__
        module_name = func.__module__

        # Log the timing
        logger.info(
            f"Function: {module_name}.{func_name}\n"
            f"Execution Time: {end_time - start_time:.2f}s"
        )

        return result

    return wrapper
