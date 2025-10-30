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
GEN_API_KEY = os.environ.get('GEN_API_KEY', '57dabe651c81b31ea5ee1bb021817051')
GEN_SORA_API_URL = os.environ.get('GEN_SORA_API_URL', 'https://api.kie.ai/api/v1/jobs/createTask')
GEN_IMAGE_API_URL = os.environ.get('GEN_IMAGE_API_URL', 'https://api.kie.ai/api/v1/gpt4o-image/generate')

MAX_RETRIES = 40
TIMEOUT_HOURS = 2
JOB_STATUS_URL = 'https://api.kie.ai/api/v1/jobs/getJobStatus'

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
    external_job_id = order.get('external_job_id')
    order_type = order['order_type']
    
    if not external_job_id:
        return {'status': 'processing', 'result_url': None, 'error': None}
    
    try:
        request_data = {'job_id': external_job_id, 'api_key': GEN_API_KEY}
        req = urllib.request.Request(
            JOB_STATUS_URL,
            data=json.dumps(request_data).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {GEN_API_KEY}'}
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            if result.get('status') == 'completed' and result.get('result_url'):
                return {'status': 'completed', 'result_url': result['result_url'], 'error': None}
            elif result.get('status') == 'failed':
                return {'status': 'failed', 'result_url': None, 'error': result.get('error', 'Unknown error')}
            else:
                return {'status': 'processing', 'result_url': None, 'error': None}
    except Exception as e:
        return {'status': 'processing', 'result_url': None, 'error': None}

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

def handle_generation_callback(conn, callback_data: Dict) -> Dict[str, Any]:
    data = callback_data.get('data', {})
    task_id = data.get('taskId')
    state = data.get('state')
    result_urls = data.get('resultUrls', [])
    fail_msg = data.get('failMsg', '')
    
    if not task_id:
        return {'error': 'Missing taskId'}
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT * FROM t_p62125649_ai_video_bot.orders 
            WHERE external_job_id = %s
        """, (task_id,))
        
        order = cur.fetchone()
        
        if not order:
            return {'error': 'Order not found'}
        
        order_id = order['order_id']
        user_id = order['user_id']
        cost = order['cost']
        order_type = order['order_type']
        
        if state == 'success' and result_urls:
            result_url = result_urls[0]
            
            cur.execute("""
                UPDATE t_p62125649_ai_video_bot.orders 
                SET status = 'completed', result_url = %s, completed_at = CURRENT_TIMESTAMP
                WHERE order_id = %s
            """, (result_url, order_id))
            conn.commit()
            
            type_labels = {
                'preview': 'Превью',
                'text-to-video': 'Видео из текста',
                'image-to-video': 'Видео из картинки',
                'storyboard': 'Сториборд'
            }
            
            caption = f"✅ Готово! {type_labels.get(order_type, 'Заказ')} #{order_id}"
            
            try:
                send_telegram_video(user_id, result_url, caption)
            except:
                send_telegram_message(user_id, f"{caption}\n\n{result_url}")
            
            return {'status': 'processed', 'order_id': order_id}
            
        elif state == 'fail':
            cur.execute("""
                UPDATE t_p62125649_ai_video_bot.orders 
                SET status = 'failed', error_message = %s, completed_at = CURRENT_TIMESTAMP
                WHERE order_id = %s
            """, (fail_msg or 'Generation failed', order_id))
            
            cur.execute("UPDATE t_p62125649_ai_video_bot.users SET balance = balance + %s WHERE user_id = %s", (cost, user_id))
            
            cur.execute("""
                INSERT INTO t_p62125649_ai_video_bot.transactions 
                (user_id, amount, type, description, order_id)
                VALUES (%s, %s, 'refund', 'Возврат за ошибку генерации', %s)
            """, (user_id, cost, order_id))
            
            conn.commit()
            
            send_telegram_message(user_id, f"❌ Ошибка генерации заказа #{order_id}.\n{cost} кредитов возвращено на баланс.")
            
            return {'status': 'refunded', 'order_id': order_id}
    
    return {'error': 'Invalid state'}

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
        conn = get_db_connection()
        
        if method == 'POST':
            body_str = event.get('body', '{}')
            callback_data = json.loads(body_str)
            result = handle_generation_callback(conn, callback_data)
            conn.close()
            
            return {
                'statusCode': 200 if 'error' not in result else 400,
                'headers': {'Content-Type': 'application/json'},
                'isBase64Encoded': False,
                'body': json.dumps(result)
            }
        
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