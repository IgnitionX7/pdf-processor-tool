Let’s refactor your PDF processing flow for enhanced_extractor.py so it’s fully Render-safe, process-based, and logs reliably. I’ll keep your existing session/status management intact.

1️⃣ Setup a global process executor

Add this near the top of your routes file:

import asyncio
from concurrent.futures import ProcessPoolExecutor

# Global executor for CPU-bound PDF processing

# Keep max_workers=1 on Render free tier

pdf_executor = ProcessPoolExecutor(max_workers=1)

2️⃣ Wrap your existing process_pdf_background in an async starter

We use asyncio.create_task with run_in_executor:

async def start_pdf_processing(session_id: str, pdf_path: Path, output_dir: Path):
"""
Starts the CPU-bound PDF processing in a separate process.
"""
loop = asyncio.get_running_loop() # Run in a separate process (bypasses GIL)
await loop.run_in_executor(
pdf_executor,
process_pdf_background,
session_id,
pdf_path,
output_dir
)

✅ This keeps the main FastAPI loop non-blocking while processing happens in a real CPU process.

3️⃣ Update your /process route

Replace your thread-based code with this:

@router.post("/process")
async def process_pdf(session_id: str):
"""
Start PDF processing in a background process.
Returns immediately with status URL for polling.
""" # Verify session exists
session = session_manager.get_session(session_id)
if not session:
raise HTTPException(status_code=404, detail="Session not found")

    if "enhanced_pdf" not in session.files:
        raise HTTPException(status_code=400, detail="PDF not found. Upload a PDF first.")

    if session.status == SessionStatus.PROCESSING:
        return {
            "message": "Processing already in progress",
            "status": "processing",
            "status_url": f"/api/sessions/{session_id}/enhanced/status"
        }

    pdf_path = Path(session.files["enhanced_pdf"])
    session_dir = session_manager.get_session_dir(session_id)
    output_dir = session_dir / "enhanced"

    # Update session status immediately
    session.status = SessionStatus.PROCESSING
    session.current_stage = 1
    session_manager.update_session(session)

    # Start processing in a separate process
    asyncio.create_task(start_pdf_processing(session_id, pdf_path, output_dir))

    logger.info(f"Started background PDF processing for session {session_id}")

    return {
        "message": "Processing started in background",
        "status": "processing",
        "status_url": f"/api/sessions/{session_id}/enhanced/status"
    }

4️⃣ Optional: Improve logging visibility

Inside process_pdf_background, add flush or logger config to ensure logs appear on Render:

import sys

logger = logging.getLogger(**name**)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

And inside your function:

logger.info(f"Background processing started for session {session_id}", flush=True)

This guarantees Render captures log output immediately.

✅ What changes

Threads → Processes: Bypasses GIL, gets real CPU

Non-blocking FastAPI: /status keeps working

Reliable logs: You can now see progress or exceptions

Safe on Render free tier: No more “forever polling”
