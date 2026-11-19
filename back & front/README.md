# Web App Akuntansi Kas & Kas Kecil (Flask + Supabase)

Aplikasi pencatatan kas masuk, kas keluar, dan kas kecil untuk usaha/kedai (studi kasus: Franchise Es Teh).
API JSON dengan login berbasis session cookie. Semua query berjalan **atas nama user yang login**
(token Supabase milik user), sehingga Row Level Security (RLS) di database PostgreSQL Supabase terpakai penuh.
`service_role` key tidak pernah dipakai di backend untuk menjamin keamanan multi-peran (*least privilege*).

---

## 5 Halaman Aplikasi (Frontend)

Disajikan dari origin yang sama oleh Flask. Setelah menjalankan server, buka `http://localhost:5000`.

| URL | Halaman | Hak Akses | Keterangan & Fitur Utama |
|---|---|---|---|
| `/login` | **Login** | Publik | Pilih kategori akun (Pemilik/Kasir/Karyawan), lalu email & password via Supabase Auth. Login gagal bila email bukan kategori yang dipilih. |
| `/dashboard` | **Beranda** | Semua role | Saldo Kas Utama & Kas Kecil, total saldo, peringatan kas kecil menipis (< Rp100.000), ringkasan arus kas hari ini (masuk, keluar, selisih), tombol aksi cepat, dan 5 transaksi terakhir. *(Karyawan: saldo Kas Utama disembunyikan)*. |
| `/transaksi` | **Transaksi** | Semua role | Formulir catat pemasukan (Tunai/QRIS) & pengeluaran, filter riwayat, pagination, dan transaksi bersifat permanen (tidak ada edit/hapus/batal). *(Karyawan: hanya pengeluaran Kas Kecil)*. |
| `/kas-kecil` | **Kas Kecil** | Semua role | Saldo kas kecil real-time, status menipis/aman, form isi ulang/transfer dari Kas Utama dengan quick chips *(khusus Pemilik)*, SOP panduan pengeluaran boleh vs tidak boleh, dan riwayat mutasi kas kecil. |
| `/laporan` | **Laporan Keuangan** | Pemilik | Filter periode (Harian, Mingguan Senin–Minggu, Bulanan, Custom tanggal), Laba Rugi Sederhana, Rekap Pemasukan & Pengeluaran per Kategori, Tabel Buku Kas Terinci (Kas Utama + Kas Kecil), dan **Unduh Excel (.xlsx)**. |

---

## Peran Pengguna (Role & Hak Akses)

1. **Pemilik (`pemilik`)**:
   - Melihat seluruh saldo (Kas Utama, Kas Kecil, Total).
   - Mencatat semua jenis transaksi (Pemasukan ke Kas Utama, Pengeluaran dari Kas Utama/Kas Kecil).
   - Mengisi ulang saldo Kas Kecil (transfer dari Kas Utama).
   - Mengakses Laporan Keuangan lengkap & mengunduh rekap Excel (.xlsx).
2. **Kasir (`kasir`)**:
   - Melihat saldo Kas Utama dan Kas Kecil di Beranda.
   - Mencatat transaksi Pemasukan (Tunai/QRIS) dan Pengeluaran.
   - Melihat riwayat transaksi dan mutasi kas kecil.
   - Tidak dapat mengisi ulang kas kecil atau membuka laporan laba rugi.
3. **Karyawan (`karyawan`)**:
   - Hanya melihat saldo Kas Kecil (saldo Kas Utama disembunyikan).
   - Hanya diizinkan mencatat Pengeluaran dari Kas Kecil sesuai SOP operasional toko.
   - Tidak dapat mencatat pemasukan, tidak dapat transfer, tidak dapat membuka laporan.

---

## SOP Penggunaan Kas Kecil (Sesuai Ketentuan Usaha Es Teh)

- **Boleh menggunakan Kas Kecil:**
  - Perlengkapan jualan: Sedotan, cup, plastik kresek, tisu.
  - Bahan tambahan: Es batu, gula pasir, teh tambahan dadakan.
  - Kebersihan: Sabun cuci piring, spons, lap meja.
  - Transportasi: Ongkos mengambil bahan baku / belanja lokal.
  - Perawatan alat: Perbaikan kecil dispenser atau termos air.
  - Konsumsi: Air minum untuk karyawan bertugas.
  - Biaya tak terduga: Pembelian perlengkapan darurat toko.
- **Wajib menggunakan Kas Utama (Dilarang lewat Kas Kecil):**
  - Pembelian mesin cup sealer atau peralatan besar.
  - Pembelian bahan baku partai besar / stok mingguan-bulanan.
  - Pembayaran gaji karyawan.
  - Pembayaran sewa lapak / stand.
  - Pembelian aset tetap inventaris usaha.

---

## Endpoint API Backend

| Method | Path | Akses | Keterangan |
|---|---|---|---|
| POST | `/api/login` | Publik | Autentikasi `{email, password, role}`. `role` = kategori yang dipilih di halaman login (`pemilik`/`kasir`/`karyawan`); ditolak jika akun bukan kategori itu, walau password benar. |
| POST | `/api/logout` | Login | Cabut token di Supabase & hapus session cookie. |
| GET | `/api/me` | Login | Info profil login `{nama, role}`. |
| GET | `/api/dashboard` | Login | Saldo kas, status menipis, ringkasan hari ini, 5 transaksi terakhir. |
| GET | `/api/kategori?jenis=masuk\|keluar` | Login | Daftar opsi kategori aktif untuk dropdown formulir. |
| GET | `/api/transaksi` | Login | Filter `dari, sampai, jenis, kategori_id, sumber_kas, status, page, per_page`. |
| POST | `/api/transaksi` | Login | Tambah transaksi baru (divalidasi backend + RLS). |
| GET | `/api/kas-kecil` | Login | Saldo kas kecil, status batas minimum, 50 mutasi terakhir. |
| POST | `/api/kas-kecil/isi-ulang` | Pemilik | Transfer saldo Kas Utama ke Kas Kecil `{nominal, keterangan?}`. |
| GET | `/api/laporan` | Pemilik | Laporan buku kas, rekap kategori, & laba rugi. |
| GET | `/api/laporan/export` | Pemilik | Download file Excel `.xlsx` (3 Sheet: Buku Kas, Rekap, Laba Rugi). |

---

## Setup & Menjalankan Lokal

```bash
# 1. Masuk ke folder back & front
cd "back & front"

# 2. Aktifkan virtual environment Python
..\venv\Scripts\activate

# 3. Jalankan automated tests (39 tests)
python -m pytest

# 4. Jalankan aplikasi web
flask --app app run --debug
```

Akses aplikasi di browser pada: `http://localhost:5000`

### Akun Uji Coba Default:
- **Pemilik**: `pemilik@esteh.test` / `Demo12345!`
- **Kasir**: `kasir@esteh.test` / `Demo12345!`
- **Karyawan**: `karyawan@esteh.test` / `Demo12345!`


## Kas, akun, dan jurnal (revisi 17 Nov 2026)

- **Tiga kas:** Kas di Tangan (cash on hand), Kas di Bank (cash in bank), dan Kas Kecil (petty cash). Pemasukan tunai masuk ke Kas di Tangan, pemasukan QRIS ke Kas di Bank. Pengeluaran memilih salah satu dari ketiganya. Isi ulang Kas Kecil memilih sumber Kas di Tangan atau Kas di Bank.
- **Saldo awal** tiap kas ada di tabel `pengaturan_kas` (diisi sekali di awal lewat SQL, lihat komentar di `db/04_pisah_kas_jurnal.sql`).
- **Debit/Kredit:** Buku Kas di Laporan memakai kolom Debit (kas bertambah) dan Kredit (kas berkurang).
- **Jurnal Umum** (`/jurnal-umum`, pemilik) dan **Jurnal Petty Cash** (`/jurnal-petty-cash`, pemilik dan kasir) tersusun otomatis dari transaksi, jadi selalu cocok dengan pencatatan. Akun lawan tiap kategori ada di kolom `kategori.akun_kode` (bagan akun di `jurnal.py`).
- Database yang sudah berjalan: jalankan `db/03_hapus_pembatalan.sql`, lalu `db/04_pisah_kas_jurnal.sql`.


## QRIS otomatis (revisi 19 Nov 2026)

- `POST /api/qris/webhook` menerima notifikasi pembayaran bertanda tangan (HMAC), mencegah dobel, dan mencatat pemasukan QRIS ke Kas di Bank. Rinciannya di `docs/qris_webhook.md`.
- Simulator pembeli: `/qris-demo` (aktif hanya jika `QRIS_SIMULATOR=1`). Nominal diketik sendiri, titik ribuan muncul otomatis.
- Beranda dan Transaksi memuat ulang tiap 5 detik; transaksi otomatis berlabel "Otomatis".
- Persiapan: jalankan `db/05_qris_otomatis.sql`, lalu `db/buat_akun_sistem_qris.py`, tempel keluarannya ke `.env`.
