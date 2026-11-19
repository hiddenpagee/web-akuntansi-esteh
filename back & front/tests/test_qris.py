import json
import time

import pytest

import qris
import supa

ID_SISTEM = "00000000-0000-0000-0000-0000000000aa"
RAHASIA = "r" * 40


@pytest.fixture
def qris_env(db, monkeypatch):
    monkeypatch.setenv("QRIS_WEBHOOK_SECRET", RAHASIA)
    monkeypatch.setenv("QRIS_SYSTEM_EMAIL", "qris-sistem@esteh.test")
    monkeypatch.setenv("QRIS_SYSTEM_PASSWORD", "sandi-sistem")
    monkeypatch.setenv("QRIS_SIMULATOR", "1")
    db.users["qris-sistem@esteh.test"] = {"id": ID_SISTEM, "password": "sandi-sistem"}
    db.data["kategori"] = [{"id": 2, "nama": "Penjualan QRIS", "jenis": "masuk", "aktif": True}]
    db.data["transaksi"] = []
    return db


def isi(ref="QR-20261119-0001", **ubah):
    return {"ref": ref, "status": "paid", "nominal": 25000, "pembayar": "Budi", "sumber": "demo", **ubah}


def kirim(client, payload, ts=None, ttd=None):
    badan = json.dumps(payload).encode()
    ts = ts or str(int(time.time()))
    ttd = qris.buat_tanda_tangan(ts, badan) if ttd is None else ttd
    return client.post("/api/qris/webhook", data=badan, content_type="application/json",
                       headers={"X-Timestamp": ts, "X-Signature": ttd})


def inserts(db):
    return [p for t, op, p, _ in db.log if t == "transaksi" and op == "insert"]


def test_webhook_mencatat_pemasukan_qris_ke_kas_bank(client, qris_env):
    r = kirim(client, isi())
    assert r.status_code == 201 and r.get_json()["status"] == "dicatat"
    p, = inserts(qris_env)
    assert (p["jenis"], p["nominal"], p["metode"], p["sumber_kas"], p["kategori_id"]) == ("masuk", 25000, "qris", "bank", 2)
    assert p["tanggal"] == supa.hari_ini().isoformat()           # tanggal otomatis dari server
    assert p["dibuat_oleh"] == ID_SISTEM and p["ref_eksternal"] == "QR-20261119-0001" and p["sumber"] == "qris_demo"
    assert "Budi" in p["keterangan"]
    assert qris_env.token_terakhir == f"tok-{ID_SISTEM}"          # ditulis atas nama akun sistem, bukan service_role


def test_notifikasi_ganda_tidak_dicatat_dua_kali(client, qris_env):
    assert kirim(client, isi()).status_code == 201
    r = kirim(client, isi())
    assert r.status_code == 200 and r.get_json()["status"] == "duplikat"
    assert len(inserts(qris_env)) == 1


def test_tanda_tangan_palsu_ditolak(client, qris_env):
    assert kirim(client, isi(), ttd="0" * 64).status_code == 401
    assert kirim(client, isi(), ttd="").status_code == 401
    badan = json.dumps(isi()).encode()
    ts = str(int(time.time()))
    ttd = qris.buat_tanda_tangan(ts, badan)
    r = client.post("/api/qris/webhook", data=json.dumps(isi(nominal=9_000_000)).encode(),   # isi diubah, tanda tangan lama
                    content_type="application/json", headers={"X-Timestamp": ts, "X-Signature": ttd})
    assert r.status_code == 401 and inserts(qris_env) == []


def test_pesan_kedaluwarsa_ditolak(client, qris_env):
    lama = str(int(time.time()) - qris.TOLERANSI_DETIK - 5)
    assert kirim(client, isi(), ts=lama).status_code == 401
    assert kirim(client, isi(), ts="abc").status_code == 401
    assert inserts(qris_env) == []


def test_status_belum_paid_diabaikan(client, qris_env):
    r = kirim(client, isi(status="pending"))
    assert r.status_code == 200 and r.get_json()["status"] == "diabaikan" and inserts(qris_env) == []


@pytest.mark.parametrize("nominal", [0, -5, "25000", 12.5, True, None, 10 ** 10])
def test_nominal_tidak_valid_ditolak(client, qris_env, nominal):
    assert kirim(client, isi(nominal=nominal)).status_code == 400
    assert inserts(qris_env) == []


@pytest.mark.parametrize("ubah", [{"ref": "x"}, {"ref": "a b c d e f"}, {"ref": None}, {"sumber": "lain"}])
def test_ref_atau_sumber_tidak_valid_ditolak(client, qris_env, ubah):
    assert kirim(client, isi(**ubah)).status_code == 400


def test_tanpa_konfigurasi_webhook_tidak_aktif(client, db, monkeypatch):
    monkeypatch.delenv("QRIS_WEBHOOK_SECRET", raising=False)
    assert kirim_mentah(client).status_code == 503


def kirim_mentah(client):
    return client.post("/api/qris/webhook", data=b"{}", content_type="application/json",
                       headers={"X-Timestamp": str(int(time.time())), "X-Signature": "x"})


def test_simulator_lewat_pintu_webhook_dan_rahasia_tidak_bocor(client, qris_env):
    r = client.post("/api/qris-demo/bayar", json={"nominal": 15000, "pembayar": "  Sari   Dewi "})
    assert r.status_code == 201
    j = r.get_json()
    assert j["nominal"] == 15000 and j["ref"].startswith("DEMO-") and j["status"] == "dicatat"
    assert RAHASIA not in r.get_data(as_text=True)
    p, = inserts(qris_env)
    assert p["sumber"] == "qris_demo" and p["sumber_kas"] == "bank" and "Sari Dewi" in p["keterangan"]


@pytest.mark.parametrize("nominal", [0, -1, "1000", 1.5, True, 10_000_001])
def test_simulator_nominal_tidak_valid(client, qris_env, nominal):
    assert client.post("/api/qris-demo/bayar", json={"nominal": nominal}).status_code == 400
    assert inserts(qris_env) == []


def test_simulator_mati_kalau_tidak_diaktifkan(client, qris_env, monkeypatch):
    monkeypatch.setenv("QRIS_SIMULATOR", "0")
    assert client.post("/api/qris-demo/bayar", json={"nominal": 1000}).status_code == 404
    assert client.get("/qris-demo").status_code == 404
    assert inserts(qris_env) == []


def test_simulator_dibatasi_per_menit(client, qris_env):
    kode = [client.post("/api/qris-demo/bayar", json={"nominal": 1000}).status_code for _ in range(22)]
    assert kode[:20] == [201] * 20 and kode[20:] == [429, 429]


def test_halaman_simulator_publik_saat_aktif(client, qris_env):
    r = client.get("/qris-demo")
    assert r.status_code == 200 and "nominal-bayar" in r.get_data(as_text=True)
