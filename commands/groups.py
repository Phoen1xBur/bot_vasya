import random
import re

import aiogram
from aiogram import Router, F, html
from aiogram.filters import Command, IS_ADMIN
from aiogram.filters.chat_member_updated import ChatMemberUpdated, ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.enums import ChatType, ContentType, ParseMode
from aiogram.types import Message, URLInputFile

from commands import func
from config import settings
from models import MessageOrm, TelegramChatOrm, GroupUserOrm, UserOrm
from run import app
from utils.Filters import ChatTypeFilter, BotNameFilter
from utils.answer_type import AnswerType
from utils.db import generate_text
from utils.enums import Rank

router_groups = Router()


# https://core.telegram.org/bots/api#html-style
help_text = """<b>Список команд:</b>

<b>• Вася шанс [от 0 до 100] —</b> изменит шанс отправки сообщения

<b>• Вася выбери [значение 1 или значение 2] —</b> выберет одно из предложенного 

<b>• Вася кот —</b> отправит картинку  котика

<b>• Вася кот [текст сообщения] —</b>  отправит картинку котика с текстом

<b>• Вася ответь [текст сообщения] / Вася ответь гиф [текст сообщения] ——</b> ответит да/нет с гифкой или без 

<b>• Вася кто [текст] —</b> выберет рандомного участника чата"""


@router_groups.message(Command('help'))
async def get_help(message):
    await message.answer(help_text, parse_mode=ParseMode.HTML)


@router_groups.my_chat_member(
    ChatMemberUpdatedFilter(
        member_status_changed=JOIN_TRANSITION
    )
)
async def bot_invite_chat(event: ChatMemberUpdated):
    await TelegramChatOrm.insert_telegram_chat(event.chat.id)
    await func.update_users(event)
    await event.answer(f'Всем привет, спасибо что пригласили меня в {html.quote(event.chat.title)}\n'
                       f'Для полноценного общения, выдайте мне права администратора группы')


@router_groups.chat_member(
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


@router_groups.chat_member()
async def change_member(event: ChatMemberUpdated):
    await func.update_user(event)


@router_groups.message(F.migrate_to_chat_id)
async def group_to_supegroup_migration(message: MessageOrm, bot: aiogram.Bot):
    # TODO: Группа изменилась на супергруппу и изменила ID, в БД нужно обновить ID
    pass
    # await bot.send_message(
    #     message.migrate_to_chat_id,
    #     f"Group upgraded to supergroup.\n"
    #     f"Old ID: {html.code(message.chat.id)}\n"
    #     f"New ID: {html.code(message.migrate_to_chat_id)}"
    # )


@router_groups.message(
    ChatTypeFilter(chat_type=[ChatType.GROUP, ChatType.SUPERGROUP]),
    BotNameFilter(bot_names=settings.BOT_NAMES),
    F.text
    & (F.content_type == ContentType.TEXT)
    & (F.text[0] != '/')
)
async def answer_by_bot_name(message: Message):
    arr_msg = message.text.split()[1:]
    group_user: GroupUserOrm = await GroupUserOrm.get_group_user(message.from_user.id, message.chat.id)
    match arr_msg:
        case []:
            answer_type = AnswerType.Text
            messages = [msg.text for msg in await MessageOrm.get_messages(message.chat.id)]
            answer = generate_text(messages)
        case 'шанс', *chance:
            answer_type = AnswerType.Text
            if group_user.chat_member_status in func.MEMBER_TYPE_ADMIN:
                answer = await func.set_chance(message, chance[0] if len(chance) > 0 else -1)
            else:
                answer = 'Эта привилегия доступна только для администраторов группы'
        case 'ответь', 'гиф', *_:
            answer_type = AnswerType.Animation
            animation, answer = await func.yesno()
        case 'ответь', *_:
            answer_type = AnswerType.Text
            animation, answer = await func.yesno()
        case 'выбери', *words:
            answer_type = AnswerType.Text
            answer = func.choice(words)
        case 'кто', *words:
            answer_type = AnswerType.Text
            # TODO: На данный момент не работает. В любом случае переделать на связку с БД
            members = []
            async with app:
                async for member in app.get_chat_members(message.chat.id):
                    if not member.user.is_bot:
                        members.append(member.user)
            member = random.choice(members)
            print(member)
            print(member.fullname)
            answer = f'Я думаю {member.mention_html()} ' + ' '.join(words)
        case 'кот', *text:
            answer_type = AnswerType.Photo
            url = 'https://cataas.com/cat'
            if text:
                url = 'https://cataas.com/cat/says/' + ' '.join(text) + '?fontSize=50&fontColor=white'
            photo = URLInputFile(url)
            answer = 'Держи котика'
        case _:
            answer_type = AnswerType.Text
            answer = 'Я ничего не понял, что ты хочешь от меня'

    # TODO: Переделать в будущем на message.chat.do(action, *param)
    match answer_type:
        case AnswerType.Text:
            await message.answer(answer)
        case AnswerType.Animation:
            await message.answer_animation(animation=animation, caption=answer)
        case AnswerType.Photo:
            await message.answer_photo(photo=photo, caption=answer)
        # case AnswerType.Video:
        #     await message.answer_video(video=video, caption=answer)
        case _:
            pass


@router_groups.message(
    ChatTypeFilter(chat_type=[ChatType.GROUP, ChatType.SUPERGROUP]),
    F.text &
    (F.content_type == ContentType.TEXT) &
    F.text[0] != '/'
)
async def echo(message: Message):
    if message.text is None or message.via_bot:
        return

    chat_group = await GroupUserOrm.get_group_user(message.from_user.id, message.chat.id)
    await MessageOrm.insert_message(chat_group.id, message.text.replace('@', ''))

    chance = (await TelegramChatOrm.get_chance(message.chat.id)).answer_chance
    if random.randint(1, 100) <= chance:
        messages = [msg.text for msg in await MessageOrm.get_messages(message.chat.id)]
        text = generate_text(messages)
        await message.answer(text)
