"""Penerima notifikasi pembayaran QRIS (webhook) dan simulator pembayaran untuk demo.

Alur webhook:  gateway --POST JSON + tanda tangan--> /api/qris/webhook
  1. cek umur pesan, 2. cek tanda tangan HMAC-SHA256, 3. validasi isi,
  4. cek duplikat (ref_eksternal unik), 5. catat pemasukan QRIS ke Kas di Bank
     lewat akun sistem "QRIS Otomatis" (role kasir, tetap kena RLS dan trigger saldo).
Simulator /api/qris-demo/bayar menembak endpoint yang SAMA dengan tanda tangan asli,
jadi yang diuji adalah jalur yang nanti dipakai gateway sungguhan.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime

from flask import Blueprint, abort, current_app, jsonify, request
from postgrest.exceptions import APIError

import supa

bp = Blueprint("qris", __name__, url_prefix="/api")

TOLERANSI_DETIK = 300
NOMINAL_MAKS = 100_000_000
NOMINAL_DEMO_MAKS = 10_000_000
POLA_REF = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
SUMBER_DB = {"demo": "qris_demo", "gateway": "qris_gateway"}

_sesi = {"klien": None, "uid": None, "exp": 0}
_kunci_sesi = threading.Lock()
_riwayat_ip: dict = defaultdict(deque)


def simulator_aktif() -> bool:
    return os.environ.get("QRIS_SIMULATOR") == "1"


def _kunci() -> bytes:
    k = os.environ.get("QRIS_WEBHOOK_SECRET", "")
    if len(k) < 16:
        raise supa.ValidasiError(503, "Webhook QRIS belum dikonfigurasi (QRIS_WEBHOOK_SECRET)")
    return k.encode()


def buat_tanda_tangan(timestamp: str, badan: bytes) -> str:
    return hmac.new(_kunci(), timestamp.encode() + b"." + badan, hashlib.sha256).hexdigest()


def klien_sistem():
    """Client Supabase atas nama akun sistem (login sekali, token dipakai ulang sampai hampir habis)."""
    with _kunci_sesi:
        if _sesi["klien"] and _sesi["exp"] - time.time() > 60:
            return _sesi["klien"], _sesi["uid"]
        email, sandi = os.environ.get("QRIS_SYSTEM_EMAIL"), os.environ.get("QRIS_SYSTEM_PASSWORD")
        if not email or not sandi:
            raise supa.ValidasiError(503, "Akun sistem QRIS belum dikonfigurasi")
        c = supa.anon_client()
        try:
            res = c.auth.sign_in_with_password({"email": email, "password": sandi})
        except Exception:
            raise supa.ValidasiError(503, "Login akun sistem QRIS gagal")
        s = res.session
        c.postgrest.auth(s.access_token)
        _sesi.update(klien=c, uid=res.user.id, exp=int(s.expires_at or time.time() + 3600))
        return c, res.user.id


def catat_pembayaran(d: dict):
    """Validasi isi notifikasi lalu catat. Mengembalikan (isi_respons, status_http)."""
    if d.get("status") != "paid":
        return {"status": "diabaikan", "alasan": "status bukan paid"}, 200
    ref = d.get("ref")
    if not isinstance(ref, str) or not POLA_REF.match(ref):
        raise supa.ValidasiError(400, "Referensi tidak valid")
    nominal = d.get("nominal")
    if isinstance(nominal, bool) or not isinstance(nominal, int) or not 0 < nominal <= NOMINAL_MAKS:
        raise supa.ValidasiError(400, "Nominal harus bilangan bulat positif")
    sumber = SUMBER_DB.get(d.get("sumber"))
    if not sumber:
        raise supa.ValidasiError(400, "Sumber notifikasi tidak dikenal")
    pembayar = d.get("pembayar")
    pembayar = " ".join(pembayar.split())[:60] if isinstance(pembayar, str) and pembayar.strip() else "Pembeli"

    c, uid = klien_sistem()
    if c.table("transaksi").select("id").eq("ref_eksternal", ref).execute().data:
        return {"status": "duplikat", "ref": ref}, 200
    kat = c.table("kategori").select("id").eq("nama", "Penjualan QRIS").eq("aktif", True).limit(1).execute().data
    if not kat:
        raise supa.ValidasiError(500, "Kategori 'Penjualan QRIS' tidak ditemukan")
    payload = {
        "tanggal": supa.hari_ini().isoformat(),           # tanggal pencatatan otomatis (WIB)
        "jenis": "masuk", "nominal": nominal, "kategori_id": kat[0]["id"],
        "metode": "qris", "sumber_kas": "bank",
        "keterangan": f"QRIS dari {pembayar} · {ref}"[:200],
        "dibuat_oleh": uid, "ref_eksternal": ref, "sumber": sumber,
    }
    try:
        res = c.table("transaksi").insert(payload).execute()
    except APIError as e:
        if e.code == "23505":                              # balapan: kiriman ganda tiba bersamaan
            return {"status": "duplikat", "ref": ref}, 200
        raise
    return {"status": "dicatat", "id": res.data[0]["id"], "ref": ref}, 201


@bp.post("/qris/webhook")
def webhook():
    badan = request.get_data()
    ts = request.headers.get("X-Timestamp", "")
    ttd = request.headers.get("X-Signature", "")
    if not ts.isdigit():
        raise supa.ValidasiError(401, "Timestamp tidak valid")
    if abs(time.time() - int(ts)) > TOLERANSI_DETIK:
        raise supa.ValidasiError(401, "Notifikasi kedaluwarsa")
    if not hmac.compare_digest(buat_tanda_tangan(ts, badan), ttd):
        raise supa.ValidasiError(401, "Tanda tangan tidak valid")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise supa.ValidasiError(400, "Isi notifikasi harus objek JSON")
    hasil, status = catat_pembayaran(data)
    return jsonify(hasil), status


def _batasi(ip: str, maks: int = 20, jendela: int = 60):
    sekarang, q = time.time(), _riwayat_ip[ip]
    while q and sekarang - q[0] > jendela:
        q.popleft()
    if len(q) >= maks:
        raise supa.ValidasiError(429, "Terlalu sering, tunggu sebentar")
    q.append(sekarang)


@bp.post("/qris-demo/bayar")
def bayar_demo():
    """Pembeli demo menekan Bayar. Kunci rahasia hanya dipakai di server, tidak pernah ke browser."""
    if not simulator_aktif():
        abort(404)
    _batasi(request.remote_addr or "?")
    d = request.get_json(silent=True) or {}
    nominal = d.get("nominal")
    if isinstance(nominal, bool) or not isinstance(nominal, int) or not 0 < nominal <= NOMINAL_DEMO_MAKS:
        raise supa.ValidasiError(400, "Nominal harus bilangan bulat, maksimal Rp10.000.000")
    pembayar = d.get("pembayar")
    pembayar = " ".join(pembayar.split())[:40] if isinstance(pembayar, str) and pembayar.strip() else "Pembeli Demo"

    sekarang = datetime.now(supa.JAKARTA)
    ref = "DEMO-" + sekarang.strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(3).upper()
    isi = {"ref": ref, "status": "paid", "nominal": nominal, "pembayar": pembayar,
           "waktu": sekarang.isoformat(), "sumber": "demo"}
    badan = json.dumps(isi, separators=(",", ":"), ensure_ascii=False).encode()
    ts = str(int(time.time()))
    r = current_app.test_client().post(            # lewat pintu webhook yang sama dengan gateway asli
        "/api/qris/webhook", data=badan, content_type="application/json",
        headers={"X-Timestamp": ts, "X-Signature": buat_tanda_tangan(ts, badan)})
    hasil = r.get_json() or {}
    if r.status_code >= 400:
        return jsonify(error=hasil.get("error", "Pembayaran gagal diproses")), r.status_code
    return jsonify(ref=ref, nominal=nominal, pembayar=pembayar, waktu=isi["waktu"], status=hasil.get("status")), 201
