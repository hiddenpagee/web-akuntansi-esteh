-- =====================================================================
-- 04: Pisah Kas Utama menjadi Kas di Tangan + Kas di Bank, dan siapkan akun jurnal.
-- Jalankan sekali di Supabase: SQL Editor > New query > paste > Run
-- (dijalankan setelah 03_hapus_pembatalan.sql). Satu transaksi: kalau ada error, semua batal.
--
-- ASUMSI DATA LAMA (cek hasilnya setelah dijalankan):
--   * pemasukan QRIS lama   -> Kas di Bank
--   * pemasukan tunai lama  -> Kas di Tangan
--   * pengeluaran dan isi ulang lama dari 'utama' -> Kas di Tangan
--   * saldo awal 'utama' lama -> seluruhnya jadi saldo awal Kas di Tangan, Kas di Bank = 0
-- Sesuaikan saldo awal dengan data asli di langkah paling bawah.
-- =====================================================================

-- 1. Lepas objek dan aturan lama yang menyebut 'utama'
drop view if exists public.saldo_kas;

do $$
declare r record;
begin
  for r in
    select conrelid::regclass::text as tabel, conname
    from pg_constraint
    where contype = 'c'
      and conrelid in ('public.transaksi'::regclass, 'public.pengaturan_kas'::regclass)
      and pg_get_constraintdef(oid) like '%utama%'
  loop
    execute format('alter table %s drop constraint %I', r.tabel, r.conname);
  end loop;
end $$;

-- 2. Pindahkan data lama (trigger anti-ubah dimatikan sebentar, lalu dinyalakan lagi)
alter table public.transaksi disable trigger transaksi_jaga_update;

update public.pengaturan_kas set kas = 'tangan' where kas = 'utama';
insert into public.pengaturan_kas (kas, saldo_awal) values ('bank', 0) on conflict (kas) do nothing;

update public.transaksi
   set sumber_kas = case when jenis = 'masuk' and metode = 'qris' then 'bank' else 'tangan' end
 where sumber_kas = 'utama';

alter table public.transaksi enable trigger transaksi_jaga_update;

-- 3. Aturan baru: tiga kas
alter table public.pengaturan_kas
  add constraint pengaturan_kas_kas_check check (kas in ('tangan', 'bank', 'kecil'));
alter table public.transaksi
  add constraint transaksi_sumber_kas_check check (sumber_kas in ('tangan', 'bank', 'kecil'));
alter table public.transaksi
  add constraint transaksi_tujuan_kas_check check (tujuan_kas in ('tangan', 'bank', 'kecil'));
alter table public.transaksi
  add constraint transaksi_bentuk check (
    (jenis = 'masuk'    and tujuan_kas is null and kategori_id is not null and metode is not null
                        and ((metode = 'tunai' and sumber_kas = 'tangan')
                          or (metode = 'qris'  and sumber_kas = 'bank')))
    or
    (jenis = 'keluar'   and tujuan_kas is null and kategori_id is not null)
    or
    (jenis = 'transfer' and sumber_kas in ('tangan', 'bank') and tujuan_kas = 'kecil'
                        and kategori_id is null and metode is null)
  );

-- 4. View saldo (rumus sama, sekarang membaca tiga kas)
create view public.saldo_kas as
with mutasi as (
  select sumber_kas as kas,
         case when jenis = 'masuk' then nominal else -nominal end as delta
  from public.transaksi
  where status = 'aktif' and jenis in ('masuk', 'keluar')
  union all
  select sumber_kas, -nominal from public.transaksi where status = 'aktif' and jenis = 'transfer'
  union all
  select tujuan_kas,  nominal from public.transaksi where status = 'aktif' and jenis = 'transfer'
)
select p.kas,
       p.saldo_awal + coalesce(sum(m.delta), 0) as saldo
from public.pengaturan_kas p
left join mutasi m on m.kas = p.kas
group by p.kas, p.saldo_awal;

revoke all on public.saldo_kas from anon;
grant select on public.saldo_kas to authenticated;

-- 5. Akun jurnal untuk tiap kategori (dipakai Jurnal Umum dan Jurnal Petty Cash)
alter table public.kategori add column if not exists akun_kode text;

update public.kategori set akun_kode = case nama
  when 'Penjualan Tunai'                        then '4-101'
  when 'Penjualan QRIS'                         then '4-101'
  when 'Penjualan Online (GoFood/ShopeeFood)'   then '4-102'
  when 'Pesanan Event'                          then '4-103'
  when 'Bahan Baku (teh, gula, es batu)'        then '5-101'
  when 'Kemasan (gelas, plastik, sedotan)'      then '5-102'
  when 'Gaji'                                   then '5-201'
  when 'Listrik/Sewa'                           then '5-202'
  when 'Operasional Lain'                       then '5-203'
end
where akun_kode is null;

-- 6. SALDO AWAL: sesuaikan dengan kondisi asli (jalankan SEKALI di awal pemakaian, jangan diubah-ubah
--    setelah ada transaksi karena semua saldo dan jurnal ikut bergeser). Contoh:
-- update public.pengaturan_kas set saldo_awal = 1500000 where kas = 'tangan';
-- update public.pengaturan_kas set saldo_awal =  500000 where kas = 'bank';
-- update public.pengaturan_kas set saldo_awal =  500000 where kas = 'kecil';
