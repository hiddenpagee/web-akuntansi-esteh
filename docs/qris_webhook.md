# QRIS otomatis: webhook dan simulator

## Cara kerja singkat
1. Pembeli bayar lewat QRIS. Payment gateway menerima dananya.
2. Gateway mengirim `POST` JSON ke `https://DOMAIN-ANDA/api/qris/webhook` dengan dua header: `X-Timestamp` (detik epoch) dan `X-Signature`.
3. Server memeriksa **umur pesan** (maks 5 menit), **tanda tangan** (HMAC-SHA256), isi pesan, lalu **duplikat** (`ref_eksternal` unik), kemudian mencatat pemasukan QRIS ke **Kas di Bank** lewat akun sistem "QRIS Otomatis" (role kasir, tetap kena RLS dan trigger saldo).
4. Halaman Beranda dan Transaksi memuat ulang data tiap 5 detik, jadi transaksi baru muncul sendiri dengan label "Otomatis".

## Format pesan (versi aplikasi ini)
```json
{"ref": "QR-20261119-0001", "status": "paid", "nominal": 25000,
 "pembayar": "Budi", "waktu": "2026-11-19T10:15:00+07:00", "sumber": "demo"}
```
`status` selain `paid` diabaikan. `nominal` harus bilangan bulat positif. `sumber` adalah `demo` (simulator) atau `gateway`.

## Tanda tangan
`X-Signature = HMAC_SHA256(QRIS_WEBHOOK_SECRET, X-Timestamp + "." + isi_mentah_pesan)` dalam heksadesimal.
```python
import hashlib, hmac, json, time, requests
badan = json.dumps({"ref": "QR-TEST-0001", "status": "paid", "nominal": 25000, "sumber": "demo"}, separators=(",", ":")).encode()
ts = str(int(time.time()))
ttd = hmac.new(RAHASIA.encode(), ts.encode() + b"." + badan, hashlib.sha256).hexdigest()
requests.post(URL, data=badan, headers={"Content-Type": "application/json", "X-Timestamp": ts, "X-Signature": ttd})
```
Pesan harus ditandatangani dari **byte yang persis sama** dengan yang dikirim.

## Memasang gateway sungguhan nanti
Gateway seperti Midtrans atau Xendit punya format dan cara tanda tangan sendiri (bukan format di atas). Cukup tambah satu adapter kecil yang memverifikasi tanda tangan resmi mereka lalu memanggil `catat_pembayaran()` dengan `sumber = "gateway"`. Cek dokumentasi resmi mereka untuk format, biaya, dan syarat daftar yang berlaku saat itu. Hal yang baru terbukti setelah itu: status pending/kedaluwarsa, penyelesaian dana (settlement), dan biaya transaksi (MDR) yang sebaiknya dicatat sebagai beban.

## Pengaturan
| Variabel `.env` | Fungsi |
|---|---|
| `QRIS_WEBHOOK_SECRET` | Kunci tanda tangan. Panjang minimal 16 karakter. Jangan dibagikan. |
| `QRIS_SYSTEM_EMAIL`, `QRIS_SYSTEM_PASSWORD` | Akun sistem penulis transaksi otomatis (dibuat `db/buat_akun_sistem_qris.py`). |
| `QRIS_SIMULATOR` | `1` = halaman `/qris-demo` dan pintu demo aktif. **Wajib `0` atau dihapus saat go-live.** |

## Sebelum go-live
- Set `QRIS_SIMULATOR=0` (atau hapus barisnya).
- Bersihkan transaksi demo: lihat perintah di bagian bawah `db/05_qris_otomatis.sql` (semua ditandai `sumber = 'qris_demo'`).
- Putar ulang `QRIS_WEBHOOK_SECRET` kalau pernah terbagi.
