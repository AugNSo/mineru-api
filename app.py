from fastapi import FastAPI, File, UploadFile, HTTPException
from rq import Queue
from rq.job import Job
from redis import Redis
import os
import uvicorn
import argparse
import signal
from pydantic import BaseModel
import uuid
from task_processor import process_pdf, process_image

# Initialize FastAPI app
app = FastAPI()

# Initialize Redis and RQ
redis = Redis(
    host="localhost", port=6379, db=0, retry_on_timeout=True, socket_keepalive=True
)
default_queue = Queue("mineru_default", connection=redis, default_timeout=600)
high_queue = Queue("mineru_high", connection=redis, default_timeout=60)


# Create temporary directory for file processing
TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)


class TaskResponse(BaseModel):
    task_id: str
    status: str


@app.post("/process/pdf", response_model=TaskResponse)
async def upload_pdf(file: UploadFile = File(...), priority: str = "default"):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, detail="Only PDF files are allowed")

    task_id = str(uuid.uuid4())
    file_path = os.path.join(TEMP_DIR, f"{task_id}.pdf")

    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    # Set queue based on priority
    if priority == "high":
        high_queue.enqueue(
            process_pdf, file_path, job_id=task_id, result_ttl=3600, ttl=60
        )
    else:
        default_queue.enqueue(process_pdf, file_path, job_id=task_id, result_ttl=3600)

    return TaskResponse(task_id=task_id, status="queued")


@app.post("/process/image", response_model=TaskResponse)
async def upload_image(file: UploadFile = File(...), priority: str = "default"):
    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        raise HTTPException(400, detail="Only PNG and JPG images are allowed")

    task_id = str(uuid.uuid4())
    file_path = os.path.join(TEMP_DIR, f"{task_id}{os.path.splitext(file.filename)[1]}")

    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    # Set queue based on priority
    queue = high_queue if priority == "high" else default_queue
    queue.enqueue(process_image, file_path, job_id=task_id, result_ttl=3600)

    return TaskResponse(task_id=task_id, status="queued")


@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    try:
        job = Job.fetch(str(task_id), connection=redis)
    except Exception as e:
        raise HTTPException(404, detail=e)

    status = job.get_status()
    result = job.result if status == "finished" else None

    return {"task_id": task_id, "status": status, "result": result}


# Server lifecycle management
server = None
SHUTDOWN_FLAG_FILE = "server_running.pid"


def start_server(host="0.0.0.0", port=9721):
    global server

    # Create pid file to indicate server is running
    with open(SHUTDOWN_FLAG_FILE, "w") as f:
        f.write(str(os.getpid()))

    # Register signal handlers
    signal.signal(signal.SIGINT, lambda sig, frame: shutdown_server())
    signal.signal(signal.SIGTERM, lambda sig, frame: shutdown_server())

    try:
        config = uvicorn.Config(app=app, host=host, port=port, lifespan="on")
        server = uvicorn.Server(config)
        server.run()
    finally:
        # Clean up pid file when server exits
        if os.path.exists(SHUTDOWN_FLAG_FILE):
            os.remove(SHUTDOWN_FLAG_FILE)


def shutdown_server():
    global server
    if server:
        # Send shutdown signal to the server
        server.handle_exit(sig=signal.SIGINT, frame=None)
        print("Server shutdown complete")

        # Clean up pid file
        if os.path.exists(SHUTDOWN_FLAG_FILE):
            os.remove(SHUTDOWN_FLAG_FILE)
    elif os.path.exists(SHUTDOWN_FLAG_FILE):
        try:
            # Read PID from file and send SIGTERM to the process
            with open(SHUTDOWN_FLAG_FILE, "r") as f:
                pid = int(f.read().strip())

            # Send signal to the running process
            os.kill(pid, signal.SIGTERM)
            print(f"Shutdown signal sent to server process (PID: {pid})")

            # Give it a moment to shut down
            import time

            time.sleep(1)

            # Remove the PID file if it still exists
            if os.path.exists(SHUTDOWN_FLAG_FILE):
                os.remove(SHUTDOWN_FLAG_FILE)

        except (ValueError, ProcessLookupError, PermissionError) as e:
            print(f"Error shutting down server: {e}")

            # Clean up stale PID file
            if os.path.exists(SHUTDOWN_FLAG_FILE):
                os.remove(SHUTDOWN_FLAG_FILE)
    else:
        print("No server running")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mineru API Server")
    parser.add_argument(
        "action", choices=["start", "shutdown"], help="Start or shutdown the server"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=9721, help="Port to bind")

    args = parser.parse_args()

    if args.action == "start":
        print(f"Starting server on {args.host}:{args.port}")
        start_server(host=args.host, port=args.port)
    elif args.action == "shutdown":
        print("Shutting down server")
        shutdown_server()
