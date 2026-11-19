// Satu skrip untuk dua halaman: Jurnal Umum dan Jurnal Petty Cash (dibedakan dari elemen yang ada).
const $ = (id) => document.getElementById(id);
const adaUmum = !!$("isi-jurnal-umum");

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
    if ($("tgl-dari").value) q.set("dari", $("tgl-dari").value);
    if ($("tgl-sampai").value) q.set("sampai", $("tgl-sampai").value);
  } else if ($("tgl-acuan").value) {
    q.set("tanggal", $("tgl-acuan").value);
  }
  return q;
}

function aturInputPeriode() {
  const custom = $("pilih-periode").value === "custom";
  $("kotak-tanggal-acuan").hidden = custom;
  $("kotak-tanggal-custom-dari").hidden = !custom;
  $("kotak-tanggal-custom-sampai").hidden = !custom;
}

const angka = (n) => (n > 0 ? rupiah(n) : "—");
const selAngka = (n) => el("td", angka(n), "kanan" + (n > 0 ? "" : " redup"));

function tampilUmum(d) {
  const pembuka = d.pembuka || [];
  $("kotak-pembuka").hidden = pembuka.length === 0;
  const tp = $("isi-pembuka");
  tp.replaceChildren();
  pembuka.forEach((b) => {
    const tr = el("tr");
    tr.append(el("td", `${b.kode}  ${b.akun}`, b.kredit > 0 ? "akun-kredit" : ""), selAngka(b.debit), selAngka(b.kredit));
    tp.append(tr);
  });

  const tb = $("isi-jurnal-umum");
  tb.replaceChildren();
  d.jurnal.forEach((j) => {
    j.baris.forEach((b, i) => {
      const tr = el("tr");
      tr.append(el("td", i === 0 ? tglFormat(j.tanggal) : ""), el("td", i === 0 ? j.no : ""));
      tr.append(el("td", `${b.kode}  ${b.akun}`, b.kredit > 0 ? "akun-kredit" : ""), selAngka(b.debit), selAngka(b.kredit));
      tb.append(tr);
    });
    const ket = el("tr");
    const sel = el("td", `(${j.keterangan})`, "ket-jurnal");
    sel.colSpan = 5;
    ket.append(sel);
    tb.append(ket);
  });
  if (d.jurnal.length) {
    const tot = el("tr", null, "baris-total");
    const label = el("td", "Total periode ini");
    label.colSpan = 3;
    tot.append(label, el("td", rupiah(d.total.debit), "kanan"), el("td", rupiah(d.total.kredit), "kanan"));
    tb.append(tot);
  }
  $("kosong-jurnal").hidden = d.jurnal.length > 0;
  const st = $("status-seimbang");
  st.textContent = d.jurnal.length ? (d.seimbang ? "Seimbang (debit = kredit)" : "TIDAK seimbang, periksa data") : "";
  st.className = "status-seimbang " + (d.seimbang ? "ok" : "tidak");
}

function tampilPetty(d) {
  $("pc-awal").textContent = rupiah(d.saldo_awal);
  $("pc-isi").textContent = rupiah(d.total_isi_ulang);
  $("pc-keluar").textContent = rupiah(d.total_pengeluaran);
  $("pc-akhir").textContent = rupiah(d.saldo_akhir);
  const tb = $("isi-petty");
  tb.replaceChildren();
  d.baris.forEach((b) => {
    const tr = el("tr");
    tr.append(el("td", tglFormat(b.tanggal)), el("td", b.no), el("td", b.keterangan), el("td", b.akun_lawan),
      selAngka(b.debit), selAngka(b.kredit), el("td", rupiah(b.saldo), "kanan"));
    tb.append(tr);
  });
  $("kosong-petty").hidden = d.baris.length > 0;
}

async function muat() {
  const pesan = $("pesan-jurnal");
  tampilPesan(pesan, "");
  const btn = $("btn-filter-jurnal");
  btn.disabled = true;
  btn.textContent = "Memuat…";
  try {
    const d = await api((adaUmum ? "/api/jurnal-umum?" : "/api/jurnal-petty-cash?") + bangunQuery().toString());
    $("periode-label").textContent = `${d.periode.label} (${tglFormat(d.periode.dari)} s/d ${tglFormat(d.periode.sampai)})`;
    if (adaUmum) tampilUmum(d); else tampilPetty(d);
  } catch (err) {
    tampilPesan(pesan, err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Tampilkan";
  }
}

$("pilih-periode").addEventListener("change", () => { aturInputPeriode(); muat(); });
$("form-jurnal").addEventListener("submit", (e) => { e.preventDefault(); muat(); });

document.addEventListener("DOMContentLoaded", () => {
  const skrg = hariIni();
  $("tgl-acuan").value = $("tgl-dari").value = $("tgl-sampai").value = skrg;
  aturInputPeriode();
  muat();
});
