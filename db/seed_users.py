"""Buat 3 akun demo (Pemilik, Kasir, Karyawan) + profilnya.

Jalankan sekali, SEBELUM 02_seed_transaksi.sql:
    pip install supabase
    export SUPABASE_URL="https://xxxx.supabase.co"
    export SUPABASE_SERVICE_ROLE_KEY="..."   # JANGAN di-commit ke GitHub
    python seed_users.py
"""
import os
from supabase import create_client

PASSWORD = os.environ.get("DEMO_PASSWORD", "Demo12345!")  # ganti kalau dipakai sungguhan

USERS = [
    ("pemilik@esteh.test",  "Pemilik Demo",  "pemilik"),
    ("kasir@esteh.test",    "Kasir Demo",    "kasir"),
    ("karyawan@esteh.test", "Karyawan Demo", "karyawan"),
]

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

for email, nama, role in USERS:
    try:
        res = sb.auth.admin.create_user(
            {"email": email, "password": PASSWORD, "email_confirm": True}
        )
        uid = res.user.id
    except Exception as e:
        print(f"[lewati] {email}: {e}")
        continue
    sb.table("profiles").insert({"id": uid, "nama": nama, "role": role}).execute()
    print(f"[ok] {role:9s} {email}")
