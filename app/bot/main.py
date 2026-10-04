import asyncio, tempfile
from pathlib import Path
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto, Message
from app.bot.keyboards import main_menu, quality_menu, references_done, review_menu
from app.bot.states import ImageTo3DFlow
from app.config import get_settings
from app.bot.backend import BackendClient
from app.storage.files import safe_name, validate_file
from app.workers.tasks import image_to_3d_revision_task

router = Router()


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Что будем создавать?", reply_markup=main_menu())


@router.message(F.text == "🖼 Изображение → 3D")
async def image_to_3d_start(message: Message, state: FSMContext):
    if message.from_user is None:
        return
    project_id = await BackendClient(get_settings().backend_url).create_project(message.from_user.id, "Изображение → 3D")
    await state.set_state(ImageTo3DFlow.references)
    await state.update_data(project_id=project_id, images=[])
    await message.answer("Отправьте PNG, JPG или WEBP. Можно загрузить несколько ракурсов: предпочтительно Front, Side и Back.", reply_markup=references_done())


@router.message(ImageTo3DFlow.references, F.photo | F.document)
async def image_reference(message: Message, state: FSMContext, bot: Bot):
    if message.from_user is None:
        return
    document = message.document
    photo = message.photo[-1] if message.photo else None
    if not document and not photo:
        await message.answer("Изображение не найдено.")
        return
    if document and not (document.mime_type or "").startswith("image/"):
        await message.answer("Для этого этапа нужен PNG, JPG или WEBP.")
        return
    if document:
        file_id = document.file_id
        original = document.file_name or f"{document.file_id}.bin"
        mime = document.mime_type or "application/octet-stream"
        file_size = document.file_size
    else:
        if photo is None:
            await message.answer("Изображение не найдено.")
            return
        file_id = photo.file_id
        original = f"{file_id}.jpg"
        mime = "image/jpeg"
        file_size = photo.file_size
    name = safe_name(original)
    validate_file(name, mime, file_size)
    data = await state.get_data()
    with tempfile.TemporaryDirectory(prefix="kira-upload-") as temp:
        destination = Path(temp) / name
        await bot.download(file_id, destination=destination)
        if destination.stat().st_size > get_settings().max_upload_mb * 1024 * 1024:
            await message.answer("Файл слишком большой.")
            return
        record = await BackendClient(get_settings().backend_url).upload(message.from_user.id, data["project_id"], destination, mime)
    images = [*data["images"], record["id"]]
    await state.update_data(images=images)
    await message.answer(f"Ракурс сохранён ({len(images)}). Отправьте следующий или нажмите «Ракурсы загружены».")


@router.message(ImageTo3DFlow.references, F.text == "✅ Ракурсы загружены")
async def references_complete(message: Message, state: FSMContext):
    if not (await state.get_data()).get("images"):
        await message.answer("Сначала отправьте хотя бы одно изображение.")
        return
    await state.set_state(ImageTo3DFlow.prompt)
    await message.answer("Опишите желаемый результат: анатомию, стиль, одежду, rig и анимацию.", reply_markup=main_menu())


@router.message(ImageTo3DFlow.prompt, F.text)
async def capture_prompt(message: Message, state: FSMContext):
    await state.update_data(prompt=message.text)
    await state.set_state(ImageTo3DFlow.quality)
    await message.answer("Выберите уровень качества. Детализация зависит от качества референсов.", reply_markup=quality_menu())


@router.callback_query(ImageTo3DFlow.quality, F.data.startswith("i3d_quality:"))
async def capture_quality(query: CallbackQuery, state: FSMContext):
    quality = (query.data or "").split(":", 1)[-1]
    data = await state.get_data()
    task = await BackendClient(get_settings().backend_url).reconstruct(query.from_user.id, data["project_id"], data["prompt"], quality)
    await state.update_data(celery_task_id=task["task_id"])
    await state.set_state(ImageTo3DFlow.processing)
    if isinstance(query.message, Message):
        await query.message.edit_text("🔍 Анализ изображения запущен. Этапы показываются без выдуманных процентов.")
    await query.answer()


def message_user_id(query: CallbackQuery) -> int:
    return query.from_user.id


@router.callback_query(F.data.startswith("i3d_review:"))
async def review(query: CallbackQuery, state: FSMContext, bot: Bot):
    action = (query.data or "").split(":", 1)[-1]
    if action == "approve":
        data = await state.get_data()
        root = get_settings().projects_root / str(query.from_user.id) / data["project_id"]
        revisions = sorted(root.glob("revisions/*/blender"), key=lambda p: p.stat().st_mtime, reverse=True)
        selected = revisions[0] if revisions else root / "blender"
        files = [selected / "Character.blend", selected / "Character.glb"]
        for output in files:
            if output.is_file():
                await bot.send_document(query.from_user.id, FSInputFile(output))
        await bot.send_message(
            query.from_user.id,
            "Модель подтверждена. Можно выбрать 🦴 Добавить скелет или 🎭 Анимировать.",
            reply_markup=main_menu(),
        )
        await state.clear()
    else:
        await state.update_data(correction_area=action)
        await state.set_state(ImageTo3DFlow.correction)
        await bot.send_message(
            query.from_user.id,
            "Опишите исправление естественным языком. Текущая модель будет изменена, а не создана заново.",
        )
    await query.answer()


@router.message(F.text == "❌ Отмена")
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Операция отменена.", reply_markup=main_menu())


@router.message(F.text.in_(set(main_menu().keyboard[i][0].text for i in range(len(main_menu().keyboard))) - {"🖼 Изображение → 3D"}))
async def choose(message: Message):
    await message.answer("Отправьте материалы, затем опишите желаемый результат.")


async def run():
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")
    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher(storage=RedisStorage.from_url(settings.redis_url))
    dp.include_router(router)
    await dp.start_polling(bot)


@router.message(ImageTo3DFlow.correction, F.text)
async def correction(message: Message, state: FSMContext):
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя. Повторите команду в личном чате с ботом.")
        return
    data = await state.get_data()
    image_to_3d_revision_task.delay(data["project_id"], message.from_user.id, message.text, data.get("correction_area", "general"))
    await state.set_state(ImageTo3DFlow.processing)
    await message.answer("Исправляю текущую модель. Новый результат пройдёт Blender QC и будет показан отдельными ракурсами.")


if __name__ == "__main__":
    asyncio.run(run())
