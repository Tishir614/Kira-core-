import json, zipfile
from app.alight.package import build_asset_pack


def test_asset_pack(tmp_path):
    a = tmp_path / "audio.mp3"
    a.write_bytes(b"audio")
    out = build_asset_pack(tmp_path / "pack.zip", {"audio.mp3": a}, [{"time": 0}], [{"scale": 100}])
    with zipfile.ZipFile(out) as z:
        assert {"audio.mp3", "timing.json", "keyframes.json", "README.txt"} <= set(z.namelist())
