from app.lipsync import envelope_fallback, map_phonemes
from app.motion.retarget import JointSample, retarget


def test_phonemes_and_envelope():
    assert map_phonemes([(0, 0.1, "p")])[0].viseme == "M/B/P"
    assert envelope_fallback([0, 0.1], [0, 1])[-1].viseme == "A"


def test_retarget_whitelist_operations():
    assert retarget([JointSample(1, "left_elbow", (0, 1, 0), 0.9)])[0]["target"] == "forearm.L"
