import logging
from fastapi import APIRouter, Header, HTTPException, Query, Request

from handlers.func import declension_word_by_number
from src.utils.telegram_auth import validate_telegram_init_data, get_user_id_from_init_data
from config import settings
from src.models.user import UserOrm
from src.models.group_user import GroupUserOrm
from src.database import async_session_factory

router = APIRouter(
    prefix="/casino",
    tags=['Казино']
)


@router.get("/main")
async def casino_route(
        request: Request,
        # chat_id: int = Query(None),
        # authorization: str = Header()
):
    logger = logging.getLogger(__name__)
    logger.debug("Вызов /casino/main: client=%s url=%s", request.client, request.url)
    return
    # Валидация авторизации
    if not validate_telegram_init_data(authorization, settings.TOKEN):
        raise HTTPException(status_code=401, detail="Invalid authorization")

    user_id = get_user_id_from_init_data(authorization)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user data")

    if not chat_id:
        raise HTTPException(status_code=400, detail="Invalid chat id")

    try:
        async with async_session_factory() as session:
            # Получаем основные данные пользователя
            user_orm = await UserOrm.get_user_by_id(user_id)
            if not user_orm:
                raise HTTPException(status_code=404, detail="User not found")

            group_user_orm = await GroupUserOrm.get_group_user(user_id, chat_id)
            if not group_user_orm:
                raise HTTPException(status_code=404, detail="GroupUser not found")

            money = group_user_orm.money

        # Формируем ответ
        vasya_coin = declension_word_by_number(money, 'васякоинов', 'васякоин', 'васякоина')

        return {
            "money": money,
            "vasya_coin": vasya_coin,
            "chat_id": chat_id,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
