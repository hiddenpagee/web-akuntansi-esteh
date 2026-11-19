const $ = (id) => document.getElementById(id);

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
$("nominal-bayar").addEventListener("input", (e) => formatRibuan(e.target));

// ---------- gambar QR contoh (hanya hiasan) ----------
function gambarQR(wadah) {
  const N = 25, ns = "http://www.w3.org/2000/svg";
  let seed = 20261119;
  const acak = () => {                           // pengacak berbenih supaya gambarnya selalu sama
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${N} ${N}`);
  svg.setAttribute("shape-rendering", "crispEdges");
  const kotak = (x, y) => {
    const r = document.createElementNS(ns, "rect");
    r.setAttribute("x", x); r.setAttribute("y", y);
    r.setAttribute("width", 1); r.setAttribute("height", 1);
    r.setAttribute("fill", "currentColor");
    svg.append(r);
  };
  const sudutPenanda = (x, y) => (x < 8 && y < 8) || (x >= N - 8 && y < 8) || (x < 8 && y >= N - 8);
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) if (!sudutPenanda(x, y) && acak() > 0.52) kotak(x, y);
  [[0, 0], [N - 7, 0], [0, N - 7]].forEach(([ox, oy]) => {
    for (let i = 0; i < 7; i++) for (let j = 0; j < 7; j++) {
      const cincin = i === 0 || i === 6 || j === 0 || j === 6;
      const inti = i >= 2 && i <= 4 && j >= 2 && j <= 4;
      if (cincin || inti) kotak(ox + j, oy + i);
    }
  });
  wadah.append(svg);
}
gambarQR($("qr-toko"));

// ---------- bayar ----------
const riwayat = [];
function tampilStruk(r) {
  $("struk").hidden = false;
  $("struk-nominal").textContent = rupiah(r.nominal);
  const waktu = new Date(r.waktu).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "medium", timeZone: "Asia/Jakarta" });
  $("struk-waktu").textContent = waktu;
  $("struk-ref").textContent = r.ref;
  $("struk-status").textContent = r.status === "duplikat" ? "Sudah tercatat sebelumnya" : "Tercatat";
  riwayat.unshift(`${waktu} · ${rupiah(r.nominal)} · ${r.pembayar}`);
  const ul = $("riwayat-demo");
  ul.replaceChildren(...riwayat.slice(0, 5).map((t) => { const li = document.createElement("li"); li.textContent = t; return li; }));
  $("kotak-riwayat-demo").hidden = false;
}

$("form-bayar").addEventListener("submit", async (e) => {
  e.preventDefault();
  const pesan = $("pesan-bayar");
  tampilPesan(pesan, "");
  const nominal = Number($("nominal-bayar").value.replace(/\./g, ""));
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
    btn.disabled = false; btn.textContent = "Bayar";
  }
});
