from dataclasses import dataclass

VISEMES = {
    "A": "A",
    "E": "E",
    "I": "I",
    "O": "O",
    "U": "U",
    "M": "M/B/P",
    "B": "M/B/P",
    "P": "M/B/P",
    "F": "F/V",
    "V": "F/V",
    "L": "L",
    "W": "W/Q",
    "Q": "W/Q",
    "REST": "REST",
}


@dataclass(frozen=True)
class VisemeCue:
    start: float
    end: float
    viseme: str
    weight: float


def map_phonemes(phonemes: list[tuple[float, float, str]]) -> list[VisemeCue]:
    return [VisemeCue(start, end, VISEMES.get(symbol.upper(), "REST"), 1.0) for start, end, symbol in phonemes]


def envelope_fallback(times: list[float], energy: list[float], threshold: float = 0.05) -> list[VisemeCue]:
    if len(times) != len(energy):
        raise ValueError("times and energy lengths differ")
    peak = max(energy, default=1) or 1
    return [VisemeCue(t, t + 0.08, "A" if value / peak > threshold else "REST", min(1, value / peak)) for t, value in zip(times, energy)]
