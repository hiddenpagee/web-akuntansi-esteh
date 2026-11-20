const form = document.getElementById("form-login");
const pesan = document.getElementById("pesan");
const btn = document.getElementById("btn-masuk");
const pw = document.getElementById("password");

document.getElementById("lihat").addEventListener("click", (e) => {
  const tampil = pw.type === "password";
  pw.type = tampil ? "text" : "password";
  e.currentTarget.textContent = tampil ? "Sembunyi" : "Lihat";
  e.currentTarget.setAttribute("aria-pressed", String(tampil));
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  tampilPesan(pesan, "");
  const dipilih = document.querySelector('input[name="kategori"]:checked');
  if (!dipilih) return tampilPesan(pesan, "Pilih dulu masuk sebagai Pemilik, Kasir, atau Karyawan");
  const email = document.getElementById("email").value.trim();
  if (!email || !pw.value) return tampilPesan(pesan, "Email dan password wajib diisi");
  btn.disabled = true;
  btn.textContent = "Memeriksa…";
  try {
    await api("/api/login", { method: "POST", body: { email, password: pw.value, role: dipilih.value }, noRedirect: true });
    location.href = "/dashboard";
  } catch (err) {
    tampilPesan(pesan, err.message);
    pw.value = "";
    pw.focus();
    btn.disabled = false;
    btn.textContent = "Masuk";
  }
});
