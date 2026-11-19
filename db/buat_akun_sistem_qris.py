"""Buat akun sistem "QRIS Otomatis" (role kasir) + kunci rahasia webhook. Jalankan SEKALI.

    export SUPABASE_URL="https://xxxx.supabase.co"
    export SUPABASE_SERVICE_ROLE_KEY="..."      # hanya untuk skrip ini; JANGAN masuk .env aplikasi
    python buat_akun_sistem_qris.py

Skrip mencetak 3 baris untuk ditempel ke .env aplikasi (folder 'back & front').
"""
import os
import secrets

from supabase import create_client

EMAIL = "qris-sistem@esteh.test"
password = secrets.token_urlsafe(24)
rahasia_webhook = secrets.token_hex(32)

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
res = sb.auth.admin.create_user({"email": EMAIL, "password": password, "email_confirm": True})
sb.table("profiles").insert({"id": res.user.id, "nama": "QRIS Otomatis", "role": "kasir"}).execute()

print("[ok] akun sistem dibuat. Tempel baris berikut ke file .env (JANGAN dibagikan):\n")
print(f"QRIS_SYSTEM_EMAIL={EMAIL}")
print(f"QRIS_SYSTEM_PASSWORD={password}")
print(f"QRIS_WEBHOOK_SECRET={rahasia_webhook}")
print("QRIS_SIMULATOR=1        # nyalakan hanya untuk demo; hapus/ubah ke 0 saat go-live")
