import logging

# Configure the logger
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,  # Default level, can be overridden
)

# Create a named logger
logger = logging.getLogger("ensplotbot")
