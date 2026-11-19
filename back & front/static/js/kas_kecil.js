const ROLE = document.body.dataset.role;
const $ = (id) => document.getElementById(id);

function el(tag, teks, kelas) {
  const e = document.createElement(tag);
  if (teks != null) e.textContent = teks;
  if (kelas) e.className = kelas;
  return e;
}

async function muatKasKecil() {
  try {
    const d = await api("/api/kas-kecil");

    // Tampilkan saldo
    $("saldo-kecil").textContent = d.saldo !== null && d.saldo !== undefined ? rupiah(d.saldo) : "-";

    // Status badge & banner
    const badge = $("badge-status");
    const banner = $("banner-menipis");
    if (d.menipis) {
      badge.textContent = "⚠️ Menipis";
      badge.className = "badge-status badge-merah";
      if (banner) banner.hidden = false;
    } else {
      badge.textContent = "✅ Aman";
      badge.className = "badge-status badge-hijau";
      if (banner) banner.hidden = true;
    }

    // Riwayat mutasi
    const tb = $("isi-mutasi-kecil");
    tb.replaceChildren();
    const rows = d.riwayat || [];
    rows.forEach((t) => {
      const tr = el("tr", null, t.status === "batal" ? "batal" : "");
      tr.append(el("td", tglFormat(t.tanggal)));

      const isTransfer = t.jenis === "transfer";
      const ket = el("td", isTransfer ? "Isi ulang kas kecil" : (t.kategori?.nama || "Pengeluaran"));
      if (t.keterangan && (!isTransfer || t.keterangan !== "Isi ulang kas kecil")) {
        ket.append(el("br"));
        ket.append(el("small", t.keterangan));
      }
      tr.append(ket);

      const tipeCell = el("td");
      const badgeTipe = el("span", isTransfer ? "Isi Ulang" : "Pengeluaran", isTransfer ? "tag tag-masuk" : "tag tag-keluar");
      tipeCell.append(badgeTipe);
      tr.append(tipeCell);

      const tanda = isTransfer ? "+" : "−";
      const warna = isTransfer ? "plus" : "minus";
      tr.append(el("td", tanda + rupiah(t.nominal), "kanan " + warna));

      tb.append(tr);
    });

    $("kosong-mutasi").hidden = rows.length > 0;
  } catch (err) {
    toast(err.message);
  }
}

// Handler form isi ulang (khusus Pemilik)
const formIsiUlang = $("form-isi-ulang");
if (formIsiUlang) {
  const nominalInput = $("nominal-isi-ulang");
  const pesan = $("pesan-isi-ulang");
  const btn = $("btn-isi-ulang");

  // Format ribuan otomatis saat mengetik
  nominalInput.addEventListener("input", (e) => {
    const angka = e.target.value.replace(/\D/g, "").replace(/^0+/, "");
    e.target.value = angka ? Number(angka).toLocaleString("id-ID") : "";
  });

  // Tombol pilihan cepat (chips)
  document.querySelectorAll(".chip").forEach((btnChip) => {
    btnChip.addEventListener("click", () => {
      const nominal = Number(btnChip.dataset.nominal || 0);
      nominalInput.value = nominal.toLocaleString("id-ID");
      nominalInput.focus();
    });
  });

  formIsiUlang.addEventListener("submit", async (e) => {
    e.preventDefault();
    tampilPesan(pesan, "");

    const nominal = parseInt(nominalInput.value.replace(/\D/g, ""), 10);
    if (!nominal || nominal <= 0) {
      return tampilPesan(pesan, "Nominal isi ulang harus lebih dari 0");
    }

    const keterangan = $("keterangan-isi-ulang").value.trim() || undefined;

    btn.disabled = true;
    btn.textContent = "Memproses transfer…";
    try {
      await api("/api/kas-kecil/isi-ulang", {
        method: "POST",
        body: { nominal, keterangan, sumber_kas: $("sumber-isi-ulang").value },
      });
      toast("Isi ulang kas kecil berhasil ✓");
      nominalInput.value = "";
      $("keterangan-isi-ulang").value = "";
      await muatKasKecil();
    } catch (err) {
      tampilPesan(pesan, err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Transfer ke Kas Kecil";
    }
  });
}

document.addEventListener("DOMContentLoaded", muatKasKecil);
