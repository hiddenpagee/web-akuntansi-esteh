"""Cek otomatis ke Supabase ASLI (hanya baca, tidak menulis data apa pun).

Jalankan dari folder 'back & front' dengan venv aktif:
    python cek_database_asli.py

Butuh akun demo dari seed_users.py (password default Demo12345!).
Kalau password akun lu beda:  set DEMO_PASSWORD=...   (PowerShell: $env:DEMO_PASSWORD="...")
"""
import logging
import os
import sys
import time

logging.getLogger("httpx").setLevel(logging.WARNING)   # sembunyikan log HTTP biar keluaran ringkas

from app import create_app

PW = os.environ.get("DEMO_PASSWORD", "Demo12345!")
hasil = []


def cek(nama, ok, info=""):
    hasil.append(ok)
    print(("[ OK ] " if ok else "[GAGAL] ") + nama + (f"  -> {info}" if info and not ok else ""))


def masuk(c, role, email=None, kategori=None):
    return c.post("/api/login", json={"email": email or f"{role}@esteh.test", "password": PW, "role": kategori or role})


app = create_app({"TESTING": True, "SESSION_COOKIE_SECURE": False})

# --- login per kategori ---
for role in ("pemilik", "kasir", "karyawan"):
    c = app.test_client()
    r = masuk(c, role)
    cek(f"login {role} sebagai {role}", r.status_code == 200, r.get_data(as_text=True)[:120])
c = app.test_client()
r = masuk(c, "kasir", kategori="pemilik")
cek("kasir pilih kategori pemilik -> DITOLAK (password benar)", r.status_code == 401 and c.get("/api/me").status_code == 401, r.get_data(as_text=True)[:120])
r = masuk(app.test_client(), "pemilik", kategori="karyawan")
cek("pemilik pilih kategori karyawan -> DITOLAK", r.status_code == 401)

# --- pemilik ---
c = app.test_client(); masuk(c, "pemilik")
d = c.get("/api/dashboard")
cek("pemilik: dashboard + saldo Kas di Tangan, Kas di Bank, Kas Kecil", d.status_code == 200 and {"tangan", "bank", "kecil"} <= set(d.get_json()["saldo"]), d.get_data(as_text=True)[:120])
cek("pemilik: riwayat transaksi", c.get("/api/transaksi").status_code == 200)
cek("pemilik: laporan bulanan", c.get("/api/laporan?periode=bulanan").status_code == 200)
x = c.get("/api/laporan/export?periode=bulanan")
cek("pemilik: export Excel (.xlsx valid)", x.status_code == 200 and x.data[:2] == b"PK")
r = app.test_client().post("/api/qris/webhook", json={"ref": "CEK-0001", "status": "paid", "nominal": 1000, "sumber": "demo"},
                           headers={"X-Timestamp": str(int(time.time())), "X-Signature": "0" * 64})
cek("webhook QRIS: tanda tangan palsu DITOLAK (tidak menulis data)", r.status_code in (401, 503), r.get_data(as_text=True)[:100])
cek("fitur batal sudah tidak ada", c.post("/api/transaksi/11111111-1111-1111-1111-111111111111/batal", json={"alasan": "uji"}).status_code == 404)

ju = c.get("/api/jurnal-umum?periode=bulanan")
cek("pemilik: jurnal umum (debit = kredit)", ju.status_code == 200 and ju.get_json()["seimbang"], ju.get_data(as_text=True)[:120])
pc = c.get("/api/jurnal-petty-cash?periode=bulanan")
cek("pemilik: jurnal petty cash", pc.status_code == 200, pc.get_data(as_text=True)[:120])

# --- kasir ---
c = app.test_client(); masuk(c, "kasir")
d = c.get("/api/dashboard")
cek("kasir: lihat Kas di Tangan dan Bank", d.status_code == 200 and {"tangan", "bank"} <= set(d.get_json()["saldo"]))
cek("kasir: laporan DITOLAK", c.get("/api/laporan").status_code == 403)
cek("kasir: jurnal umum DITOLAK", c.get("/api/jurnal-umum").status_code == 403)
cek("kasir: jurnal petty cash boleh", c.get("/api/jurnal-petty-cash").status_code == 200)
cek("kasir: isi ulang kas kecil DITOLAK", c.post("/api/kas-kecil/isi-ulang", json={"nominal": 1000}).status_code == 403)

# --- karyawan ---
c = app.test_client(); masuk(c, "karyawan")
d = c.get("/api/dashboard")
cek("karyawan: Kas di Tangan dan Bank TIDAK terlihat", d.status_code == 200 and not ({"tangan", "bank"} & set(d.get_json()["saldo"])))
cek("karyawan: catat pemasukan DITOLAK", c.post("/api/transaksi", json={"jenis": "masuk", "nominal": 1000, "kategori_id": 1, "metode": "tunai"}).status_code == 403)
cek("karyawan: laporan DITOLAK", c.get("/api/laporan").status_code == 403)
cek("karyawan: jurnal petty cash DITOLAK", c.get("/api/jurnal-petty-cash").status_code == 403)

print(f"\n{sum(hasil)}/{len(hasil)} lolos")
sys.exit(0 if all(hasil) else 1)
