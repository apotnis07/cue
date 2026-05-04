import asyncio
import json
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/process")
async def process_video(url: str):
    async def event_stream():
        try:
            yield {
                "event": "status",
                "data": json.dumps({"message": "Starting pipeline..."})
            }

            process = await asyncio.create_subprocess_exec(
                sys.executable, "-u", "pipeline.py", "run",
                "--video_url", url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            current_step = None
            results_file = None

            step_order = ["start", "download", "extract_audio", "transcribe", "detect_moments", "end"]
            step_messages = {
                "download": "Downloading video...",
                "extract_audio": "Extracting audio...",
                "transcribe": "Transcribing: this takes about a minute...",
                "detect_moments": "Detecting moments...",
                "end": "Finalizing results...",
            }

            async for line in process.stdout:
                line = line.decode().strip()
                if not line:
                    continue

                # strip metaflow prefix: "2026-... [run/step/task (pid N)] actual message"
                actual_message = line
                if ")] " in line:
                    actual_message = line.split(")] ", 1)[-1].strip()

                # detect step transitions
                for step in step_order:
                    if f"/{step}/" in line and "Task is starting" in line:
                        if step in step_messages:
                            current_step = step
                            yield {
                                "event": "status",
                                "data": json.dumps({
                                    "message": step_messages[step],
                                    "step": step
                                })
                            }

                # detect results file
                if "Saved to:" in actual_message:
                    results_file = actual_message.split("Saved to:")[-1].strip()

                # stream moments
                if current_step == "end" and actual_message.startswith("["):
                    try:
                        bracket_end = actual_message.index("]")
                        timestamp_display = actual_message[1:bracket_end]

                        paren_start = actual_message.index("(")
                        paren_end = actual_message.index(")")
                        types_str = actual_message[paren_start + 1:paren_end]
                        types = [t.strip() for t in types_str.split(",")]

                        text = actual_message[paren_end + 2:].strip()

                        yield {
                            "event": "moment",
                            "data": json.dumps({
                                "timestamp_display": timestamp_display,
                                "types": types,
                                "text": text,
                            })
                        }
                    except (ValueError, IndexError):
                        pass

            await process.wait()

            if process.returncode == 0 and results_file:
                results_path = Path(results_file)
                if results_path.exists():
                    with open(results_path) as f:
                        results = json.load(f)
                    yield {
                        "event": "complete",
                        "data": json.dumps({
                            "title": results["title"],
                            "duration": results["duration"],
                            "total_moments": results["total_moments"],
                            "transcript": results["transcript"]
                        })
                    }
            else:
                yield {
                    "event": "error",
                    "data": json.dumps({"message": "Pipeline failed"})
                }

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e)})
            }

    return EventSourceResponse(event_stream())

@app.get("/health")
async def health():
    return {"status": "ok"}