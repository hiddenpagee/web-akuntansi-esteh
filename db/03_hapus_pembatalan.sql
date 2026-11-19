-- =====================================================================
-- 03: Hapus fitur pembatalan. Transaksi jadi PERMANEN (tidak bisa diubah/dihapus).
-- Jalankan sekali di Supabase: SQL Editor > New query > paste > Run
-- Aman dijalankan ulang.
-- =====================================================================

-- 1. Cabut izin update. Tanpa policy UPDATE, RLS menolak semua perubahan.
drop policy if exists transaksi_batal on public.transaksi;

-- 2. Lapis kedua: trigger menolak UPDATE dan DELETE siapa pun (termasuk service_role).
create or replace function public.jaga_update_transaksi()
returns trigger
language plpgsql
as $$
begin
  raise exception 'Transaksi bersifat permanen: tidak bisa diubah atau dihapus';
end;
$$;

drop trigger if exists transaksi_jaga_update on public.transaksi;
create trigger transaksi_jaga_update
  before update on public.transaksi
  for each row execute function public.jaga_update_transaksi();

drop trigger if exists transaksi_jaga_hapus on public.transaksi;
create trigger transaksi_jaga_hapus
  before delete on public.transaksi
  for each row execute function public.jaga_update_transaksi();

-- Catatan: kolom status/batal_* tetap ada supaya baris lama tidak rusak.
-- Baris berstatus 'batal' (kalau ada) tetap diabaikan di saldo dan laporan.
