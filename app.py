from fastapi import FastAPI, File, UploadFile, HTTPException
from rq import Queue
from rq.job import Job
from redis import Redis
import os
import uvicorn
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9721)
