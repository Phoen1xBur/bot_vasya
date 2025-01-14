import aiogram
from aiogram import Router, F, html
from aiogram.types import CallbackQuery
from aiogram.filters.chat_member_updated import ChatMemberUpdated, ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.exceptions import TelegramBadRequest

from handlers import func
from keyboards.inline_kb_rob_police import build_inline_kb_rob_police
from models import TelegramChatOrm, MessageOrm
from utils.filters import ChatTypeFilter
from utils.enums import ChatType

router = Router(name=__name__)
router.callback_query.filter()


# @router.callback_query(F.data.startswith('rob_police'))
# async def rob_police_handler(callback_query: CallbackQuery):
#     await callback_query.answer()


@router.callback_query(F.data.startswith('rob_police'))
async def rob_police_handler_yes(callback_query: CallbackQuery):
    data = callback_query.data.split(':')
    print(data)
    await callback_query.answer(text='хули жмешь кнопку?')
    name = callback_query.from_user.mention_html()
    new_text = f'{name} нажал {data[1]}'
    try:
        await callback_query.message.edit_text(
            text=new_text,
            reply_markup=build_inline_kb_rob_police(callback_query.from_user.id)
        )
    except TelegramBadRequest:
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
