import argparse
import hashlib
import json
import math
import os
import re
import shutil
import signal
import struct
import subprocess
import threading
import time
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".vectorforge"
OUTPUT = ROOT / "outputs"
QUEUE = STATE / "jobs"

WAKE = threading.Event()
STOP = threading.Event()

STAGES = ["plan", "image", "audio", "video", "web", "app", "game"]
PALETTE = ["#22d3ee", "#a78bfa", "#fb7185", "#fbbf24"]


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def number(value, default, lower, upper):
    try:
        value = float(value)
        if not math.isfinite(value):
            return default
        return max(lower, min(upper, value))
    except (TypeError, ValueError):
        return default


def normalize(raw):
    """El modelo propone datos; nunca ejecutamos código del modelo."""
    color = str(raw.get("color", PALETTE[0]))
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        color = PALETTE[0]

    return {
        "version": 1,
        "width": 320,
        "height": 180,
        "fps": 24,
        "duration": number(raw.get("duration"), 3, 1, 10),
        "radius": number(raw.get("radius"), 22, 8, 40),
        "speed": number(raw.get("speed"), 1.5, 0.2, 4),
        "frequency": number(raw.get("frequency"), 220, 65, 880),
        "color": color,
        "background": "#08111f",
    }


def plan(prompt):
    key = os.getenv("OPENAI_API_KEY")

    if not key:
        # Fallback reproducible. No pretende comprender el prompt como una IA.
        seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16)
        return {
            "planner": "procedural-hash",
            "scene": normalize({
                "color": PALETTE[seed % len(PALETTE)],
                "frequency": [110, 164.81, 220, 329.63][seed % 4],
                "speed": 0.5 + (seed % 20) / 10,
            }),
        }

    model = os.getenv("OPENAI_MODEL")
    if not model:
        raise RuntimeError("Configura OPENAI_MODEL para usar el planificador IA.")

    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Devuelve exclusivamente un objeto JSON, sin Markdown. "
                    "Diseña una escena procedural de una esfera animada. "
                    "Campos permitidos: color hexadecimal #RRGGBB, "
                    "duration entre 1 y 10 segundos, radius entre 8 y 40, "
                    "speed entre 0.2 y 4, frequency entre 65 y 880 Hz. "
                    "Interpreta el estilo del usuario dentro de esas restricciones. "
                    "No devuelvas código ni instrucciones."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }

    request = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=90) as response:
        result = json.load(response)

    raw = json.loads(result["choices"][0]["message"]["content"])
    if not isinstance(raw, dict):
        raise ValueError("El planificador no devolvió un objeto JSON.")

    return {"planner": model, "scene": normalize(raw)}


def position(scene, t):
    """Trayectoria paramétrica compartida por imagen, vídeo y web."""
    w, h = scene["width"], scene["height"]
    speed = scene["speed"]
    return (
        w / 2 + math.sin(t * speed) * w * 0.28,
        h / 2 + math.cos(t * speed * 0.7) * h * 0.22,
    )


def image(scene, folder):
    x, y = position(scene, 0)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {scene["width"]} {scene["height"]}">'
        f'<rect width="100%" height="100%" fill="{scene["background"]}"/>'
        f'<circle cx="{x}" cy="{y}" r="{scene["radius"]}" '
        f'fill="{scene["color"]}"/></svg>'
    )
    (folder / "image.svg").write_text(svg, encoding="utf-8")


def audio(scene, folder):
    rate = 44100
    samples = int(scene["duration"] * rate)
    data = bytearray()

    for i in range(samples):
        t = i / rate
        envelope = min(1, t / 0.03, (scene["duration"] - t) / 0.08)
        f = scene["frequency"]
        sample = (
            math.sin(2 * math.pi * f * t)
            + 0.3 * math.sin(2 * math.pi * 2 * f * t)
            + 0.12 * math.sin(2 * math.pi * 3 * f * t)
        )
        value = int(0.45 * 32767 * envelope * sample)
        data.extend(struct.pack("<h", value))

    with wave.open(str(folder / "audio.wav"), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(data)


def rgb(color):
    return bytes.fromhex(color[1:])


def frame(scene, t):
    """Rasteriza una esfera a partir de su ecuación geométrica."""
    w, h = scene["width"], scene["height"]
    cx, cy = position(scene, t)
    radius = scene["radius"]
    foreground = rgb(scene["color"])
    pixels = bytearray(rgb(scene["background"]) * (w * h))

    for y in range(max(0, int(cy - radius)), min(h, int(cy + radius) + 1)):
        for x in range(max(0, int(cx - radius)), min(w, int(cx + radius) + 1)):
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                offset = (y * w + x) * 3
                pixels[offset:offset + 3] = foreground

    return pixels


def video(scene, folder):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("Falta FFmpeg. Instálalo y reanuda el trabajo.")

    target = folder / "video.partial.mp4"
    command = [
        ffmpeg, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f'{scene["width"]}x{scene["height"]}',
        "-r", str(scene["fps"]), "-i", "pipe:0",
        "-i", str(folder / "audio.wav"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        "-movflags", "+faststart", str(target),
    ]

    log_path = folder / "ffmpeg.log"
    with log_path.open("wb") as log:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log)
        try:
            count = int(scene["duration"] * scene["fps"])
            for i in range(count):
                if STOP.is_set():
                    raise InterruptedError("Exportación detenida.")
                process.stdin.write(frame(scene, i / scene["fps"]))
            process.stdin.close()
            if process.wait(timeout=120) != 0:
                raise RuntimeError(f"FFmpeg falló. Revisa {log_path}")
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait()
            raise

    target.replace(folder / "video.mp4")


def browser_project(scene, folder, kind):
    # Plantilla acotada: no es generación arbitraria de aplicaciones.
    html = """"""

    html = html.replace("__SCENE__", json.dumps(scene))
    html = html.replace("__KIND__", kind)
    destination = folder / kind
    destination.mkdir(exist_ok=True)
    (destination / "index.html").write_text(html, encoding="utf-8")


def execute(stage, job, folder):
    if stage == "plan":
        save_json(folder / "scene.json", plan(job["prompt"]))
        return

    scene = load_json(folder / "scene.json")["scene"]
    if stage == "image":
        image(scene, folder)
    elif stage == "audio":
        audio(scene, folder)
    elif stage == "video":
        video(scene, folder)
    else:
        browser_project(scene, folder, stage)


def process_job(path):
    job = load_json(path)
    folder = OUTPUT / job["id"]
    folder.mkdir(parents=True, exist_ok=True)

    for stage in STAGES:
        if STOP.is_set():
            return
        if stage in job["completed"]:
            continue

        attempts = job["attempts"].get(stage, 0)
        if attempts >= 3:
            job["status"] = "blocked"
            save_json(path, job)
            return

        job["status"] = "running"
        job["attempts"][stage] = attempts + 1
        save_json(path, job)

        try:
            execute(stage, job, folder)
            job["completed"].append(stage)
            job.pop("error", None)
            print(f'[{job["id"]}] completado: {stage}', flush=True)
        except Exception as error:
            job["error"] = str(error)
            job["status"] = (
                "blocked" if job["attempts"][stage] >= 3 else "pending"
            )
            print(f'[{job["id"]}] {stage}: {error}', flush=True)
            save_json(path, job)
            return

        save_json(path, job)

    job["status"] = "done"
    save_json(path, job)


def worker():
    # Bloqueo de proceso para impedir dos trabajadores sobre la misma cola.
    import fcntl

    STATE.mkdir(parents=True, exist_ok=True)
    lock = (STATE / "worker.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Ya existe un trabajador activo.")

    (STATE / "worker.pid").write_text(str(os.getpid()))

    def terminate(*_):
        STOP.set()
        WAKE.set()

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    signal.signal(signal.SIGUSR1, lambda *_: WAKE.set())

    print("Trabajador activo. Esperando trabajos.", flush=True)
    while not STOP.is_set():
        for path in sorted(QUEUE.glob("*.json")):
            if STOP.is_set():
                break
            if load_json(path)["status"] not in {"done", "blocked"}:
                process_job(path)
        WAKE.wait(timeout=5)
        WAKE.clear()


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    submit = commands.add_parser("submit")
    submit.add_argument("prompt")

    commands.add_parser("worker")
    commands.add_parser("status")

    retry = commands.add_parser("retry")
    retry.add_argument("job_id")

    args = parser.parse_args()
    QUEUE.mkdir(parents=True, exist_ok=True)

    if args.command == "submit":
        job_id = str(time.time_ns())
        save_json(QUEUE / f"{job_id}.json", {
            "id": job_id,
            "prompt": args.prompt,
            "status": "pending",
            "completed": [],
            "attempts": {},
        })
        print(job_id)

    elif args.command == "worker":
        worker()

    elif args.command == "status":
        for path in sorted(QUEUE.glob("*.json")):
            job = load_json(path)
            print(job["id"], job["status"], ",".join(job["completed"]))
            if job.get("error"):
                print("  Error:", job["error"])

    elif args.command == "retry":
        if not args.job_id.isdigit():
            raise SystemExit("Identificador inválido.")
        path = QUEUE / f"{args.job_id}.json"
        job = load_json(path)
        job.update(status="pending", attempts={})
        job.pop("error", None)
        save_json(path, job)


if __name__ == "__main__":
    main()
