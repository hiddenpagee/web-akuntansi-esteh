# Panduan CRUD & QRIS untuk Web Akuntansi

## Ringkasan Fitur
- **CRUD Transaksi (Pemilik saja)**: API endpoint `GET /api/transaksi/<id>`, `PUT /api/transaksi/<id>`, `DELETE /api/transaksi/<id>` dilindungi dengan decorator `@role_required("pemilik")`. UI menampilkan kolom **Aksi** dengan tombol **Edit** dan **Hapus** hanya bila `session["role"] == "pemilik"`.
- **QRIS Demo / Simulator**: Mode simulator diaktifkan dengan environment variable `QRIS_SIMULATOR=1`. Demo menyediakan QR code statis serta endpoint webhook yang menerima notifikasi dummy.

## Cara Menggunakan CRUD
1. **Login sebagai Pemilik**
   - Pastikan sesi login berhasil (`session["role"] == "pemilik"`).
2. **Buka halaman Transaksi** (`/transaksi`).
3. Pada tabel, kolom **Aksi** akan muncul apabila Anda pemilik.
   - **Edit**: Klik tombol ✏️, modal edit terbuka, ubah data, klik **Simpan** → melakukan `PUT /api/transaksi/<id>`.
   - **Hapus**: Klik tombol 🗑️, konfirmasi modal, akan mengirim `DELETE /api/transaksi/<id>`.
4. **Respons API**
   - **200 OK** – berhasil mengubah/hapus.
   - **403 Forbidden** – bila bukan pemilik atau trigger SQL belum diterapkan.
   - **415 Unsupported Media Type** – body bukan JSON (hanya berlaku untuk `POST/PUT/PATCH`/`DELETE` jika ada payload).

## Mengaktifkan Trigger di Supabase
File trigger berada di `db/06_crud_pemilik.sql`.
```sql
-- 06_crud_pemilik.sql
-- Pastikan Anda berada di Supabase SQL editor dengan hak akses admin.
\i db/06_crud_pemilik.sql;
```
Setelah dijalankan, pemilik dapat meng‑edit dan meng‑hapus transaksi secara langsung. Tanpa menjalankan file ini, API akan mengembalikan **403** dengan pesan:
```
Gagal mengubah transaksi. Pastikan file db/06_crud_pemilik.sql sudah dijalankan di Supabase SQL Editor.
```

## QRIS Demo
### Konfigurasi .env (sudah disertakan)
```dotenv
QRIS_WEBHOOK_SECRET=0123456789abcdef0123456789abcdef
QRIS_SYSTEM_EMAIL=kasir@esteh.test
QRIS_SYSTEM_PASSWORD=Demo12345!
QRIS_SIMULATOR=1   # 1 = aktif, 0 = non‑aktif
```
- **Simulator aktif**: `qris.simulator_aktif()` mengembalikan `True` sehingga template `qris_demo.html` menampilkan QR code dummy dan tombol "Cek Status Pembayaran".
- **Cara menguji**: Buka `/qris_demo` di browser, scan QR (gambar statis) atau klik tombol untuk memanggil webhook dummy. Pada console server akan muncul log webhook.

## Menjalankan Test Suite
```bash
# Pastikan dependencies terpasang
pip install -r requirements.txt

# Jalankan tes
pytest -q
```
Semua 72 tes harus lulus. Jika ada kegagalan pada edit/delete, pastikan langkah **Mengaktifkan Trigger** sudah dilakukan.

## Deploy / Release
1. Commit semua perubahan (`git add . && git commit -m "feat: CRUD pemilik + QRIS demo"`).
2. Tag rilis baru:
   ```bash
   git tag v1.2-crud-qris
   git push --tags
   ```
3. Deploy ke server produksi (misalnya dengan `gunicorn "app:create_app()"`). Pastikan file `.env` produksi berisi variabel QRIS yang sesuai (simulator biasanya dimatikan).

---
*Panduan ini dibuat otomatis oleh Antigravity. Jika ada yang kurang jelas, beri tahu saya untuk menambahkan detail.*
