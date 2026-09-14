"""Роутер пользователя: профиль (баланс васякоинов)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from shared.models.group_user import GroupUserOrm
from shared.models.user import UserOrm
from shared.utils import vasya_coin_word
from src_fastapi.deps import require_telegram_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["Пользователь"])


@router.get("/profile")
async def get_user_profile(
    chat_id: int = Query(default=None),
    profile: dict = Depends(require_telegram_user),
):
    """Профиль пользователя с балансом для конкретного чата."""
    user_id = profile["id"]
    user = await UserOrm.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    money = 0
    if chat_id:
        group_user = await GroupUserOrm.get_group_user(user_id, chat_id)
        if group_user:
            money = group_user.money

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
