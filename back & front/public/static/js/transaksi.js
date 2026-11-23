const ROLE = document.body.dataset.role;           // pemilik | kasir | karyawan
const $ = (id) => document.getElementById(id);
const PER_HALAMAN = 20;
let semuaKategori = [], halaman = 1, total = 0;

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


// ---------- helper kecil ----------
function el(tag, teks, kelas) {
  const e = document.createElement(tag);
  if (teks != null) e.textContent = teks;   // textContent: aman dari XSS
  if (kelas) e.className = kelas;
  return e;
}
function toast(teks) {
  const t = $("toast");
  t.textContent = teks; t.hidden = false;
  clearTimeout(toast.id);
  toast.id = setTimeout(() => (t.hidden = true), 2500);
}
const jenisDipilih = () => document.querySelector('input[name="jenis"]:checked').value;

// ---------- saldo ----------
async function muatSaldo() {
  const d = await api("/api/dashboard");
  const punya = d.saldo.tangan !== undefined;   // Karyawan tidak boleh lihat Kas di Tangan dan Kas di Bank
  $("kotak-tangan").hidden = !punya;
  $("kotak-bank").hidden = !punya;
  if (punya) {
    $("saldo-tangan").textContent = rupiah(d.saldo.tangan);
    $("saldo-bank").textContent = rupiah(d.saldo.bank);
  }
  $("saldo-kecil").textContent = d.saldo.kecil === undefined ? "-" : rupiah(d.saldo.kecil);
  $("peringatan-kecil").hidden = !d.kas_kecil_menipis;
}

// ---------- tanggal: otomatis hari ini, boleh diubah ----------
const tglManual = () => !$("tanggal").hidden;
function aturTanggal(manual) {
  $("tanggal").hidden = !manual;
  $("tgl-otomatis").hidden = manual;
  $("ubah-tgl").textContent = manual ? "Pakai hari ini" : "Ubah";
  $("tgl-teks").textContent = "Hari ini · " + tglFormat(hariIni());
  if (manual) $("tanggal").value = hariIni();
}
$("ubah-tgl").addEventListener("click", () => aturTanggal(!tglManual()));

// ---------- form ----------
function isiKategori() {
  const j = jenisDipilih();
  const sel = $("kategori");
  sel.replaceChildren(new Option("— pilih kategori —", ""));
  semuaKategori.filter((k) => k.jenis === j).forEach((k) => sel.add(new Option(k.nama, k.id)));
}

function aturForm() {
  const masuk = jenisDipilih() === "masuk";
  isiKategori();
  $("kotak-sumber").hidden = masuk || ROLE === "karyawan";   // pemasukan ditentukan metode bayar; karyawan selalu Kas Kecil
  $("info-kas-masuk").hidden = !masuk;
  $("metode").options[0].textContent = masuk ? "— pilih metode —" : "— tidak ditentukan —";
}

$("nominal").addEventListener("input", (e) => {           // tampil 35.000, kirim 35000
  const angka = e.target.value.replace(/\D/g, "").replace(/^0+/, "");
  e.target.value = angka ? Number(angka).toLocaleString("id-ID") : "";
});
document.querySelectorAll('input[name="jenis"]').forEach((r) => r.addEventListener("change", aturForm));

$("form-transaksi").addEventListener("submit", async (e) => {
  e.preventDefault();
  const pesan = $("pesan-form");
  tampilPesan(pesan, "");
  const jenis = jenisDipilih();
  const nominal = parseInt($("nominal").value.replace(/\D/g, ""), 10);

  // validasi cepat di browser (aturan resminya tetap di server + database)
  if (!$("kategori").value) return tampilPesan(pesan, "Kategori wajib dipilih");
  if (!nominal) return tampilPesan(pesan, "Nominal harus lebih dari 0");
  if (tglManual() && !$("tanggal").value) return tampilPesan(pesan, "Tanggal wajib diisi");
  if (jenis === "masuk" && !$("metode").value) return tampilPesan(pesan, "Pilih metode bayar: tunai atau QRIS");

  const body = {
    jenis, nominal,
    kategori_id: Number($("kategori").value),
    metode: $("metode").value || null,
    keterangan: $("keterangan").value.trim() || null,
  };
  if (tglManual()) body.tanggal = $("tanggal").value;   // kosong = server pakai hari pencatatan (WIB)
  if (jenis === "keluar") body.sumber_kas = ROLE === "karyawan" ? "kecil" : $("sumber").value;

  const btn = $("btn-simpan");
  btn.disabled = true; btn.textContent = "Menyimpan…";
  try {
    await api("/api/transaksi", { method: "POST", body });
    toast("Transaksi tersimpan ✓");
    $("nominal").value = ""; $("keterangan").value = ""; $("kategori").value = "";
    aturTanggal(false);
    $("nominal").focus();
    halaman = 1;
    await Promise.all([muatSaldo(), muatRiwayat()]);
  } catch (err) {
    tampilPesan(pesan, err.message);        // mis. "Saldo kas kecil tidak cukup (sisa Rp85000)"
  } finally {
    btn.disabled = false; btn.textContent = "Simpan transaksi";
  }
});

// ---------- riwayat ----------
function namaKas(t) {
  if (t.jenis === "transfer") return labelKas(t.sumber_kas) + " → Kas Kecil";
  return labelKas(t.sumber_kas);
}

async function muatRiwayat() {
  const q = new URLSearchParams({ page: halaman, per_page: PER_HALAMAN });
  [["jenis", "f-jenis"], ["dari", "f-dari"], ["sampai", "f-sampai"]]
    .forEach(([k, id]) => $(id).value && q.set(k, $(id).value));
  const res = await api("/api/transaksi?" + q);
  total = res.total ?? res.data.length;
  cekTransaksiBaru(res.data);

  const tb = $("isi-tabel");
  tb.replaceChildren();
  res.data.forEach((t) => {
    const tr = el("tr", null, t.status === "batal" ? "batal" : "");
    tr.append(el("td", tglFormat(t.tanggal)));

    const k = el("td", t.jenis === "transfer" ? "Isi ulang kas kecil" : (t.kategori?.nama || "-"));
    if (t.metode) k.append(el("span", t.metode.toUpperCase(), "tag"));
    if (t.sumber && t.sumber !== "manual") k.append(el("span", "Otomatis", "tag tag-oto"));
    if (t.keterangan) { k.append(el("br")); k.append(el("small", t.keterangan)); }
    tr.append(k, el("td", namaKas(t)));

    const tanda = t.jenis === "masuk" ? "+" : t.jenis === "keluar" ? "−" : "";
    const warna = t.jenis === "masuk" ? "plus" : t.jenis === "keluar" ? "minus" : "netral";
    tr.append(el("td", tanda + rupiah(t.nominal), "kanan " + warna));

    if (ROLE === "pemilik") {
      const tdAksi = el("td", null, "kanan aksi-kolom");
      const btnEdit = el("button", "Edit", "sekunder btn-sm");
      btnEdit.type = "button";
      btnEdit.onclick = () => bukaModalEdit(t);

      const btnHapus = el("button", "Hapus", "bahaya btn-sm");
      btnHapus.type = "button";
      btnHapus.onclick = () => bukaModalHapus(t);

      tdAksi.append(btnEdit, btnHapus);
      tr.append(tdAksi);
    }

    tb.append(tr);
  });

  $("kosong").hidden = res.data.length > 0;
  const maks = Math.max(Math.ceil(total / PER_HALAMAN), 1);
  $("info-halaman").textContent = `Hal ${halaman} dari ${maks} · ${total} transaksi`;
  $("prev").disabled = halaman <= 1;
  $("next").disabled = halaman >= maks;
}

$("prev").addEventListener("click", () => { halaman--; muatRiwayat(); });
$("next").addEventListener("click", () => { halaman++; muatRiwayat(); });
$("filter").addEventListener("change", () => { halaman = 1; muatRiwayat().catch((e) => toast(e.message)); });

// ---------- modal edit & hapus (khusus pemilik) ----------
let idTransaksiHapus = null;

function isiKategoriEdit(jenis, terpilihId) {
  const sel = $("edit-kategori");
  if (!sel) return;
  sel.replaceChildren(new Option("— pilih kategori —", ""));
  semuaKategori.filter((k) => k.jenis === jenis).forEach((k) => {
    const opt = new Option(k.nama, k.id);
    if (k.id === terpilihId) opt.selected = true;
    sel.add(opt);
  });
}

function aturFormEdit() {
  const jenis = $("edit-jenis").value;
  const masuk = jenis === "masuk";
  const transfer = jenis === "transfer";

  $("edit-kotak-kategori").hidden = transfer;
  $("edit-kotak-sumber").hidden = masuk;
  $("edit-kotak-metode").hidden = !masuk;
  $("edit-info-kas-masuk").hidden = !masuk;

  if (!transfer) {
    isiKategoriEdit(jenis, Number($("edit-kategori").value));
  }

  const sumberSel = $("edit-sumber");
  const optKecil = sumberSel.querySelector('option[value="kecil"]');
  if (optKecil) optKecil.hidden = transfer;
  if (transfer && sumberSel.value === "kecil") sumberSel.value = "tangan";
}

function bukaModalEdit(t) {
  const modal = $("modal-edit");
  if (!modal) return;
  tampilPesan($("pesan-modal-edit"), "");
  $("edit-id").value = t.id;
  $("edit-tanggal").value = t.tanggal;
  $("edit-jenis").value = t.jenis;
  $("edit-nominal").value = Number(t.nominal).toLocaleString("id-ID");
  aturFormEdit();
  if (t.kategori_id) isiKategoriEdit(t.jenis, t.kategori_id);
  if (t.sumber_kas) $("edit-sumber").value = t.sumber_kas;
  if (t.metode) $("edit-metode").value = t.metode;
  $("edit-keterangan").value = t.keterangan || "";
  modal.showModal();
}

function bukaModalHapus(t) {
  const modal = $("modal-hapus");
  if (!modal) return;
  idTransaksiHapus = t.id;
  const namaKat = t.jenis === "transfer" ? "Isi ulang kas kecil" : (t.kategori?.nama || "-");
  $("hapus-info").textContent = `${tglFormat(t.tanggal)} · ${namaKat} · ${rupiah(t.nominal)}`;
  modal.showModal();
}

if (ROLE === "pemilik") {
  const modalEdit = $("modal-edit");
  const modalHapus = $("modal-hapus");

  $("edit-jenis")?.addEventListener("change", aturFormEdit);

  $("edit-nominal")?.addEventListener("input", (e) => {
    const angka = e.target.value.replace(/\D/g, "").replace(/^0+/, "");
    e.target.value = angka ? Number(angka).toLocaleString("id-ID") : "";
  });

  $("btn-batal-edit")?.addEventListener("click", () => modalEdit.close());
  $("btn-batal-hapus")?.addEventListener("click", () => modalHapus.close());

  $("form-edit")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const pesan = $("pesan-modal-edit");
    tampilPesan(pesan, "");

    const id = $("edit-id").value;
    const jenis = $("edit-jenis").value;
    const nominal = parseInt($("edit-nominal").value.replace(/\D/g, ""), 10);
    const tanggal = $("edit-tanggal").value;
    const kid = $("edit-kategori").value;
    const sumber = $("edit-sumber").value;
    const metode = $("edit-metode").value;
    const ket = $("edit-keterangan").value.trim();

    if (!nominal) return tampilPesan(pesan, "Nominal harus lebih dari 0");
    if (!tanggal) return tampilPesan(pesan, "Tanggal wajib diisi");
    if (jenis !== "transfer" && !kid) return tampilPesan(pesan, "Kategori wajib dipilih");
    if (jenis === "masuk" && !metode) return tampilPesan(pesan, "Metode pembayaran wajib dipilih");

    const body = {
      tanggal, jenis, nominal,
      keterangan: ket || null,
    };
    if (jenis !== "transfer") {
      body.kategori_id = Number(kid);
      body.metode = metode || null;
      if (jenis === "keluar") body.sumber_kas = sumber;
    } else {
      body.sumber_kas = sumber;
    }

    const btn = $("btn-simpan-edit");
    btn.disabled = true; btn.textContent = "Menyimpan…";
    try {
      await api(`/api/transaksi/${id}`, { method: "PUT", body });
      modalEdit.close();
      toast("Transaksi berhasil diubah ✓");
      await Promise.all([muatSaldo(), muatRiwayat()]);
    } catch (err) {
      tampilPesan(pesan, err.message);
    } finally {
      btn.disabled = false; btn.textContent = "Simpan Perubahan";
    }
  });

  $("btn-konfirmasi-hapus")?.addEventListener("click", async () => {
    if (!idTransaksiHapus) return;
    const btn = $("btn-konfirmasi-hapus");
    btn.disabled = true; btn.textContent = "Menghapus…";
    try {
      await api(`/api/transaksi/${idTransaksiHapus}`, { method: "DELETE" });
      modalHapus.close();
      toast("Transaksi berhasil dihapus ✓");
      await Promise.all([muatSaldo(), muatRiwayat()]);
    } catch (err) {
      alert(err.message);
    } finally {
      btn.disabled = false; btn.textContent = "Ya, Hapus";
      idTransaksiHapus = null;
    }
  });
}

// ---------- mulai ----------
(async function init() {
  $("tanggal").max = hariIni();
  aturTanggal(false);
  if (ROLE === "karyawan") {                       // Karyawan: hanya pengeluaran Kas Kecil
    $("opsi-masuk").hidden = true;
    $("f-jenis").querySelector('[value="masuk"]').hidden = true;
  }
  try {
    semuaKategori = await api("/api/kategori");
    aturForm();
    await Promise.all([muatSaldo(), muatRiwayat()]);
  } catch (err) {
    tampilPesan($("pesan-form"), err.message);
  }
})();

// ---------- auto-refresh: transaksi QRIS otomatis muncul sendiri (tiap 5 detik, hanya di halaman 1) ----------
setInterval(async () => {
  if (document.hidden || halaman !== 1) return;
  try { await muatSaldo(); await muatRiwayat(); } catch { /* percobaan berikutnya 5 detik lagi */ }
}, 5000);
