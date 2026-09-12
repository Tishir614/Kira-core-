from app.audio.analysis import MusicAnalysis, animation_markers
from app.ai.planner import plan_pipeline


def test_markers_follow_beats():
    assert len(animation_markers(MusicAnalysis(120, 2, [0.5, 1.0], [], [0.1]))) == 3


def test_planner_routes_music_model():
    p = plan_pipeline(["hero.glb", "song.mp3"], "танец")
    keys = [x.key for x in p]
    assert "rig" in keys and "music" in keys and all(x.queue in {"ai", "video", "blender"} for x in p)
