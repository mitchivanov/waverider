# test_logging.py

import logging
from root import settings  # Ensure this path matches your project structure

# Create a logger
logger = logging.getLogger(__name__)

def test_logging():
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")

if __name__ == "__main__":
    test_logging()

