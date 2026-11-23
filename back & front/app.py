"""Backend Flask: Akuntansi Kas & Kas Kecil (Es Teh).

Jalankan lokal:  flask --app app run --debug
Production:      gunicorn "app:create_app()"
"""
import logging
import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from postgrest.exceptions import APIError
from werkzeug.exceptions import HTTPException

import auth
import jurnal
import qris
import laporan
import pages
import supa
import transaksi

PESAN_HTTP = {
    401: "Belum login atau sesi sudah habis",
    403: "Kamu tidak punya akses untuk aksi ini",
    404: "Data tidak ditemukan",
    405: "Metode tidak diizinkan",
    415: "Kirim data sebagai JSON (Content-Type: application/json)",
}


def create_app(test_config: dict | None = None) -> Flask:
    from pathlib import Path
    load_dotenv(Path(__file__).parent / ".env")
    load_dotenv()
    app = Flask(__name__, static_folder="public/static")
    app.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "1") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=int(os.environ.get("SESSION_LIFETIME_HOURS", "12"))),
        JSON_AS_ASCII=False,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("FLASK_SECRET_KEY belum diisi (lihat .env.example)")

    app.register_blueprint(auth.bp)
    app.register_blueprint(transaksi.bp)
    app.register_blueprint(laporan.bp)
    app.register_blueprint(jurnal.bp)
    app.register_blueprint(qris.bp)

    @app.context_processor
    def _konteks():
        return {"qris_demo": qris.simulator_aktif()}
    app.register_blueprint(pages.bp)

    @app.before_request
    def wajib_json():
        # Selain input yang rapi, ini menutup CSRF lewat form lintas situs:
        # form HTML biasa tidak bisa mengirim Content-Type application/json.
        if request.method in ("POST", "PUT", "PATCH") and request.path.startswith("/api/"):
            if not request.is_json:
                return jsonify(error=PESAN_HTTP[415]), 415
        elif request.method == "DELETE" and request.path.startswith("/api/"):
            if request.data and not request.is_json:
                return jsonify(error=PESAN_HTTP[415]), 415

    @app.after_request
    def header_keamanan(resp):
        # Halaman & API tidak boleh di-cache (tombol Back setelah logout tidak boleh
        # menampilkan data lama). File statis boleh di-cache browser.
        if not request.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
        return resp

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    @app.errorhandler(supa.ValidasiError)
    def _validasi(e):
        return jsonify(error=e.pesan), e.status

    @app.errorhandler(APIError)
    def _db(e):
        status, pesan = supa.terjemah_error_db(e)
        if status == 500:
            app.logger.error("Error database: %s", e)
        return jsonify(error=pesan), status

    @app.errorhandler(HTTPException)
    def _http(e):
        return jsonify(error=PESAN_HTTP.get(e.code, e.description)), e.code

    @app.errorhandler(Exception)
    def _lain(e):
        app.logger.exception("Error tak terduga")
        return jsonify(error="Terjadi kesalahan di server"), 500

    logging.basicConfig(level=logging.INFO)
    return app


if __name__ == "__main__":
    create_app().run(debug=True)
