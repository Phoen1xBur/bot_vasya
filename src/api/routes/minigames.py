import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Query

from config import settings, redis
from src.utils.telegram_auth import validate_telegram_init_data, get_user_id_from_init_data, get_user_profile_from_init_data


router = APIRouter(
    prefix="/minigames",
    tags=['Мини-игры']
)


def _key_ttt(chat_id: int) -> str:
    return f'mg:ttt:room:{chat_id}'


def _key_roulette(chat_id: int) -> str:
    return f'mg:roulette:room:{chat_id}'


def _ensure_same_group(chat_id_param: int, chat_id_room: Optional[int]) -> None:
    if chat_id_room is None or int(chat_id_room) != int(chat_id_param):
        raise HTTPException(status_code=403, detail="Группа не совпадает")


def _get_ttt_state(chat_id: int) -> dict:
    data = redis.hgetall(_key_ttt(chat_id))
    if not data:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    # Нормализуем типы
    result = {
        'creator_id': int(data.get('creator_id', 0)),
        'player2_id': int(data.get('player2_id', 0)),
        'bet_creator': int(data.get('bet_creator', 0)),
        'bet_player2': int(data.get('bet_player2', 0)),
        'state': data.get('state', 'waiting'),
        'turn': data.get('turn', 'X'),
        'board': data.get('board', ' ' * 9),
        'creator_name': data.get('creator_name', ''),
        'player2_name': data.get('player2_name', ''),
    }
    return result


def _save_ttt_state(chat_id: int, state: dict) -> None:
    redis.hset(_key_ttt(chat_id), mapping={
        'creator_id': state['creator_id'],
        'player2_id': state['player2_id'],
        'bet_creator': state['bet_creator'],
        'bet_player2': state['bet_player2'],
        'state': state['state'],
        'turn': state.get('turn', 'X'),
        'board': state.get('board', ' ' * 9),
    })


def _check_ttt_winner(board: str) -> Optional[str]:
    wins = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6)
    ]
    for a, b, c in wins:
        if board[a] != ' ' and board[a] == board[b] == board[c]:
            return board[a]
    if ' ' not in board:
        return 'draw'
    return None


@router.post('/ttt/join')
async def ttt_join(
        chat_id: int = Query(...),
        authorization: str = Header()
):
    if not validate_telegram_init_data(authorization, settings.TOKEN):
        raise HTTPException(status_code=401, detail="Invalid authorization")
    user_id = get_user_id_from_init_data(authorization)
    profile = get_user_profile_from_init_data(authorization)
    state = _get_ttt_state(chat_id)
    # Резерв создателя: место 1, игрок 2 — любой из той же группы
    if state['player2_id'] == 0 and user_id != state['creator_id']:
        state['player2_id'] = user_id
        state['player2_name'] = profile.get('username') or profile.get('first_name') or ''
        _save_ttt_state(chat_id, state)
    return state


@router.post('/ttt/bet')
async def ttt_bet(
        chat_id: int = Query(...),
        bet: int = Query(..., ge=0),
        authorization: str = Header()
):
    if not validate_telegram_init_data(authorization, settings.TOKEN):
        raise HTTPException(status_code=401, detail="Invalid authorization")
    user_id = get_user_id_from_init_data(authorization)
    profile = get_user_profile_from_init_data(authorization)
    state = _get_ttt_state(chat_id)
    if user_id == state['creator_id']:
        state['bet_creator'] = bet
        state['creator_name'] = profile.get('username') or profile.get('first_name') or ''
    elif user_id == state['player2_id']:
        state['bet_player2'] = bet
        state['player2_name'] = profile.get('username') or profile.get('first_name') or ''
    else:
        raise HTTPException(status_code=403, detail="Вы не участник комнаты")

    # Если оба выбрали одинаковую ставку и есть оба игрока — старт
    if state['player2_id'] and state['bet_creator'] == state['bet_player2']:
        if state['state'] == 'waiting' or state['state'] == 'betting':
            state['state'] = 'playing'
            state['board'] = ' ' * 9
            state['turn'] = 'X'  # создатель — X, второй — O
    else:
        state['state'] = 'betting'

    _save_ttt_state(chat_id, state)
    return state


@router.get('/ttt/state')
async def ttt_state(chat_id: int = Query(...)):
    return _get_ttt_state(chat_id)


@router.post('/ttt/move')
async def ttt_move(
        chat_id: int = Query(...),
        cell: int = Query(..., ge=0, le=8),
        authorization: str = Header()
):
    if not validate_telegram_init_data(authorization, settings.TOKEN):
        raise HTTPException(status_code=401, detail="Invalid authorization")
    user_id = get_user_id_from_init_data(authorization)
    state = _get_ttt_state(chat_id)
    if state['state'] != 'playing':
        raise HTTPException(status_code=400, detail="Игра ещё не началась")
    mark = 'X' if user_id == state['creator_id'] else ('O' if user_id == state['player2_id'] else None)
    if mark is None:
        raise HTTPException(status_code=403, detail="Вы не участник комнаты")
    if (mark == 'X' and state['turn'] != 'X') or (mark == 'O' and state['turn'] != 'O'):
        raise HTTPException(status_code=400, detail="Сейчас ход другого игрока")
    board = state['board']
    if board[cell] != ' ':
        raise HTTPException(status_code=400, detail="Клетка занята")
    board = board[:cell] + mark + board[cell + 1:]
    state['board'] = board
    winner = _check_ttt_winner(board)
    if winner == 'X':
        state['state'] = 'finished'
        state['winner'] = state['creator_id']
    elif winner == 'O':
        state['state'] = 'finished'
        state['winner'] = state['player2_id']
    elif winner == 'draw':
        state['state'] = 'finished'
        state['winner'] = 0
    else:
        state['turn'] = 'O' if state['turn'] == 'X' else 'X'
    _save_ttt_state(chat_id, state)
    return state


# ---------------- Roulette ----------------


@router.post('/roulette/join')
async def roulette_join(
        chat_id: int = Query(...),
        authorization: str = Header()
):
    if not validate_telegram_init_data(authorization, settings.TOKEN):
        raise HTTPException(status_code=401, detail="Invalid authorization")
    user_id = get_user_id_from_init_data(authorization)
    key = _key_roulette(chat_id)
    if not redis.exists(key):
        raise HTTPException(status_code=404, detail="Комната не найдена")
    # Список игроков
    players_key = f'{key}:players'
    redis.sadd(players_key, user_id)
    # Имя
    profile = get_user_profile_from_init_data(authorization)
    if profile:
        redis.hset(key, mapping={f'name:{user_id}': profile.get('username') or profile.get('first_name') or ''})
    return {
        'state': redis.hget(key, 'state') or 'open',
        'players': [int(x) for x in redis.smembers(players_key)],
        'names': {pid.decode() if hasattr(pid, 'decode') else str(pid): redis.hget(key, f'name:{pid}') for pid in redis.smembers(players_key)},
    }


@router.post('/roulette/bet')
async def roulette_bet(
        chat_id: int = Query(...),
        bet_json: str = Query(...),
        authorization: str = Header()
):
    # bet_json: {"type":"color","value":"red","amount":10} или число 0-36 при ставке на номер, и т.д.
    if not validate_telegram_init_data(authorization, settings.TOKEN):
        raise HTTPException(status_code=401, detail="Invalid authorization")
    user_id = get_user_id_from_init_data(authorization)
    key = _key_roulette(chat_id)
    if not redis.exists(key):
        raise HTTPException(status_code=404, detail="Комната не найдена")
    try:
        bet = json.loads(bet_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Некорректная ставка")
    redis.rpush(f'{key}:bets', json.dumps({'user_id': user_id, **bet}))
    return {"ok": True}


@router.post('/roulette/spin')
async def roulette_spin(
        chat_id: int = Query(...),
        authorization: str = Header()
):
    if not validate_telegram_init_data(authorization, settings.TOKEN):
        raise HTTPException(status_code=401, detail="Invalid authorization")
    key = _key_roulette(chat_id)
    if not redis.exists(key):
        raise HTTPException(status_code=404, detail="Комната не найдена")
    # Простая заглушка: крутим число 0-36 и цвет
    import random
    number = random.randint(0, 36)
    color = 'green' if number == 0 else ('red' if number % 2 == 1 else 'black')
    bets_key = f'{key}:bets'
    all_bets = [json.loads(x) for x in redis.lrange(bets_key, 0, -1)]
    # Выплаты считаются на фронте или здесь — для MVP вернём результат и ставки
    redis.delete(bets_key)
    return {
        'number': number,
        'color': color,
        'bets': all_bets,
    }


@router.get('/roulette/state')
async def roulette_state(chat_id: int = Query(...)):
    key = _key_roulette(chat_id)
    if not redis.exists(key):
        raise HTTPException(status_code=404, detail="Комната не найдена")
    players_key = f'{key}:players'
    return {
        'state': redis.hget(key, 'state') or 'open',
        'players': [int(x) for x in redis.smembers(players_key)],
        'names': {pid.decode() if hasattr(pid, 'decode') else str(pid): redis.hget(key, f'name:{pid}') for pid in redis.smembers(players_key)},
    }


