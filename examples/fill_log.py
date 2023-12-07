#!/usr/bin/python

from navconfig.logging import logging
import ecs_logging
import time
from random import randint

# logger = logging.getLogger(__name__)
logger = logging.getLogger("app")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('elvis.json')
handler.setFormatter(ecs_logging.StdlibFormatter())
logger.addHandler(handler)

print("Generating log entries...")

messages = [
    "Elvis has left the building.",
    "Elvis has left the oven on.",
    "Elvis has two left feet.",
    "Elvis was left out in the cold.",
    "Elvis was left holding the baby.",
    "Elvis left the cake out in the rain.",
    "Elvis came out of left field.",
    "Elvis exited stage left.",
    "Elvis took a left turn.",
    "Elvis left no stone unturned.",
    "Elvis picked up where he left off.",
    "Elvis's train has left the station."
]

while True:
    random1 = randint(0, 15)
    random2 = randint(1, 10)
    if random1 > 11:
        random1 = 0
    if (random1 <= 4):
        logger.info(messages[random1], extra={"http.request.body.content": messages[random1]})
    elif (random1 >= 5 and random1 <= 8):
        logger.warning(messages[random1], extra={"http.request.body.content": messages[random1]})
    elif (random1 >= 9 and random1 <= 10):
        logger.error(messages[random1], extra={"http.request.body.content": messages[random1]})
    else:
        logger.critical(messages[random1], extra={"http.request.body.content": messages[random1]})
    time.sleep(random2)
