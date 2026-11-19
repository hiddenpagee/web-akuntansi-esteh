from conftest import login


def test_halaman_butuh_login(client):
    for path in ("/", "/dashboard", "/transaksi", "/kas-kecil", "/laporan", "/jurnal-umum", "/jurnal-petty-cash"):
        r = client.get(path)
        assert r.status_code == 302 and r.headers["Location"].endswith("/login"), path
    assert client.get("/login").status_code == 200


def test_halaman_setelah_login(client):
    login(client, "kasir")
    assert client.get("/").headers["Location"].endswith("/dashboard")
    assert client.get("/login").headers["Location"].endswith("/dashboard")

    # kasir bisa buka dashboard, transaksi, kas-kecil
    for path in ("/dashboard", "/transaksi", "/kas-kecil"):
        r = client.get(path)
        assert r.status_code == 200, path
        html = r.get_data(as_text=True)
        assert 'data-role="kasir"' in html and "Kasir" in html

    # kasir tidak punya akses ke laporan (diarahkan ke /dashboard)
    r_lap = client.get("/laporan")
    assert r_lap.status_code == 302 and r_lap.headers["Location"].endswith("/dashboard")


def test_halaman_laporan_pemilik(client):
    login(client, "pemilik")
    r = client.get("/laporan")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'data-role="pemilik"' in html and "Laporan Keuangan" in html


def test_header_keamanan_dan_static(client):
    r = client.get("/login")
    assert r.headers["Cache-Control"] == "no-store"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    for f in (
        "css/app.css",
        "js/api.js",
        "js/login.js",
        "js/transaksi.js",
        "js/dashboard.js",
        "js/kas_kecil.js",
        "js/laporan.js",
    ):
        assert client.get("/static/" + f).status_code == 200, f


def test_nama_user_di_html_di_escape(client, db):
    db.data["profiles"][0]["nama"] = "<script>alert(1)</script>"
    login(client, "pemilik")
    for path in ("/dashboard", "/transaksi", "/kas-kecil", "/laporan"):
        assert "<script>alert(1)</script>" not in client.get(path).get_data(as_text=True)


def test_halaman_jurnal_per_role(client):
    login(client, "pemilik")
    assert client.get("/jurnal-umum").status_code == 200 and client.get("/jurnal-petty-cash").status_code == 200
    client.post("/api/logout", json={})
    login(client, "kasir")
    assert client.get("/jurnal-umum").status_code == 302                       # kasir: hanya petty cash
    assert client.get("/jurnal-petty-cash").status_code == 200
    client.post("/api/logout", json={})
    login(client, "karyawan")
    assert client.get("/jurnal-petty-cash").status_code == 302
