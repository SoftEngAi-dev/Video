# VectorForge: Mathematical Media Engine

A reproducible media generation system with persistent worker queue. Generates procedural animations, audio synthesis, and video exports from scene specifications—no AI-generated images, only mathematics and parameters.

## Architecture

**Agent → Scene Specification → Mathematical Engine → Exporters**

- **Plan**: Scene parameters via OpenAI-compatible API or procedural fallback
- **Image**: SVG from geometric calculations
- **Audio**: WAV synthesis with harmonic envelope
- **Video**: Frame-by-frame rasterization via FFmpeg
- **Web/App/Game**: Browser projects with shared scene trajectory

## Quick Start

### Prerequisites

- Python 3.10+
- FFmpeg (for video export)
- Linux/macOS (signal-based worker management)

### Setup

```bash
git clone git@github.com:SoftEngAi-dev/Video.git
cd Video
mkdir -p vectorforge
```

Copy `vectorforge/main.py` into the repository.

### Optional: Configure AI Planner

```bash
export OPENAI_API_KEY="your-key"
export OPENAI_MODEL="gpt-4o-mini"  # or compatible provider
# export OPENAI_BASE_URL="https://your-provider/v1"
```

Without these, the system uses deterministic procedural planning (local, no API calls).

### Start Worker

```bash
mkdir -p .vectorforge
nohup python3 vectorforge/main.py worker > .vectorforge/worker.log 2>&1 &
```

### Submit Job

```bash
python3 vectorforge/main.py submit "Purple sphere with slow movement and deep bass sound, space theme"
```

Returns a job ID. The worker picks it up automatically and processes all stages: `plan` → `image` → `audio` → `video` → `web` → `app` → `game`.

### Monitor Progress

```bash
python3 vectorforge/main.py status
tail -f .vectorforge/worker.log
```

### Wake Worker Immediately

```bash
kill -USR1 "$(cat .vectorforge/worker.pid)"
```

### Stop Worker

```bash
kill -TERM "$(cat .vectorforge/worker.pid)"
```

### Retry Failed Job

```bash
python3 vectorforge/main.py retry <job_id>
```

## Outputs

Each job produces:

```
outputs/<id>/
├── scene.json           # Normalized scene parameters
├── image.svg            # Initial frame as SVG
├── audio.wav            # Synthesized audio
├── video.mp4            # Full animation with audio
├── ffmpeg.log           # Video encoder log
├── web/index.html       # Standalone web viewer
├── app/index.html       # Embedded app template
└── game/index.html      # Interactive click game
```

### View Results Locally

```bash
python3 -m http.server 8080 --bind 127.0.0.1 --directory outputs
# Visit http://localhost:8080/<job_id>/web/
```

## Commands

| Command | Usage |
|---------|-------|
| `submit PROMPT` | Create a new job |
| `worker` | Start the persistent worker |
| `status` | List all jobs and their stages |
| `retry JOB_ID` | Reset failed stages for a job |

## Design Principles

1. **Reproducible**: All output is code + parameters, never AI-generated pixels.
2. **Safe**: Model data is normalized; no arbitrary code execution.
3. **Fault-tolerant**: Persistent queue, limited retries, graceful errors.
4. **Autonomous**: Worker runs continuously; `SIGUSR1` wakes, `SIGTERM` stops.
5. **Scoped**: This is the bootstrap. Future work includes multimodal input, 3D rendering, advanced audio, and dynamic game generation.

## Future Work

| Area | Status |
|------|--------|
| Multimodal reference analysis | Planned |
| Scene graphs (objects, materials, cameras) | Planned |
| 3D rendering (Three.js/WebGPU) | Planned |
| Advanced audio (filters, sequencers) | Planned |
| Procedural game/app generation | Planned |
| Development agent (modify code, run tests) | Planned |
| Persistent service, budgets, webhooks | Planned |

## Environment Variables

- `OPENAI_API_KEY`: API key for the planning service
- `OPENAI_MODEL`: Model identifier (e.g., `gpt-4o-mini`)
- `OPENAI_BASE_URL`: Provider URL (optional, defaults to OpenAI)

**Store keys in `.env` or system secrets, never in Git.**

## License

TBD
