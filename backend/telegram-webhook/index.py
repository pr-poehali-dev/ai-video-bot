'''
Business: Обработка webhook-запросов от Telegram Bot API, управление диалогами, кредитной системой и заказами
Args: event с httpMethod, body (JSON от Telegram), context с request_id
Returns: HTTP response 200 OK для подтверждения получения update
'''

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import urllib.request

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
DATABASE_URL = os.environ.get('DATABASE_URL')
GEN_API_KEY = os.environ.get('GEN_API_KEY', '57dabe651c81b31ea5ee1bb021817051')
GEN_SORA_API_URL = os.environ.get('GEN_SORA_API_URL', 'https://api.kie.ai/api/v1/jobs/createTask')
GEN_IMAGE_API_URL = os.environ.get('GEN_IMAGE_API_URL', 'https://api.kie.ai/api/v1/gpt4o-image/generate')
GEN_MODEL_TEXT2VIDEO = os.environ.get('GEN_MODEL_TEXT2VIDEO', 'sora-2-pro-text-to-video')
GEN_MODEL_IMAGE2VIDEO = os.environ.get('GEN_MODEL_IMAGE2VIDEO', 'sora-2-pro-image-to-video')
GEN_MODEL_STORYBOARD = os.environ.get('GEN_MODEL_STORYBOARD', 'sora-2-pro-storyboard')
GEN_MODEL_IMAGE = os.environ.get('GEN_MODEL_IMAGE', '4o-image-api')
GEN_CALLBACK_URL = os.environ.get('GEN_CALLBACK_URL', 'https://functions.poehali.dev/1655da17-3061-4871-9fbb-026dcf946587')
TELEGRAM_PAYMENT_PROVIDER_TOKEN = os.environ.get('TELEGRAM_PAYMENT_PROVIDER_TOKEN', '')
TELEGRAM_STARS_ENABLED = os.environ.get('TELEGRAM_STARS_ENABLED', 'true').lower() == 'true'

PREVIEW_COST = 30
VIDEO_COSTS = {
    5: {'standard': 180, 'high': 380},
    10: {'standard': 400, 'high': 600},
    15: {'standard': 600, 'high': 800}
}

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def send_telegram_message(chat_id: int, text: str, reply_markup: Optional[Dict] = None):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if reply_markup:
        data['reply_markup'] = reply_markup
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"[ERROR] Telegram API error: {e.code} - {error_body}")
        raise

def main_menu_keyboard():
    return {
        'inline_keyboard': [
            [{'text': '🎬 Создать видео', 'callback_data': 'main_create'}],
            [{'text': '💰 Баланс', 'callback_data': 'main_balance'}],
            [{'text': '➕ Пополнить', 'callback_data': 'main_topup'}],
            [{'text': 'ℹ️ Помощь', 'callback_data': 'main_help'}]
        ]
    }

def create_menu_keyboard():
    return {
        'inline_keyboard': [
            [{'text': '🎨 Превью', 'callback_data': 'create_preview'}],
            [{'text': '📝 Видео из текста', 'callback_data': 'create_textvideo'}],
            [{'text': '🖼️ Видео из картинки', 'callback_data': 'create_imagevideo'}],
            [{'text': '🎬 Сториборд', 'callback_data': 'create_storyboard'}],
            [{'text': '⬅️ Назад', 'callback_data': 'back_to_main'}]
        ]
    }

def topup_menu_keyboard():
    keyboard = []
    if TELEGRAM_PAYMENT_PROVIDER_TOKEN:
        keyboard.append([{'text': '💳 Оплатить картой', 'callback_data': 'topup_card'}])
    if TELEGRAM_STARS_ENABLED:
        keyboard.append([{'text': '⭐ Оплатить звёздами', 'callback_data': 'topup_stars'}])
    keyboard.append([{'text': '⬅️ Назад', 'callback_data': 'back_to_main'}])
    return {'inline_keyboard': keyboard}

def check_rate_limit(conn, user_id: int, action_type: str, max_actions: int = 10) -> bool:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT action_count, window_start 
            FROM t_p62125649_ai_video_bot.rate_limits 
            WHERE user_id = %s AND action_type = %s
        """, (user_id, action_type))
        
        result = cur.fetchone()
        now = datetime.now()
        
        if not result:
            cur.execute("""
                INSERT INTO t_p62125649_ai_video_bot.rate_limits (user_id, action_type, action_count, window_start)
                VALUES (%s, %s, 1, %s)
            """, (user_id, action_type, now))
            conn.commit()
            return True
        
        action_count, window_start = result
        
        if now - window_start > timedelta(minutes=1):
            cur.execute("""
                UPDATE t_p62125649_ai_video_bot.rate_limits 
                SET action_count = 1, window_start = %s
                WHERE user_id = %s AND action_type = %s
            """, (now, user_id, action_type))
            conn.commit()
            return True
        
        if action_count >= max_actions:
            return False
        
        cur.execute("""
            UPDATE t_p62125649_ai_video_bot.rate_limits 
            SET action_count = action_count + 1
            WHERE user_id = %s AND action_type = %s
        """, (user_id, action_type))
        conn.commit()
        return True

def get_or_create_user(conn, user_id: int, username: str, first_name: str) -> Dict:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM t_p62125649_ai_video_bot.users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        
        if not user:
            cur.execute("""
                INSERT INTO t_p62125649_ai_video_bot.users (user_id, username, first_name, balance)
                VALUES (%s, %s, %s, 500)
                RETURNING *
            """, (user_id, username, first_name))
            user = cur.fetchone()
            
            cur.execute("""
                INSERT INTO t_p62125649_ai_video_bot.transactions (user_id, amount, type, description)
                VALUES (%s, 500, 'welcome_bonus', 'Приветственный бонус')
            """, (user_id,))
            
            conn.commit()
            return {'user': dict(user), 'is_new': True}
        
        cur.execute("""
            UPDATE t_p62125649_ai_video_bot.users 
            SET last_activity = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """, (user_id,))
        conn.commit()
        
        return {'user': dict(user), 'is_new': False}

def handle_start_command(conn, chat_id: int, user_id: int, username: str, first_name: str):
    user_info = get_or_create_user(conn, user_id, username, first_name)
    user = user_info['user']
    
    if user.get('is_blocked'):
        send_telegram_message(chat_id, "🚫 Ваш аккаунт заблокирован. Поддержка: @support")
        return
    
    if user_info['is_new']:
        text = "🎉 Добро пожаловать в AI Video Studio!\n\nВам начислено 500 кредитов. Хватит, чтобы сделать превью или видео.\n\n💡 1 кредит = 1 рубль"
    else:
        text = f"👋 С возвращением, {first_name}!\n💰 Баланс: {user['balance']} кредитов"
    
    send_telegram_message(chat_id, text, main_menu_keyboard())

def handle_balance(conn, chat_id: int, user_id: int):
    with conn.cursor() as cur:
        cur.execute("SELECT balance FROM t_p62125649_ai_video_bot.users WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        
        if result:
            balance = result[0]
            keyboard = {
                'inline_keyboard': [
                    [{'text': '➕ Пополнить', 'callback_data': 'main_topup'}],
                    [{'text': '🎬 Создать видео', 'callback_data': 'main_create'}]
                ]
            }
            send_telegram_message(chat_id, f"💰 Ваш баланс: {balance} кредитов", keyboard)

def handle_topup(chat_id: int):
    send_telegram_message(chat_id, "💰 Выберите способ пополнения баланса:", topup_menu_keyboard())

def handle_topup_card(chat_id: int):
    keyboard = {
        'inline_keyboard': [
            [{'text': '100₽', 'callback_data': 'pay_card_100'}],
            [{'text': '500₽', 'callback_data': 'pay_card_500'}],
            [{'text': '1000₽', 'callback_data': 'pay_card_1000'}],
            [{'text': '⬅️ Назад', 'callback_data': 'main_topup'}]
        ]
    }
    send_telegram_message(chat_id, "💳 Выберите сумму пополнения:", keyboard)

def handle_topup_stars(chat_id: int):
    keyboard = {
        'inline_keyboard': [
            [{'text': '10⭐', 'callback_data': 'pay_stars_10'}],
            [{'text': '50⭐', 'callback_data': 'pay_stars_50'}],
            [{'text': '100⭐', 'callback_data': 'pay_stars_100'}],
            [{'text': '⬅️ Назад', 'callback_data': 'main_topup'}]
        ]
    }
    send_telegram_message(chat_id, "⭐ Выберите количество звёзд:", keyboard)

def send_invoice(chat_id: int, title: str, description: str, payload: str, currency: str, prices: list):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendInvoice'
    
    data = {
        'chat_id': chat_id,
        'title': title,
        'description': description,
        'payload': payload,
        'currency': currency,
        'prices': prices
    }
    
    if currency == 'XTR':
        # Telegram Stars payment - no provider token needed
        pass
    else:
        # Card payment - requires provider token
        if not TELEGRAM_PAYMENT_PROVIDER_TOKEN:
            send_telegram_message(chat_id, "❌ Оплата картой временно недоступна", topup_menu_keyboard())
            return
        data['provider_token'] = TELEGRAM_PAYMENT_PROVIDER_TOKEN
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        send_telegram_message(chat_id, f"❌ Ошибка при создании счета: {str(e)}", topup_menu_keyboard())
        return None

def handle_payment_card(chat_id: int, user_id: int, amount: int):
    if not TELEGRAM_PAYMENT_PROVIDER_TOKEN:
        send_telegram_message(chat_id, "❌ Оплата картой временно недоступна", topup_menu_keyboard())
        return
    
    credits = amount
    title = f"Пополнение баланса на {credits} кредитов"
    description = f"Пополнение баланса AI Video Studio Bot на {credits} кредитов"
    payload = json.dumps({'user_id': user_id, 'amount': amount, 'type': 'card'})
    
    send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        currency='RUB',
        prices=[{'label': f'{credits} кредитов', 'amount': amount * 100}]  # amount in kopecks
    )

def handle_payment_stars(chat_id: int, user_id: int, stars: int):
    if not TELEGRAM_STARS_ENABLED:
        send_telegram_message(chat_id, "❌ Оплата звёздами временно недоступна", topup_menu_keyboard())
        return
    
    # 1 star = 10 credits (you can adjust this rate)
    credits = stars * 10
    title = f"Пополнение на {credits} кредитов"
    description = f"Пополнение баланса AI Video Studio Bot за {stars} звёзд"
    payload = json.dumps({'user_id': user_id, 'stars': stars, 'credits': credits, 'type': 'stars'})
    
    send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        currency='XTR',
        prices=[{'label': f'{credits} кредитов', 'amount': stars}]  # amount in stars
    )

def handle_help(chat_id: int):
    text = """ℹ️ <b>AI Video Studio Bot</b>

<b>Что умеет бот:</b>
🎨 <b>Превью</b> (30₽) - генерация кадра
📝 <b>Видео из текста</b> - создание видео

<b>Цены на видео:</b>
5 сек (стандарт) - 180₽
10 сек (стандарт) - 400₽
15 сек (стандарт) - 600₽
Высокое качество: +200₽

Поддержка: @support"""
    
    keyboard = {'inline_keyboard': [[{'text': '⬅️ Назад', 'callback_data': 'back_to_main'}]]}
    send_telegram_message(chat_id, text, keyboard)

def handle_create_preview(conn, chat_id: int, user_id: int):
    with conn.cursor() as cur:
        cur.execute("SELECT balance FROM t_p62125649_ai_video_bot.users WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        
        if not result or result[0] < PREVIEW_COST:
            send_telegram_message(chat_id, "❌ Недостаточно кредитов. Пополните баланс.", main_menu_keyboard())
            return
        
        cur.execute("""
            INSERT INTO t_p62125649_ai_video_bot.user_states (user_id, state, updated_at)
            VALUES (%s, 'waiting_preview_prompt', CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) 
            DO UPDATE SET state = 'waiting_preview_prompt', updated_at = CURRENT_TIMESTAMP
        """, (user_id,))
        conn.commit()
    
    send_telegram_message(chat_id, f"🎨 <b>Создание превью</b>\n\nСтоимость: {PREVIEW_COST} кредитов\n\nОпишите кадр:")

def handle_create_textvideo(conn, chat_id: int, user_id: int):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO t_p62125649_ai_video_bot.user_states (user_id, state, updated_at)
            VALUES (%s, 'waiting_textvideo_prompt', CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) 
            DO UPDATE SET state = 'waiting_textvideo_prompt', updated_at = CURRENT_TIMESTAMP
        """, (user_id,))
        conn.commit()
    
    send_telegram_message(chat_id, "📝 <b>Видео из текста</b>\n\nОпишите видео:")

def handle_create_imagevideo(conn, chat_id: int, user_id: int):
    with conn.cursor() as cur:
        cur.execute("SELECT balance FROM t_p62125649_ai_video_bot.users WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        
        if not result or result[0] < 300:
            send_telegram_message(chat_id, "❌ Недостаточно кредитов (мин. 300). Пополните баланс.", main_menu_keyboard())
            return
        
        cur.execute("""
            INSERT INTO t_p62125649_ai_video_bot.user_states (user_id, state, updated_at)
            VALUES (%s, 'waiting_image_to_video', CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) 
            DO UPDATE SET state = 'waiting_image_to_video', updated_at = CURRENT_TIMESTAMP
        """, (user_id,))
        conn.commit()
    
    send_telegram_message(chat_id, "🖼️ <b>Видео из картинки</b>\n\nОтправьте фото, которое нужно оживить:")

def handle_create_storyboard(conn, chat_id: int, user_id: int):
    with conn.cursor() as cur:
        cur.execute("SELECT balance FROM t_p62125649_ai_video_bot.users WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        
        if not result or result[0] < 500:
            send_telegram_message(chat_id, "❌ Недостаточно кредитов (мин. 500). Пополните баланс.", main_menu_keyboard())
            return
        
        cur.execute("""
            INSERT INTO t_p62125649_ai_video_bot.user_states (user_id, state, updated_at)
            VALUES (%s, 'waiting_storyboard_scenes', CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) 
            DO UPDATE SET state = 'waiting_storyboard_scenes', updated_at = CURRENT_TIMESTAMP
        """, (user_id,))
        conn.commit()
    
    keyboard = {
        'inline_keyboard': [
            [{'text': '3 сцены', 'callback_data': 'storyboard_scenes_3'}],
            [{'text': '5 сцен', 'callback_data': 'storyboard_scenes_5'}],
            [{'text': '10 сцен', 'callback_data': 'storyboard_scenes_10'}],
            [{'text': '❌ Отмена', 'callback_data': 'back_to_main'}]
        ]
    }
    send_telegram_message(chat_id, "🎬 <b>Сториборд</b>\n\nСколько сцен сделать?", keyboard)

def handle_preview_prompt(conn, chat_id: int, user_id: int, prompt: str):
    with conn.cursor() as cur:
        cur.execute("SELECT balance FROM t_p62125649_ai_video_bot.users WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        
        if not result or result[0] < PREVIEW_COST:
            send_telegram_message(chat_id, "❌ Недостаточно кредитов.", main_menu_keyboard())
            return
        
        cur.execute("UPDATE t_p62125649_ai_video_bot.users SET balance = balance - %s WHERE user_id = %s", (PREVIEW_COST, user_id))
        
        task_id = f'preview_{user_id}_{int(datetime.now().timestamp())}'
        cur.execute("""
            INSERT INTO t_p62125649_ai_video_bot.orders 
            (user_id, order_type, prompt, status, cost, task_id)
            VALUES (%s, 'preview', %s, 'processing', %s, %s)
            RETURNING order_id
        """, (user_id, prompt, PREVIEW_COST, task_id))
        
        order_id = cur.fetchone()[0]
        
        cur.execute("""
            INSERT INTO t_p62125649_ai_video_bot.transactions 
            (user_id, amount, type, description, order_id)
            VALUES (%s, %s, 'preview', 'Списание за превью', %s)
        """, (user_id, -PREVIEW_COST, order_id))
        
        cur.execute("DELETE FROM t_p62125649_ai_video_bot.user_states WHERE user_id = %s", (user_id,))
        conn.commit()
    
    send_telegram_message(chat_id, "⏳ Генерирую превью... Это займёт несколько секунд.")
    
    try:
        request_data = {
            'model': GEN_MODEL_IMAGE,
            'prompt': prompt,
            'api_key': GEN_API_KEY
        }
        
        req = urllib.request.Request(
            GEN_IMAGE_API_URL,
            data=json.dumps(request_data).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {GEN_API_KEY}'}
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            if result.get('status') == 'success' and result.get('image_url'):
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE t_p62125649_ai_video_bot.orders 
                        SET status = 'completed', result_url = %s, completed_at = CURRENT_TIMESTAMP
                        WHERE task_id = %s
                    """, (result['image_url'], task_id))
                    conn.commit()
                
                send_telegram_message(chat_id, f"✅ Ваше превью готово!\n\n{result['image_url']}", main_menu_keyboard())
            else:
                raise Exception("Invalid API response")
    except Exception as e:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE t_p62125649_ai_video_bot.orders 
                SET status = 'failed', error_message = %s
                WHERE task_id = %s
            """, (str(e), task_id))
            cur.execute("UPDATE t_p62125649_ai_video_bot.users SET balance = balance + %s WHERE user_id = %s", (PREVIEW_COST, user_id))
            conn.commit()
        
        send_telegram_message(chat_id, "❌ Ошибка генерации. Кредиты возвращены.", main_menu_keyboard())

def handle_textvideo_prompt(conn, chat_id: int, user_id: int, prompt: str):
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE t_p62125649_ai_video_bot.user_states 
            SET state = 'waiting_textvideo_duration', temp_prompt = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """, (prompt, user_id))
        conn.commit()
    
    keyboard = {
        'inline_keyboard': [
            [{'text': '5 секунд (180₽)', 'callback_data': 'duration_5'}],
            [{'text': '10 секунд (400₽)', 'callback_data': 'duration_10'}],
            [{'text': '15 секунд (600₽)', 'callback_data': 'duration_15'}],
            [{'text': '❌ Отмена', 'callback_data': 'back_to_main'}]
        ]
    }
    send_telegram_message(chat_id, "⏱ Выберите длительность видео:", keyboard)

def handle_duration_selection(conn, chat_id: int, user_id: int, duration: int):
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE t_p62125649_ai_video_bot.user_states 
            SET state = 'waiting_textvideo_quality', temp_duration = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """, (duration, user_id))
        conn.commit()
    
    standard_cost = VIDEO_COSTS[duration]['standard']
    high_cost = VIDEO_COSTS[duration]['high']
    
    keyboard = {
        'inline_keyboard': [
            [{'text': f'Стандартное ({standard_cost}₽)', 'callback_data': 'quality_standard'}],
            [{'text': f'Высокое ({high_cost}₽)', 'callback_data': 'quality_high'}],
            [{'text': '❌ Отмена', 'callback_data': 'back_to_main'}]
        ]
    }
    send_telegram_message(chat_id, f"🎨 Выберите качество:", keyboard)

def handle_quality_selection(conn, chat_id: int, user_id: int, quality: str):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT temp_prompt, temp_duration FROM t_p62125649_ai_video_bot.user_states 
            WHERE user_id = %s
        """, (user_id,))
        state = cur.fetchone()
        
        if not state:
            send_telegram_message(chat_id, "❌ Ошибка. Начните заново.", main_menu_keyboard())
            return
        
        prompt = state['temp_prompt']
        duration = state['temp_duration']
        cost = VIDEO_COSTS[duration][quality]
        
        cur.execute("SELECT balance FROM t_p62125649_ai_video_bot.users WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        
        if not result or result['balance'] < cost:
            send_telegram_message(chat_id, "❌ Недостаточно кредитов. Пополните баланс.", main_menu_keyboard())
            return
        
        cur.execute("UPDATE t_p62125649_ai_video_bot.users SET balance = balance - %s WHERE user_id = %s", (cost, user_id))
        
        task_id = f'video_{user_id}_{int(datetime.now().timestamp())}'
        
        cur.execute("""
            INSERT INTO t_p62125649_ai_video_bot.orders 
            (user_id, order_type, prompt, duration, quality, status, cost, task_id)
            VALUES (%s, 'text-to-video', %s, %s, %s, 'processing', %s, %s)
            RETURNING order_id
        """, (user_id, prompt, duration, quality, cost, task_id))
        
        order_id = cur.fetchone()['order_id']
        
        cur.execute("""
            INSERT INTO t_p62125649_ai_video_bot.transactions 
            (user_id, amount, type, description, order_id)
            VALUES (%s, %s, 'video', %s, %s)
        """, (user_id, -cost, f'Списание за видео {duration}с {quality}', order_id))
        
        cur.execute("DELETE FROM t_p62125649_ai_video_bot.user_states WHERE user_id = %s", (user_id,))
        conn.commit()
    
    send_telegram_message(chat_id, f"⏳ Генерирую видео {duration}с ({quality})...")
    
    try:
        request_data = {
            'model': GEN_MODEL_TEXT2VIDEO,
            'callbackUrl': GEN_CALLBACK_URL,
            'input': {
                'prompt': prompt,
                'n_frames': f'{duration}s',
                'aspect_ratio': 'landscape',
                'size': 'high' if quality == 'high' else 'standard'
            }
        }
        
        req = urllib.request.Request(
            GEN_SORA_API_URL,
            data=json.dumps(request_data).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {GEN_API_KEY}'}
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            task_id_from_api = result.get('data', {}).get('taskId') or result.get('job_id')
            if task_id_from_api:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE t_p62125649_ai_video_bot.orders 
                        SET external_job_id = %s
                        WHERE task_id = %s
                    """, (task_id_from_api, task_id))
                    conn.commit()
                
                send_telegram_message(chat_id, "✅ Заказ создан! Я пришлю видео, как только оно будет готово.", main_menu_keyboard())
            else:
                raise Exception("Invalid API response")
    except Exception as e:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE t_p62125649_ai_video_bot.orders 
                SET status = 'failed', error_message = %s
                WHERE task_id = %s
            """, (str(e), task_id))
            cur.execute("UPDATE t_p62125649_ai_video_bot.users SET balance = balance + %s WHERE user_id = %s", (cost, user_id))
            conn.commit()
        
        send_telegram_message(chat_id, "❌ Ошибка генерации. Кредиты возвращены.", main_menu_keyboard())

def get_telegram_file_url(file_id: str) -> str:
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/getFile'
    data = {'file_id': file_id}
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        file_path = result['result']['file_path']
        return f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}'

def handle_image_to_video_photo(conn, chat_id: int, user_id: int, photo: list):
    file_id = photo[-1]['file_id']
    image_url = get_telegram_file_url(file_id)
    cost = 300
    
    with conn.cursor() as cur:
        cur.execute("SELECT balance FROM t_p62125649_ai_video_bot.users WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        
        if not result or result[0] < cost:
            send_telegram_message(chat_id, "❌ Недостаточно кредитов. Пополните баланс.", main_menu_keyboard())
            return
        
        cur.execute("UPDATE t_p62125649_ai_video_bot.users SET balance = balance - %s WHERE user_id = %s", (cost, user_id))
        
        task_id = f'imagevideo_{user_id}_{int(datetime.now().timestamp())}'
        cur.execute("""
            INSERT INTO t_p62125649_ai_video_bot.orders 
            (user_id, order_type, prompt, status, cost, task_id)
            VALUES (%s, 'image-to-video', %s, 'processing', %s, %s)
            RETURNING order_id
        """, (user_id, 'animate this image', cost, task_id))
        
        order_id = cur.fetchone()[0]
        
        cur.execute("""
            INSERT INTO t_p62125649_ai_video_bot.transactions 
            (user_id, amount, type, description, order_id)
            VALUES (%s, %s, 'video', 'Списание за image-to-video', %s)
        """, (user_id, -cost, order_id))
        
        cur.execute("DELETE FROM t_p62125649_ai_video_bot.user_states WHERE user_id = %s", (user_id,))
        conn.commit()
    
    send_telegram_message(chat_id, "⏳ Создаю видео из вашей картинки...")
    
    try:
        request_data = {
            'model': GEN_MODEL_IMAGE2VIDEO,
            'callbackUrl': GEN_CALLBACK_URL,
            'input': {
                'prompt': 'animate this image',
                'image_urls': [image_url],
                'aspect_ratio': 'landscape',
                'n_frames': '10',
                'size': 'high',
                'remove_watermark': True
            }
        }
        
        req = urllib.request.Request(
            GEN_SORA_API_URL,
            data=json.dumps(request_data).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {GEN_API_KEY}'}
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            if result.get('data', {}).get('taskId'):
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE t_p62125649_ai_video_bot.orders 
                        SET external_job_id = %s
                        WHERE task_id = %s
                    """, (result['data']['taskId'], task_id))
                    conn.commit()
                
                send_telegram_message(chat_id, "✅ Заказ создан! Я пришлю видео, как только оно будет готово.", main_menu_keyboard())
            else:
                raise Exception("Invalid API response")
    except Exception as e:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE t_p62125649_ai_video_bot.orders 
                SET status = 'failed', error_message = %s
                WHERE task_id = %s
            """, (str(e), task_id))
            cur.execute("UPDATE t_p62125649_ai_video_bot.users SET balance = balance + %s WHERE user_id = %s", (cost, user_id))
            conn.commit()
        
        send_telegram_message(chat_id, "❌ Ошибка создания заказа. Кредиты возвращены.", main_menu_keyboard())

def handle_storyboard_scene_input(conn, chat_id: int, user_id: int, text: str, state: Dict):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT temp_data FROM t_p62125649_ai_video_bot.user_states WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        temp_data = json.loads(result['temp_data']) if result and result['temp_data'] else {}
        
        scenes = temp_data.get('scenes', [])
        total_scenes = temp_data.get('total_scenes', 3)
        current_scene = len(scenes) + 1
        
        scenes.append({'text': text, 'duration': 7.5})
        
        if current_scene < total_scenes:
            temp_data['scenes'] = scenes
            cur.execute("""
                UPDATE t_p62125649_ai_video_bot.user_states 
                SET state = %s, temp_data = %s, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            """, (f'waiting_storyboard_scene_{current_scene + 1}', json.dumps(temp_data), user_id))
            conn.commit()
            
            send_telegram_message(chat_id, f"Сцена {current_scene} сохранена!\n\nОпишите сцену {current_scene + 1}:")
        else:
            cost = 500
            
            cur.execute("SELECT balance FROM t_p62125649_ai_video_bot.users WHERE user_id = %s", (user_id,))
            balance_result = cur.fetchone()
            
            if not balance_result or balance_result['balance'] < cost:
                send_telegram_message(chat_id, "❌ Недостаточно кредитов. Пополните баланс.", main_menu_keyboard())
                return
            
            cur.execute("UPDATE t_p62125649_ai_video_bot.users SET balance = balance - %s WHERE user_id = %s", (cost, user_id))
            
            task_id = f'storyboard_{user_id}_{int(datetime.now().timestamp())}'
            cur.execute("""
                INSERT INTO t_p62125649_ai_video_bot.orders 
                (user_id, order_type, prompt, status, cost, task_id, scenes_count)
                VALUES (%s, 'storyboard', %s, 'processing', %s, %s, %s)
                RETURNING order_id
            """, (user_id, json.dumps(scenes), cost, task_id, total_scenes))
            
            order_id = cur.fetchone()['order_id']
            
            cur.execute("""
                INSERT INTO t_p62125649_ai_video_bot.transactions 
                (user_id, amount, type, description, order_id)
                VALUES (%s, %s, 'video', 'Списание за storyboard', %s)
            """, (user_id, -cost, order_id))
            
            cur.execute("DELETE FROM t_p62125649_ai_video_bot.user_states WHERE user_id = %s", (user_id,))
            conn.commit()
            
            send_telegram_message(chat_id, f"⏳ Создаю сториборд из {total_scenes} сцен...")
            
            try:
                request_data = {
                    'model': GEN_MODEL_STORYBOARD,
                    'callbackUrl': GEN_CALLBACK_URL,
                    'input': {
                        'shots': scenes,
                        'n_frames': '15s',
                        'aspect_ratio': 'landscape'
                    }
                }
                
                req = urllib.request.Request(
                    GEN_SORA_API_URL,
                    data=json.dumps(request_data).encode('utf-8'),
                    headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {GEN_API_KEY}'}
                )
                
                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    
                    if result.get('data', {}).get('taskId'):
                        cur.execute("""
                            UPDATE t_p62125649_ai_video_bot.orders 
                            SET external_job_id = %s
                            WHERE task_id = %s
                        """, (result['data']['taskId'], task_id))
                        conn.commit()
                        
                        send_telegram_message(chat_id, "✅ Заказ создан! Я пришлю сториборд, как только он будет готов.", main_menu_keyboard())
                    else:
                        raise Exception("Invalid API response")
            except Exception as e:
                cur.execute("""
                    UPDATE t_p62125649_ai_video_bot.orders 
                    SET status = 'failed', error_message = %s
                    WHERE task_id = %s
                """, (str(e), task_id))
                cur.execute("UPDATE t_p62125649_ai_video_bot.users SET balance = balance + %s WHERE user_id = %s", (cost, user_id))
                conn.commit()
                
                send_telegram_message(chat_id, "❌ Ошибка создания заказа. Кредиты возвращены.", main_menu_keyboard())

def handle_callback_query(conn, callback_query: Dict):
    callback_id = callback_query['id']
    user_id = callback_query['from']['id']
    chat_id = callback_query['message']['chat']['id']
    data = callback_query['data']
    username = callback_query['from'].get('username', '')
    first_name = callback_query['from'].get('first_name', 'User')
    
    if not check_rate_limit(conn, user_id, 'callback'):
        url = f'https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery'
        req_data = {'callback_query_id': callback_id, 'text': '⚠️ Слишком много запросов'}
        req = urllib.request.Request(url, data=json.dumps(req_data).encode('utf-8'), headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req)
        return
    
    user_info = get_or_create_user(conn, user_id, username, first_name)
    if user_info['user'].get('is_blocked'):
        send_telegram_message(chat_id, "🚫 Ваш аккаунт заблокирован")
        return
    
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery'
    req = urllib.request.Request(url, data=json.dumps({'callback_query_id': callback_id}).encode('utf-8'), headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req)
    
    if data == 'main_create':
        send_telegram_message(chat_id, "🎬 <b>Выберите тип контента:</b>", create_menu_keyboard())
    elif data == 'main_balance':
        handle_balance(conn, chat_id, user_id)
    elif data == 'main_topup':
        handle_topup(chat_id)
    elif data == 'main_help':
        handle_help(chat_id)
    elif data == 'back_to_main':
        with conn.cursor() as cur:
            cur.execute("DELETE FROM t_p62125649_ai_video_bot.user_states WHERE user_id = %s", (user_id,))
            conn.commit()
        send_telegram_message(chat_id, "Главное меню:", main_menu_keyboard())
    elif data == 'create_preview':
        handle_create_preview(conn, chat_id, user_id)
    elif data == 'create_textvideo':
        handle_create_textvideo(conn, chat_id, user_id)
    elif data == 'create_imagevideo':
        handle_create_imagevideo(conn, chat_id, user_id)
    elif data == 'create_storyboard':
        handle_create_storyboard(conn, chat_id, user_id)
    elif data.startswith('storyboard_scenes_'):
        scenes_count = int(data.split('_')[2])
        with conn.cursor() as cur:
            temp_data = json.dumps({'scenes': [], 'total_scenes': scenes_count})
            cur.execute("""
                UPDATE t_p62125649_ai_video_bot.user_states 
                SET state = 'waiting_storyboard_scene_1', temp_data = %s, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            """, (temp_data, user_id))
            conn.commit()
        send_telegram_message(chat_id, f"Отлично! Теперь опишите сцену 1 из {scenes_count}:")
    elif data == 'topup_card':
        handle_topup_card(chat_id)
    elif data == 'topup_stars':
        handle_topup_stars(chat_id)
    elif data.startswith('pay_card_'):
        amount = int(data.split('_')[2])
        handle_payment_card(chat_id, user_id, amount)
    elif data.startswith('pay_stars_'):
        stars = int(data.split('_')[2])
        handle_payment_stars(chat_id, user_id, stars)
    elif data.startswith('duration_'):
        duration = int(data.split('_')[1])
        handle_duration_selection(conn, chat_id, user_id, duration)
    elif data.startswith('quality_'):
        quality = data.split('_')[1]
        handle_quality_selection(conn, chat_id, user_id, quality)

def handle_message(conn, message: Dict):
    user_id = message['from']['id']
    chat_id = message['chat']['id']
    username = message['from'].get('username', '')
    first_name = message['from'].get('first_name', 'User')
    text = message.get('text', '')
    photo = message.get('photo', [])
    
    if not check_rate_limit(conn, user_id, 'message'):
        send_telegram_message(chat_id, "⚠️ Слишком много запросов. Подождите минуту.")
        return
    
    user_info = get_or_create_user(conn, user_id, username, first_name)
    if user_info['user'].get('is_blocked'):
        send_telegram_message(chat_id, "🚫 Ваш аккаунт заблокирован")
        return
    
    if text.startswith('/start'):
        handle_start_command(conn, chat_id, user_id, username, first_name)
        return
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT state, temp_data FROM t_p62125649_ai_video_bot.user_states WHERE user_id = %s", (user_id,))
        state = cur.fetchone()
    
    if not state:
        send_telegram_message(chat_id, "Используйте кнопки меню:", main_menu_keyboard())
        return
    
    if state['state'] == 'waiting_preview_prompt':
        handle_preview_prompt(conn, chat_id, user_id, text)
    elif state['state'] == 'waiting_textvideo_prompt':
        handle_textvideo_prompt(conn, chat_id, user_id, text)
    elif state['state'] == 'waiting_image_to_video' and photo:
        handle_image_to_video_photo(conn, chat_id, user_id, photo)
    elif state['state'].startswith('waiting_storyboard_scene_'):
        handle_storyboard_scene_input(conn, chat_id, user_id, text, state)
    else:
        send_telegram_message(chat_id, "Используйте кнопки для выбора:", main_menu_keyboard())

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
        print(f"[DEBUG] Received update: {json.dumps(body)}")
        
        conn = get_db_connection()
        
        if 'message' in body:
            print(f"[DEBUG] Processing message from user {body['message']['from']['id']}")
            handle_message(conn, body['message'])
        elif 'callback_query' in body:
            print(f"[DEBUG] Processing callback_query: {body['callback_query'].get('data')}")
            handle_callback_query(conn, body['callback_query'])
        else:
            print(f"[DEBUG] Unknown update type: {list(body.keys())}")
        
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'isBase64Encoded': False,
            'body': json.dumps({'ok': True})
        }
        
    except Exception as e:
        print(f"[ERROR] Exception in handler: {str(e)}")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'isBase64Encoded': False,
            'body': json.dumps({'ok': True, 'error': str(e)})
        }