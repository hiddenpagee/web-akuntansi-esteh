"""Jurnal Umum dan Jurnal Petty Cash.

Keduanya DITURUNKAN dari tabel transaksi (tidak ada tabel jurnal yang bisa diketik), jadi selalu
cocok dengan pencatatan dan tidak bisa dipalsukan terpisah. Tiap transaksi menghasilkan satu entri
dengan total debit = total kredit.
"""
from flask import Blueprint, jsonify, request

import supa
from auth import role_required
from laporan import NAMA_KAS, tentukan_periode

bp = Blueprint("jurnal", __name__, url_prefix="/api")

AKUN = {
    "1-101": "Kas di Tangan", "1-102": "Kas di Bank", "1-103": "Kas Kecil",
    "3-101": "Modal Pemilik",
    "4-101": "Penjualan", "4-102": "Penjualan Online", "4-103": "Pendapatan Pesanan Event",
    "5-101": "Beban Bahan Baku", "5-102": "Beban Kemasan", "5-201": "Beban Gaji",
    "5-202": "Beban Listrik/Sewa", "5-203": "Beban Operasional Lain",
}
AKUN_KAS = {"tangan": "1-101", "bank": "1-102", "kecil": "1-103"}
AKUN_BAWAAN = {"masuk": "4-101", "keluar": "5-203"}   # dipakai kalau kategori belum punya akun_kode
KOLOM = "id,tanggal,jenis,nominal,sumber_kas,tujuan_kas,keterangan,created_at,kategori_id,kategori(nama)"


def peta_akun_kategori(c) -> dict:
    rows = c.table("kategori").select("id,akun_kode").execute().data
    return {r["id"]: r["akun_kode"] for r in rows if r.get("akun_kode")}


def akun_lawan(t: dict, peta: dict) -> str:
    return peta.get(t.get("kategori_id")) or AKUN_BAWAAN[t["jenis"]]


def entri(t: dict, peta: dict) -> list:
    """Satu transaksi -> [(kode_akun, debit, kredit), ...]."""
    n = t["nominal"]
    if t["jenis"] == "masuk":      # Debit kas, Kredit pendapatan
        return [(AKUN_KAS[t["sumber_kas"]], n, 0), (akun_lawan(t, peta), 0, n)]
    if t["jenis"] == "keluar":     # Debit beban, Kredit kas
        return [(akun_lawan(t, peta), n, 0), (AKUN_KAS[t["sumber_kas"]], 0, n)]
    return [(AKUN_KAS[t["tujuan_kas"]], n, 0), (AKUN_KAS[t["sumber_kas"]], 0, n)]   # isi ulang kas kecil


def _baris(k, debit, kredit):
    return {"kode": k, "akun": AKUN.get(k, k), "debit": debit, "kredit": kredit}


def _ambil(c, d1, **filter_eq):
    def q():
        x = c.table("transaksi").select(KOLOM).eq("status", "aktif").lte("tanggal", d1)
        for kolom, nilai in filter_eq.items():
            x = x.eq(kolom, nilai)
        return x.order("tanggal").order("created_at")
    return supa.fetch_all(q)


def _saldo_awal(c) -> dict:
    return {r["kas"]: r["saldo_awal"] for r in c.table("pengaturan_kas").select("kas,saldo_awal").execute().data}


@bp.get("/jurnal-umum")
@role_required("pemilik")
def jurnal_umum():
    dari, sampai, label = tentukan_periode(request.args, supa.hari_ini())
    d0, d1 = dari.isoformat(), sampai.isoformat()
    c = supa.user_client()
    peta = peta_akun_kategori(c)

    jurnal, total_d, total_k = [], 0, 0
    for no, t in enumerate(_ambil(c, d1), 1):          # nomor urut dihitung dari awal, jadi stabil
        if t["tanggal"] < d0:
            continue
        baris = [_baris(k, d, kr) for k, d, kr in entri(t, peta)]
        total_d += sum(b["debit"] for b in baris)
        total_k += sum(b["kredit"] for b in baris)
        nama_kat = (t.get("kategori") or {}).get("nama")
        jurnal.append({
            "no": f"JU-{no:04d}", "tanggal": t["tanggal"], "jenis": t["jenis"],
            "keterangan": t.get("keterangan") or nama_kat or "Isi ulang kas kecil", "baris": baris,
        })

    awal = _saldo_awal(c)
    pembuka = [_baris(AKUN_KAS[k], awal[k], 0) for k in ("tangan", "bank", "kecil") if awal.get(k)]
    if pembuka:
        pembuka.append(_baris("3-101", 0, sum(b["debit"] for b in pembuka)))

    return jsonify(
        periode={"dari": d0, "sampai": d1, "label": label},
        pembuka=pembuka, jurnal=jurnal,
        total={"debit": total_d, "kredit": total_k}, seimbang=total_d == total_k,
    )


@bp.get("/jurnal-petty-cash")
@role_required("pemilik", "kasir")
def jurnal_petty_cash():
    dari, sampai, label = tentukan_periode(request.args, supa.hari_ini())
    d0, d1 = dari.isoformat(), sampai.isoformat()
    c = supa.user_client()
    peta = peta_akun_kategori(c)

    semua = _ambil(c, d1, jenis="keluar", sumber_kas="kecil") + _ambil(c, d1, jenis="transfer")
    semua.sort(key=lambda r: (r["tanggal"], r["created_at"]))

    saldo = saldo_awal_periode = _saldo_awal(c).get("kecil", 0)
    baris, isi_ulang, pengeluaran = [], 0, 0
    for no, t in enumerate(semua, 1):
        masuk = t["nominal"] if t["jenis"] == "transfer" else 0
        keluar = t["nominal"] if t["jenis"] == "keluar" else 0
        saldo += masuk - keluar
        if t["tanggal"] < d0:
            saldo_awal_periode = saldo
            continue
        isi_ulang += masuk
        pengeluaran += keluar
        lawan = AKUN_KAS[t["sumber_kas"]] if t["jenis"] == "transfer" else akun_lawan(t, peta)
        nama_kat = (t.get("kategori") or {}).get("nama")
        baris.append({
            "no": f"PC-{no:04d}", "tanggal": t["tanggal"],
            "keterangan": t.get("keterangan") or nama_kat or "Isi ulang kas kecil",
            "akun_lawan": AKUN.get(lawan, lawan), "debit": masuk, "kredit": keluar, "saldo": saldo,
        })

    return jsonify(
        periode={"dari": d0, "sampai": d1, "label": label},
        saldo_awal=saldo_awal_periode, saldo_akhir=saldo,
        total_isi_ulang=isi_ulang, total_pengeluaran=pengeluaran, baris=baris,
    )
