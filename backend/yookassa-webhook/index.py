'''
Business: Обработка webhook-уведомлений от ЮКасса о статусе платежей, начисление кредитов на баланс пользователей
Args: event с httpMethod (POST), body с данными от ЮКассы, context с request_id
Returns: HTTP response 200 OK
'''

import json
import os
from typing import Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import urllib.request

DATABASE_URL = os.environ.get('DATABASE_URL')
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def send_telegram_message(chat_id: int, text: str):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

def handle_payment_succeeded(conn, payment: Dict):
    payment_id = payment['id']
    metadata = payment.get('metadata', {})
    user_id = int(metadata.get('user_id', 0))
    credits = int(metadata.get('credits', 0))
    
    if not user_id or not credits:
        return
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT transaction_id FROM t_p62125649_ai_video_bot.transactions 
            WHERE external_payment_id = %s
        """, (payment_id,))
        
        if cur.fetchone():
            return
        
        cur.execute("UPDATE t_p62125649_ai_video_bot.users SET balance = balance + %s WHERE user_id = %s", (credits, user_id))
        
        cur.execute("""
            INSERT INTO t_p62125649_ai_video_bot.transactions 
            (user_id, amount, type, description, external_payment_id)
            VALUES (%s, %s, 'purchase', %s, %s)
        """, (user_id, credits, f'Пополнение на {credits} кредитов', payment_id))
        
        conn.commit()
    
    send_telegram_message(user_id, f"✅ Оплата прошла!\n💰 Баланс пополнен на {credits} кредитов")

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
        event_type = body.get('event')
        
        if event_type == 'payment.succeeded':
            conn = get_db_connection()
            payment = body.get('object', {})
            handle_payment_succeeded(conn, payment)
            conn.close()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'isBase64Encoded': False,
            'body': json.dumps({'ok': True})
        }
        
    except Exception as e:
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'isBase64Encoded': False,
            'body': json.dumps({'ok': True, 'error': str(e)})
        }
