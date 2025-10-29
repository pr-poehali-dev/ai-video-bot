"""
Business: Admin API - provides dashboard data (stats, users, orders, revenue)
Args: event with query param endpoint=dashboard, context with request_id
Returns: HTTP response with JSON dashboard data
"""

import json
import os
from typing import Dict, Any, List
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta


DATABASE_URL = os.environ.get('DATABASE_URL')


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
        params = event.get('queryStringParameters', {}) or {}
        endpoint = params.get('endpoint', 'dashboard')
        
        conn = psycopg2.connect(DATABASE_URL)
        
        if endpoint == 'dashboard':
            data = get_dashboard_data(conn)
        else:
            data = {'error': 'Unknown endpoint'}
        
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'isBase64Encoded': False,
            'body': json.dumps(data, default=str)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'isBase64Encoded': False,
            'body': json.dumps({'error': str(e)})
        }


def get_dashboard_data(conn) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT COUNT(*) as total_users FROM users")
    total_users = cur.fetchone()['total_users']
    
    cur.execute("""
        SELECT COUNT(*) as active_users_24h 
        FROM users 
        WHERE last_activity > %s
    """, (datetime.now() - timedelta(hours=24),))
    active_users_24h = cur.fetchone()['active_users_24h']
    
    cur.execute("SELECT COUNT(*) as total_orders FROM orders")
    total_orders = cur.fetchone()['total_orders']
    
    cur.execute("SELECT COUNT(*) as processing_orders FROM orders WHERE status = 'processing'")
    processing_orders = cur.fetchone()['processing_orders']
    
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_revenue 
        FROM transactions 
        WHERE type = 'purchase' AND amount > 0
    """)
    total_revenue = cur.fetchone()['total_revenue']
    
    cur.execute("""
        SELECT COALESCE(SUM(ABS(amount)), 0) as credits_spent 
        FROM transactions 
        WHERE type IN ('preview', 'video') AND amount < 0
    """)
    credits_spent = cur.fetchone()['credits_spent']
    
    cur.execute("""
        SELECT user_id, username, first_name, balance, created_at, last_activity, is_blocked
        FROM users 
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    recent_users = [dict(row) for row in cur.fetchall()]
    
    cur.execute("""
        SELECT o.order_id, o.user_id, o.order_type, o.status, o.cost, o.created_at,
               u.username, u.first_name
        FROM orders o
        JOIN users u ON o.user_id = u.user_id
        ORDER BY o.created_at DESC 
        LIMIT 20
    """)
    recent_orders = [dict(row) for row in cur.fetchall()]
    
    cur.execute("""
        SELECT order_type, COUNT(*) as count, COALESCE(SUM(cost), 0) as total_cost
        FROM orders
        WHERE status != 'cancelled'
        GROUP BY order_type
    """)
    order_stats = [dict(row) for row in cur.fetchall()]
    
    cur.execute("""
        SELECT 
            DATE(t.created_at) as date,
            COALESCE(SUM(t.amount), 0) as revenue,
            COUNT(*) as transaction_count
        FROM transactions t
        WHERE t.type = 'purchase' 
            AND t.amount > 0
            AND t.created_at > %s
        GROUP BY DATE(t.created_at)
        ORDER BY date DESC
        LIMIT 7
    """, (datetime.now() - timedelta(days=7),))
    daily_revenue = [dict(row) for row in cur.fetchall()]
    
    return {
        'stats': {
            'total_users': total_users,
            'active_users_24h': active_users_24h,
            'total_orders': total_orders,
            'processing_orders': processing_orders,
            'total_revenue': int(total_revenue),
            'credits_spent': int(credits_spent)
        },
        'recent_users': recent_users,
        'recent_orders': recent_orders,
        'order_stats': order_stats,
        'daily_revenue': daily_revenue
    }
