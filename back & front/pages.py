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


def _ambil_ip_lokal():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


@bp.get("/qris-demo")
def qris_demo():
    """Halaman simulator HP pembeli & testing QRIS."""
    import qris
    from flask import abort, request
    if not qris.simulator_aktif():
        abort(404)
    host = request.host
    port = host.split(":")[1] if ":" in host else ""
    ip_lokal = _ambil_ip_lokal()
    url_hp = f"http://{ip_lokal}:{port}/qris-demo" if port else f"http://{ip_lokal}/qris-demo"
    if not host.startswith(("localhost", "127.0.0.1")):
        url_hp = request.base_url
    return render_template("qris_demo.html", url_hp=url_hp, ip_lokal=ip_lokal)
