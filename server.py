#!/usr/bin/env python3
"""HTTP server with PostgreSQL database support for Railway deployment"""

import http.server
import socketserver
import os
import sys
import json

# Database support
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_DB = True
except ImportError:
    HAS_DB = False
    print("⚠️  psycopg2 not installed - running without database")

PORT = int(os.environ.get('PORT', 8000))
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:LkXKcgMFwZLTqDwVUneCrThnqEtYGjfX@switchyard.proxy.rlwy.net:41189/railway')

MIME_TYPES = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.csv': 'text/csv',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
}

def get_db_connection():
    """Get database connection"""
    if not DATABASE_URL or not HAS_DB:
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def init_database():
    """Initialize database table"""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS restaurants (
                id SERIAL PRIMARY KEY,
                zone VARCHAR(10) NOT NULL,
                name VARCHAR(255) NOT NULL,
                address VARCHAR(500) NOT NULL,
                type VARCHAR(100) DEFAULT 'Restaurant',
                phone VARCHAR(50) DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Database initialized")
        return True
    except Exception as e:
        print(f"Database init error: {e}")
        return False

class APIHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()
    
    def guess_type(self, path):
        ext = os.path.splitext(path)[1].lower()
        return MIME_TYPES.get(ext, super().guess_type(path))
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def read_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        return json.loads(body.decode('utf-8')) if body else {}
    
    def do_GET(self):
        # API endpoints
        if self.path == '/api/restaurants':
            return self.get_restaurants()
        elif self.path == '/api/health':
            return self.send_json({'status': 'ok', 'database': bool(DATABASE_URL and HAS_DB)})
        
        # Serve static files
        if self.path == '/':
            self.path = '/index.html'
        return super().do_GET()
    
    def do_POST(self):
        if self.path == '/api/restaurants':
            return self.add_restaurant()
        elif self.path == '/api/restaurants/bulk':
            return self.bulk_add_restaurants()
        elif self.path == '/api/sync':
            return self.sync_from_client()
        self.send_response(404)
        self.end_headers()
    
    def do_PUT(self):
        if self.path.startswith('/api/restaurants/'):
            return self.update_restaurant()
        self.send_response(404)
        self.end_headers()
    
    def do_DELETE(self):
        if self.path.startswith('/api/restaurants/'):
            return self.delete_restaurant()
        elif self.path == '/api/restaurants':
            return self.delete_all_restaurants()
        self.send_response(404)
        self.end_headers()
    
    # ============== API METHODS ==============
    
    def get_restaurants(self):
        conn = get_db_connection()
        if not conn:
            return self.send_json({'error': 'No database', 'data': []}, 200)
        
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute('SELECT id, zone, name, address, type, phone FROM restaurants ORDER BY zone, name')
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return self.send_json({'data': [dict(r) for r in rows]})
        except Exception as e:
            return self.send_json({'error': str(e), 'data': []}, 500)
    
    def add_restaurant(self):
        conn = get_db_connection()
        if not conn:
            return self.send_json({'error': 'No database'}, 500)
        
        try:
            data = self.read_body()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute('''
                INSERT INTO restaurants (zone, name, address, type, phone)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, zone, name, address, type, phone
            ''', (data.get('zone', '1'), data['name'], data['address'], 
                  data.get('type', 'Restaurant'), data.get('phone', '')))
            row = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
            return self.send_json({'data': dict(row)}, 201)
        except Exception as e:
            return self.send_json({'error': str(e)}, 500)
    
    def bulk_add_restaurants(self):
        conn = get_db_connection()
        if not conn:
            return self.send_json({'error': 'No database'}, 500)
        
        try:
            data = self.read_body()
            restaurants = data.get('restaurants', [])
            replace = data.get('replace', False)
            
            cur = conn.cursor()
            
            if replace:
                cur.execute('DELETE FROM restaurants')
            
            count = 0
            for r in restaurants:
                cur.execute('''
                    INSERT INTO restaurants (zone, name, address, type, phone)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (r.get('zone', '1'), r['name'], r['address'],
                      r.get('type', 'Restaurant'), r.get('phone', '')))
                count += 1
            
            conn.commit()
            cur.close()
            conn.close()
            return self.send_json({'message': f'{count} restaurants added', 'count': count}, 201)
        except Exception as e:
            return self.send_json({'error': str(e)}, 500)
    
    def sync_from_client(self):
        """Sync data from client localStorage to database"""
        conn = get_db_connection()
        if not conn:
            return self.send_json({'error': 'No database'}, 500)
        
        try:
            data = self.read_body()
            restaurants = data.get('restaurants', [])
            
            cur = conn.cursor()
            cur.execute('DELETE FROM restaurants')
            
            count = 0
            for r in restaurants:
                cur.execute('''
                    INSERT INTO restaurants (zone, name, address, type, phone)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (r.get('zone', '1'), r.get('name', ''), r.get('address', ''),
                      r.get('type', 'Restaurant'), r.get('phone', '')))
                count += 1
            
            conn.commit()
            cur.close()
            conn.close()
            return self.send_json({'message': f'Synced {count} restaurants', 'count': count}, 200)
        except Exception as e:
            return self.send_json({'error': str(e)}, 500)
    
    def update_restaurant(self):
        conn = get_db_connection()
        if not conn:
            return self.send_json({'error': 'No database'}, 500)
        
        try:
            restaurant_id = int(self.path.split('/')[-1])
            data = self.read_body()
            
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute('''
                UPDATE restaurants 
                SET zone = %s, name = %s, address = %s, type = %s, phone = %s
                WHERE id = %s
                RETURNING id, zone, name, address, type, phone
            ''', (data.get('zone', '1'), data['name'], data['address'],
                  data.get('type', 'Restaurant'), data.get('phone', ''), restaurant_id))
            row = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
            
            if row:
                return self.send_json({'data': dict(row)})
            return self.send_json({'error': 'Not found'}, 404)
        except Exception as e:
            return self.send_json({'error': str(e)}, 500)
    
    def delete_restaurant(self):
        conn = get_db_connection()
        if not conn:
            return self.send_json({'error': 'No database'}, 500)
        
        try:
            restaurant_id = int(self.path.split('/')[-1])
            cur = conn.cursor()
            cur.execute('DELETE FROM restaurants WHERE id = %s', (restaurant_id,))
            deleted = cur.rowcount
            conn.commit()
            cur.close()
            conn.close()
            
            if deleted:
                return self.send_json({'message': 'Deleted'})
            return self.send_json({'error': 'Not found'}, 404)
        except Exception as e:
            return self.send_json({'error': str(e)}, 500)
    
    def delete_all_restaurants(self):
        conn = get_db_connection()
        if not conn:
            return self.send_json({'error': 'No database'}, 500)
        
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM restaurants')
            conn.commit()
            cur.close()
            conn.close()
            return self.send_json({'message': 'All deleted'})
        except Exception as e:
            return self.send_json({'error': str(e)}, 500)
    
    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}")


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')
    
    # Initialize database
    if DATABASE_URL and HAS_DB:
        init_database()
    else:
        print("⚠️  No DATABASE_URL or psycopg2 - using client-side localStorage only")
    
    with ReusableTCPServer(("", PORT), APIHandler) as httpd:
        print(f"🍽️  Manager Restaurante running at http://localhost:{PORT}")
        if DATABASE_URL and HAS_DB:
            print(f"   Database: Connected ✓")
        print("   Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Server stopped")
            sys.exit(0)
