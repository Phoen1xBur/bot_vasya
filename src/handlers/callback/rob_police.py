import aiogram
from aiogram import Router, F, html
from aiogram.types import CallbackQuery
from aiogram.filters.chat_member_updated import ChatMemberUpdated, ChatMemberUpdatedFilter, JOIN_TRANSITION

from handlers import func
from models import TelegramChatOrm, MessageOrm
from utils.filters import ChatTypeFilter
from utils.enums import ChatType

router = Router(name=__name__)
router.callback_query.filter(
    ChatTypeFilter(
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    )
)


@router.callback_query(F.data.startswith('rob_police'))
async def rob_police_handler(callback_query: CallbackQuery):
    await callback_query.answer()
