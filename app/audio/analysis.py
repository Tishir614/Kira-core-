from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class MusicAnalysis:
    bpm: float
    duration: float
    beats: list[float]
    onsets: list[float]
    energy: list[float]

    def json(self) -> dict:
        return asdict(self)


def analyze_music(path: Path) -> MusicAnalysis:
    import librosa
    import numpy as np

    y, sr = librosa.load(path, sr=None, mono=True)
    if y.size == 0:
        raise ValueError("Audio is empty")
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    rms = librosa.feature.rms(y=y)[0]
    return MusicAnalysis(
        float(np.asarray(tempo).flat[0]),
        float(librosa.get_duration(y=y, sr=sr)),
        librosa.frames_to_time(beat_frames, sr=sr).round(4).tolist(),
        np.asarray(onsets).round(4).tolist(),
        rms.round(5).tolist(),
    )


def animation_markers(data: MusicAnalysis) -> list[dict]:
    markers = []
    peak = max(data.energy, default=0)
    for i, beat in enumerate(data.beats):
        action = "head_nod" if i % 2 == 0 else "body_sway"
        markers.append({"time": beat, "label": f"Beat {i+1}", "action": action})
    if peak:
        markers.append({"time": data.duration / 2, "label": "Energy peak", "action": "camera_zoom"})
    return sorted(markers, key=lambda x: x["time"])
