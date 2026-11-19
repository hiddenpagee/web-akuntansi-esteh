-- =====================================================================
-- Data dummy transaksi (14 hari terakhir)
-- Jalankan SETELAH: 01_schema.sql dan seed_users.py
-- =====================================================================
do $$
declare
  v_pemilik  uuid := (select id from public.profiles where role = 'pemilik'  limit 1);
  v_kasir    uuid := (select id from public.profiles where role = 'kasir'    limit 1);
  v_karyawan uuid := (select id from public.profiles where role = 'karyawan' limit 1);
begin
  if v_pemilik is null or v_kasir is null or v_karyawan is null then
    raise exception 'Akun pemilik/kasir/karyawan belum ada. Jalankan seed_users.py dulu.';
  end if;

  -- Pemasukan: penjualan tunai & QRIS tiap hari, diinput Kasir
  insert into public.transaksi (tanggal, jenis, kategori_id, nominal, metode, sumber_kas, keterangan, dibuat_oleh)
  select current_date - (13 - i), 'masuk',
         (select id from public.kategori where nama = 'Penjualan Tunai'),
         600000 + (i % 5) * 50000, 'tunai', 'tangan', 'Penjualan tunai harian', v_kasir
  from generate_series(0, 13) i;

  insert into public.transaksi (tanggal, jenis, kategori_id, nominal, metode, sumber_kas, keterangan, dibuat_oleh)
  select current_date - (13 - i), 'masuk',
         (select id from public.kategori where nama = 'Penjualan QRIS'),
         300000 + (i % 4) * 40000, 'qris', 'bank', 'Penjualan QRIS harian', v_kasir
  from generate_series(0, 13) i;

  -- Pemasukan event (sekali) dan online (tiap 3 hari)
  insert into public.transaksi (tanggal, jenis, kategori_id, nominal, metode, sumber_kas, keterangan, dibuat_oleh)
  values (current_date - 6, 'masuk', (select id from public.kategori where nama = 'Pesanan Event'),
          450000, 'qris', 'bank', 'Pesanan 50 cup acara kampus', v_kasir);

  insert into public.transaksi (tanggal, jenis, kategori_id, nominal, metode, sumber_kas, keterangan, dibuat_oleh)
  select current_date - (13 - i), 'masuk',
         (select id from public.kategori where nama = 'Penjualan Online (GoFood/ShopeeFood)'),
         180000 + (i % 3) * 20000, 'qris', 'bank', 'Pesanan online', v_kasir
  from generate_series(0, 13, 3) i;

  -- Pengeluaran Kas Utama, diinput Pemilik: bahan baku tiap 2 hari, gaji & listrik sekali
  insert into public.transaksi (tanggal, jenis, kategori_id, nominal, sumber_kas, keterangan, dibuat_oleh)
  select current_date - (13 - i), 'keluar',
         (select id from public.kategori where nama = 'Bahan Baku (teh, gula, es batu)'),
         250000 + (i % 3) * 25000, 'tangan', 'Belanja teh, gula, dan es batu', v_pemilik
  from generate_series(0, 13, 2) i;

  insert into public.transaksi (tanggal, jenis, kategori_id, nominal, sumber_kas, keterangan, dibuat_oleh)
  values
    (current_date - 7, 'keluar', (select id from public.kategori where nama = 'Gaji'),
      1500000, 'tangan', 'Gaji karyawan mingguan', v_pemilik),
    (current_date - 3, 'keluar', (select id from public.kategori where nama = 'Listrik/Sewa'),
      300000, 'tangan', 'Token listrik', v_pemilik);

  -- Isi ulang Kas Kecil (transfer Kas Utama -> Kas Kecil), diinput Pemilik
  insert into public.transaksi (tanggal, jenis, nominal, sumber_kas, tujuan_kas, keterangan, dibuat_oleh)
  values
    (current_date - 9, 'transfer', 300000, 'tangan', 'kecil', 'Isi ulang kas kecil', v_pemilik),
    (current_date - 4, 'transfer', 300000, 'tangan', 'kecil', 'Isi ulang kas kecil', v_pemilik);

  -- Pengeluaran Kas Kecil, diinput Karyawan
  insert into public.transaksi (tanggal, jenis, kategori_id, nominal, sumber_kas, keterangan, dibuat_oleh)
  select current_date - (13 - i), 'keluar',
         (select id from public.kategori where nama = case when i % 2 = 0
            then 'Kemasan (gelas, plastik, sedotan)' else 'Operasional Lain' end),
         35000 + (i % 4) * 15000, 'kecil',
         case when i % 2 = 0 then 'Beli gelas dan sedotan' else 'Es batu dan kebutuhan kecil' end,
         v_karyawan
  from generate_series(0, 13) i;
end $$;

-- Cek hasil: saldo tiap kas
select * from public.saldo_kas;
