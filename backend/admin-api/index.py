"""
Business: Admin API - provides dashboard data for web panel
Args: event with httpMethod, queryStringParameters; context with request_id
Returns: JSON with users, orders, transactions, stats
"""

import json
import os
from typing import Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def get_dashboard_stats(conn) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT COUNT(*) as total_users FROM users")
        total_users = cur.fetchone()['total_users']
        
        cur.execute("""
            SELECT COUNT(*) as active_users 
            FROM users 
            WHERE last_activity > %s
        """, (datetime.now() - timedelta(days=1),))
        active_users = cur.fetchone()['active_users']
        
        cur.execute("SELECT COUNT(*) as total_orders FROM orders")
        total_orders = cur.fetchone()['total_orders']
        
        cur.execute("""
            SELECT COUNT(*) as processing_orders 
            FROM orders 
            WHERE status = 'processing'
        """)
        processing_orders = cur.fetchone()['processing_orders']
        
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_revenue 
            FROM transactions 
            WHERE type = 'purchase'
        """)
        total_revenue = cur.fetchone()['total_revenue']
        
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as credits_spent 
            FROM transactions 
            WHERE type IN ('preview', 'video')
        """)
        credits_spent = abs(cur.fetchone()['credits_spent'])
        
        return {
            'total_users': total_users,
            'active_users_24h': active_users,
            'total_orders': total_orders,
            'processing_orders': processing_orders,
            'total_revenue': total_revenue,
            'credits_spent': credits_spent
        }

def get_recent_users(conn, limit: int = 50) -> list:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT user_id, username, first_name, balance, 
                   created_at, last_activity, is_blocked
            FROM users 
            ORDER BY created_at DESC 
            LIMIT %s
        """, (limit,))
        
        users = cur.fetchall()
        return [dict(u) for u in users]

def get_recent_orders(conn, limit: int = 50) -> list:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT o.order_id, o.user_id, o.order_type, o.status, 
                   o.cost, o.created_at, o.completed_at, o.error_message,
                   u.username, u.first_name
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.user_id
            ORDER BY o.created_at DESC 
            LIMIT %s
        """, (limit,))
        
        orders = cur.fetchall()
        return [dict(o) for o in orders]

def get_recent_transactions(conn, limit: int = 100) -> list:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT t.transaction_id, t.user_id, t.amount, t.type, 
                   t.description, t.created_at,
                   u.username, u.first_name
            FROM transactions t
            LEFT JOIN users u ON t.user_id = u.user_id
            ORDER BY t.created_at DESC 
            LIMIT %s
        """, (limit,))
        
        transactions = cur.fetchall()
        return [dict(t) for t in transactions]

def get_order_stats_by_type(conn) -> list:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT order_type, COUNT(*) as count, 
                   SUM(cost) as total_cost
            FROM orders
            GROUP BY order_type
            ORDER BY count DESC
        """)
        
        stats = cur.fetchall()
        return [dict(s) for s in stats]

def get_daily_revenue(conn, days: int = 7) -> list:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT DATE(created_at) as date, 
                   SUM(amount) as revenue,
                   COUNT(*) as transaction_count
            FROM transactions
            WHERE type = 'purchase' 
              AND created_at > %s
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """, (datetime.now() - timedelta(days=days),))
        
        revenue = cur.fetchall()
        return [dict(r) for r in revenue]

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
            'body': ''
        }
    
    try:
        params = event.get('queryStringParameters', {}) or {}
        endpoint = params.get('endpoint', 'dashboard')
        
        conn = get_db_connection()
        
        response_data = {}
        
        if endpoint == 'dashboard':
            response_data = {
                'stats': get_dashboard_stats(conn),
                'recent_users': get_recent_users(conn, 10),
                'recent_orders': get_recent_orders(conn, 20),
                'order_stats': get_order_stats_by_type(conn),
                'daily_revenue': get_daily_revenue(conn, 7)
            }
        
        elif endpoint == 'users':
            limit = int(params.get('limit', 50))
            response_data = {
                'users': get_recent_users(conn, limit)
            }
        
        elif endpoint == 'orders':
            limit = int(params.get('limit', 50))
            response_data = {
                'orders': get_recent_orders(conn, limit)
            }
        
        elif endpoint == 'transactions':
            limit = int(params.get('limit', 100))
            response_data = {
                'transactions': get_recent_transactions(conn, limit)
            }
        
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data, default=str)
        }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }
