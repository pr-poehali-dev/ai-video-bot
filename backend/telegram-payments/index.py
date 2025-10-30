'''
Business: Обработка платежей через Telegram (карты и звёзды), начисление кредитов, логирование транзакций
Args: event с httpMethod, body (Telegram update), context с request_id
Returns: HTTP response с подтверждением или ошибкой
'''

import json
import os
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get('DATABASE_URL')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_PAYMENT_PROVIDER_TOKEN = os.environ.get('TELEGRAM_PAYMENT_PROVIDER_TOKEN', '')
TELEGRAM_STARS_ENABLED = os.environ.get('TELEGRAM_STARS_ENABLED', 'false').lower() == 'true'
TELEGRAM_STARS_RATE = float(os.environ.get('TELEGRAM_STARS_RATE', '1'))

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def log_payment(conn, user_id: int, payment_method: str, status: str, amount: float, 
                currency: str, external_id: Optional[str], telegram_update: Dict, 
                error_message: Optional[str] = None):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO t_p62125649_ai_video_bot.payment_logs 
            (user_id, payment_method, payment_status, amount, currency, 
             external_payment_id, telegram_update, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, payment_method, status, amount, currency, external_id, 
              json.dumps(telegram_update), error_message))
        conn.commit()

def process_successful_payment(conn, user_id: int, amount: float, currency: str, 
                               payment_method: str, external_payment_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if currency == 'XTR':
            credits = int(amount * TELEGRAM_STARS_RATE)
        else:
            credits = int(amount)
        
        cur.execute("""
            UPDATE t_p62125649_ai_video_bot.users 
            SET balance = balance + %s 
            WHERE user_id = %s
            RETURNING balance
        """, (credits, user_id))
        
        result = cur.fetchone()
        if not result:
            return {'success': False, 'error': 'User not found'}
        
        new_balance = result['balance']
        
        cur.execute("""
            INSERT INTO t_p62125649_ai_video_bot.transactions 
            (user_id, amount, type, description, external_payment_id, payment_method)
            VALUES (%s, %s, 'purchase', %s, %s, %s)
        """, (user_id, credits, f'Telegram payment ({currency})', external_payment_id, payment_method))
        
        conn.commit()
        
        return {
            'success': True, 
            'credits_added': credits, 
            'new_balance': new_balance,
            'currency': currency
        }

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    method = event.get('httpMethod', 'POST')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-Telegram-Bot-Api-Secret-Token',
                'Access-Control-Max-Age': '86400'
            },
            'isBase64Encoded': False,
            'body': ''
        }
    
    try:
        body_str = event.get('body', '{}')
        update = json.loads(body_str)
        
        conn = get_db_connection()
        
        if 'pre_checkout_query' in update:
            pre_checkout = update['pre_checkout_query']
            query_id = pre_checkout['id']
            user_id = pre_checkout['from']['id']
            currency = pre_checkout['currency']
            total_amount = pre_checkout['total_amount']
            
            log_payment(conn, user_id, 
                       'telegram_stars' if currency == 'XTR' else 'telegram_card',
                       'pre_checkout', total_amount / 100 if currency != 'XTR' else total_amount,
                       currency, query_id, update)
            
            import requests
            requests.post(
                f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerPreCheckoutQuery',
                json={'pre_checkout_query_id': query_id, 'ok': True}
            )
            
            conn.close()
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'isBase64Encoded': False,
                'body': json.dumps({'status': 'ok'})
            }
        
        elif 'message' in update and 'successful_payment' in update['message']:
            message = update['message']
            payment = message['successful_payment']
            user_id = message['from']['id']
            currency = payment['currency']
            total_amount = payment['total_amount']
            telegram_payment_charge_id = payment['telegram_payment_charge_id']
            
            amount = total_amount / 100 if currency != 'XTR' else total_amount
            payment_method = 'telegram_stars' if currency == 'XTR' else 'telegram_card'
            
            log_payment(conn, user_id, payment_method, 'success', amount, currency, 
                       telegram_payment_charge_id, update)
            
            result = process_successful_payment(conn, user_id, amount, currency, 
                                               payment_method, telegram_payment_charge_id)
            
            if result['success']:
                import requests
                requests.post(
                    f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
                    json={
                        'chat_id': user_id,
                        'text': f"✅ Платёж успешно обработан!\n\n💳 Начислено кредитов: {result['credits_added']}\n💰 Ваш баланс: {result['new_balance']}"
                    }
                )
            else:
                log_payment(conn, user_id, payment_method, 'failed', amount, currency,
                           telegram_payment_charge_id, update, result.get('error'))
            
            conn.close()
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'isBase64Encoded': False,
                'body': json.dumps(result)
            }
        
        else:
            conn.close()
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'isBase64Encoded': False,
                'body': json.dumps({'status': 'ignored'})
            }
        
    except Exception as e:
        try:
            if 'conn' in locals():
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO t_p62125649_ai_video_bot.error_logs 
                        (error_type, error_message, telegram_update)
                        VALUES (%s, %s, %s)
                    """, ('payment_processing_error', str(e), json.dumps(update if 'update' in locals() else {})))
                    conn.commit()
                conn.close()
        except:
            pass
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'isBase64Encoded': False,
            'body': json.dumps({'error': str(e)})
        }
