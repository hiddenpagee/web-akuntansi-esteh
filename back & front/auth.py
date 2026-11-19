"""Login, logout, dan penjaga akses (login_required / role_required)."""
from functools import wraps

from flask import Blueprint, abort, jsonify, request, session

from supabase_auth.errors import AuthError

import supa

bp = Blueprint("auth", __name__, url_prefix="/api")

KATEGORI = ("pemilik", "kasir", "karyawan")
PESAN_GAGAL = "Email, password, atau kategori akun salah"  # sengaja satu pesan untuk semua penyebab


def login_required(f):
    @wraps(f)
    def wrapper(*a, **k):
        if "user_id" not in session:
            abort(401)
        return f(*a, **k)

    return wrapper


def role_required(*roles):
    def deco(f):
        @login_required
        @wraps(f)
        def wrapper(*a, **k):
            if session.get("role") not in roles:
                abort(403)
            return f(*a, **k)

        return wrapper

    return deco


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    kategori = data.get("role")
    if kategori not in KATEGORI:
        raise supa.ValidasiError(400, "Pilih kategori akun dulu (Pemilik, Kasir, atau Karyawan)")
    if not email or not isinstance(password, str) or not password:
        raise supa.ValidasiError(400, "Email dan password wajib diisi")

    try:
        res = supa.anon_client().auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except AuthError:
        # pesan sengaja sama untuk email salah maupun password salah
        raise supa.ValidasiError(401, PESAN_GAGAL)

    s, user = res.session, res.user
    if not s or not user:
        raise supa.ValidasiError(401, PESAN_GAGAL)

    c = supa.anon_client()
    c.postgrest.auth(s.access_token)
    baris = (
        c.table("profiles").select("nama,role,aktif").eq("id", user.id).limit(1).execute().data
    )
    if not baris:
        raise supa.ValidasiError(403, "Akun belum punya profil. Hubungi Pemilik.")

    if baris[0]["role"] != kategori:
        # Password benar tapi akun bukan kategori yang dipilih: tolak, dan cabut token yang baru
        # terbit supaya tidak ada sesi Supabase yang menggantung. Pesan sama dengan password salah.
        try:
            c.auth.set_session(s.access_token, s.refresh_token)
            c.auth.sign_out({"scope": "local"})
        except Exception:
            pass
        raise supa.ValidasiError(401, PESAN_GAGAL)
    if not baris[0]["aktif"]:
        raise supa.ValidasiError(403, "Akun belum aktif. Hubungi Pemilik.")

    session.clear()  # cegah session fixation
    session.permanent = True
    session["user_id"] = user.id
    session["nama"] = baris[0]["nama"]
    session["role"] = baris[0]["role"]
    supa.simpan_sesi(s)
    return jsonify(nama=baris[0]["nama"], role=baris[0]["role"])


@bp.post("/logout")
def logout():
    token = session.get("access_token")
    if token:
        try:  # cabut sesi di Supabase juga (hanya perangkat ini), gagal pun tidak masalah
            c = supa.anon_client()
            c.auth.set_session(token, session.get("refresh_token", ""))
            c.auth.sign_out({"scope": "local"})
        except Exception:
            pass
    session.clear()
    return jsonify(ok=True)


@bp.get("/me")
@login_required
def me():
    return jsonify(nama=session["nama"], role=session["role"])
