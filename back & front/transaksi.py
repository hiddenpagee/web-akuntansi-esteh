"""Dashboard, kategori, transaksi, dan kas kecil."""
import os
from datetime import date

from flask import Blueprint, jsonify, request, session

import supa
from auth import login_required, role_required

bp = Blueprint("transaksi", __name__, url_prefix="/api")

KOLOM = "id,tanggal,jenis,nominal,metode,sumber_kas,tujuan_kas,keterangan,status,sumber,created_at,kategori(nama)"
JENIS = ("masuk", "keluar", "transfer")
KAS = ("tangan", "bank", "kecil")
SUMBER_MASUK = {"tunai": "tangan", "qris": "bank"}   # tunai -> Kas di Tangan, QRIS -> Kas di Bank
METODE = ("tunai", "qris")


# ---------- validasi (fungsi murni, gampang dites) ----------
def angka_positif(v):
    """Rupiah harus bilangan bulat > 0. Float, bool, dan teks non-angka ditolak."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        n = v
    elif isinstance(v, str) and v.strip().isdigit():
        n = int(v.strip())
    else:
        return None
    return n if 0 < n <= 10_000_000_000 else None


def parse_tanggal(v, default: date) -> date:
    if v in (None, ""):
        return default
    try:
        d = date.fromisoformat(str(v))
    except ValueError:
        raise supa.ValidasiError(400, "Format tanggal harus YYYY-MM-DD")
    return d


def validasi_transaksi(d: dict, role: str, hari: date) -> dict:
    jenis = d.get("jenis")
    if jenis not in ("masuk", "keluar"):
        raise supa.ValidasiError(400, "Jenis harus 'masuk' atau 'keluar'")

    nominal = angka_positif(d.get("nominal"))
    if nominal is None:
        raise supa.ValidasiError(400, "Nominal harus bilangan bulat lebih dari 0")

    kid = d.get("kategori_id")
    if isinstance(kid, bool) or not (isinstance(kid, int) or (isinstance(kid, str) and kid.isdigit())):
        raise supa.ValidasiError(400, "Kategori wajib dipilih")
    kid = int(kid)

    tanggal = parse_tanggal(d.get("tanggal"), hari)
    if tanggal > hari:
        raise supa.ValidasiError(400, "Tanggal tidak boleh di masa depan")

    metode = d.get("metode") or None
    sumber = d.get("sumber_kas")
    if jenis == "masuk":
        if metode not in METODE:
            raise supa.ValidasiError(400, "Metode pembayaran wajib: tunai atau qris")
        tujuan = SUMBER_MASUK[metode]
        if sumber not in (None, "", tujuan):
            raise supa.ValidasiError(400, "Pemasukan tunai masuk ke Kas di Tangan, QRIS ke Kas di Bank")
        sumber = tujuan
    else:
        if sumber not in KAS:
            raise supa.ValidasiError(400, "Sumber kas wajib: tangan, bank, atau kecil")
        if metode is not None and metode not in METODE:
            raise supa.ValidasiError(400, "Metode harus tunai atau qris")

    ket = d.get("keterangan")
    if ket is not None:
        if not isinstance(ket, str):
            raise supa.ValidasiError(400, "Keterangan harus berupa teks")
        ket = ket.strip() or None
        if ket and len(ket) > 200:
            raise supa.ValidasiError(400, "Keterangan maksimal 200 karakter")

    # aturan hak akses (RLS di database tetap jadi lapisan kedua)
    if role == "karyawan" and not (jenis == "keluar" and sumber == "kecil"):
        raise supa.ValidasiError(403, "Karyawan hanya boleh mencatat pengeluaran Kas Kecil")

    return {
        "tanggal": tanggal.isoformat(), "jenis": jenis, "kategori_id": kid,
        "nominal": nominal, "metode": metode, "sumber_kas": sumber, "keterangan": ket,
    }


# ---------- endpoint ----------
@bp.get("/dashboard")
@login_required
def dashboard():
    c, role = supa.user_client(), session["role"]
    hari = supa.hari_ini().isoformat()

    saldo = {r["kas"]: r["saldo"] for r in c.table("saldo_kas").select("kas,saldo").execute().data}
    if role == "karyawan":
        saldo.pop("tangan", None)
        saldo.pop("bank", None)

    # untuk Karyawan, RLS otomatis membatasi ke transaksi miliknya sendiri
    hari_ini_rows = (
        c.table("transaksi").select("jenis,nominal").eq("tanggal", hari).eq("status", "aktif")
        .in_("jenis", ["masuk", "keluar"]).execute().data
    )
    masuk = sum(r["nominal"] for r in hari_ini_rows if r["jenis"] == "masuk")
    keluar = sum(r["nominal"] for r in hari_ini_rows if r["jenis"] == "keluar")

    terakhir = (
        c.table("transaksi").select(KOLOM).eq("status", "aktif")
        .order("tanggal", desc=True).order("created_at", desc=True).limit(5).execute().data
    )
    batas = int(os.environ.get("KAS_KECIL_MINIMUM", "100000"))
    return jsonify(
        saldo=saldo,
        kas_kecil_menipis=saldo.get("kecil") is not None and saldo["kecil"] < batas,
        hari_ini={"tanggal": hari, "masuk": masuk, "keluar": keluar, "selisih": masuk - keluar},
        transaksi_terakhir=terakhir,
    )


@bp.get("/kategori")
@login_required
def daftar_kategori():
    q = supa.user_client().table("kategori").select("id,nama,jenis").eq("aktif", True)
    if request.args.get("jenis") in ("masuk", "keluar"):
        q = q.eq("jenis", request.args["jenis"])
    return jsonify(q.order("jenis").order("nama").execute().data)


@bp.get("/transaksi")
@login_required
def daftar_transaksi():
    a = request.args
    q = supa.user_client().table("transaksi").select(KOLOM, count="exact")
    if a.get("dari"):
        q = q.gte("tanggal", parse_tanggal(a["dari"], None).isoformat())
    if a.get("sampai"):
        q = q.lte("tanggal", parse_tanggal(a["sampai"], None).isoformat())
    if a.get("jenis") in JENIS:
        q = q.eq("jenis", a["jenis"])
    if a.get("sumber_kas") in KAS:
        q = q.eq("sumber_kas", a["sumber_kas"])
    q = q.eq("status", "aktif")   # baris lama berstatus batal (sisa fitur pembatalan) tidak ditampilkan
    if a.get("kategori_id", "").isdigit():
        q = q.eq("kategori_id", int(a["kategori_id"]))

    halaman = max(int(a.get("page", 1)) if a.get("page", "1").isdigit() else 1, 1)
    per = min(int(a.get("per_page", 20)) if a.get("per_page", "20").isdigit() else 20, 100)
    mulai = (halaman - 1) * per
    res = q.order("tanggal", desc=True).order("created_at", desc=True).range(mulai, mulai + per - 1).execute()
    return jsonify(data=res.data, total=res.count, page=halaman, per_page=per)


@bp.post("/transaksi")
@login_required
def tambah_transaksi():
    payload = validasi_transaksi(request.get_json(silent=True) or {}, session["role"], supa.hari_ini())
    payload["dibuat_oleh"] = session["user_id"]
    res = supa.user_client().table("transaksi").insert(payload).execute()
    return jsonify(res.data[0]), 201


@bp.get("/kas-kecil")
@login_required
def kas_kecil():
    c = supa.user_client()
    saldo = {r["kas"]: r["saldo"] for r in c.table("saldo_kas").select("kas,saldo").execute().data}
    pengeluaran = (
        c.table("transaksi").select(KOLOM).eq("jenis", "keluar").eq("sumber_kas", "kecil")
        .order("tanggal", desc=True).order("created_at", desc=True).limit(50).execute().data
    )
    isi_ulang = (  # Karyawan tidak akan melihat ini: RLS hanya memberi transaksi miliknya
        c.table("transaksi").select(KOLOM).eq("jenis", "transfer")
        .order("tanggal", desc=True).order("created_at", desc=True).limit(50).execute().data
    )
    riwayat = sorted(pengeluaran + isi_ulang, key=lambda r: (r["tanggal"], r["created_at"]), reverse=True)[:50]
    batas = int(os.environ.get("KAS_KECIL_MINIMUM", "100000"))
    s = saldo.get("kecil")
    return jsonify(saldo=s, menipis=s is not None and s < batas, riwayat=riwayat)


@bp.post("/kas-kecil/isi-ulang")
@role_required("pemilik")
def isi_ulang():
    d = request.get_json(silent=True) or {}
    nominal = angka_positif(d.get("nominal"))
    if nominal is None:
        raise supa.ValidasiError(400, "Nominal harus bilangan bulat lebih dari 0")
    sumber = d.get("sumber_kas")
    if sumber not in ("tangan", "bank"):
        raise supa.ValidasiError(400, "Pilih sumber isi ulang: Kas di Tangan atau Kas di Bank")
    ket = d.get("keterangan")
    ket = ket.strip()[:200] if isinstance(ket, str) and ket.strip() else "Isi ulang kas kecil"
    res = supa.user_client().table("transaksi").insert({
        "tanggal": supa.hari_ini().isoformat(), "jenis": "transfer", "nominal": nominal,
        "sumber_kas": sumber, "tujuan_kas": "kecil", "keterangan": ket,
        "dibuat_oleh": session["user_id"],
    }).execute()
    return jsonify(res.data[0]), 201
