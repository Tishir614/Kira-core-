from aiogram.fsm.state import State, StatesGroup


class ImageTo3DFlow(StatesGroup):
    references = State()
    prompt = State()
    quality = State()
    processing = State()
    review = State()
    correction = State()
