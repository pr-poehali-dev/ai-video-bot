"""
Business: Telegram webhook handler - processes all bot messages and callbacks
Args: event with httpMethod, body (Telegram update JSON); context with request_id
Returns: HTTP response with statusCode 200
"""

import json
import os
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

DATABASE_URL = os.environ.get('DATABASE_URL')
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def send_telegram_message(chat_id: int, text: str, reply_markup: Optional[Dict] = None):
    import urllib.request
    import urllib.parse
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

def get_main_menu():
    return {
        'inline_keyboard': [
            [{'text': '🎬 Создать видео', 'callback_data': 'main_create'}],
            [{'text': '💰 Баланс', 'callback_data': 'main_balance'}],
            [{'text': '➕ Пополнить', 'callback_data': 'main_topup'}],
            [{'text': 'ℹ️ Помощь', 'callback_data': 'main_help'}]
        ]
    }

def check_rate_limit(conn, user_id: int, action_type: str) -> bool:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT action_count, window_start 
            FROM rate_limits 
            WHERE user_id = %s AND action_type = %s
        """, (user_id, action_type))
        
        result = cur.fetchone()
        now = datetime.now()
        
        if not result:
            cur.execute("""
                INSERT INTO rate_limits (user_id, action_type, action_count, window_start)
                VALUES (%s, %s, 1, %s)
            """, (user_id, action_type, now))
            conn.commit()
            return True
        
        window_start = result['window_start']
        if now - window_start > timedelta(minutes=1):
            cur.execute("""
                UPDATE rate_limits 
                SET action_count = 1, window_start = %s
                WHERE user_id = %s AND action_type = %s
            """, (now, user_id, action_type))
            conn.commit()
            return True
        
        if result['action_count'] >= 10:
            return False
        
        cur.execute("""
            UPDATE rate_limits 
            SET action_count = action_count + 1
            WHERE user_id = %s AND action_type = %s
        """, (user_id, action_type))
        conn.commit()
        return True

def get_or_create_user(conn, user_id: int, username: str, first_name: str) -> Dict:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        
        if user:
            cur.execute("""
                UPDATE users 
                SET last_activity = %s, username = %s, first_name = %s
                WHERE user_id = %s
            """, (datetime.now(), username, first_name, user_id))
            conn.commit()
            return dict(user)
        
        cur.execute("""
            INSERT INTO users (user_id, username, first_name, balance, created_at, last_activity)
            VALUES (%s, %s, %s, 800, %s, %s)
            RETURNING *
        """, (user_id, username, first_name, datetime.now(), datetime.now()))
        
        new_user = cur.fetchone()
        
        cur.execute("""
            INSERT INTO transactions (user_id, amount, type, description, created_at)
            VALUES (%s, 800, 'welcome_bonus', 'Приветственный бонус', %s)
        """, (user_id, datetime.now()))
        
        conn.commit()
        return dict(new_user)

def handle_start(conn, user_id: int, username: str, first_name: str, chat_id: int):
    user = get_or_create_user(conn, user_id, username, first_name)
    
    if user['balance'] == 800 and user['created_at'].replace(tzinfo=None) > datetime.now() - timedelta(seconds=5):
        text = (
            "🎉 <b>Добро пожаловать в AI Video Studio!</b>\n\n"
            f"Вам начислено <b>800 кредитов</b>. Хватит, чтобы сделать превью или видео.\n\n"
            "Выберите действие:"
        )
    else:
        text = (
            f"👋 <b>С возвращением, {first_name}!</b>\n\n"
            f"💰 Баланс: <b>{user['balance']} кредитов</b>\n\n"
            "Выберите действие:"
        )
    
    send_telegram_message(chat_id, text, get_main_menu())

def handle_balance(conn, user_id: int, chat_id: int):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        
        balance = user['balance'] if user else 0
        
        text = f"💰 <b>Ваш баланс: {balance} кредитов</b>"
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '➕ Пополнить', 'callback_data': 'main_topup'}],
                [{'text': '🎬 Создать видео', 'callback_data': 'main_create'}],
                [{'text': '🏠 Главное меню', 'callback_data': 'main_menu'}]
            ]
        }
        
        send_telegram_message(chat_id, text, keyboard)

def handle_topup(chat_id: int):
    text = "💳 <b>Пополнение баланса</b>\n\nВыберите пакет кредитов:"
    
    keyboard = {
        'inline_keyboard': [
            [{'text': '200 кредитов — 200₽', 'callback_data': 'buy_200'}],
            [{'text': '500 кредитов — 500₽', 'callback_data': 'buy_500'}],
            [{'text': '1000 кредитов — 1000₽', 'callback_data': 'buy_1000'}],
            [{'text': '🏠 Главное меню', 'callback_data': 'main_menu'}]
        ]
    }
    
    send_telegram_message(chat_id, text, keyboard)

def handle_create(chat_id: int):
    text = "🎬 <b>Создание контента</b>\n\nВыберите тип:"
    
    keyboard = {
        'inline_keyboard': [
            [{'text': '🎨 Превью (30 кредитов)', 'callback_data': 'create_preview'}],
            [{'text': '🎥 Видео из текста', 'callback_data': 'create_textvideo'}],
            [{'text': '📽 Storyboard (мультисцена)', 'callback_data': 'create_storyboard'}],
            [{'text': '🏠 Главное меню', 'callback_data': 'main_menu'}]
        ]
    }
    
    send_telegram_message(chat_id, text, keyboard)

def handle_help(chat_id: int):
    text = (
        "ℹ️ <b>Помощь - AI Video Studio</b>\n\n"
        "<b>🎨 Превью</b> - 30 кредитов\n"
        "Создаёт статичный кадр из описания\n\n"
        "<b>🎥 Видео из текста</b>\n"
        "• 5 сек standard - 180 кредитов\n"
        "• 10 сек standard - 400 кредитов\n"
        "• 15 сек standard - 600 кредитов\n"
        "• high качество - +200 кредитов\n\n"
        "<b>📽 Storyboard</b>\n"
        "Мультисценное видео (2-15 сцен)\n"
        "От 180 кредитов + 50 за каждую сцену после 3-й\n\n"
        "💰 1 кредит = 1 рубль"
    )
    
    keyboard = {
        'inline_keyboard': [
            [{'text': '🏠 Главное меню', 'callback_data': 'main_menu'}]
        ]
    }
    
    send_telegram_message(chat_id, text, keyboard)

def handle_create_preview(conn, user_id: int, chat_id: int):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        
        if user['balance'] < 30:
            text = "⚠️ Недостаточно кредитов для создания превью.\n\nТребуется: 30 кредитов"
            keyboard = {
                'inline_keyboard': [
                    [{'text': '➕ Пополнить', 'callback_data': 'main_topup'}],
                    [{'text': '🏠 Главное меню', 'callback_data': 'main_menu'}]
                ]
            }
            send_telegram_message(chat_id, text, keyboard)
            return
        
        cur.execute("""
            INSERT INTO user_states (user_id, state, updated_at)
            VALUES (%s, 'waiting_preview_prompt', %s)
            ON CONFLICT (user_id) DO UPDATE 
            SET state = 'waiting_preview_prompt', updated_at = %s
        """, (user_id, datetime.now(), datetime.now()))
        conn.commit()
        
        text = "🎨 <b>Создание превью</b>\n\nОпишите, что вы хотите увидеть на кадре:"
        send_telegram_message(chat_id, text)

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
            'body': ''
        }
    
    try:
        body = json.loads(event.get('body', '{}'))
        conn = get_db_connection()
        
        if 'message' in body:
            message = body['message']
            user_id = message['from']['id']
            chat_id = message['chat']['id']
            username = message['from'].get('username', '')
            first_name = message['from'].get('first_name', 'User')
            text = message.get('text', '')
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT is_blocked FROM users WHERE user_id = %s", (user_id,))
                user = cur.fetchone()
                
                if user and user['is_blocked']:
                    send_telegram_message(chat_id, "🚫 Ваш аккаунт заблокирован. Поддержка: @support")
                    conn.close()
                    return {'statusCode': 200, 'body': json.dumps({'ok': True})}
            
            if not check_rate_limit(conn, user_id, 'message'):
                send_telegram_message(chat_id, "⚠️ Слишком много запросов. Подождите минуту.")
                conn.close()
                return {'statusCode': 200, 'body': json.dumps({'ok': True})}
            
            if text == '/start':
                handle_start(conn, user_id, username, first_name, chat_id)
            else:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT state FROM user_states WHERE user_id = %s", (user_id,))
                    state = cur.fetchone()
                    
                    if state and state['state'] == 'waiting_preview_prompt':
                        send_telegram_message(chat_id, "⏳ Создаю превью... Это займёт 30-60 секунд.")
        
        elif 'callback_query' in body:
            callback = body['callback_query']
            user_id = callback['from']['id']
            chat_id = callback['message']['chat']['id']
            username = callback['from'].get('username', '')
            first_name = callback['from'].get('first_name', 'User')
            data = callback['data']
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT is_blocked FROM users WHERE user_id = %s", (user_id,))
                user = cur.fetchone()
                
                if user and user['is_blocked']:
                    send_telegram_message(chat_id, "🚫 Ваш аккаунт заблокирован. Поддержка: @support")
                    conn.close()
                    return {'statusCode': 200, 'body': json.dumps({'ok': True})}
            
            if not check_rate_limit(conn, user_id, 'callback'):
                send_telegram_message(chat_id, "⚠️ Слишком много запросов. Подождите минуту.")
                conn.close()
                return {'statusCode': 200, 'body': json.dumps({'ok': True})}
            
            get_or_create_user(conn, user_id, username, first_name)
            
            if data == 'main_menu':
                handle_start(conn, user_id, username, first_name, chat_id)
            elif data == 'main_balance':
                handle_balance(conn, user_id, chat_id)
            elif data == 'main_topup':
                handle_topup(chat_id)
            elif data == 'main_create':
                handle_create(chat_id)
            elif data == 'main_help':
                handle_help(chat_id)
            elif data == 'create_preview':
                handle_create_preview(conn, user_id, chat_id)
        
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'ok': True})
        }
    
    except Exception as e:
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO error_logs (workflow_name, error_type, error_message, telegram_update, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                """, ('telegram_webhook', type(e).__name__, str(e), json.dumps(body), datetime.now()))
            conn.commit()
            conn.close()
        except:
            pass
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }
