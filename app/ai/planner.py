from dataclasses import dataclass


@dataclass(frozen=True)
class Stage:
    key: str
    title: str
    queue: str


def plan_pipeline(filenames: list[str], prompt: str) -> list[Stage]:
    extensions = {name.rsplit(".", 1)[-1].lower() for name in filenames if "." in name}
    text = prompt.lower()
    stages = [Stage("analyze", "🔍 Анализ материалов", "ai")]
    is_3d = bool(extensions & {"glb", "gltf", "fbx", "obj", "blend"}) or any(x in text for x in ("3d", "rig", "риг", "модел"))
    has_audio = bool(extensions & {"mp3", "wav", "ogg"})
    if is_3d:
        stages += [Stage("topology", "🔍 Проверка topology", "blender"), Stage("rig", "🦴 Создание rig", "blender")]
    if has_audio:
        stages.append(Stage("music", "🎵 Анализ музыки", "ai"))
    stages += [
        Stage("animate", "🎭 Создание анимации", "blender" if is_3d else "video"),
        Stage("camera", "🎥 Настройка камеры", "blender" if is_3d else "video"),
        Stage("render", "🖼 Рендер", "blender" if is_3d else "video"),
        Stage("quality", "🔍 Проверка результата", "video"),
        Stage("encode", "🎬 Кодирование", "video"),
    ]
    return stages
