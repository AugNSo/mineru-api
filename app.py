from fastapi import FastAPI, File, UploadFile, HTTPException
from rq import Queue
from rq.job import Job
from redis import Redis
from dotenv import dotenv_values
import os
import uvicorn
from pydantic import BaseModel
import uuid
from task_processor import process_pdf, process_image
import signal
import sys

# Initialize FastAPI app
app = FastAPI()

# Load environment variables
config = dotenv_values(".env")

# Initialize Redis and RQ
redis = Redis(
    host=config["REDIS_HOST"],
    port=config["REDIS_PORT"],
    password=config["REDIS_PASSWORD"],
    db=config["REDIS_DB"],
    retry_on_timeout=True,
    socket_keepalive=True,
)
default_queue = Queue("mineru_default", connection=redis, default_timeout=600)
high_queue = Queue("mineru_high", connection=redis, default_timeout=60)


# Create temporary directory for file processing
TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)


class TaskResponse(BaseModel):
    task_id: str
    status: str


class ShutdownResponse(BaseModel):
    message: str


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
    except Exception:
        raise HTTPException(404, detail="No job found.")

    status = job.get_status()
    result = job.result if status == "finished" else None

    return {"task_id": task_id, "status": status, "result": result}


# Admin endpoint for shutdown
@app.post("/shutdown", response_model=ShutdownResponse)
async def shutdown_server():
    # This will trigger the shutdown process
    if hasattr(app, "shutdown_handler") and app.shutdown_handler.server:
        # Schedule the shutdown to happen after response is sent
        app.shutdown_handler.schedule_shutdown()
        return ShutdownResponse(message="Server shutdown initiated.")
    else:
        raise HTTPException(500, detail="Shutdown handler not properly configured")


# Graceful shutdown class
class GracefulShutdown:
    def __init__(self):
        self.should_exit = False
        self.server = None
        self.shutdown_scheduled = False

    def register_signal_handlers(self):
        # Register for SIGINT (Ctrl+C) and SIGTERM
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def handle_signal(self, sig, frame):
        print(f"Received shutdown signal: {signal.Signals(sig).name}")
        self.schedule_shutdown()

    def schedule_shutdown(self):
        if not self.shutdown_scheduled:
            print("Scheduling server shutdown...")
            self.shutdown_scheduled = True
            # Use a background thread to wait a short time before shutting down
            # This allows current requests to complete
            import threading

            threading.Thread(target=self._delayed_shutdown, daemon=True).start()

    def _delayed_shutdown(self):
        import time

        # Wait a moment to let current request finish
        time.sleep(1)
        if self.server:
            self.server.should_exit = True
        else:
            print("No server instance available, exiting immediately...")
            sys.exit(0)

    def set_server(self, server):
        self.server = server


if __name__ == "__main__":
    # Create instance of graceful shutdown handler
    shutdown_handler = GracefulShutdown()
    shutdown_handler.register_signal_handlers()

    # Configure server
    config = uvicorn.Config(app, host="0.0.0.0", port=9721)
    server = uvicorn.Server(config)

    # Register server with shutdown handler
    shutdown_handler.set_server(server)

    # Store the shutdown handler on the app instance
    app.shutdown_handler = shutdown_handler

    # Run server
    server.run()
