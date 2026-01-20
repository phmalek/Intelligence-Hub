#!/usr/bin/env python3
import http.server
import socketserver
from pathlib import Path

BASE_DIR = Path('/home/ali/repos/porsche')
SERVE_DIR = BASE_DIR / 'pwc reports' / 'outputs'
PORT = 8000

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SERVE_DIR), **kwargs)


with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving dashboard at http://localhost:{PORT}/dashboard/index.html")
    httpd.serve_forever()
