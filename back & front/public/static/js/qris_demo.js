const $ = (id) => document.getElementById(id);

// ---------- tab: Simulator HP / QRIS Toko Asli / Panduan ----------
const PANEL = { simulator: "panel-simulator", real: "panel-real", panduan: "panel-panduan" };
function pilihTab(mode) {
  for (const [k, id] of Object.entries(PANEL)) $(id).hidden = k !== mode;
}
document.querySelectorAll('input[name="mode-qris"]').forEach((r) =>
  r.addEventListener("change", () => pilihTab(r.value)));
pilihTab(document.querySelector('input[name="mode-qris"]:checked').value);

// ---------- nominal: ketik angka, titik ribuan muncul otomatis ----------
function formatRibuan(input) {
  const awal = input.selectionStart ?? input.value.length;
  const digitSebelumKursor = input.value.slice(0, awal).replace(/\D/g, "").length;
  const angka = input.value.replace(/\D/g, "").replace(/^0+(?=\d)/, "").slice(0, 8);
  const teks = angka.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  input.value = teks;
  let pos = 0, hitung = 0;                       // kursor tetap di tempat yang sama walau titik bertambah
  while (pos < teks.length && hitung < digitSebelumKursor) {
    if (/\d/.test(teks[pos])) hitung++;
    pos++;
  }
  input.setSelectionRange(pos, pos);
}
const angkaDari = (input) => Number(input.value.replace(/\./g, ""));
["nominal-bayar", "real-nominal-bayar"].forEach((id) =>
  $(id).addEventListener("input", (e) => formatRibuan(e.target)));

// pilihan cepat nominal
document.querySelectorAll("#chips-nominal .chip").forEach((c) =>
  c.addEventListener("click", () => {
    $("nominal-bayar").value = Number(c.dataset.nominal).toLocaleString("id-ID");
    $("nominal-bayar").focus();
  }));

// ---------- QR asli: isinya alamat halaman ini, jadi bisa discan kamera HP ----------
function gambarQR(wadah, teks) {
  if (typeof QRCode === "undefined") { wadah.textContent = "QR gagal dimuat, pakai tautan di bawah."; return; }
  new QRCode(wadah, { text: teks, width: 190, height: 190, correctLevel: QRCode.CorrectLevel.M });
  // library membuat <img data:...> yang diblokir CSP; pakai canvas yang sudah tergambar
  const kanvas = wadah.querySelector("canvas"), img = wadah.querySelector("img");
  if (kanvas) kanvas.style.display = "block";
  if (img) img.style.display = "none";
}
gambarQR($("qr-toko"), $("tautan-hp").href);

// ---------- struk & riwayat sesi ----------
const riwayat = [];
function tampilStruk(r) {
  $("struk").hidden = false;
  $("struk-nominal").textContent = rupiah(r.nominal);
  const waktu = new Date(r.waktu).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "medium", timeZone: "Asia/Jakarta" });
  $("struk-waktu").textContent = waktu;
  $("struk-ref").textContent = r.ref;
  $("struk-status").textContent = r.status === "duplikat" ? "Sudah tercatat sebelumnya" : "Tercatat";
  riwayat.unshift(`${waktu} · ${rupiah(r.nominal)} · ${r.pembayar}`);
  $("riwayat-demo").replaceChildren(...riwayat.slice(0, 5).map((t) => { const li = document.createElement("li"); li.textContent = t; return li; }));
  $("kotak-riwayat-demo").hidden = false;
}

// ---------- Simulator HP: bayar ----------
$("form-bayar").addEventListener("submit", async (e) => {
  e.preventDefault();
  const pesan = $("pesan-bayar");
  tampilPesan(pesan, "");
  const nominal = angkaDari($("nominal-bayar"));
  if (!nominal) return tampilPesan(pesan, "Isi nominal pembayaran dulu");
  const btn = $("btn-bayar");
  btn.disabled = true; btn.textContent = "Memproses…";
  try {
    const r = await api("/api/qris-demo/bayar", { method: "POST", body: { nominal, pembayar: $("nama-pembeli").value.trim() } });
    tampilStruk(r);
    $("nominal-bayar").value = "";
    $("nominal-bayar").focus();
  } catch (err) {
    tampilPesan(pesan, err.message);
  } finally {
    btn.disabled = false; btn.textContent = "Bayar Sekarang";
  }
});

// ---------- QRIS Toko Asli: pratinjau foto (hanya di browser, tidak diunggah) ----------
let urlFoto = null;
$("input-foto-qris").addEventListener("change", (e) => {
  const f = e.target.files[0];
  if (urlFoto) URL.revokeObjectURL(urlFoto);
  if (!f || !f.type.startsWith("image/")) { $("kotak-foto-qris").hidden = true; return; }
  urlFoto = URL.createObjectURL(f);
  $("img-qris-toko").src = urlFoto;
  $("kotak-foto-qris").hidden = false;
});

// ---------- QRIS Toko Asli: catat manual ke Kas di Bank (wajib login) ----------
$("form-real-qris").addEventListener("submit", async (e) => {
  e.preventDefault();
  const pesan = $("pesan-real-bayar");
  tampilPesan(pesan, "");
  const nominal = angkaDari($("real-nominal-bayar"));
  if (!nominal) return tampilPesan(pesan, "Isi nominal yang diterima dulu");
  const btn = $("btn-real-bayar");
  btn.disabled = true; btn.textContent = "Mencatat…";
  try {
    const kat = await api("/api/kategori", { noRedirect: true });
    const masuk = kat.filter((k) => k.jenis === "masuk");
    const pilih = masuk.find((k) => /qris/i.test(k.nama)) || masuk[0];
    if (!pilih) throw new Error("Kategori pemasukan tidak ditemukan");
    const nama = $("real-nama-pembeli").value.trim();
    await api("/api/transaksi", {
      method: "POST", noRedirect: true,
      body: { jenis: "masuk", nominal, kategori_id: pilih.id, metode: "qris",
              keterangan: nama ? `QRIS toko dari ${nama}` : "QRIS toko (dicatat manual)" },
    });
    tampilPesan(pesan, `Tercatat ${rupiah(nominal)} ke Kas di Bank ✓`, true);
    $("real-nominal-bayar").value = "";
    $("real-nama-pembeli").value = "";
  } catch (err) {
    const perluLogin = /login|sesi|autentik|401/i.test(err.message);
    tampilPesan(pesan, perluLogin ? "Fitur ini perlu login. Masuk dulu di halaman utama (Pemilik/Kasir), lalu coba lagi." : err.message);
  } finally {
    btn.disabled = false; btn.textContent = "Catat QRIS Masuk ke Kas Bank";
  }
});
