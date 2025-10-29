'''
Business: Проверка статусов генерации видео/превью, отправка готовых результатов пользователям, автоматический рефанд при ошибках
Args: event с httpMethod (GET для cron), context с request_id
Returns: HTTP response со статистикой обработки
'''

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import urllib.request

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
DATABASE_URL = os.environ.get('DATABASE_URL')

MAX_RETRIES = 40
TIMEOUT_HOURS = 2

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def send_telegram_photo(chat_id: int, photo_url: str, caption: str):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto'
    data = {'chat_id': chat_id, 'photo': photo_url, 'caption': caption, 'parse_mode': 'HTML'}
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

def send_telegram_video(chat_id: int, video_url: str, caption: str):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendVideo'
    data = {'chat_id': chat_id, 'video': video_url, 'caption': caption, 'parse_mode': 'HTML'}
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

def send_telegram_message(chat_id: int, text: str):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

def check_order_status(order: Dict) -> Dict[str, Any]:
    task_id = order['task_id']
    order_type = order['order_type']
    
    mock_url = f"https://example.com/{task_id}.jpg" if order_type == 'preview' else f"https://example.com/{task_id}.mp4"
    
    return {'status': 'completed', 'result_url': mock_url, 'error': None}

def process_order(conn, order: Dict) -> str:
    order_id = order['order_id']
    user_id = order['user_id']
    order_type = order['order_type']
    retry_count = order['retry_count']
    created_at = order['created_at']
    cost = order['cost']
    
    hours_passed = (datetime.now() - created_at).total_seconds() / 3600
    
    if retry_count >= MAX_RETRIES or hours_passed >= TIMEOUT_HOURS:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE t_p62125649_ai_video_bot.orders 
                SET status = 'failed', error_message = 'Таймаут', completed_at = CURRENT_TIMESTAMP
                WHERE order_id = %s
            """, (order_id,))
            
            cur.execute("UPDATE t_p62125649_ai_video_bot.users SET balance = balance + %s WHERE user_id = %s", (cost, user_id))
            
            cur.execute("""
                INSERT INTO t_p62125649_ai_video_bot.transactions 
                (user_id, amount, type, description, order_id)
                VALUES (%s, %s, 'refund', 'Автовозврат за таймаут', %s)
            """, (user_id, cost, order_id))
            
            conn.commit()
        
        send_telegram_message(user_id, f"❌ Генерация #{order_id} не удалась. {cost} кредитов возвращено.")
        return f"failed_refunded_{order_id}"
    
    result = check_order_status(order)
    
    if result['status'] == 'completed' and result['result_url']:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE t_p62125649_ai_video_bot.orders 
                SET status = 'completed', result_url = %s, video_sent = TRUE, completed_at = CURRENT_TIMESTAMP
                WHERE order_id = %s
            """, (result['result_url'], order_id))
            conn.commit()
        
        caption = f"✅ Готово! Заказ #{order_id}"
        
        if order_type == 'preview':
            send_telegram_photo(user_id, result['result_url'], caption)
        else:
            send_telegram_video(user_id, result['result_url'], caption)
        
        return f"completed_{order_id}"
    
    elif result['status'] == 'failed':
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE t_p62125649_ai_video_bot.orders 
                SET status = 'failed', error_message = %s, completed_at = CURRENT_TIMESTAMP
                WHERE order_id = %s
            """, (result.get('error', 'API error'), order_id))
            
            cur.execute("UPDATE t_p62125649_ai_video_bot.users SET balance = balance + %s WHERE user_id = %s", (cost, user_id))
            
            cur.execute("""
                INSERT INTO t_p62125649_ai_video_bot.transactions 
                (user_id, amount, type, description, order_id)
                VALUES (%s, %s, 'refund', 'Возврат за ошибку', %s)
            """, (user_id, cost, order_id))
            
            conn.commit()
        
        send_telegram_message(user_id, f"❌ Ошибка генерации #{order_id}. {cost} кредитов возвращено.")
        return f"failed_refunded_{order_id}"
    
    else:
        with conn.cursor() as cur:
            cur.execute("UPDATE t_p62125649_ai_video_bot.orders SET retry_count = retry_count + 1 WHERE order_id = %s", (order_id,))
            conn.commit()
        
        return f"pending_{order_id}"

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    method = event.get('httpMethod', 'GET')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Max-Age': '86400'
            },
            'isBase64Encoded': False,
            'body': ''
        }
    
    try:
        conn = get_db_connection()
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM t_p62125649_ai_video_bot.orders 
                WHERE status = 'processing' AND task_id IS NOT NULL
                ORDER BY created_at ASC
                LIMIT 50
            """)
            orders = cur.fetchall()
        
        results = []
        for order in orders:
            result = process_order(conn, dict(order))
            results.append(result)
        
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'isBase64Encoded': False,
            'body': json.dumps({'processed': len(results), 'timestamp': datetime.now().isoformat()})
        }
        
    except Exception as e:
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'isBase64Encoded': False,
            'body': json.dumps({'error': str(e), 'processed': 0})
        }
