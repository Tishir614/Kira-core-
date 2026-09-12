from dataclasses import dataclass

DEFAULT_MAPPING = {
    "left_shoulder": "upper_arm.L",
    "left_elbow": "forearm.L",
    "left_wrist": "hand.L",
    "right_shoulder": "upper_arm.R",
    "right_elbow": "forearm.R",
    "right_wrist": "hand.R",
    "hip": "hips",
    "left_knee": "shin.L",
    "right_knee": "shin.R",
}


@dataclass(frozen=True)
class JointSample:
    frame: int
    joint: str
    rotation: tuple[float, float, float]
    confidence: float


def retarget(samples: list[JointSample], mapping: dict[str, str] = DEFAULT_MAPPING, min_confidence: float = 0.5) -> list[dict]:
    operations = []
    for sample in samples:
        bone = mapping.get(sample.joint)
        if bone and sample.confidence >= min_confidence:
            operations.append({"operation": "add_keyframe", "target": bone, "frame": sample.frame, "property": "rotation_euler", "value": sample.rotation})
    return operations
