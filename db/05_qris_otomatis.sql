-- =====================================================================
-- 05: QRIS otomatis. Kolom penanda sumber + nomor referensi unik (anti dobel).
-- Jalankan sekali di Supabase SQL Editor (setelah 04). Aman dijalankan ulang.
-- =====================================================================

alter table public.transaksi add column if not exists ref_eksternal text;
alter table public.transaksi add column if not exists sumber text not null default 'manual';

alter table public.transaksi drop constraint if exists transaksi_sumber_check;
alter table public.transaksi add constraint transaksi_sumber_check
  check (sumber in ('manual', 'qris_demo', 'qris_gateway'));

-- transaksi manual tidak punya referensi; transaksi otomatis WAJIB punya
alter table public.transaksi drop constraint if exists transaksi_ref_sesuai_sumber;
alter table public.transaksi add constraint transaksi_ref_sesuai_sumber
  check ((sumber = 'manual') = (ref_eksternal is null));

-- transaksi otomatis hanya boleh berupa pemasukan QRIS
alter table public.transaksi drop constraint if exists transaksi_otomatis_hanya_qris;
alter table public.transaksi add constraint transaksi_otomatis_hanya_qris
  check (sumber = 'manual' or (jenis = 'masuk' and metode = 'qris'));

-- satu nomor referensi = satu transaksi (notifikasi yang terkirim dua kali tidak tercatat dua kali)
create unique index if not exists transaksi_ref_eksternal_uniq
  on public.transaksi (ref_eksternal) where ref_eksternal is not null;

-- ---------------------------------------------------------------------
-- Membersihkan transaksi DEMO sebelum go-live (transaksi biasanya permanen, jadi trigger
-- anti-hapus dimatikan sebentar). Jalankan HANYA kalau memang mau membuang data demo:
--
-- alter table public.transaksi disable trigger transaksi_jaga_hapus;
-- delete from public.transaksi where sumber = 'qris_demo';
-- alter table public.transaksi enable trigger transaksi_jaga_hapus;
-- ---------------------------------------------------------------------
