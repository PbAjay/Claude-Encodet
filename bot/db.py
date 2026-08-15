"""
Persistence layer. Two collections:

  jobs      - one document per queued/active encode job. Survives restarts,
              so the queue is never silently dropped if the process dies.
  settings  - a single document holding runtime-changeable config
              (current ffmpeg args, thumbnail) so /setcode survives restarts
              instead of living only in memory.

Design choice: we do NOT attempt byte-level resume of an interrupted
download or encode. On startup, any job that was left in "downloading",
"encoding" or "uploading" state gets reset to "queued" and restarts from
scratch — but it is never lost from the queue.
"""
import time
from motor.motor_asyncio import AsyncIOMotorClient

from .config import MONGO_URI, MONGO_DB_NAME

_client = AsyncIOMotorClient(MONGO_URI)
_db = _client[MONGO_DB_NAME]
jobs = _db["jobs"]
settings = _db["settings"]

STATUS_QUEUED = "queued"
STATUS_DOWNLOADING = "downloading"
STATUS_ENCODING = "encoding"
STATUS_UPLOADING = "uploading"


async def ensure_indexes():
    await jobs.create_index("status")
    await jobs.create_index("added_at")


async def add_job(job: dict) -> str:
    job.setdefault("status", STATUS_QUEUED)
    job.setdefault("added_at", time.time())
    job.setdefault("updated_at", time.time())
    result = await jobs.insert_one(job)
    return str(result.inserted_id)


async def set_status(job_id, status: str, **extra):
    await jobs.update_one(
        {"_id": job_id},
        {"$set": {"status": status, "updated_at": time.time(), **extra}},
    )


async def delete_job(job_id):
    await jobs.delete_one({"_id": job_id})


async def next_queued_job():
    return await jobs.find_one({"status": STATUS_QUEUED}, sort=[("added_at", 1)])


async def count_pending():
    return await jobs.count_documents(
        {"status": {"$in": [STATUS_QUEUED, STATUS_DOWNLOADING, STATUS_ENCODING, STATUS_UPLOADING]}}
    )


async def reset_interrupted_jobs():
    """Called on startup. Any job that was mid-flight when the process died
    goes back to 'queued' so it restarts cleanly instead of being lost."""
    result = await jobs.update_many(
        {"status": {"$in": [STATUS_DOWNLOADING, STATUS_ENCODING, STATUS_UPLOADING]}},
        {"$set": {"status": STATUS_QUEUED, "updated_at": time.time()}},
    )
    return result.modified_count


async def clear_all_jobs():
    result = await jobs.delete_many({})
    return result.deleted_count


async def get_setting(key: str, default=None):
    doc = await settings.find_one({"_id": "runtime"})
    if doc and key in doc:
        return doc[key]
    return default


async def set_setting(key: str, value):
    await settings.update_one(
        {"_id": "runtime"}, {"$set": {key: value}}, upsert=True
    )
