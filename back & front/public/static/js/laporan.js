const $ = (id) => document.getElementById(id);

function el(tag, teks, kelas) {
  const e = document.createElement(tag);
  if (teks != null) e.textContent = teks;
  if (kelas) e.className = kelas;
  return e;
}

function bangunQuery() {
  const periode = $("pilih-periode").value;
  const q = new URLSearchParams({ periode });

  if (periode === "custom") {
    const dari = $("tgl-dari").value;
    const sampai = $("tgl-sampai").value;
    if (dari) q.set("dari", dari);
    if (sampai) q.set("sampai", sampai);
  } else {
    const tgl = $("tgl-acuan").value;
    if (tgl) q.set("tanggal", tgl);
  }
  return q;
}

function aturInputPeriode() {
  const isCustom = $("pilih-periode").value === "custom";
  $("kotak-tanggal-acuan").hidden = isCustom;
  $("kotak-tanggal-custom-dari").hidden = !isCustom;
  $("kotak-tanggal-custom-sampai").hidden = !isCustom;
}

async function muatLaporan() {
  const pesan = $("pesan-laporan");
  tampilPesan(pesan, "");

  const q = bangunQuery();
  const btn = $("btn-filter-laporan");
  btn.disabled = true;
  btn.textContent = "Memuat…";

  try {
    const d = await api("/api/laporan?" + q.toString());

    // 1. Label Periode
    const periodeTeks = `${d.periode.label || "Periode"} (${tglFormat(d.periode.dari)} s/d ${tglFormat(d.periode.sampai)})`;
    $("periode-label").textContent = periodeTeks;

    // 2. Laba Rugi
    const lr = d.laba_rugi;
    $("lr-masuk").textContent = "+" + rupiah(lr.total_masuk);
    $("lr-keluar").textContent = "−" + rupiah(lr.total_keluar);

    const elLaba = $("lr-laba");
    if (lr.laba > 0) {
      elLaba.textContent = "+" + rupiah(lr.laba);
      elLaba.className = "angka-metrik plus";
    } else if (lr.laba < 0) {
      elLaba.textContent = "−" + rupiah(Math.abs(lr.laba));
      elLaba.className = "angka-metrik minus";
    } else {
      elLaba.textContent = rupiah(0);
      elLaba.className = "angka-metrik netral";
    }

    // 3. Rekap Kategori Pemasukan
    const tbMasuk = $("isi-rekap-masuk");
    tbMasuk.replaceChildren();
    const rowsMasuk = d.rekap?.masuk || [];
    rowsMasuk.forEach((r) => {
      const tr = el("tr");
      tr.append(el("td", r.kategori || "Lain-lain"), el("td", rupiah(r.total), "kanan plus"));
      tbMasuk.append(tr);
    });
    $("kosong-rekap-masuk").hidden = rowsMasuk.length > 0;

    // Rekap Kategori Pengeluaran
    const tbKeluar = $("isi-rekap-keluar");
    tbKeluar.replaceChildren();
    const rowsKeluar = d.rekap?.keluar || [];
    rowsKeluar.forEach((r) => {
      const tr = el("tr");
      tr.append(el("td", r.kategori || "Lain-lain"), el("td", rupiah(r.total), "kanan minus"));
      tbKeluar.append(tr);
    });
    $("kosong-rekap-keluar").hidden = rowsKeluar.length > 0;

    // 4. Buku Kas Terinci
    $("buku-saldo-awal").textContent = rupiah(d.saldo_awal);
    $("buku-saldo-akhir").textContent = rupiah(d.saldo_akhir);

    const tbBuku = $("isi-buku-kas");
    tbBuku.replaceChildren();
    const buku = d.buku_kas || [];
    buku.forEach((b) => {
      const tr = el("tr");
      tr.append(el("td", tglFormat(b.tanggal)));
      tr.append(el("td", b.keterangan || "-"));
      tr.append(el("td", b.kategori || "-"));
      tr.append(el("td", b.kas));
      tr.append(el("td", b.metode ? b.metode.toUpperCase() : "-"));
      tr.append(el("td", b.masuk > 0 ? rupiah(b.masuk) : "—", "kanan" + (b.masuk > 0 ? "" : " redup")));
      tr.append(el("td", b.keluar > 0 ? rupiah(b.keluar) : "—", "kanan" + (b.keluar > 0 ? "" : " redup")));
      tr.append(el("td", rupiah(b.saldo), "kanan"));
      tbBuku.append(tr);
    });
    $("kosong-buku").hidden = buku.length > 0;

  } catch (err) {
    tampilPesan(pesan, err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Tampilkan";
  }
}

// Handler ganti periode
$("pilih-periode").addEventListener("change", () => {
  aturInputPeriode();
  muatLaporan();
});

// Handler submit filter
$("form-laporan").addEventListener("submit", (e) => {
  e.preventDefault();
  muatLaporan();
});

// Handler download Excel
$("btn-export").addEventListener("click", () => {
  const q = bangunQuery();
  location.href = "/api/laporan/export?" + q.toString();
});

document.addEventListener("DOMContentLoaded", () => {
  const skrg = hariIni();
  $("tgl-acuan").value = skrg;
  $("tgl-dari").value = skrg;
  $("tgl-sampai").value = skrg;
  aturInputPeriode();
  muatLaporan();
});
