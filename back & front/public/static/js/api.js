// Pembantu bersama untuk semua halaman.
const NAMA_KAS = { tangan: "Kas di Tangan", bank: "Kas di Bank", kecil: "Kas Kecil" };
const labelKas = (k) => NAMA_KAS[k] || k;
const rupiah = (n) => "Rp" + Number(n).toLocaleString("id-ID");

// "Hari ini" menurut jam Indonesia (sama dengan aturan server), format YYYY-MM-DD
const hariIni = () => new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Jakarta" });

const tglFormat = (s) => {
  if (!s) return "-";
  const [y, m, d] = s.split("-");
  return `${d}/${m}/${y}`;
};

async function api(path, { method = "GET", body, noRedirect = false } = {}) {
  const opt = { method, credentials: "same-origin", headers: {} };
  if (method !== "GET") {                       // backend mewajibkan JSON untuk semua POST
    opt.headers["Content-Type"] = "application/json";
    opt.body = JSON.stringify(body ?? {});
  }
  let res;
  try {
    res = await fetch(path, opt);
  } catch {
    throw new Error("Tidak bisa terhubung ke server. Cek koneksi internet.");
  }
  let data = null;
  try { data = await res.json(); } catch { /* bukan JSON */ }
  if (res.status === 401 && !noRedirect) {      // sesi habis -> balik ke login
    location.href = "/login";
    throw new Error("Sesi habis, silakan login lagi");
  }
  if (!res.ok) throw new Error((data && data.error) || "Terjadi kesalahan");
  return data;
}

function tampilPesan(el, teks, ok = false) {
  if (!el) return;
  el.textContent = teks;
  el.classList.toggle("ok", ok);
  el.hidden = !teks;
}

function toast(teks) {
  const t = document.getElementById("toast");
  if (!t) return;
  t.textContent = teks;
  t.hidden = false;
  clearTimeout(toast.id);
  toast.id = setTimeout(() => (t.hidden = true), 2500);
}

// Pasang handler tombol logout secara global
document.addEventListener("DOMContentLoaded", () => {
  const btnLogout = document.getElementById("btn-logout");
  if (btnLogout) {
    btnLogout.addEventListener("click", async () => {
      try { await api("/api/logout", { method: "POST", noRedirect: true }); } catch {}
      location.href = "/login";
    });
  }
});

// Responsif: isi data-label tiap sel dari judul kolom (dipakai tampilan kartu di HP)
function pasangLabelTabel(tabel) {
  const judul = [...tabel.querySelectorAll("thead th")].map((th) => th.textContent.trim());
  tabel.querySelectorAll("tbody tr").forEach((tr) => {
    [...tr.children].forEach((td, i) => {
      if (td.colSpan === 1 && judul[i] && !td.dataset.label) td.dataset.label = judul[i];
    });
  });
}
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("table").forEach((tabel) => {
    const tb = tabel.querySelector("tbody");
    if (!tb) return;
    new MutationObserver(() => pasangLabelTabel(tabel)).observe(tb, { childList: true });
    pasangLabelTabel(tabel);
  });
  const aktif = document.querySelector(".nav-menu [aria-current]");
  if (aktif) aktif.scrollIntoView({ inline: "center", block: "nearest" });
});
