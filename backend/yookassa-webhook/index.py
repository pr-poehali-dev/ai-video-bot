"""
Business: YooKassa payment webhook - processes successful payments and credits user balance
Args: event with POST body (YooKassa notification), context with request_id
Returns: HTTP response 200 OK
"""

import json
import os
from typing import Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import urllib.request

DATABASE_URL = os.environ.get('DATABASE_URL')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
YOOKASSA_SHOP_ID = os.environ.get('YOOKASSA_SHOP_ID')
YOOKASSA_SECRET_KEY = os.environ.get('YOOKASSA_SECRET_KEY')

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


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
        
        event_type = body.get('event')
        payment = body.get('object', {})
        
        if event_type == 'payment.succeeded':
            handle_successful_payment(payment, conn)
        
        elif event_type == 'payment.canceled':
            handle_canceled_payment(payment, conn)
        
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'isBase64Encoded': False,
            'body': json.dumps({'ok': True})
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'isBase64Encoded': False,
            'body': json.dumps({'error': str(e)})
        }


def handle_successful_payment(payment: Dict[str, Any], conn) -> None:
    payment_id = payment.get('id')
    amount_value = float(payment.get('amount', {}).get('value', 0))
    amount_credits = int(amount_value)
    
    metadata = payment.get('metadata', {})
    user_id = int(metadata.get('user_id', 0))
    
    if not user_id or amount_credits <= 0:
        return
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM transactions 
        WHERE external_payment_id = %s AND type = 'purchase'
    """, (payment_id,))
    
    existing = cur.fetchone()
    
    if existing:
        return
    
    cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount_credits, user_id))
    
    cur.execute("""
        INSERT INTO transactions (user_id, amount, type, description, external_payment_id)
        VALUES (%s, %s, 'purchase', %s, %s)
    """, (user_id, amount_credits, f"Пополнение на {amount_credits} кредитов", payment_id))
    
    cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()
    
    new_balance = user['balance'] if user else amount_credits
    
    send_message(user_id, f"✅ Оплата прошла успешно!\n\n💰 Начислено: {amount_credits} кредитов\n💵 Новый баланс: {new_balance} кредитов")


def handle_canceled_payment(payment: Dict[str, Any], conn) -> None:
    payment_id = payment.get('id')
    metadata = payment.get('metadata', {})
    user_id = int(metadata.get('user_id', 0))
    
    if user_id:
        send_message(user_id, "❌ Платёж отменён")


def send_message(chat_id: int, text: str) -> None:
    payload = {'chat_id': chat_id, 'text': text}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(f"{TELEGRAM_API}/sendMessage", data=data, headers={'Content-Type': 'application/json'})
    
    try:
        urllib.request.urlopen(req, timeout=5)
    except:
        pass


def create_payment(user_id: int, amount: int) -> Dict[str, Any]:
    import base64
    
    auth_string = f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}"
    auth_header = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    
    payload = {
        "amount": {
            "value": str(amount),
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/your_bot"
        },
        "capture": True,
        "metadata": {
            "user_id": str(user_id)
        },
        "description": f"Пополнение баланса {amount} кредитов"
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        "https://api.yookassa.ru/v3/payments",
        data=data,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Basic {auth_header}',
            'Idempotence-Key': f"{user_id}_{amount}_{int(datetime.now().timestamp())}"
        }
    )
    
    with urllib.request.urlopen(req, timeout=10) as response:
        result = json.loads(response.read().decode('utf-8'))
        return result
