"""Koneksi ke Supabase ATAS NAMA user yang login (opsi A).

Tiap request: bikin client dengan anon key, lalu pasang access token milik user.
Dengan begitu Row Level Security di database kepakai penuh. service_role key
tidak dipakai sama sekali di backend ini.
"""
import os
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask import abort, session
from postgrest.exceptions import APIError
from supabase import Client, create_client

JAKARTA = ZoneInfo("Asia/Jakarta")


class ValidasiError(Exception):
    """Dilempar saat input user tidak valid atau tidak boleh."""

    def __init__(self, status: int, pesan: str):
        super().__init__(pesan)
        self.status = status
        self.pesan = pesan


def hari_ini() -> date:
    # Server biasanya jalan di UTC; "hari ini" harus ikut jam Indonesia (WIB).
    return datetime.now(JAKARTA).date()


def _env(nama: str) -> str:
    nilai = os.environ.get(nama)
    if not nilai:
        raise RuntimeError(f"Environment variable {nama} belum diisi")
    return nilai


def anon_client() -> Client:
    return create_client(_env("SUPABASE_URL"), _env("SUPABASE_ANON_KEY"))


def simpan_sesi(s) -> None:
    """Simpan token dari Supabase ke session cookie Flask (ditandatangani)."""
    session["access_token"] = s.access_token
    session["refresh_token"] = s.refresh_token
    session["expires_at"] = int(s.expires_at or (time.time() + (s.expires_in or 3600)))


def _token_valid() -> str:
    if "access_token" not in session:
        abort(401)
    # access token Supabase umurnya ~1 jam; perbarui diam-diam kalau hampir habis
    if time.time() >= session.get("expires_at", 0) - 60:
        try:
            res = anon_client().auth.refresh_session(session["refresh_token"])
            if not res.session:
                raise ValueError("refresh gagal")
            simpan_sesi(res.session)
        except Exception:
            session.clear()
            abort(401)
    return session["access_token"]


def user_client() -> Client:
    c = anon_client()
    c.postgrest.auth(_token_valid())
    return c


def fetch_all(buat_query, ukuran: int = 1000) -> list:
    """PostgREST membatasi 1000 baris per request; ambil semua halaman."""
    hasil, mulai = [], 0
    while True:
        baris = buat_query().range(mulai, mulai + ukuran - 1).execute().data
        hasil.extend(baris)
        if len(baris) < ukuran:
            return hasil
        mulai += ukuran


def terjemah_error_db(e: APIError) -> tuple[int, str]:
    kode = getattr(e, "code", None) or ""
    pesan = getattr(e, "message", None) or str(e)
    if kode.startswith("PGRST3"):          # JWT kedaluwarsa / tidak valid
        session.clear()
        return 401, "Sesi habis, silakan login lagi"
    if kode == "42501":                    # ditolak Row Level Security
        return 403, "Kamu tidak punya akses untuk aksi ini"
    if kode == "P0001":                    # raise exception dari trigger database
        return 422, pesan
    if kode in ("23514", "23502", "23503", "22P02"):
        return 400, "Data tidak valid"
    return 500, "Terjadi kesalahan pada database"
