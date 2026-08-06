from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

router = Router()


@router.message()
async def block_text(message: Message, state: FSMContext):
    if await state.get_state() is not None:
        return  # FSM ожидает ввод — пропускаем
    if message.text and message.text.startswith("/"):
        return  # команды пропускаем
    await message.answer("Используй кнопки меню. Напиши /start")
