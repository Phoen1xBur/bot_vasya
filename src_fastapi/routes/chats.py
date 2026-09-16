"""Роутер чатов WebApp: список админ-чатов и редактирование настроек."""

import logging

from fastapi import APIRouter, Body, Depends, HTTPException
from pyrogram.enums import ChatMemberStatus

from shared.models.chat import TelegramChatOrm
from shared.models.group_user import GroupUserOrm
from shared.redis_client import get_redis
from src_fastapi.deps import require_telegram_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chats", tags=["Чаты"])

_ADMIN = (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)


def _status_val(st) -> str:
    return st.value if hasattr(st, "value") else str(st)


async def _require_chat_admin(user_id: int, chat_id: int) -> GroupUserOrm:
    gu = await GroupUserOrm.get_group_user(user_id, chat_id)
    if gu is None or gu.chat_member_status not in _ADMIN:
        raise HTTPException(status_code=403, detail="Нужны права администратора чата")
    return gu


@router.get("/mine")
async def list_my_admin_chats(profile: dict = Depends(require_telegram_user)):
    """Чаты, где пользователь — админ/владелец и Вася знает о членстве."""
    memberships = await GroupUserOrm.get_admin_memberships(profile["id"])
    chats = []
    for m in memberships:
        chat = await TelegramChatOrm.get_telegram_chat(m.telegram_chat_id)
        if chat is None:
            continue
        chats.append(
            {
                "chat_id": chat.chat_id,
                "answer_chance": chat.answer_chance,
                "ai_generate_text": bool(chat.ai_generate_text),
                "member_status": _status_val(m.chat_member_status),
                "can_tag": bool(m.can_tag),
                "money": m.money,
            }
        )
    return {"chats": chats}


@router.get("/{chat_id}/settings")
async def get_chat_settings(chat_id: int, profile: dict = Depends(require_telegram_user)):
    await _require_chat_admin(profile["id"], chat_id)
    chat = await TelegramChatOrm.get_telegram_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Чат не найден")
    gu = await GroupUserOrm.get_group_user(profile["id"], chat_id)
    return {
        "chat_id": chat.chat_id,
        "answer_chance": chat.answer_chance,
        "ai_generate_text": bool(chat.ai_generate_text),
        "can_tag": bool(gu.can_tag) if gu else True,
    }


@router.patch("/{chat_id}/settings")
async def patch_chat_settings(
    chat_id: int,
    body: dict = Body(...),
    profile: dict = Depends(require_telegram_user),
):
    """Изменить админ-настройки чата: answer_chance, ai_generate_text."""
    await _require_chat_admin(profile["id"], chat_id)
    chat = await TelegramChatOrm.get_telegram_chat(chat_id)
    if chat is None:
        await TelegramChatOrm.insert_or_update_telegram_chat(chat_id=chat_id)
        chat = await TelegramChatOrm.get_telegram_chat(chat_id)

    updates: dict = {}
    if "answer_chance" in body and body["answer_chance"] is not None:
        try:
            chance = int(body["answer_chance"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Шанс должен быть числом 0–100")
        if chance < 0 or chance > 100:
            raise HTTPException(status_code=400, detail="Шанс должен быть числом 0–100")
        updates["answer_chance"] = chance
    if "ai_generate_text" in body and body["ai_generate_text"] is not None:
        updates["ai_generate_text"] = bool(body["ai_generate_text"])

    if updates:
        await TelegramChatOrm.insert_or_update_telegram_chat(chat_id, **updates)
        if "answer_chance" in updates:
            try:
                get_redis().set(f"tg_chat_chance:{chat_id}", updates["answer_chance"], ex=120)
            except Exception:
                logger.debug("redis chance cache update failed", exc_info=True)

    chat = await TelegramChatOrm.get_telegram_chat(chat_id)
    return {
        "chat_id": chat_id,
        "answer_chance": chat.answer_chance if chat else updates.get("answer_chance"),
        "ai_generate_text": bool(chat.ai_generate_text) if chat else bool(updates.get("ai_generate_text")),
        "ok": True,
    }
