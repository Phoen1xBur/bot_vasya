from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from handlers.callback.callback_data.user_settings import UserSettings, Action
import keyboards.inline_kb_profile_change_settings as inline_kb
from models import GroupUserOrm

router = Router(name=__name__)
router.callback_query.filter()


@router.callback_query(UserSettings.filter(F.action == Action.notify))
async def change_settings_handler(callback_query: CallbackQuery, callback_data: UserSettings, bot: Bot):
    if callback_query.from_user.id != callback_data.tg_user_id:
        await callback_query.answer('Вы не можете менять настройки чужого пользователя')
        return

    await callback_query.answer()

    tg_user = callback_data.tg_user_id
    tg_chat = callback_data.tg_chat_id

    can_tag = await GroupUserOrm.change_can_tag(tg_user, tg_chat)

    notification = '❌ Выключить' if can_tag else '✅ Включить'
    try:
        await callback_query.message.edit_text(
            text=callback_query.message.text,
            reply_markup=await inline_kb.profile_change_settings(
                tg_user,
                tg_chat,
                notification
            )
        )
    except TelegramBadRequest:
        # Ошибка - скорее всего сообщение не изменилось
        pass


# @router.callback_query(F.data.startswith('no_from'))
# async def rob_police_handler_no(callback_query: CallbackQuery):
#     print(callback_query.id)
#     await callback_query.answer(text='хули жмешь кнопку?')
#     name = callback_query.from_user.mention_html()
#     await callback_query.message.edit_text(
#         text=f'{name} нажал нет',
#         reply_markup=build_inline_kb_rob_police(callback_query.from_user.id)
#     )
