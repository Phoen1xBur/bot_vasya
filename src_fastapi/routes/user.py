"""Роутер пользователя: профиль (баланс васякоинов)."""

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from shared.models.group_user import GroupUserOrm
from shared.models.user import UserOrm
from shared.utils import vasya_coin_word
from src_fastapi.deps import require_telegram_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["Пользователь"])


@router.get("/profile")
async def get_user_profile(
    chat_id: int | None = Query(default=None),
    profile: dict = Depends(require_telegram_user),
):
    """Профиль пользователя с балансом для конкретного чата."""
    user_id = profile["id"]
    user = await UserOrm.get_user_by_id(user_id)
    if not user:
        # WebApp может открыться до первого сообщения в чате — создаём из initData
        class _U:
            first_name = profile.get("first_name")
            last_name = profile.get("last_name")
            username = profile.get("username")

        await UserOrm.insert_or_update_user(user_id, _U())
        user = await UserOrm.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=500, detail="Не удалось создать пользователя")

    money = 0
    if chat_id is not None:
        group_user = await GroupUserOrm.get_group_user(user_id, chat_id)
        if group_user:
            money = group_user.money
    else:
        money = await GroupUserOrm.get_total_money(user_id)

    return {
        "user_id": user_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
        "money": money,
        "vasya_coin": vasya_coin_word(money),
        "chat_id": chat_id,
    }


@router.get("/balance")
async def get_balance(
    chat_id: int = Query(...),
    profile: dict = Depends(require_telegram_user),
):
    """Баланс васякоинов пользователя в конкретном чате."""
    user_id = profile["id"]
    group_user = await GroupUserOrm.get_group_user(user_id, chat_id)
    money = group_user.money if group_user else 0
    return {"money": money, "vasya_coin": vasya_coin_word(money), "chat_id": chat_id}


@router.post("/update_profile")
async def update_profile(
    profile: dict = Depends(require_telegram_user),
):
    """Обновить профиль из Telegram-данных (first_name и т.д.)."""
    await UserOrm.insert_or_update_user(
        profile["id"],
        first_name=profile.get("first_name"),
        last_name=profile.get("last_name"),
        username=profile.get("username"),
    )
    return {"ok": True}


@router.get("/settings")
async def get_user_settings(
    chat_id: int = Query(...),
    profile: dict = Depends(require_telegram_user),
):
    """Пользовательские настройки в чате (can_tag и т.п.)."""
    user_id = profile["id"]
    group_user = await GroupUserOrm.get_group_user(user_id, chat_id)
    if group_user is None:
        raise HTTPException(status_code=404, detail="Вы не участник этого чата")
    status = group_user.chat_member_status
    return {
        "chat_id": chat_id,
        "can_tag": bool(group_user.can_tag),
        "money": group_user.money,
        "member_status": status.value if hasattr(status, "value") else str(status),
    }


@router.post("/settings/toggle_tag")
async def toggle_tag_setting(
    body: dict = Body(default=None),
    profile: dict = Depends(require_telegram_user),
):
    """Включить/выключить тег (зеркало bot callback toggle_tag)."""
    body = body or {}
    chat_id = body.get("chat_id")
    if chat_id is None:
        raise HTTPException(status_code=400, detail="Укажите chat_id")
    chat_id = int(chat_id)
    user_id = profile["id"]
    group_user = await GroupUserOrm.get_group_user(user_id, chat_id)
    if group_user is None:
        raise HTTPException(status_code=404, detail="Вы не участник этого чата")
    can_tag = await GroupUserOrm.change_can_tag(user_id, chat_id)
    return {"chat_id": chat_id, "can_tag": can_tag, "ok": True}

