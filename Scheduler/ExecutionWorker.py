import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bullmq import Worker
from Backend.Gateway.schemas import ToolAction
from Backend.Gateway.execution import _execute_mock_service
from Backend.Gateway.audit import log_audit_event

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
connection = {"host": REDIS_HOST, "port": REDIS_PORT}


async def process_action_job(job, job_token):
    """Processes enqueued async side-effect actions and writes audit outcome."""
    print(f"[ExecutionWorker] Processing job {job.id} ({job.name})...")
    data = job.data
    action = ToolAction.model_validate(data)

    try:
        result = await _execute_mock_service(action)
        print(f"[ExecutionWorker] Job {job.id} executed successfully: {result}")

        # Record async completion in audit trail
        await log_audit_event(
            action_id=str(action.action_id),
            tool=action.tool,
            operation=action.operation,
            flow_id="async_worker",
            decision="EXECUTED_ASYNC",
            agent_id=action.agent_id,
            user_id=action.user_id,
            details={"job_id": job.id, "result": result},
        )
        return result

    except Exception as e:
        err_msg = str(e)
        print(f"[ExecutionWorker] Job {job.id} failed: {err_msg}")
        await log_audit_event(
            action_id=str(action.action_id),
            tool=action.tool,
            operation=action.operation,
            flow_id="async_worker",
            decision="EXECUTION_ASYNC_FAILED",
            agent_id=action.agent_id,
            user_id=action.user_id,
            details={"job_id": job.id, "error": err_msg},
        )
        raise


async def main():
    print(f"[ExecutionWorker] Starting BullMQ worker for 'ActionSideEffects' on {REDIS_HOST}:{REDIS_PORT}...")
    worker = Worker("ActionSideEffects", process_action_job, {"connection": connection})
    print("[ExecutionWorker] Worker listening for side-effect jobs. Press Ctrl+C to exit.")
    try:
        await asyncio.Future()
    finally:
        await worker.close()


if __name__ == "__main__":
    asyncio.run(main())
