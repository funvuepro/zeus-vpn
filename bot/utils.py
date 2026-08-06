import json
import os

from aiogram.types import CallbackQuery

_PHOTOS_FILE = "/app/data/section_photos.json"
_cache: dict[str, str] = {}
_loaded = False


def _load():
    global _cache, _loaded
    if _loaded:
        return
    if os.path.exists(_PHOTOS_FILE):
        try:
            with open(_PHOTOS_FILE) as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}
    _loaded = True


def _save():
    os.makedirs(os.path.dirname(_PHOTOS_FILE), exist_ok=True)
    with open(_PHOTOS_FILE, "w") as f:
        json.dump(_cache, f)


def set_section_photo(section: str, file_id: str):
    global _loaded
    _loaded = True
    _cache[section] = file_id
    _save()


def get_section_photo(section: str) -> str | None:
    _load()
    return _cache.get(section)


async def smart_edit(callback: CallbackQuery, text: str, keyboard=None, parse_mode: str = "HTML"):
    """Edit text message or delete+resend if current message is a photo."""
    if callback.message.photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=keyboard, parse_mode=parse_mode)
    else:
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=parse_mode)
        except Exception:
            await callback.message.answer(text, reply_markup=keyboard, parse_mode=parse_mode)


async def send_section(
    callback: CallbackQuery,
    section: str,
    text: str,
    keyboard,
    parse_mode: str = "HTML",
):
    """Send section with photo if configured, otherwise smart_edit."""
    photo_id = get_section_photo(section)
    if photo_id:
        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            await callback.message.answer_photo(
                photo_id, caption=text, reply_markup=keyboard, parse_mode=parse_mode
            )
            return
        except Exception:
            pass
    await smart_edit(callback, text, keyboard, parse_mode)