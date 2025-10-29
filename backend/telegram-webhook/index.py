"""
Business: Telegram webhook - processes bot messages, callbacks, handles orders and billing
Args: event with POST body (Telegram update JSON), context with request_id
Returns: HTTP response 200 OK
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import urllib.request
import urllib.parse

DATABASE_URL = os.environ.get('DATABASE_URL')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
IMAGE_API_URL = os.environ.get('IMAGE_API_URL', 'https://example.com/image')
VIDEO_API_URL = os.environ.get('VIDEO_API_URL', 'https://example.com/video')
STORYBOARD_API_URL = os.environ.get('STORYBOARD_API_URL', 'https://example.com/storyboard')

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

PRICING = {
    'preview': 30,
    'text-to-video': {
        (5, 'standard'): 180,
        (10, 'standard'): 400,
        (15, 'standard'): 600,
        (5, 'high'): 380,
        (10, 'high'): 600,
        (15, 'high'): 800
    },
    'storyboard': {10: 180, 15: 400, 25: 510}
}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    method = event.get('httpMethod', 'POST')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Max-Age': '86400'
            },
            'isBase64Encoded': False,
            'body': ''
        }
    
    try:
        body = json.loads(event.get('body', '{}'))
        
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        
        if 'message' in body:
            handle_message(body['message'], conn)
        elif 'callback_query' in body:
            handle_callback(body['callback_query'], conn)
        
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'isBase64Encoded': False,
            'body': json.dumps({'ok': True})
        }
        
    except Exception as e:
        log_error(None, None, 'telegram_webhook', 'exception', str(e), body if 'body' in locals() else {})
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'isBase64Encoded': False,
            'body': json.dumps({'ok': True})
        }


def handle_message(message: Dict[str, Any], conn) -> None:
    user_id = message['from']['id']
    username = message['from'].get('username')
    first_name = message['from'].get('first_name', 'User')
    text = message.get('text', '')
    
    if not check_rate_limit(user_id, 'message', conn):
        send_message(user_id, "⚠️ Слишком много запросов. Подождите минуту.")
        return
    
    user = get_or_create_user(user_id, username, first_name, conn)
    
    if user['is_blocked']:
        send_message(user_id, "🚫 Ваш аккаунт заблокирован. Поддержка: @support")
        return
    
    update_last_activity(user_id, conn)
    
    state = get_user_state(user_id, conn)
    
    if text == '/start':
        clear_user_state(user_id, conn)
        welcome_text = f"👋 С возвращением, {first_name}!\nБаланс: {user['balance']} кредитов" if user.get('existing') else "🎉 Добро пожаловать в AI Video Studio!\nВам начислено 800 кредитов. Хватит, чтобы сделать превью или видео."
        send_message(user_id, welcome_text, get_main_menu())
        return
    
    if state:
        handle_state_message(user_id, text, state, message, conn)
    else:
        send_message(user_id, "Используйте кнопки меню ниже 👇", get_main_menu())


def handle_callback(callback: Dict[str, Any], conn) -> None:
    user_id = callback['from']['id']
    callback_id = callback['id']
    data = callback['data']
    message_id = callback['message']['message_id']
    
    if not check_rate_limit(user_id, 'callback', conn):
        answer_callback(callback_id, "⚠️ Слишком много запросов")
        return
    
    user = get_user(user_id, conn)
    
    if not user:
        answer_callback(callback_id, "Пожалуйста, отправьте /start")
        return
    
    if user['is_blocked']:
        answer_callback(callback_id, "Аккаунт заблокирован")
        return
    
    update_last_activity(user_id, conn)
    
    if data == 'main_balance':
        edit_message(user_id, message_id, f"💰 Ваш баланс: {user['balance']} кредитов", get_balance_keyboard())
        answer_callback(callback_id)
    
    elif data == 'main_topup':
        edit_message(user_id, message_id, "💳 Выберите пакет кредитов:", get_topup_keyboard())
        answer_callback(callback_id)
    
    elif data == 'main_create':
        edit_message(user_id, message_id, "🎬 Что создаём?", get_create_keyboard())
        answer_callback(callback_id)
    
    elif data == 'main_help':
        help_text = """ℹ️ Справка по боту:

🎨 Превью — 30 кредитов
🎥 Видео из текста — 180-800 кредитов
📽 Storyboard — от 180 кредитов

1 кредит = 1 рубль"""
        edit_message(user_id, message_id, help_text, get_back_keyboard())
        answer_callback(callback_id)
    
    elif data == 'create_preview':
        set_user_state(user_id, 'waiting_preview_prompt', conn)
        edit_message(user_id, message_id, "🎨 Опишите, что изобразить на превью:", get_cancel_keyboard())
        answer_callback(callback_id, "Напишите описание")
    
    elif data == 'create_textvideo':
        set_user_state(user_id, 'waiting_textvideo_prompt', conn)
        edit_message(user_id, message_id, "📝 Опишите видео:", get_cancel_keyboard())
        answer_callback(callback_id, "Напишите описание")
    
    elif data.startswith('topup_'):
        amount = int(data.split('_')[1])
        handle_topup(user_id, amount, message_id, conn)
        answer_callback(callback_id, f"Оплата {amount}₽")
    
    elif data.startswith('duration_'):
        duration = int(data.split('_')[1])
        handle_duration_selection(user_id, duration, conn)
        edit_message(user_id, message_id, f"✅ Выбрана длительность: {duration}с\n\nВыберите качество:", get_quality_keyboard())
        answer_callback(callback_id)
    
    elif data.startswith('quality_'):
        quality = data.split('_')[1]
        handle_quality_selection(user_id, quality, message_id, conn)
        answer_callback(callback_id)
    
    elif data.startswith('confirm_order_'):
        order_id = int(data.split('_')[2])
        process_order_payment(user_id, order_id, message_id, conn)
        answer_callback(callback_id)
    
    elif data == 'cancel':
        clear_user_state(user_id, conn)
        edit_message(user_id, message_id, "❌ Отменено", get_main_menu())
        answer_callback(callback_id)
    
    elif data == 'back':
        clear_user_state(user_id, conn)
        edit_message(user_id, message_id, "Главное меню:", get_main_menu())
        answer_callback(callback_id)
    
    else:
        answer_callback(callback_id)


def handle_state_message(user_id: int, text: str, state: Dict, message: Dict, conn) -> None:
    state_name = state['state']
    
    if state_name == 'waiting_preview_prompt':
        handle_preview_order(user_id, text, conn)
    
    elif state_name == 'waiting_textvideo_prompt':
        update_user_state(user_id, {'temp_prompt': text}, conn)
        set_user_state(user_id, 'waiting_textvideo_duration', conn)
        send_message(user_id, "⏱ Выберите длительность видео:", get_duration_keyboard())
    
    elif state_name == 'storyboard_adding_scene':
        pass


def handle_preview_order(user_id: int, prompt: str, conn) -> None:
    cost = PRICING['preview']
    user = get_user(user_id, conn)
    
    if user['balance'] < cost:
        send_message(user_id, f"❌ Недостаточно кредитов. Нужно {cost}, у вас {user['balance']}", get_topup_keyboard())
        clear_user_state(user_id, conn)
        return
    
    deduct_balance(user_id, cost, 'preview', f"Превью: {prompt[:50]}", conn)
    order_id = create_order(user_id, 'preview', prompt, None, None, cost, conn)
    
    submit_to_image_api(order_id, prompt, conn)
    
    clear_user_state(user_id, conn)
    send_message(user_id, f"✅ Заказ #{order_id} создан!\n⏳ Генерация займёт 30-60 секунд...", get_main_menu())


def handle_duration_selection(user_id: int, duration: int, conn) -> None:
    update_user_state(user_id, {'temp_duration': duration}, conn)
    set_user_state(user_id, 'waiting_textvideo_quality', conn)


def handle_quality_selection(user_id: int, quality: str, message_id: int, conn) -> None:
    state = get_user_state(user_id, conn)
    duration = state.get('temp_duration')
    prompt = state.get('temp_prompt')
    
    cost = PRICING['text-to-video'][(duration, quality)]
    user = get_user(user_id, conn)
    
    confirmation_text = f"""📋 Подтвердите заказ:

📝 Описание: {prompt[:100]}
⏱ Длительность: {duration}с
🎞 Качество: {quality}

💰 Стоимость: {cost} кредитов
💵 Ваш баланс: {user['balance']} кредитов"""
    
    if user['balance'] < cost:
        edit_message(user_id, message_id, f"❌ Недостаточно кредитов\n\nНужно: {cost}\nУ вас: {user['balance']}", get_topup_keyboard())
        clear_user_state(user_id, conn)
        return
    
    temp_order_id = create_temp_order(user_id, 'text-to-video', prompt, duration, quality, cost, conn)
    
    keyboard = {
        'inline_keyboard': [
            [{'text': '✅ Подтвердить', 'callback_data': f'confirm_order_{temp_order_id}'}],
            [{'text': '❌ Отменить', 'callback_data': 'cancel'}]
        ]
    }
    
    edit_message(user_id, message_id, confirmation_text, keyboard)


def process_order_payment(user_id: int, order_id: int, message_id: int, conn) -> None:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM orders WHERE order_id = %s AND user_id = %s", (order_id, user_id))
    order = cur.fetchone()
    
    if not order or order['status'] != 'pending':
        edit_message(user_id, message_id, "❌ Заказ не найден или уже обработан", get_main_menu())
        return
    
    user = get_user(user_id, conn)
    
    if user['balance'] < order['cost']:
        edit_message(user_id, message_id, "❌ Недостаточно кредитов", get_topup_keyboard())
        return
    
    deduct_balance(user_id, order['cost'], 'video', f"Видео {order['duration']}с", conn)
    cur.execute("UPDATE orders SET status = 'processing' WHERE order_id = %s", (order_id,))
    
    submit_to_video_api(order_id, order['prompt'], order['duration'], order['quality'], conn)
    
    clear_user_state(user_id, conn)
    edit_message(user_id, message_id, f"✅ Заказ #{order_id} оплачен!\n⏳ Генерация видео займёт 2-5 минут...", get_main_menu())


def submit_to_image_api(order_id: int, prompt: str, conn) -> None:
    try:
        data = json.dumps({'prompt': prompt, 'order_id': order_id}).encode('utf-8')
        req = urllib.request.Request(IMAGE_API_URL, data=data, headers={'Content-Type': 'application/json'})
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            task_id = result.get('task_id')
            
            if task_id:
                cur = conn.cursor()
                cur.execute("UPDATE orders SET task_id = %s, status = 'processing' WHERE order_id = %s", (task_id, order_id))
    except Exception as e:
        log_error(None, order_id, 'submit_image_api', 'api_error', str(e), {})
        cur = conn.cursor()
        cur.execute("UPDATE orders SET status = 'failed', error_message = %s WHERE order_id = %s", (str(e), order_id))


def submit_to_video_api(order_id: int, prompt: str, duration: int, quality: str, conn) -> None:
    try:
        data = json.dumps({'prompt': prompt, 'duration': duration, 'quality': quality, 'order_id': order_id}).encode('utf-8')
        req = urllib.request.Request(VIDEO_API_URL, data=data, headers={'Content-Type': 'application/json'})
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            task_id = result.get('task_id')
            
            if task_id:
                cur = conn.cursor()
                cur.execute("UPDATE orders SET task_id = %s WHERE order_id = %s", (task_id, order_id))
    except Exception as e:
        log_error(None, order_id, 'submit_video_api', 'api_error', str(e), {})
        cur = conn.cursor()
        cur.execute("UPDATE orders SET status = 'failed', error_message = %s WHERE order_id = %s", (str(e), order_id))


def get_or_create_user(user_id: int, username: str, first_name: str, conn) -> Dict:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()
    
    if not user:
        cur.execute(
            "INSERT INTO users (user_id, username, first_name, balance) VALUES (%s, %s, %s, 800) RETURNING *",
            (user_id, username, first_name)
        )
        user = cur.fetchone()
        
        cur.execute(
            "INSERT INTO transactions (user_id, amount, type, description) VALUES (%s, %s, %s, %s)",
            (user_id, 800, 'welcome_bonus', 'Приветственный бонус')
        )
        return dict(user, existing=False)
    
    return dict(user, existing=True)


def get_user(user_id: int, conn) -> Optional[Dict]:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    return cur.fetchone()


def update_last_activity(user_id: int, conn) -> None:
    cur = conn.cursor()
    cur.execute("UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = %s", (user_id,))


def check_rate_limit(user_id: int, action_type: str, conn) -> bool:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM rate_limits WHERE user_id = %s AND action_type = %s", (user_id, action_type))
    limit = cur.fetchone()
    
    now = datetime.now()
    
    if not limit:
        cur.execute(
            "INSERT INTO rate_limits (user_id, action_type, action_count, window_start) VALUES (%s, %s, 1, %s)",
            (user_id, action_type, now)
        )
        return True
    
    window_start = limit['window_start']
    
    if (now - window_start).total_seconds() > 60:
        cur.execute(
            "UPDATE rate_limits SET action_count = 1, window_start = %s WHERE user_id = %s AND action_type = %s",
            (now, user_id, action_type)
        )
        return True
    
    if limit['action_count'] >= 10:
        return False
    
    cur.execute(
        "UPDATE rate_limits SET action_count = action_count + 1 WHERE user_id = %s AND action_type = %s",
        (user_id, action_type)
    )
    return True


def deduct_balance(user_id: int, amount: int, trans_type: str, description: str, conn) -> None:
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance - %s WHERE user_id = %s", (amount, user_id))
    cur.execute(
        "INSERT INTO transactions (user_id, amount, type, description) VALUES (%s, %s, %s, %s)",
        (user_id, -amount, trans_type, description)
    )


def create_order(user_id: int, order_type: str, prompt: str, duration: Optional[int], quality: Optional[str], cost: int, conn) -> int:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (user_id, order_type, prompt, duration, quality, cost, status) VALUES (%s, %s, %s, %s, %s, %s, 'pending') RETURNING order_id",
        (user_id, order_type, prompt, duration, quality, cost)
    )
    return cur.fetchone()[0]


def create_temp_order(user_id: int, order_type: str, prompt: str, duration: int, quality: str, cost: int, conn) -> int:
    return create_order(user_id, order_type, prompt, duration, quality, cost, conn)


def get_user_state(user_id: int, conn) -> Optional[Dict]:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM user_states WHERE user_id = %s", (user_id,))
    return cur.fetchone()


def set_user_state(user_id: int, state: str, conn) -> None:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO user_states (user_id, state) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET state = %s, updated_at = CURRENT_TIMESTAMP",
        (user_id, state, state)
    )


def update_user_state(user_id: int, data: Dict, conn) -> None:
    cur = conn.cursor()
    updates = []
    values = []
    
    for key, value in data.items():
        updates.append(f"{key} = %s")
        values.append(value)
    
    values.append(user_id)
    cur.execute(f"UPDATE user_states SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s", values)


def clear_user_state(user_id: int, conn) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM user_states WHERE user_id = %s", (user_id,))


def log_error(user_id: Optional[int], order_id: Optional[int], workflow: str, error_type: str, message: str, update: Dict) -> None:
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO error_logs (user_id, order_id, workflow_name, error_type, error_message, telegram_update) VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, order_id, workflow, error_type, message, Json(update))
        )
        conn.commit()
        conn.close()
    except:
        pass


def send_message(chat_id: int, text: str, keyboard: Optional[Dict] = None) -> None:
    payload = {'chat_id': chat_id, 'text': text}
    if keyboard:
        payload['reply_markup'] = keyboard
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(f"{TELEGRAM_API}/sendMessage", data=data, headers={'Content-Type': 'application/json'})
    
    try:
        urllib.request.urlopen(req, timeout=5)
    except:
        pass


def edit_message(chat_id: int, message_id: int, text: str, keyboard: Optional[Dict] = None) -> None:
    payload = {'chat_id': chat_id, 'message_id': message_id, 'text': text}
    if keyboard:
        payload['reply_markup'] = keyboard
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(f"{TELEGRAM_API}/editMessageText", data=data, headers={'Content-Type': 'application/json'})
    
    try:
        urllib.request.urlopen(req, timeout=5)
    except:
        pass


def answer_callback(callback_id: str, text: str = None) -> None:
    payload = {'callback_query_id': callback_id}
    if text:
        payload['text'] = text
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(f"{TELEGRAM_API}/answerCallbackQuery", data=data, headers={'Content-Type': 'application/json'})
    
    try:
        urllib.request.urlopen(req, timeout=5)
    except:
        pass


def handle_topup(user_id: int, amount: int, message_id: int, conn) -> None:
    send_message(user_id, f"💳 Оплата {amount}₽\n\n⏳ Интеграция с ЮKassa в процессе...")


def get_main_menu() -> Dict:
    return {
        'inline_keyboard': [
            [{'text': '🎬 Создать видео', 'callback_data': 'main_create'}],
            [{'text': '💰 Баланс', 'callback_data': 'main_balance'}, {'text': '➕ Пополнить', 'callback_data': 'main_topup'}],
            [{'text': 'ℹ️ Помощь', 'callback_data': 'main_help'}]
        ]
    }


def get_balance_keyboard() -> Dict:
    return {
        'inline_keyboard': [
            [{'text': '➕ Пополнить', 'callback_data': 'main_topup'}],
            [{'text': '🎬 Создать видео', 'callback_data': 'main_create'}],
            [{'text': '◀️ Назад', 'callback_data': 'back'}]
        ]
    }


def get_topup_keyboard() -> Dict:
    return {
        'inline_keyboard': [
            [{'text': '200₽', 'callback_data': 'topup_200'}, {'text': '500₽', 'callback_data': 'topup_500'}],
            [{'text': '1000₽', 'callback_data': 'topup_1000'}, {'text': '2000₽', 'callback_data': 'topup_2000'}],
            [{'text': '◀️ Назад', 'callback_data': 'back'}]
        ]
    }


def get_create_keyboard() -> Dict:
    return {
        'inline_keyboard': [
            [{'text': '🎨 Превью (30₽)', 'callback_data': 'create_preview'}],
            [{'text': '🎥 Видео из текста', 'callback_data': 'create_textvideo'}],
            [{'text': '◀️ Назад', 'callback_data': 'back'}]
        ]
    }


def get_duration_keyboard() -> Dict:
    return {
        'inline_keyboard': [
            [{'text': '5 сек (от 180₽)', 'callback_data': 'duration_5'}],
            [{'text': '10 сек (от 400₽)', 'callback_data': 'duration_10'}],
            [{'text': '15 сек (от 600₽)', 'callback_data': 'duration_15'}],
            [{'text': '❌ Отменить', 'callback_data': 'cancel'}]
        ]
    }


def get_quality_keyboard() -> Dict:
    return {
        'inline_keyboard': [
            [{'text': '📺 Standard', 'callback_data': 'quality_standard'}],
            [{'text': '🎬 High (+200₽)', 'callback_data': 'quality_high'}],
            [{'text': '❌ Отменить', 'callback_data': 'cancel'}]
        ]
    }


def get_cancel_keyboard() -> Dict:
    return {
        'inline_keyboard': [[{'text': '❌ Отменить', 'callback_data': 'cancel'}]]
    }


def get_back_keyboard() -> Dict:
    return {
        'inline_keyboard': [[{'text': '◀️ Назад', 'callback_data': 'back'}]]
    }
