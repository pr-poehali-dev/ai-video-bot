"""
Business: Background worker - checks video/image generation status and sends results to users
Args: event (empty for cron), context with request_id
Returns: HTTP response with processed orders count
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import urllib.request

DATABASE_URL = os.environ.get('DATABASE_URL')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
IMAGE_API_URL = os.environ.get('IMAGE_API_URL', 'https://example.com/image')
VIDEO_API_URL = os.environ.get('VIDEO_API_URL', 'https://example.com/video')
STORYBOARD_API_URL = os.environ.get('STORYBOARD_API_URL', 'https://example.com/storyboard')

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

MAX_RETRIES = 40
TIMEOUT_HOURS = 2


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
            'isBase64Encoded': False,
            'body': ''
        }
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        
        processed = check_processing_orders(conn)
        
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'isBase64Encoded': False,
            'body': json.dumps({'processed': processed, 'timestamp': datetime.now().isoformat()})
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'isBase64Encoded': False,
            'body': json.dumps({'error': str(e)})
        }


def check_processing_orders(conn) -> int:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM orders 
        WHERE status = 'processing' AND task_id IS NOT NULL
        ORDER BY created_at ASC
    """)
    
    orders = cur.fetchall()
    processed_count = 0
    
    for order in orders:
        order_id = order['order_id']
        task_id = order['task_id']
        order_type = order['order_type']
        user_id = order['user_id']
        created_at = order['created_at']
        retry_count = order['retry_count']
        
        timeout = datetime.now() - timedelta(hours=TIMEOUT_HOURS)
        if created_at < timeout:
            handle_timeout(order_id, user_id, order['cost'], conn)
            processed_count += 1
            continue
        
        if retry_count >= MAX_RETRIES:
            handle_max_retries(order_id, user_id, order['cost'], conn)
            processed_count += 1
            continue
        
        try:
            status_url = get_status_url(order_type, task_id)
            
            req = urllib.request.Request(status_url, headers={'Content-Type': 'application/json'})
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                
                api_status = result.get('status')
                
                if api_status == 'completed':
                    result_url = result.get('result_url') or result.get('url')
                    
                    if result_url:
                        cur.execute("""
                            UPDATE orders 
                            SET status = 'completed', result_url = %s, completed_at = %s
                            WHERE order_id = %s
                        """, (result_url, datetime.now(), order_id))
                        
                        send_result_to_user(user_id, order_id, order_type, result_url)
                        
                        cur.execute("UPDATE orders SET video_sent = TRUE WHERE order_id = %s", (order_id,))
                        
                        processed_count += 1
                
                elif api_status == 'failed':
                    error_msg = result.get('error', 'Генерация не удалась')
                    
                    cur.execute("""
                        UPDATE orders 
                        SET status = 'failed', error_message = %s
                        WHERE order_id = %s
                    """, (error_msg, order_id))
                    
                    refund_user(user_id, order['cost'], order_id, conn)
                    send_message(user_id, f"❌ Заказ #{order_id} не удался\n\n{order['cost']} кредитов возвращены на ваш баланс")
                    
                    processed_count += 1
                
                else:
                    cur.execute("""
                        UPDATE orders 
                        SET retry_count = retry_count + 1
                        WHERE order_id = %s
                    """, (order_id,))
        
        except Exception as e:
            log_error(user_id, order_id, 'status_checker', 'api_error', str(e), {'task_id': task_id})
            
            cur.execute("""
                UPDATE orders 
                SET retry_count = retry_count + 1
                WHERE order_id = %s
            """, (order_id,))
    
    return processed_count


def get_status_url(order_type: str, task_id: str) -> str:
    if order_type == 'preview':
        return f"{IMAGE_API_URL}/status/{task_id}"
    elif order_type in ['text-to-video', 'image-to-video']:
        return f"{VIDEO_API_URL}/status/{task_id}"
    elif order_type == 'storyboard':
        return f"{STORYBOARD_API_URL}/status/{task_id}"
    else:
        return f"{VIDEO_API_URL}/status/{task_id}"


def handle_timeout(order_id: int, user_id: int, cost: int, conn) -> None:
    cur = conn.cursor()
    cur.execute("""
        UPDATE orders 
        SET status = 'failed', error_message = 'Превышено время ожидания (2 часа)'
        WHERE order_id = %s
    """, (order_id,))
    
    refund_user(user_id, cost, order_id, conn)
    send_message(user_id, f"❌ Заказ #{order_id} отменён (таймаут)\n\n{cost} кредитов возвращены на ваш баланс")


def handle_max_retries(order_id: int, user_id: int, cost: int, conn) -> None:
    cur = conn.cursor()
    cur.execute("""
        UPDATE orders 
        SET status = 'failed', error_message = 'Превышено максимальное количество попыток проверки'
        WHERE order_id = %s
    """, (order_id,))
    
    refund_user(user_id, cost, order_id, conn)
    send_message(user_id, f"❌ Заказ #{order_id} отменён (макс. попыток)\n\n{cost} кредитов возвращены на ваш баланс")


def refund_user(user_id: int, amount: int, order_id: int, conn) -> None:
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, user_id))
    cur.execute("""
        INSERT INTO transactions (user_id, amount, type, description, order_id)
        VALUES (%s, %s, 'refund', 'Возврат за заказ #' || %s, %s)
    """, (user_id, amount, order_id, order_id))


def send_result_to_user(user_id: int, order_id: int, order_type: str, result_url: str) -> None:
    if order_type == 'preview':
        send_photo(user_id, result_url, f"✅ Превью готово! Заказ #{order_id}")
    else:
        send_video(user_id, result_url, f"✅ Видео готово! Заказ #{order_id}")


def send_message(chat_id: int, text: str) -> None:
    payload = {'chat_id': chat_id, 'text': text}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(f"{TELEGRAM_API}/sendMessage", data=data, headers={'Content-Type': 'application/json'})
    
    try:
        urllib.request.urlopen(req, timeout=5)
    except:
        pass


def send_photo(chat_id: int, photo_url: str, caption: str) -> None:
    payload = {'chat_id': chat_id, 'photo': photo_url, 'caption': caption}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(f"{TELEGRAM_API}/sendPhoto", data=data, headers={'Content-Type': 'application/json'})
    
    try:
        urllib.request.urlopen(req, timeout=10)
    except:
        pass


def send_video(chat_id: int, video_url: str, caption: str) -> None:
    payload = {'chat_id': chat_id, 'video': video_url, 'caption': caption}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(f"{TELEGRAM_API}/sendVideo", data=data, headers={'Content-Type': 'application/json'})
    
    try:
        urllib.request.urlopen(req, timeout=15)
    except:
        pass


def log_error(user_id: int, order_id: int, workflow: str, error_type: str, message: str, update: Dict) -> None:
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO error_logs (user_id, order_id, workflow_name, error_type, error_message, telegram_update)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, order_id, workflow, error_type, message, Json(update)))
        conn.commit()
        conn.close()
    except:
        pass
