# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CUE is a full-stack app that indexes cooking videos for key instructional moments. Users paste a YouTube URL; the system transcribes the video and extracts timestamped cues (ingredients, measurements, techniques, timing) into an interactive timeline.

## Commands

### Backend
```bash
# Install dependencies
pip install -e .

# Run the pipeline directly
python -u pipeline.py run --video_url <YOUTUBE_URL>

# Start the API server
uvicorn api:app --reload --port 8000
```

### Frontend
```bash
cd my-app
npm install
npm run dev      # Dev server at http://localhost:5173
npm run build    # Production build to my-app/dist/
npm run lint     # ESLint
npm run preview  # Preview production build
```

### Full Stack
Run in separate terminals:
1. `uvicorn api:app --reload --port 8000`
2. `cd my-app && npm run dev`

## Architecture

### Data Flow
1. User submits a YouTube URL on the landing page
2. Frontend opens an SSE connection to `GET /process?url=...`
3. FastAPI (`api.py`) spawns the Metaflow pipeline as a subprocess
4. Pipeline logs are parsed and streamed as SSE events (`status`, `moment`, `complete`)
5. Frontend updates the UI in real-time; results are also saved as `results_{run_id}.json`

### Backend (`pipeline.py` + `api.py`)

**Pipeline steps (Metaflow, sequential):**
1. `start` — validate input, generate run ID
2. `download` — fetch video with yt-dlp
3. `extract_audio` — normalize to 16kHz mono PCM via ffmpeg
4. `transcribe` — speech-to-text using mlx-whisper (Apple Silicon optimized)
5. `detect_moments` — semantic similarity via sentence-transformers (`all-MiniLM-L6-v2`) against moment anchors, with regex validation; 0.35 cosine similarity threshold, 4-second dedup window
6. `end` — deduplicate, save JSON, print summary

`api.py` is a FastAPI app with a single SSE endpoint at `/process`. It parses Metaflow stdout to emit structured events and is CORS-configured for `localhost:5173`.

`pipeline_v1.py` is the previous regex-only approach (kept for reference).

### Frontend (`my-app/src/`)

- **`App.jsx`** — React Router setup with two routes
- **`pages/LandingPage.jsx`** — YouTube URL input and validation
- **`pages/VideoPage.jsx`** — Main viewer: embedded YouTube iframe (IFrame API), SSE listener, two-panel layout (moments list + transcript), playback controls (prev/next moment, loop), auto-scroll synced to current timestamp

Stack: React 19, Vite, Tailwind CSS 4, Framer Motion, React Router 7.

### Moment Categories & Colors
| Category    | Color     | Hex       |
|-------------|-----------|-----------|
| ingredient  | sage      | `#869489` |
| measurement | warm beige| `#C2B8A3` |
| technique   | slate blue| `#A3B2C2` |
| timing      | dusty rose| `#C2A3A3` |

## Key Dependencies

**Python** (see `pyproject.toml`): `fastapi`, `uvicorn`, `metaflow`, `mlx-whisper`, `faster-whisper`, `sentence-transformers`, `sse-starlette`, `yt-dlp`

**JavaScript** (see `my-app/package.json`): React 19, Vite 8, Tailwind CSS 4, Framer Motion, React Router 7
