import aiogram
from aiogram import Router, F, html
from aiogram.filters.chat_member_updated import ChatMemberUpdated, ChatMemberUpdatedFilter, JOIN_TRANSITION

from handlers import func
from shared.bot_identity import help_mention
from shared.models import MessageOrm, TelegramChatOrm
from utils.filters import ChatTypeFilter
from shared.enums import ChatType

router = Router(name=__name__)
router.message.filter(ChatTypeFilter(ChatType.GROUP, ChatType.SUPERGROUP))


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def bot_invite_chat(event: ChatMemberUpdated):
    await TelegramChatOrm.insert_or_update_telegram_chat(event.chat.id)
    await func.update_users(event)
    await event.answer(
        f"Всем привет, спасибо что пригласили меня в {html.quote(event.chat.title)}\n"
        f"Команды: {html.quote(help_mention())}"
    )


@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def new_member(event: ChatMemberUpdated):
    await func.update_users(event)
    await event.answer(
        f"Привет, {event.new_chat_member.user.mention_html()}!\n"
        f"Добро пожаловать в {event.chat.title}"
    )


@router.chat_member()
async def change_member(event: ChatMemberUpdated):
    await func.update_user(event)


@router.message(F.migrate_to_chat_id)
async def group_to_supergroup_migration(message: MessageOrm, bot: aiogram.Bot):
    pass
