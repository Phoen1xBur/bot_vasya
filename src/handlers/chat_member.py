import aiogram
from aiogram import Router, F, html
from aiogram.filters.chat_member_updated import ChatMemberUpdated, ChatMemberUpdatedFilter, JOIN_TRANSITION

from handlers import func
from models import TelegramChatOrm, MessageOrm
from utils.filters import ChatTypeFilter
from utils.enums import ChatType


router = Router(name=__name__)
router.message.filter(
    ChatTypeFilter(
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    )
)


@router.my_chat_member(
    ChatMemberUpdatedFilter(
        member_status_changed=JOIN_TRANSITION
    )
)
async def bot_invite_chat(event: ChatMemberUpdated):
    await TelegramChatOrm.insert_or_update_telegram_chat(event.chat.id)
    await func.update_users(event)
    await event.answer(f'Всем привет, спасибо что пригласили меня в {html.quote(event.chat.title)}\n'
                       f'Для полноценного общения, выдайте мне права администратора группы')


@router.chat_member(
    ChatMemberUpdatedFilter(
        member_status_changed=JOIN_TRANSITION
    )
)
async def new_member(event: ChatMemberUpdated):
    await func.update_user(event)
    await event.answer(
        f'Привет, {event.new_chat_member.user.mention_html()}!\n'
        f'Добро пожаловать в {event.chat.title}'
    )


@router.chat_member()
async def change_member(event: ChatMemberUpdated):
    await func.update_user(event)


@router.message(F.migrate_to_chat_id)
async def group_to_supegroup_migration(message: MessageOrm, bot: aiogram.Bot):
    # TODO: Группа изменилась на супергруппу и изменила ID, в БД нужно обновить ID
    pass
    # await bot.send_message(
    #     message.migrate_to_chat_id,
    #     f"Group upgraded to supergroup.\n"
    #     f"Old ID: {html.code(message.chat.id)}\n"
    #     f"New ID: {html.code(message.migrate_to_chat_id)}"
    # )

