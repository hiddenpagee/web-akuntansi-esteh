"""Laporan (buku kas, rekap, laba rugi) + export Excel. Khusus Pemilik."""
import calendar
from datetime import date, timedelta
from io import BytesIO

from flask import Blueprint, jsonify, request, send_file

import supa
from auth import role_required

bp = Blueprint("laporan", __name__, url_prefix="/api/laporan")

NAMA_KAS = {"tangan": "Kas di Tangan", "bank": "Kas di Bank", "kecil": "Kas Kecil"}


def tentukan_periode(args, hari: date):
    """Kembalikan (dari, sampai, label) dari parameter ?periode=&tanggal=&dari=&sampai=."""
    from transaksi import parse_tanggal

    periode = args.get("periode", "harian")
    if periode == "custom":
        if not args.get("dari") or not args.get("sampai"):
            raise supa.ValidasiError(400, "Periode custom butuh parameter dari dan sampai")
        dari, sampai = parse_tanggal(args["dari"], None), parse_tanggal(args["sampai"], None)
        if dari > sampai:
            raise supa.ValidasiError(400, "Tanggal 'dari' tidak boleh setelah 'sampai'")
        if (sampai - dari).days > 366:
            raise supa.ValidasiError(400, "Rentang maksimal 366 hari")
        return dari, sampai, "Custom"

    acuan = parse_tanggal(args.get("tanggal"), hari)
    if periode == "harian":
        return acuan, acuan, "Harian"
    if periode == "mingguan":  # Senin sampai Minggu
        senin = acuan - timedelta(days=acuan.weekday())
        return senin, senin + timedelta(days=6), "Mingguan"
    if periode == "bulanan":
        akhir = calendar.monthrange(acuan.year, acuan.month)[1]
        return acuan.replace(day=1), acuan.replace(day=akhir), "Bulanan"
    raise supa.ValidasiError(400, "Periode harus harian, mingguan, bulanan, atau custom")


def hitung_laporan(c, dari: date, sampai: date) -> dict:
    d0, d1 = dari.isoformat(), sampai.isoformat()

    saldo_awal_kas = sum(
        r["saldo_awal"] for r in c.table("pengaturan_kas").select("saldo_awal").execute().data
    )
    # transfer antar kas tidak mengubah total kas, jadi cukup hitung masuk & keluar
    sebelum = supa.fetch_all(
        lambda: c.table("transaksi").select("jenis,nominal").eq("status", "aktif")
        .in_("jenis", ["masuk", "keluar"]).lt("tanggal", d0).order("tanggal")
    )
    saldo = saldo_awal_kas + sum(
        r["nominal"] if r["jenis"] == "masuk" else -r["nominal"] for r in sebelum
    )
    saldo_awal = saldo

    rows = supa.fetch_all(
        lambda: c.table("transaksi")
        .select("tanggal,jenis,nominal,metode,sumber_kas,tujuan_kas,keterangan,created_at,kategori(nama)")
        .eq("status", "aktif").gte("tanggal", d0).lte("tanggal", d1)
        .order("tanggal").order("created_at")
    )

    buku, rekap = [], {"masuk": {}, "keluar": {}}
    total = {"masuk": 0, "keluar": 0}
    for r in rows:
        kategori = (r.get("kategori") or {}).get("nama")
        masuk = r["nominal"] if r["jenis"] == "masuk" else 0
        keluar = r["nominal"] if r["jenis"] == "keluar" else 0
        saldo += masuk - keluar
        if r["jenis"] in rekap:
            rekap[r["jenis"]][kategori] = rekap[r["jenis"]].get(kategori, 0) + r["nominal"]
            total[r["jenis"]] += r["nominal"]
        kas = (f'{NAMA_KAS.get(r.get("sumber_kas"), "")} → {NAMA_KAS.get(r.get("tujuan_kas"), "")}' if r["jenis"] == "transfer"
               else NAMA_KAS.get(r.get("sumber_kas"), r.get("sumber_kas")))
        buku.append({
            "tanggal": r["tanggal"], "keterangan": r.get("keterangan") or kategori or "Isi ulang kas kecil",
            "kategori": kategori or "Transfer", "kas": kas, "metode": r.get("metode"),
            "masuk": masuk, "keluar": keluar, "saldo": saldo,
        })

    return {
        "periode": {"dari": d0, "sampai": d1},
        "saldo_awal": saldo_awal,
        "buku_kas": buku,
        "saldo_akhir": saldo,
        "rekap": {
            j: [{"kategori": k, "total": t} for k, t in sorted(v.items(), key=lambda x: -x[1])]
            for j, v in rekap.items()
        },
        "laba_rugi": {
            "total_masuk": total["masuk"], "total_keluar": total["keluar"],
            "laba": total["masuk"] - total["keluar"],  # transfer tidak dihitung
        },
    }


@bp.get("")
@role_required("pemilik")
def laporan():
    dari, sampai, label = tentukan_periode(request.args, supa.hari_ini())
    hasil = hitung_laporan(supa.user_client(), dari, sampai)
    hasil["periode"]["label"] = label
    return jsonify(hasil)


def buat_excel(h: dict) -> BytesIO:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    rp = '#,##0'
    tebal = Font(bold=True)
    kepala = PatternFill("solid", fgColor="DCE9E1")
    wb = Workbook()

    ws = wb.active
    ws.title = "Buku Kas"
    ws["A1"] = f"Buku Kas {h['periode']['dari']} s/d {h['periode']['sampai']}"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = "Saldo awal (Kas di Tangan + Kas di Bank + Kas Kecil)"
    ws["F2"] = h["saldo_awal"]
    for i, t in enumerate(["Tanggal", "Keterangan", "Kategori", "Kas", "Metode", "Debit", "Kredit", "Saldo"], 1):
        c = ws.cell(row=4, column=i, value=t)
        c.font, c.fill = tebal, kepala
    for n, r in enumerate(h["buku_kas"], 5):
        ws.append([r["tanggal"], r["keterangan"], r["kategori"], r["kas"], r["metode"] or "",
                   r["masuk"], r["keluar"], r["saldo"]])
    ws.cell(row=ws.max_row + 2, column=1, value="Saldo akhir").font = tebal
    ws.cell(row=ws.max_row, column=8, value=h["saldo_akhir"]).font = tebal
    for baris in ws.iter_rows(min_row=2):
        for sel in baris[5:8]:
            sel.number_format = rp
    for kolom, lebar in zip("ABCDEFGH", (12, 34, 34, 14, 10, 14, 14, 14)):
        ws.column_dimensions[kolom].width = lebar

    ws2 = wb.create_sheet("Rekap")
    for i, t in enumerate(["Jenis", "Kategori", "Total"], 1):
        c = ws2.cell(row=1, column=i, value=t)
        c.font, c.fill = tebal, kepala
    for jenis, nama in (("masuk", "Pemasukan"), ("keluar", "Pengeluaran")):
        for r in h["rekap"][jenis]:
            ws2.append([nama, r["kategori"], r["total"]])
    for baris in ws2.iter_rows(min_row=2, min_col=3, max_col=3):
        baris[0].number_format = rp
    for kolom, lebar in zip("ABC", (14, 38, 16)):
        ws2.column_dimensions[kolom].width = lebar

    ws3 = wb.create_sheet("Laba Rugi")
    lr = h["laba_rugi"]
    ws3.append(["Laba Rugi Sederhana", f"{h['periode']['dari']} s/d {h['periode']['sampai']}"])
    ws3["A1"].font = Font(bold=True, size=13)
    ws3.append(["Total pemasukan", lr["total_masuk"]])
    ws3.append(["Total pengeluaran", lr["total_keluar"]])
    ws3.append(["Laba", lr["laba"]])
    ws3["A4"].font = ws3["B4"].font = tebal
    ws3.append(["Catatan: isi ulang kas kecil tidak dihitung sebagai pengeluaran."])
    for baris in ws3.iter_rows(min_row=2, max_row=4, min_col=2, max_col=2):
        baris[0].number_format = rp
        baris[0].alignment = Alignment(horizontal="right")
    ws3.column_dimensions["A"].width = 26
    ws3.column_dimensions["B"].width = 24

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out


@bp.get("/export")
@role_required("pemilik")
def export_excel():
    dari, sampai, _ = tentukan_periode(request.args, supa.hari_ini())
    hasil = hitung_laporan(supa.user_client(), dari, sampai)
    return send_file(
        buat_excel(hasil), as_attachment=True,
        download_name=f"laporan-kas_{dari}_{sampai}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
