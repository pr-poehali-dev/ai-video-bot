"""
Business: Background worker - checks video generation status and sends results
Args: event (scheduled trigger); context with request_id
Returns: HTTP response with processed orders count
"""

import json
import os
from typing import Dict, Any, List
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import urllib.request
import urllib.parse

DATABASE_URL = os.environ.get('DATABASE_URL')
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
VIDEO_API_URL = os.environ.get('VIDEO_API_URL', '')
IMAGE_API_URL = os.environ.get('IMAGE_API_URL', '')
STORYBOARD_API_URL = os.environ.get('STORYBOARD_API_URL', '')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def send_telegram_message(chat_id: int, text: str, reply_markup: Dict = None):
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

def send_telegram_photo(chat_id: int, photo_url: str, caption: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    data = {
        'chat_id': chat_id,
        'photo': photo_url,
        'caption': caption,
        'parse_mode': 'HTML'
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

def send_telegram_video(chat_id: int, video_url: str, caption: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    data = {
        'chat_id': chat_id,
        'video': video_url,
        'caption': caption,
        'parse_mode': 'HTML'
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

def check_api_status(api_url: str, task_id: str) -> Dict[str, Any]:
    url = f"{api_url}/status/{task_id}"
    
    req = urllib.request.Request(url, headers={'Content-Type': 'application/json'})
    
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

def process_order(conn, order: Dict) -> bool:
    order_id = order['order_id']
    user_id = order['user_id']
    task_id = order['task_id']
    order_type = order['order_type']
    
    api_url = ''
    if order_type == 'preview':
        api_url = IMAGE_API_URL
    elif order_type in ('text-to-video', 'image-to-video'):
        api_url = VIDEO_API_URL
    elif order_type == 'storyboard':
        api_url = STORYBOARD_API_URL
    
    if not api_url:
        return False
    
    status_response = check_api_status(api_url, task_id)
    
    if status_response.get('status') == 'completed':
        result_url = status_response.get('result_url')
        
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE orders 
                SET status = 'completed', result_url = %s, completed_at = %s
                WHERE order_id = %s
            """, (result_url, datetime.now(), order_id))
            conn.commit()
        
        if order_type == 'preview':
            send_telegram_photo(
                user_id, 
                result_url,
                "✅ Готово! Создаём видео?"
            )
        else:
            send_telegram_video(
                user_id,
                result_url,
                "✅ Ваше видео готово!"
            )
        
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE orders SET video_sent = true WHERE order_id = %s
            """, (order_id,))
            conn.commit()
        
        return True
    
    elif status_response.get('status') == 'failed':
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE orders 
                SET status = 'failed', error_message = %s, completed_at = %s
                WHERE order_id = %s
            """, (status_response.get('error', 'Unknown error'), datetime.now(), order_id))
            
            cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
            user = cur.fetchone()
            
            if user:
                new_balance = user[0] + order['cost']
                cur.execute("UPDATE users SET balance = %s WHERE user_id = %s", (new_balance, user_id))
                
                cur.execute("""
                    INSERT INTO transactions (user_id, amount, type, description, order_id, created_at)
                    VALUES (%s, %s, 'refund', 'Автоматический возврат за неудачную генерацию', %s, %s)
                """, (user_id, order['cost'], order_id, datetime.now()))
            
            conn.commit()
        
        send_telegram_message(
            user_id,
            f"⚠️ К сожалению, генерация не удалась.\n\n💰 Возвращено {order['cost']} кредитов на баланс."
        )
        
        return True
    
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE orders SET retry_count = retry_count + 1 WHERE order_id = %s
        """, (order_id,))
        conn.commit()
    
    if order['retry_count'] >= order['max_retries']:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE orders 
                SET status = 'failed', error_message = 'Timeout - max retries exceeded', completed_at = %s
                WHERE order_id = %s
            """, (datetime.now(), order_id))
            
            cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
            user = cur.fetchone()
            
            if user:
                new_balance = user[0] + order['cost']
                cur.execute("UPDATE users SET balance = %s WHERE user_id = %s", (new_balance, user_id))
                
                cur.execute("""
                    INSERT INTO transactions (user_id, amount, type, description, order_id, created_at)
                    VALUES (%s, %s, 'refund', 'Автоматический возврат - таймаут генерации', %s, %s)
                """, (user_id, order['cost'], order_id, datetime.now()))
            
            conn.commit()
        
        send_telegram_message(
            user_id,
            f"⚠️ Время ожидания истекло.\n\n💰 Возвращено {order['cost']} кредитов на баланс."
        )
        
        return True
    
    timeout = datetime.now() - timedelta(hours=2)
    if order['created_at'].replace(tzinfo=None) < timeout:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE orders 
                SET status = 'failed', error_message = 'Timeout - 2 hours exceeded', completed_at = %s
                WHERE order_id = %s
            """, (datetime.now(), order_id))
            
            cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
            user = cur.fetchone()
            
            if user:
                new_balance = user[0] + order['cost']
                cur.execute("UPDATE users SET balance = %s WHERE user_id = %s", (new_balance, user_id))
                
                cur.execute("""
                    INSERT INTO transactions (user_id, amount, type, description, order_id, created_at)
                    VALUES (%s, %s, 'refund', 'Автоматический возврат - таймаут 2 часа', %s, %s)
                """, (user_id, order['cost'], order_id, datetime.now()))
            
            conn.commit()
        
        send_telegram_message(
            user_id,
            f"⚠️ Генерация заняла слишком много времени.\n\n💰 Возвращено {order['cost']} кредитов на баланс."
        )
        
        return True
    
    return False

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    method = event.get('httpMethod', 'GET')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Max-Age': '86400'
            },
            'body': ''
        }
    
    try:
        conn = get_db_connection()
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM orders 
                WHERE status = 'processing' AND task_id IS NOT NULL
                ORDER BY created_at ASC
            """)
            orders = cur.fetchall()
        
        processed_count = 0
        for order in orders:
            if process_order(conn, dict(order)):
                processed_count += 1
        
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'processed': processed_count,
                'total_orders': len(orders)
            })
        }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }
