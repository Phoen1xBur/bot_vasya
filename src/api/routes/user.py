import logging
from fastapi import APIRouter, Header, HTTPException, Query

from handlers.func import declension_word_by_number
from src.utils.telegram_auth import validate_telegram_init_data, get_user_id_from_init_data
from config import settings
from src.models.user import UserOrm
from src.models.group_user import GroupUserOrm
from src.database import async_session_factory

router = APIRouter(
    prefix="/user",
    tags=['Пользователь']
)


@router.get("/profile")
async def get_user_profile(
        chat_id: int = Query(None),
        authorization: str = Header()
):
    logger = logging.getLogger(__name__)
    # Валидация авторизации
    if not validate_telegram_init_data(authorization, settings.TOKEN):
        logger.warning("Неверный заголовок авторизации для /user/profile")
        raise HTTPException(status_code=401, detail="Invalid authorization")

    user_id = get_user_id_from_init_data(authorization)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user data")

    try:
        async with async_session_factory() as session:
            # Получаем основные данные пользователя
            user = await UserOrm.get_user_by_id(user_id)

            if not user:
                logger.info("Пользователь не найден: user_id=%s", user_id)
                raise HTTPException(status_code=404, detail="User not found")

            # Если указан chat_id, получаем баланс для конкретного чата
            money = 0
            if chat_id:
                group_user = await GroupUserOrm.get_group_user(user_id, chat_id)
                if group_user:
                    money = group_user.money
                else:
                    # Создаем запись если не существует
                    new_group_user = GroupUserOrm(
                        user_id=user_id,
                        telegram_chat_id=chat_id,
                        money=0
                    )
                    session.add(new_group_user)
                    await session.commit()
            else:
                # Если chat_id не указан, берем первый доступный
                group_user = await GroupUserOrm.get_first_group_user(session, user_id)
                money = group_user.money if group_user else 0

        # Формируем ответ
        vasya_coin = declension_word_by_number(money, 'васякоинов', 'васякоин', 'васякоина')

        response = {
            "user_id": user_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "money": money,
            "vasya_coin": vasya_coin,
            "chat_id": chat_id
        }
        logger.debug("Ответ /user/profile: %s", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Внутренняя ошибка на /user/profile: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
