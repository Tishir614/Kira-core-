import json, subprocess  # nosec B404 - fixed FFmpeg argv only; shell mode is never used
from dataclasses import dataclass
from pathlib import Path
from app.config import get_settings


@dataclass(frozen=True)
class VideoSpec:
    width: int = 1080
    height: int = 1920
    fps: int = 30

    def validate(self):
        if self.width < 64 or self.height < 64 or self.width > 7680 or self.height > 7680:
            raise ValueError("Invalid resolution")
        if self.fps not in {24, 30, 60}:
            raise ValueError("FPS must be 24, 30 or 60")


def encode_video(frames: Path, output: Path, spec: VideoSpec, audio: Path | None = None) -> None:
    spec.validate()
    args = [get_settings().ffmpeg_bin, "-y", "-framerate", str(spec.fps), "-i", str(frames / "%06d.png")]
    if audio:
        args += ["-i", str(audio), "-shortest"]
    args += ["-vf", f"scale={spec.width}:{spec.height}:flags=lanczos", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    if audio:
        args += ["-c:a", "aac"]
    args.append(str(output))
    subprocess.run(args, check=True, capture_output=True)  # nosec B603


def probe_video(path: Path, spec: VideoSpec, audio_required: bool = False) -> dict:
    cmd = [
        get_settings().ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,width,height,avg_frame_rate",
        "-of",
        "json",
        str(path),
    ]
    data = json.loads(subprocess.run(cmd, check=True, capture_output=True, text=True).stdout)  # nosec B603
    streams = data.get("streams", [])
    video = next((x for x in streams if x.get("codec_type") == "video"), None)
    issues = []
    if not video:
        issues.append("video stream missing")
    elif (video.get("width"), video.get("height")) != (spec.width, spec.height):
        issues.append("resolution mismatch")
    if float(data.get("format", {}).get("duration", 0)) <= 0:
        issues.append("duration is zero")
    if audio_required and not any(x.get("codec_type") == "audio" for x in streams):
        issues.append("audio stream missing")
    if issues:
        raise RuntimeError("Video quality control failed: " + ", ".join(issues))
    return data
