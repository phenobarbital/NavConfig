from navconfig.logging import logger

## set a new logger name
logger.setName('config.example')

## debugging
logger.debug("Hello World!")
## error:
logger.info("info message")
logger.warning("warning message")
logger.error("error message")
logger.critical("critical message")
try:
    raise Exception('Very Critical Exception')
except Exception:
    logger.critical("critical message with traceback", stacktrace=True)
