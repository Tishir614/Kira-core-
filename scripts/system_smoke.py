"""End-to-end infrastructure smoke test using generated, non-user demo assets."""

import asyncio, json, subprocess, tempfile
from pathlib import Path
from app.blender.runner import run_blender
from app.blender.scripts import smoke_script
from app.config import get_settings
from app.video.engine import VideoSpec, probe_video


async def dependencies(report: dict) -> None:
    from redis.asyncio import from_url
    from sqlalchemy import text
    from app.database.session import SessionLocal

    redis = from_url(get_settings().redis_url)
    try:
        report["redis"] = bool(await redis.ping())
    finally:
        await redis.aclose()
    async with SessionLocal() as db:
        report["database"] = (await db.execute(text("SELECT 1"))).scalar_one() == 1


async def main() -> None:
    settings = get_settings()
    report = {}
    with tempfile.TemporaryDirectory(prefix="kira-system-smoke-") as directory:
        root = Path(directory)
        frame = root / "000001.png"
        script = root / "scene.py"
        script.write_text(smoke_script(str(frame)), encoding="utf-8")
        run_blender(script, root / "blender.log", 300)
        report["blender"] = frame.is_file() and frame.stat().st_size > 0
        video = root / "demo.mp4"
        subprocess.run(
            [
                settings.ffmpeg_bin,
                "-y",
                "-loop",
                "1",
                "-i",
                str(frame),
                "-t",
                "1",
                "-vf",
                "scale=720:1280",
                "-r",
                "30",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(video),
            ],
            check=True,
            capture_output=True,
        )
        probe_video(video, VideoSpec(720, 1280, 30))
        report["ffmpeg"] = True
        await dependencies(report)
        if settings.telegram_bot_token:
            import httpx

            response = await httpx.AsyncClient(timeout=15).get(f"https://api.telegram.org/bot{settings.telegram_bot_token}/getMe")
            report["telegram"] = response.json().get("ok", False)
        if not all(report.values()):
            raise RuntimeError(f"Smoke test failed: {report}")
        print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
