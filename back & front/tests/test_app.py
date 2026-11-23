import io
from datetime import date

import pytest
from openpyxl import load_workbook

import supa
from conftest import api_error, login
from laporan import tentukan_periode
from transaksi import angka_positif


# ---------- login / logout / sesi ----------
def test_health_dan_endpoint_terlindungi(client):
    assert client.get("/api/health").get_json() == {"status": "ok"}
    for path in ("/api/me", "/api/dashboard", "/api/transaksi", "/api/kas-kecil", "/api/laporan"):
        assert client.get(path).status_code == 401, path


def test_login_salah_dan_benar(client):
    r = client.post("/api/login", json={"email": "pemilik@esteh.test", "password": "salah", "role": "pemilik"})
    assert r.status_code == 401 and "salah" in r.get_json()["error"]
    assert client.post("/api/login", json={"email": "", "password": "", "role": "kasir"}).status_code == 400
    login(client, "pemilik")
    assert client.get("/api/me").get_json() == {"nama": "Pemilik", "role": "pemilik"}


def test_logout_mengakhiri_sesi(client, db):
    login(client, "kasir")
    assert client.post("/api/logout", json={}).status_code == 200
    assert db.sign_out_opts == {"scope": "local"}  # hanya perangkat ini, bukan semua perangkat
    assert client.get("/api/me").status_code == 401


def test_akun_nonaktif_ditolak(client, db):
    db.data["profiles"][1]["aktif"] = False
    r = client.post("/api/login", json={"email": "kasir@esteh.test", "password": "rahasia123", "role": "kasir"})
    assert r.status_code == 403
    assert client.get("/api/me").status_code == 401


def test_post_bukan_json_ditolak(client):
    assert client.post("/api/login", data="email=a", content_type="application/x-www-form-urlencoded").status_code == 415


def test_token_kedaluwarsa_diperbarui_otomatis(client, db):
    db.expires_at = 1  # sudah lewat
    login(client, "pemilik")
    assert client.get("/api/dashboard").status_code == 200
    assert db.refresh_dipanggil == 1
    assert db.token_terakhir == "tok-baru"  # request berikutnya pakai token baru


def test_request_memakai_token_user_bukan_service_role(client, db):
    login(client, "kasir")
    client.get("/api/dashboard")
    assert db.token_terakhir == f"tok-{db.ids['kasir']}"


# ---------- hak akses ----------
def test_role_gating(client, db):
    login(client, "kasir")
    assert client.post("/api/kas-kecil/isi-ulang", json={"nominal": 100000}).status_code == 403
    assert client.get("/api/laporan").status_code == 403
    assert client.get("/api/laporan/export").status_code == 403


def test_karyawan_hanya_pengeluaran_kas_kecil(client, db):
    login(client, "karyawan")
    base = {"kategori_id": 6, "nominal": 20000, "keterangan": "gelas"}
    assert client.post("/api/transaksi", json={**base, "jenis": "masuk", "metode": "tunai"}).status_code == 403
    assert client.post("/api/transaksi", json={**base, "jenis": "keluar", "sumber_kas": "tangan"}).status_code == 403
    r = client.post("/api/transaksi", json={**base, "jenis": "keluar", "sumber_kas": "kecil"})
    assert r.status_code == 201
    assert db.log[-1][2]["dibuat_oleh"] == db.ids["karyawan"]  # diambil dari sesi, bukan dari input


def test_dibuat_oleh_dari_input_diabaikan(client, db):
    login(client, "kasir")
    client.post("/api/transaksi", json={"jenis": "masuk", "kategori_id": 1, "nominal": 5000,
                                        "metode": "tunai", "dibuat_oleh": db.ids["pemilik"]})
    assert db.log[-1][2]["dibuat_oleh"] == db.ids["kasir"]


def test_dashboard_karyawan_hanya_saldo_kas_kecil(client):
    login(client, "karyawan")
    d = client.get("/api/dashboard").get_json()
    assert "tangan" not in d["saldo"] and "bank" not in d["saldo"] and d["saldo"]["kecil"] == 85000
    assert d["kas_kecil_menipis"] is True


def test_dashboard_pemilik_lengkap(client, db):
    hari = supa.hari_ini().isoformat()
    db.data["transaksi"] = [
        {"id": "1", "tanggal": hari, "jenis": "masuk", "nominal": 700000, "status": "aktif", "created_at": "a"},
        {"id": "2", "tanggal": hari, "jenis": "keluar", "nominal": 200000, "status": "aktif", "created_at": "b"},
        {"id": "3", "tanggal": hari, "jenis": "masuk", "nominal": 999999, "status": "batal", "created_at": "c"},
    ]
    login(client, "pemilik")
    d = client.get("/api/dashboard").get_json()
    assert d["saldo"] == {"tangan": 3000000, "bank": 2000000, "kecil": 85000}
    assert d["hari_ini"]["masuk"] == 700000 and d["hari_ini"]["keluar"] == 200000  # yang batal tidak dihitung
    assert d["hari_ini"]["selisih"] == 500000 and len(d["transaksi_terakhir"]) == 2


# ---------- validasi input ----------
@pytest.mark.parametrize("nominal", [0, -5, "abc", 1.5, True, None, "", 99_999_999_999])
def test_nominal_tidak_valid(client, nominal):
    login(client, "pemilik")
    r = client.post("/api/transaksi", json={"jenis": "keluar", "kategori_id": 5, "nominal": nominal, "sumber_kas": "tangan"})
    assert r.status_code == 400


def test_validasi_lain(client):
    login(client, "pemilik")
    ok = {"jenis": "masuk", "kategori_id": 1, "nominal": 1000, "metode": "tunai"}
    assert client.post("/api/transaksi", json={**ok, "kategori_id": None}).status_code == 400
    assert client.post("/api/transaksi", json={**ok, "metode": None}).status_code == 400
    assert client.post("/api/transaksi", json={**ok, "metode": "kartu"}).status_code == 400
    assert client.post("/api/transaksi", json={**ok, "sumber_kas": "kecil"}).status_code == 400
    assert client.post("/api/transaksi", json={**ok, "jenis": "transfer"}).status_code == 400
    assert client.post("/api/transaksi", json={**ok, "tanggal": "2099-01-01"}).status_code == 400
    assert client.post("/api/transaksi", json={**ok, "tanggal": "31/12/2026"}).status_code == 400
    assert client.post("/api/transaksi", json={**ok, "keterangan": "x" * 201}).status_code == 400
    assert client.post("/api/transaksi", json={**ok, "nominal": "25000"}).status_code == 201  # angka dalam teks boleh


def test_pemasukan_masuk_ke_kas_sesuai_metode(client, db):
    login(client, "kasir")
    client.post("/api/transaksi", json={"jenis": "masuk", "kategori_id": 2, "nominal": 1000, "metode": "qris"})
    assert db.log[-1][2]["sumber_kas"] == "bank"          # QRIS -> Kas di Bank
    client.post("/api/transaksi", json={"jenis": "masuk", "kategori_id": 1, "nominal": 1000, "metode": "tunai"})
    assert db.log[-1][2]["sumber_kas"] == "tangan"        # tunai -> Kas di Tangan
    r = client.post("/api/transaksi", json={"jenis": "masuk", "kategori_id": 1, "nominal": 1000, "metode": "tunai", "sumber_kas": "bank"})
    assert r.status_code == 400                           # tidak boleh dipaksa ke kas lain


# ---------- kas kecil & batal ----------
def test_isi_ulang_membuat_transfer(client, db):
    login(client, "pemilik")
    r = client.post("/api/kas-kecil/isi-ulang", json={"nominal": 300000, "sumber_kas": "bank"})
    assert r.status_code == 201
    p = db.log[-1][2]
    assert (p["jenis"], p["sumber_kas"], p["tujuan_kas"], p["nominal"]) == ("transfer", "bank", "kecil", 300000)
    assert client.post("/api/kas-kecil/isi-ulang", json={"nominal": 0, "sumber_kas": "bank"}).status_code == 400
    assert client.post("/api/kas-kecil/isi-ulang", json={"nominal": 1000}).status_code == 400            # sumber wajib
    assert client.post("/api/kas-kecil/isi-ulang", json={"nominal": 1000, "sumber_kas": "kecil"}).status_code == 400


def test_fitur_batal_sudah_dihapus(client, db):
    login(client, "pemilik")
    tid = "11111111-1111-1111-1111-111111111111"
    assert client.post(f"/api/transaksi/{tid}/batal", json={"alasan": "salah input"}).status_code == 404
    assert not any(op == "update" for _, op, _, _ in db.log)  # tidak ada jalur ubah data transaksi


def test_login_per_kategori(client, db):
    kirim = lambda email, role: client.post("/api/login", json={"email": email, "password": "rahasia123", "role": role})
    # password benar, tapi kategori tidak cocok -> gagal, tanpa sesi, dan token Supabase dicabut
    for email, role in (("kasir@esteh.test", "pemilik"), ("pemilik@esteh.test", "karyawan"), ("karyawan@esteh.test", "kasir")):
        db.sign_out_opts = None
        r = kirim(email, role)
        assert r.status_code == 401 and r.get_json()["error"] == "Email, password, atau kategori akun salah"
        assert db.sign_out_opts == {"scope": "local"}
        assert client.get("/api/me").status_code == 401
    # kategori kosong atau ngawur -> 400
    assert kirim("pemilik@esteh.test", None).status_code == 400
    assert kirim("pemilik@esteh.test", "admin").status_code == 400
    # kategori cocok -> berhasil
    assert kirim("kasir@esteh.test", "kasir").status_code == 200
    assert client.get("/api/me").get_json()["role"] == "kasir"


def test_daftar_transaksi_filter_dan_paging(client, db):
    db.data["transaksi"] = [
        {"id": str(i), "tanggal": f"2026-11-{i:02d}", "jenis": "masuk" if i % 2 else "keluar",
         "nominal": i, "status": "aktif", "sumber_kas": "tangan", "created_at": str(i)} for i in range(1, 8)
    ]
    login(client, "pemilik")
    r = client.get("/api/transaksi?jenis=masuk&per_page=2&page=2").get_json()
    assert r["total"] == 4 and len(r["data"]) == 2 and r["data"][0]["tanggal"] == "2026-11-03"
    assert client.get("/api/transaksi?dari=bukan-tanggal").status_code == 400
    assert client.get("/api/transaksi?per_page=9999").get_json()["per_page"] == 100


# ---------- laporan ----------
def test_tentukan_periode():
    rabu = date(2026, 11, 11)
    assert tentukan_periode({}, rabu)[:2] == (rabu, rabu)
    assert tentukan_periode({"periode": "mingguan"}, rabu)[:2] == (date(2026, 11, 9), date(2026, 11, 15))
    assert tentukan_periode({"periode": "bulanan"}, rabu)[:2] == (date(2026, 11, 1), date(2026, 11, 30))
    assert tentukan_periode({"periode": "bulanan", "tanggal": "2028-02-10"}, rabu)[1] == date(2028, 2, 29)
    assert tentukan_periode({"periode": "custom", "dari": "2026-11-01", "sampai": "2026-11-05"}, rabu)[:2] == (date(2026, 11, 1), date(2026, 11, 5))
    for buruk in ({"periode": "tahunan"}, {"periode": "custom"},
                  {"periode": "custom", "dari": "2026-11-05", "sampai": "2026-11-01"},
                  {"periode": "custom", "dari": "2020-01-01", "sampai": "2026-11-01"}):
        with pytest.raises(supa.ValidasiError):
            tentukan_periode(buruk, rabu)


def data_laporan(db):
    kat = lambda n: {"nama": n}
    db.data["transaksi"] = [
        # sebelum periode: +1.000.000 -300.000 => saldo awal 2.5M + 700k = 3.2M
        {"tanggal": "2026-10-31", "jenis": "masuk", "nominal": 1000000, "status": "aktif", "created_at": "1"},
        {"tanggal": "2026-10-31", "jenis": "keluar", "nominal": 300000, "status": "aktif", "created_at": "2"},
        {"tanggal": "2026-10-30", "jenis": "masuk", "nominal": 888888, "status": "batal", "created_at": "0"},
        # dalam periode 1-3 Nov
        {"tanggal": "2026-11-01", "jenis": "masuk", "nominal": 700000, "metode": "tunai", "sumber_kas": "tangan", "status": "aktif", "created_at": "3", "kategori": kat("Penjualan Tunai"), "keterangan": "Harian"},
        {"tanggal": "2026-11-01", "jenis": "masuk", "nominal": 400000, "metode": "qris", "sumber_kas": "bank", "status": "aktif", "created_at": "4", "kategori": kat("Penjualan QRIS")},
        {"tanggal": "2026-11-02", "jenis": "keluar", "nominal": 250000, "sumber_kas": "tangan", "status": "aktif", "created_at": "5", "kategori": kat("Bahan Baku"), "keterangan": "Teh"},
        {"tanggal": "2026-11-02", "jenis": "transfer", "nominal": 300000, "sumber_kas": "tangan", "tujuan_kas": "kecil", "status": "aktif", "created_at": "6"},
        {"tanggal": "2026-11-03", "jenis": "keluar", "nominal": 50000, "sumber_kas": "kecil", "status": "aktif", "created_at": "7", "kategori": kat("Bahan Baku")},
        {"tanggal": "2026-11-03", "jenis": "masuk", "nominal": 111111, "sumber_kas": "tangan", "status": "batal", "created_at": "8", "kategori": kat("Penjualan Tunai")},
        # setelah periode: tidak boleh ikut
        {"tanggal": "2026-11-04", "jenis": "masuk", "nominal": 5000000, "sumber_kas": "tangan", "status": "aktif", "created_at": "9", "kategori": kat("Pesanan Event")},
    ]


def test_laporan_hitungan(client, db):
    data_laporan(db)
    login(client, "pemilik")
    h = client.get("/api/laporan?periode=custom&dari=2026-11-01&sampai=2026-11-03").get_json()
    assert h["saldo_awal"] == 2_500_000 + 700_000
    assert [b["saldo"] for b in h["buku_kas"]] == [3_900_000, 4_300_000, 4_050_000, 4_050_000, 4_000_000]
    assert h["buku_kas"][3]["kas"] == "Kas di Tangan → Kas Kecil"  # transfer tampil tapi saldo total tetap
    assert h["saldo_akhir"] == 4_000_000
    assert h["laba_rugi"] == {"total_masuk": 1_100_000, "total_keluar": 300_000, "laba": 800_000}
    assert h["rekap"]["keluar"][0] == {"kategori": "Bahan Baku", "total": 300_000}
    assert h["rekap"]["masuk"][0]["kategori"] == "Penjualan Tunai"


def test_export_excel(client, db):
    data_laporan(db)
    login(client, "pemilik")
    r = client.get("/api/laporan/export?periode=custom&dari=2026-11-01&sampai=2026-11-03")
    assert r.status_code == 200 and "spreadsheetml" in r.mimetype
    assert "laporan-kas_2026-11-01_2026-11-03.xlsx" in r.headers["Content-Disposition"]
    wb = load_workbook(io.BytesIO(r.data))
    assert wb.sheetnames == ["Buku Kas", "Rekap", "Laba Rugi"]
    assert wb["Laba Rugi"]["B4"].value == 800_000
    assert wb["Buku Kas"]["H5"].value == 3_900_000


def test_laporan_pagination_ambil_semua_baris(client, db):
    db.data["transaksi"] = [
        {"tanggal": "2026-11-01", "jenis": "masuk", "nominal": 1000, "sumber_kas": "tangan", "status": "aktif",
         "created_at": f"{i:05d}", "kategori": {"nama": "Penjualan Tunai"}} for i in range(2500)
    ]
    login(client, "pemilik")
    h = client.get("/api/laporan?periode=harian&tanggal=2026-11-01").get_json()
    assert len(h["buku_kas"]) == 2500 and h["laba_rugi"]["total_masuk"] == 2_500_000


def test_angka_positif():
    assert angka_positif(10) == 10 and angka_positif(" 10 ") == 10
    assert angka_positif(0) is None and angka_positif(1.0) is None and angka_positif(False) is None


def test_rls_tolak_jadi_403_dan_error_aneh_jadi_500_tanpa_bocor(client, db):
    login(client, "pemilik")
    body = {"jenis": "keluar", "kategori_id": 6, "nominal": 1000, "sumber_kas": "kecil"}
    db.on_insert = lambda t, p: (_ for _ in ()).throw(api_error("42501", "new row violates row-level security policy"))
    assert client.post("/api/transaksi", json=body).status_code == 403
    db.on_insert = lambda t, p: (_ for _ in ()).throw(api_error("XX000", "relation internal_secret_table broken"))
    r = client.post("/api/transaksi", json=body)
    assert r.status_code == 500 and "internal_secret" not in r.get_data(as_text=True)


def test_saldo_tidak_cukup_jadi_422(client, db):
    login(client, "pemilik")
    db.on_insert = lambda t, p: (_ for _ in ()).throw(api_error("P0001", "Saldo kas kecil tidak cukup (sisa Rp85000)"))
    r = client.post("/api/transaksi", json={"jenis": "keluar", "kategori_id": 6, "nominal": 900000, "sumber_kas": "kecil"})
    assert r.status_code == 422 and "tidak cukup" in r.get_json()["error"]


# ---------- jurnal umum & jurnal petty cash ----------
def data_jurnal(db):
    kat = lambda n: {"nama": n}
    db.data["kategori"] = [{"id": 1, "akun_kode": "4-101"}, {"id": 5, "akun_kode": "5-101"}]
    db.data["pengaturan_kas"] = [{"kas": "tangan", "saldo_awal": 1_000_000}, {"kas": "bank", "saldo_awal": 500_000},
                                 {"kas": "kecil", "saldo_awal": 500_000}]
    db.data["transaksi"] = [
        {"id": "a", "tanggal": "2026-10-31", "jenis": "keluar", "nominal": 100000, "sumber_kas": "kecil", "kategori_id": 5,
         "status": "aktif", "created_at": "1", "kategori": kat("Bahan Baku"), "keterangan": "es batu"},      # sebelum periode
        {"id": "b", "tanggal": "2026-11-01", "jenis": "masuk", "nominal": 700000, "sumber_kas": "tangan", "metode": "tunai",
         "kategori_id": 1, "status": "aktif", "created_at": "2", "kategori": kat("Penjualan Tunai")},
        {"id": "c", "tanggal": "2026-11-01", "jenis": "masuk", "nominal": 400000, "sumber_kas": "bank", "metode": "qris",
         "kategori_id": 1, "status": "aktif", "created_at": "3", "kategori": kat("Penjualan QRIS")},
        {"id": "d", "tanggal": "2026-11-02", "jenis": "keluar", "nominal": 250000, "sumber_kas": "bank", "kategori_id": 5,
         "status": "aktif", "created_at": "4", "kategori": kat("Bahan Baku")},
        {"id": "e", "tanggal": "2026-11-02", "jenis": "transfer", "nominal": 300000, "sumber_kas": "bank", "tujuan_kas": "kecil",
         "status": "aktif", "created_at": "5"},
        {"id": "f", "tanggal": "2026-11-03", "jenis": "keluar", "nominal": 50000, "sumber_kas": "kecil", "kategori_id": 5,
         "status": "aktif", "created_at": "6", "kategori": kat("Bahan Baku"), "keterangan": "sedotan"},
        {"id": "g", "tanggal": "2026-11-03", "jenis": "masuk", "nominal": 999, "sumber_kas": "tangan", "metode": "tunai",
         "kategori_id": 1, "status": "batal", "created_at": "7", "kategori": kat("Penjualan Tunai")},       # batal: diabaikan
    ]


def test_jurnal_umum_debit_kredit(client, db):
    data_jurnal(db)
    login(client, "pemilik")
    j = client.get("/api/jurnal-umum?periode=custom&dari=2026-11-01&sampai=2026-11-03").get_json()
    ringkas = lambda e: [(b["kode"], b["debit"], b["kredit"]) for b in e["baris"]]
    assert [e["no"] for e in j["jurnal"]] == ["JU-0002", "JU-0003", "JU-0004", "JU-0005", "JU-0006"]   # nomor stabil dari awal
    assert ringkas(j["jurnal"][0]) == [("1-101", 700000, 0), ("4-101", 0, 700000)]      # tunai: D Kas di Tangan, K Penjualan
    assert ringkas(j["jurnal"][1]) == [("1-102", 400000, 0), ("4-101", 0, 400000)]      # QRIS: D Kas di Bank
    assert ringkas(j["jurnal"][2]) == [("5-101", 250000, 0), ("1-102", 0, 250000)]      # beli bahan: D Beban, K Kas di Bank
    assert ringkas(j["jurnal"][3]) == [("1-103", 300000, 0), ("1-102", 0, 300000)]      # isi ulang: D Kas Kecil, K Kas di Bank
    assert ringkas(j["jurnal"][4]) == [("5-101", 50000, 0), ("1-103", 0, 50000)]
    assert j["total"] == {"debit": 1_700_000, "kredit": 1_700_000} and j["seimbang"] is True
    assert [(b["kode"], b["debit"], b["kredit"]) for b in j["pembuka"]] == [
        ("1-101", 1_000_000, 0), ("1-102", 500_000, 0), ("1-103", 500_000, 0), ("3-101", 0, 2_000_000)]


def test_jurnal_petty_cash(client, db):
    data_jurnal(db)
    login(client, "kasir")                                    # kasir boleh lihat jurnal petty cash
    j = client.get("/api/jurnal-petty-cash?periode=custom&dari=2026-11-01&sampai=2026-11-03").get_json()
    assert j["saldo_awal"] == 400_000                          # 500rb - 100rb sebelum periode
    assert [(b["no"], b["debit"], b["kredit"], b["saldo"], b["akun_lawan"]) for b in j["baris"]] == [
        ("PC-0002", 300000, 0, 700000, "Kas di Bank"), ("PC-0003", 0, 50000, 650000, "Beban Bahan Baku")]
    assert (j["total_isi_ulang"], j["total_pengeluaran"], j["saldo_akhir"]) == (300000, 50000, 650000)


def test_akses_jurnal_per_role(client, db):
    data_jurnal(db)
    login(client, "kasir")
    assert client.get("/api/jurnal-umum").status_code == 403
    assert client.get("/api/jurnal-petty-cash").status_code == 200
    client.post("/api/logout", json={})
    login(client, "karyawan")
    assert client.get("/api/jurnal-umum").status_code == 403
    assert client.get("/api/jurnal-petty-cash").status_code == 403


def test_pemilik_crud_transaksi(client, db):
    login(client, "pemilik")
    # Tambah transaksi awal
    res_tambah = client.post("/api/transaksi", json={
        "jenis": "keluar", "nominal": 25000, "kategori_id": 4, "sumber_kas": "kecil", "keterangan": "Beli cup"
    })
    assert res_tambah.status_code == 201
    tid = res_tambah.get_json()["id"]

    # Detail
    res_det = client.get(f"/api/transaksi/{tid}")
    assert res_det.status_code == 200
    assert res_det.get_json()["nominal"] == 25000

    # Ubah (PUT)
    res_ubah = client.put(f"/api/transaksi/{tid}", json={
        "jenis": "keluar", "nominal": 30000, "kategori_id": 4, "sumber_kas": "kecil", "keterangan": "Beli cup 2 pack"
    })
    assert res_ubah.status_code == 200
    assert res_ubah.get_json()["nominal"] == 30000
    assert res_ubah.get_json()["keterangan"] == "Beli cup 2 pack"

    # Hapus (DELETE)
    res_hapus = client.delete(f"/api/transaksi/{tid}")
    assert res_hapus.status_code == 200
    assert res_hapus.get_json()["status"] == "ok"

    # Detail setelah hapus harus 404
    assert client.get(f"/api/transaksi/{tid}").status_code == 404


def test_non_pemilik_dilarang_edit_dan_hapus_transaksi(client, db):
    login(client, "pemilik")
    tid = client.post("/api/transaksi", json={
        "jenis": "keluar", "nominal": 20000, "kategori_id": 4, "sumber_kas": "kecil", "keterangan": "Uji"
    }).get_json()["id"]
    client.post("/api/logout", json={})

    # Kasir coba edit & hapus -> 403
    login(client, "kasir")
    assert client.put(f"/api/transaksi/{tid}", json={"nominal": 25000, "kategori_id": 4, "sumber_kas": "kecil"}).status_code == 403
    assert client.delete(f"/api/transaksi/{tid}").status_code == 403
    client.post("/api/logout", json={})

    # Karyawan coba edit & hapus -> 403
    login(client, "karyawan")
    assert client.put(f"/api/transaksi/{tid}", json={"nominal": 25000, "kategori_id": 4, "sumber_kas": "kecil"}).status_code == 403
    assert client.delete(f"/api/transaksi/{tid}").status_code == 403

