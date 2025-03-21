from rq import Queue, Worker
from rq.command import send_shutdown_command
from redis import Redis
import argparse

# Initialize Redis and RQ
redis = Redis(
    host="localhost", port=6379, db=0, retry_on_timeout=True, socket_keepalive=True
)
default_queue = Queue('mineru_default', connection=redis, default_timeout=600)
high_queue = Queue("mineru_high", connection=redis, default_timeout=60)
worker = Worker([high_queue, default_queue], connection=redis)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RQ Worker Control")
    parser.add_argument(
        "action",
        choices=["work", "shutdown"],
        help="Action to perform: work (start working) or shutdown (send shutdown command)",
    )

    args = parser.parse_args()
    if args.action == "work":
        worker.work()
    elif args.action == "shutdown":
        workers = Worker.all(connection=redis, queue=high_queue)
        for worker in workers:
            send_shutdown_command(connection=redis, worker_name=worker.name)
