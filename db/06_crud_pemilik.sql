-- =====================================================================
-- 06: Hak Akses CRUD (Update & Delete) Transaksi Khusus Pemilik
-- Jalankan di Supabase: SQL Editor > New query > paste > Run
-- =====================================================================

-- 1. Perbarui trigger agar Pemilik (role = 'pemilik') diizinkan mengubah
--    dan menghapus riwayat transaksi, sedangkan role lain (kasir/karyawan) tetap ditolak.
create or replace function public.jaga_update_transaksi()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if (select public.role_saya()) = 'pemilik' then
    return new;
  end if;
  raise exception 'Transaksi bersifat permanen: hanya pemilik yang dapat mengubah atau menghapus transaksi';
end;
$$;

create or replace function public.jaga_hapus_transaksi()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if (select public.role_saya()) = 'pemilik' then
    return old;
  end if;
  raise exception 'Transaksi bersifat permanen: hanya pemilik yang dapat mengubah atau menghapus transaksi';
end;
$$;

drop trigger if exists transaksi_jaga_update on public.transaksi;
create trigger transaksi_jaga_update
  before update on public.transaksi
  for each row execute function public.jaga_update_transaksi();

drop trigger if exists transaksi_jaga_hapus on public.transaksi;
create trigger transaksi_jaga_hapus
  before delete on public.transaksi
  for each row execute function public.jaga_hapus_transaksi();

-- 2. Kebijakan Row Level Security (RLS) untuk UPDATE dan DELETE khusus Pemilik
drop policy if exists transaksi_update on public.transaksi;
create policy transaksi_update on public.transaksi for update to authenticated
  using ((select public.role_saya()) = 'pemilik')
  with check ((select public.role_saya()) = 'pemilik');

drop policy if exists transaksi_delete on public.transaksi;
create policy transaksi_delete on public.transaksi for delete to authenticated
  using ((select public.role_saya()) = 'pemilik');
