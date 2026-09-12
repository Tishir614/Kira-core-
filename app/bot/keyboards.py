from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

MENU = [
    "🎨 Создать анимацию",
    "🖼 Изображение → 3D",
    "🧊 Blender 3D",
    "🎬 Видео",
    "🎵 Анимация под музыку",
    "🧍 Создать персонажа",
    "🦴 Rig персонажа",
    "🎭 Анимировать модель",
    "🎥 Видео → движение 3D",
    "🖌 Текстуры",
    "📱 Alight Motion",
    "📂 Мои проекты",
    "⏳ Очередь задач",
    "📦 Скачать весь проект",
    "⚙️ Настройки",
]


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=x)] for x in MENU], resize_keyboard=True)


def references_done() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Ракурсы загружены")], [KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)


def quality_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ Черновик", callback_data="i3d_quality:draft")],
            [InlineKeyboardButton(text="⚖️ Хорошее качество", callback_data="i3d_quality:good")],
            [InlineKeyboardButton(text="💎 Высокое качество", callback_data="i3d_quality:high")],
        ]
    )


def review_menu() -> InlineKeyboardMarkup:
    labels = [
        ("✅ Всё хорошо", "approve"),
        ("🔧 Исправить", "fix"),
        ("🎨 Изменить текстуру", "texture"),
        ("📐 Исправить пропорции", "proportions"),
        ("👁 Исправить лицо", "face"),
        ("🐾 Исправить лапы", "paws"),
        ("👂 Исправить уши", "ears"),
        ("🦊 Исправить хвост", "tail"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=a, callback_data=f"i3d_review:{b}")] for a, b in labels])
