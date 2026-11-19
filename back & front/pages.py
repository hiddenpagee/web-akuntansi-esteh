"""Halaman HTML (frontend). Datanya diambil lewat fetch ke /api/* dari browser."""
from flask import Blueprint, redirect, render_template, session, url_for

bp = Blueprint("pages", __name__)


@bp.get("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("pages.login"))
    return redirect(url_for("pages.dashboard"))


@bp.get("/login")
def login():
    if "user_id" in session:
        return redirect(url_for("pages.dashboard"))
    return render_template("login.html")


@bp.get("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("pages.login"))
    return render_template("dashboard.html", nama=session["nama"], role=session["role"], page="dashboard")


@bp.get("/transaksi")
def transaksi():
    if "user_id" not in session:
        return redirect(url_for("pages.login"))
    return render_template("transaksi.html", nama=session["nama"], role=session["role"], page="transaksi")


@bp.get("/kas-kecil")
def kas_kecil():
    if "user_id" not in session:
        return redirect(url_for("pages.login"))
    return render_template("kas_kecil.html", nama=session["nama"], role=session["role"], page="kas_kecil")


@bp.get("/laporan")
def laporan():
    if "user_id" not in session:
        return redirect(url_for("pages.login"))
    if session.get("role") != "pemilik":
        return redirect(url_for("pages.dashboard"))
    return render_template("laporan.html", nama=session["nama"], role=session["role"], page="laporan")


@bp.get("/jurnal-umum")
def jurnal_umum():
    if "user_id" not in session:
        return redirect(url_for("pages.login"))
    if session.get("role") != "pemilik":
        return redirect(url_for("pages.dashboard"))
    return render_template("jurnal_umum.html", nama=session["nama"], role=session["role"], page="jurnal_umum")


@bp.get("/jurnal-petty-cash")
def jurnal_petty_cash():
    if "user_id" not in session:
        return redirect(url_for("pages.login"))
    if session.get("role") not in ("pemilik", "kasir"):
        return redirect(url_for("pages.dashboard"))
    return render_template("jurnal_petty_cash.html", nama=session["nama"], role=session["role"], page="jurnal_petty_cash")


@bp.get("/qris-demo")
def qris_demo():
    """Halaman simulator HP pembeli. Publik, tapi hanya ada kalau QRIS_SIMULATOR=1."""
    import os
    from flask import abort
    if os.environ.get("QRIS_SIMULATOR") != "1":
        abort(404)
    return render_template("qris_demo.html")
