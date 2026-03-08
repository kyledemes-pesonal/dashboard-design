"""Simple HTTP server for serving the VIVA dashboard on Railway."""
import http.server
import os

PORT = int(os.environ.get("PORT", 8080))

handler = http.server.SimpleHTTPRequestHandler
handler.extensions_map.update({
    ".js": "application/javascript",
    ".json": "application/json",
    ".html": "text/html",
    ".css": "text/css",
})

with http.server.HTTPServer(("0.0.0.0", PORT), handler) as httpd:
    print(f"Serving on port {PORT}")
    httpd.serve_forever()
