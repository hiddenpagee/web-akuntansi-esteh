const ROLE = document.body.dataset.role;
const $ = (id) => document.getElementById(id);

function el(tag, teks, kelas) {
  const e = document.createElement(tag);
  if (teks != null) e.textContent = teks;
  if (kelas) e.className = kelas;
  return e;
}

function namaKas(t) {
  if (t.jenis === "transfer") return labelKas(t.sumber_kas) + " → Kas Kecil";
  return labelKas(t.sumber_kas);
}


// ---------- transaksi QRIS otomatis: toast saat ada yang baru ----------
let idDikenal = null;
function cekTransaksiBaru(rows) {
  const ids = new Set(rows.map((t) => t.id));
  if (idDikenal) {
    rows.filter((t) => !idDikenal.has(t.id) && t.sumber && t.sumber !== "manual")
      .forEach((t) => toast(`QRIS masuk: ${rupiah(t.nominal)}`));
  }
  idDikenal = ids;
}

async function muatDashboard(senyap = false) {
  try {
    const d = await api("/api/dashboard");

    // Saldo Kas (Karyawan hanya melihat Kas Kecil)
    const punyaUtama = d.saldo.tangan !== undefined;
    for (const id of ["kotak-tangan", "kotak-bank", "kotak-total"]) {
      if ($(id)) $(id).hidden = !punyaUtama;
    }
    if (punyaUtama) {
      $("saldo-tangan").textContent = rupiah(d.saldo.tangan);
      $("saldo-bank").textContent = rupiah(d.saldo.bank);
      $("saldo-total").textContent = rupiah(d.saldo.tangan + d.saldo.bank + (d.saldo.kecil || 0));
    }

    $("saldo-kecil").textContent = d.saldo.kecil !== undefined ? rupiah(d.saldo.kecil) : "-";
    const warnKecil = $("peringatan-kecil");
    if (warnKecil) warnKecil.hidden = !d.kas_kecil_menipis;

    // Ringkasan Hari Ini
    if (d.hari_ini) {
      if ($("tgl-hari-ini")) $("tgl-hari-ini").textContent = tglFormat(d.hari_ini.tanggal);
      $("hari-masuk").textContent = "+" + rupiah(d.hari_ini.masuk);
      $("hari-keluar").textContent = "−" + rupiah(d.hari_ini.keluar);

      const elSelisih = $("hari-selisih");
      const selisih = d.hari_ini.selisih;
      if (selisih > 0) {
        elSelisih.textContent = "+" + rupiah(selisih);
        elSelisih.className = "angka-metrik plus";
      } else if (selisih < 0) {
        elSelisih.textContent = "−" + rupiah(Math.abs(selisih));
        elSelisih.className = "angka-metrik minus";
      } else {
        elSelisih.textContent = rupiah(0);
        elSelisih.className = "angka-metrik netral";
      }
    }

    // 5 Transaksi Terakhir
    const tb = $("isi-terakhir");
    tb.replaceChildren();
    const rows = d.transaksi_terakhir || [];
    cekTransaksiBaru(rows);
    rows.forEach((t) => {
      const tr = el("tr", null, t.status === "batal" ? "batal" : "");
      tr.append(el("td", tglFormat(t.tanggal)));

      const k = el("td", t.jenis === "transfer" ? "Isi ulang kas kecil" : (t.kategori?.nama || "-"));
      if (t.metode) k.append(el("span", t.metode.toUpperCase(), "tag"));
      if (t.sumber && t.sumber !== "manual") k.append(el("span", "Otomatis", "tag tag-oto"));
      if (t.keterangan) {
        k.append(el("br"));
        k.append(el("small", t.keterangan));
      }
      tr.append(k, el("td", namaKas(t)));

      const tanda = t.jenis === "masuk" ? "+" : t.jenis === "keluar" ? "−" : "";
      const warna = t.jenis === "masuk" ? "plus" : t.jenis === "keluar" ? "minus" : "netral";
      tr.append(el("td", tanda + rupiah(t.nominal), "kanan " + warna));

      tb.append(tr);
    });

    $("kosong-terakhir").hidden = rows.length > 0;
  } catch (err) {
    if (!senyap) toast(err.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  muatDashboard();
  setInterval(() => { if (!document.hidden) muatDashboard(true); }, 5000);   // QRIS masuk muncul sendiri
});
