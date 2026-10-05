import logging
import os

from redis import Redis
from rq import Queue, Worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s : %(message)s",
)

conn = Redis.from_url(os.environ["REDIS_URL"])
Worker([Queue("acp-deposit", connection=conn)], connection=conn).work()