'''
Business: API для админ-панели бота - статистика, управление пользователями, аналитика транзакций и заказов
Args: event с httpMethod, queryStringParameters (endpoint, action), context с request_id
Returns: HTTP response с данными или ошибкой
'''

import json
import os
from typing import Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get('DATABASE_URL')
ADMIN_SECRET_KEY = os.environ.get('ADMIN_SECRET_KEY', '')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def check_admin_auth(headers: Dict) -> bool:
    auth_token = headers.get('X-Admin-Key', headers.get('x-admin-key', ''))
    return auth_token == ADMIN_SECRET_KEY

def get_dashboard_stats(conn) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT COUNT(*) as total_users FROM t_p62125649_ai_video_bot.users")
        total_users = cur.fetchone()['total_users']
        
        cur.execute("SELECT COUNT(*) FROM t_p62125649_ai_video_bot.users WHERE last_activity > NOW() - INTERVAL '24 hours'")
        active_users = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) FROM t_p62125649_ai_video_bot.orders")
        total_orders = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) FROM t_p62125649_ai_video_bot.orders WHERE status = 'processing'")
        processing_orders = cur.fetchone()['count']
        
        cur.execute("SELECT COALESCE(SUM(amount), 0) FROM t_p62125649_ai_video_bot.transactions WHERE type = 'purchase'")
        total_revenue = cur.fetchone()['coalesce']
        
        cur.execute("SELECT COALESCE(SUM(-amount), 0) FROM t_p62125649_ai_video_bot.transactions WHERE type IN ('preview', 'video')")
        credits_spent = cur.fetchone()['coalesce']
        
        return {
            'total_users': total_users,
            'active_users_24h': active_users,
            'total_orders': total_orders,
            'processing_orders': processing_orders,
            'total_revenue': int(total_revenue),
            'credits_spent': int(credits_spent)
        }

def get_recent_users(conn, limit: int = 10):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT user_id, username, first_name, balance, created_at, last_activity, is_blocked
            FROM t_p62125649_ai_video_bot.users
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
        return [dict(u) for u in cur.fetchall()]

def get_recent_orders(conn, limit: int = 20):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT o.order_id, o.user_id, u.username, o.order_type, o.status, o.cost, o.created_at, o.completed_at
            FROM t_p62125649_ai_video_bot.orders o
            LEFT JOIN t_p62125649_ai_video_bot.users u ON o.user_id = u.user_id
            ORDER BY o.created_at DESC
            LIMIT %s
        """, (limit,))
        return [dict(o) for o in cur.fetchall()]

def get_order_stats(conn):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT order_type, status, COUNT(*) as count
            FROM t_p62125649_ai_video_bot.orders
            GROUP BY order_type, status
            ORDER BY order_type, status
        """)
        return [dict(s) for s in cur.fetchall()]

def get_daily_revenue(conn, days: int = 7):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT DATE(created_at) as date, SUM(amount) as revenue, COUNT(*) as transaction_count
            FROM t_p62125649_ai_video_bot.transactions
            WHERE type = 'purchase' AND created_at > NOW() - INTERVAL '%s days'
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """, (days,))
        return [dict(r) for r in cur.fetchall()]

def update_user_balance(conn, user_id: int, amount: int, admin_username: str, reason: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT balance FROM t_p62125649_ai_video_bot.users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        old_balance = user['balance']
        new_balance = old_balance + amount
        
        cur.execute("""
            UPDATE t_p62125649_ai_video_bot.users 
            SET balance = %s 
            WHERE user_id = %s
        """, (new_balance, user_id))
        
        cur.execute("""
            INSERT INTO t_p62125649_ai_video_bot.transactions (user_id, amount, type, description)
            VALUES (%s, %s, 'admin_adjustment', %s)
        """, (user_id, amount, reason))
        
        cur.execute("""
            INSERT INTO t_p62125649_ai_video_bot.admin_actions (admin_username, action_type, target_user_id, details)
            VALUES (%s, 'balance_change', %s, %s)
        """, (admin_username, user_id, json.dumps({'old_balance': old_balance, 'new_balance': new_balance, 'amount': amount, 'reason': reason})))
        
        conn.commit()
        
        return {'success': True, 'old_balance': old_balance, 'new_balance': new_balance}

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    method = event.get('httpMethod', 'GET')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-Admin-Key',
                'Access-Control-Max-Age': '86400'
            },
            'isBase64Encoded': False,
            'body': ''
        }
    
    headers = event.get('headers', {})
    
    if not check_admin_auth(headers):
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json'},
            'isBase64Encoded': False,
            'body': json.dumps({'error': 'Unauthorized'})
        }
    
    try:
        conn = get_db_connection()
        params = event.get('queryStringParameters', {})
        endpoint = params.get('endpoint', 'dashboard')
        
        if method == 'GET':
            if endpoint == 'dashboard':
                stats = get_dashboard_stats(conn)
                recent_users = get_recent_users(conn, 10)
                recent_orders = get_recent_orders(conn, 20)
                order_stats = get_order_stats(conn)
                daily_revenue = get_daily_revenue(conn, 7)
                
                data = {
                    'stats': stats,
                    'recent_users': recent_users,
                    'recent_orders': recent_orders,
                    'order_stats': order_stats,
                    'daily_revenue': daily_revenue
                }
            else:
                data = {'error': 'Unknown endpoint'}
        
        elif method == 'POST':
            body_data = json.loads(event.get('body', '{}'))
            action = body_data.get('action')
            
            if action == 'update_balance':
                user_id = body_data.get('user_id')
                amount = body_data.get('amount')
                admin_username = body_data.get('admin_username', 'admin')
                reason = body_data.get('reason', 'Manual adjustment')
                
                result = update_user_balance(conn, user_id, amount, admin_username, reason)
                data = result
            else:
                data = {'error': 'Unknown action'}
        else:
            data = {'error': 'Method not allowed'}
        
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'isBase64Encoded': False,
            'body': json.dumps(data, default=str)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'isBase64Encoded': False,
            'body': json.dumps({'error': str(e)})
        }