"""Tes tingkat kabel: pastikan client SUNGGUHAN mengirim token user ke PostgREST."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import app as app_module
import supa


def test_token_user_terkirim_ke_postgrest(monkeypatch):
    dilihat = []

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            dilihat.append({k.lower(): v for k, v in self.headers.items()})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps([{"kas": "kecil", "saldo": 1}]).encode())

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("SUPABASE_URL", f"http://127.0.0.1:{srv.server_port}")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "ANON-KEY")

    app = app_module.create_app({"TESTING": True, "SECRET_KEY": "x" * 32})
    with app.test_request_context():
        from flask import session
        session.update(access_token="TOKEN-MILIK-USER", refresh_token="r", expires_at=9999999999)
        hasil = supa.user_client().table("saldo_kas").select("kas,saldo").execute().data
    srv.shutdown()

    assert hasil == [{"kas": "kecil", "saldo": 1}]
    assert dilihat[0]["authorization"] == "Bearer TOKEN-MILIK-USER"  # bukan anon key
    assert dilihat[0]["apikey"] == "ANON-KEY"
