-- =====================================================================
-- Skema database: Akuntansi Kas & Kas Kecil (Es Teh)
-- Jalankan di Supabase: SQL Editor > New query > paste > Run
-- =====================================================================

-- ---------- 1. PROFIL PENGGUNA (nyambung ke Supabase Auth) ----------
create table public.profiles (
  id         uuid primary key references auth.users (id) on delete cascade,
  nama       text not null,
  role       text not null check (role in ('pemilik', 'kasir', 'karyawan')),
  aktif      boolean not null default true,
  created_at timestamptz not null default now()
);

-- ---------- 2. KATEGORI ----------
create table public.kategori (
  id         smallint generated always as identity primary key,
  nama       text not null unique,
  jenis      text not null check (jenis in ('masuk', 'keluar')),
  aktif      boolean not null default true,
  akun_kode  text            -- kode akun lawan di jurnal (lihat jurnal.py)
);

-- ---------- 3. PENGATURAN KAS (saldo awal tiap dompet) ----------
create table public.pengaturan_kas (
  kas         text primary key check (kas in ('tangan', 'bank', 'kecil')),
  saldo_awal  bigint not null check (saldo_awal >= 0)
);

-- ---------- 4. TRANSAKSI (satu tabel gabungan: masuk, keluar, transfer) ----------
create table public.transaksi (
  id            uuid primary key default gen_random_uuid(),
  tanggal       date not null default current_date,
  jenis         text not null check (jenis in ('masuk', 'keluar', 'transfer')),
  kategori_id   smallint references public.kategori (id),
  nominal       bigint not null check (nominal > 0),          -- Rupiah, tanpa desimal
  metode        text check (metode in ('tunai', 'qris')),
  sumber_kas    text not null check (sumber_kas in ('tangan', 'bank', 'kecil')),
  tujuan_kas    text check (tujuan_kas in ('tangan', 'bank', 'kecil')), -- hanya untuk transfer
  keterangan    text,
  dibuat_oleh   uuid not null references public.profiles (id),
  status        text not null default 'aktif' check (status in ('aktif', 'batal')),
  batal_alasan  text,
  batal_oleh    uuid references public.profiles (id),
  batal_at      timestamptz,
  created_at    timestamptz not null default now(),

  -- Bentuk data yang valid per jenis transaksi
  constraint transaksi_bentuk check (
    (jenis = 'masuk'    and tujuan_kas is null and kategori_id is not null and metode is not null
                        and ((metode = 'tunai' and sumber_kas = 'tangan')
                          or (metode = 'qris'  and sumber_kas = 'bank')))
    or
    (jenis = 'keluar'   and tujuan_kas is null and kategori_id is not null)
    or
    (jenis = 'transfer' and sumber_kas in ('tangan', 'bank') and tujuan_kas = 'kecil'
                        and kategori_id is null and metode is null)
  ),
  constraint transaksi_batal_lengkap check (
    status = 'aktif' or (batal_alasan is not null and batal_oleh is not null and batal_at is not null)
  )
);

create index transaksi_tanggal_idx     on public.transaksi (tanggal desc);
create index transaksi_dibuat_oleh_idx on public.transaksi (dibuat_oleh);
create index transaksi_kategori_idx    on public.transaksi (kategori_id);
create index transaksi_sumber_idx      on public.transaksi (sumber_kas, status);

-- ---------- 5. SALDO KAS (dihitung dari transaksi, tidak pernah diketik manual) ----------
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

-- ---------- 6. TRIGGER: validasi saat transaksi baru masuk ----------
create function public.cek_transaksi_baru()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_jenis_kategori text;
  v_saldo bigint;
begin
  -- kategori harus sesuai jenis transaksi
  if new.jenis in ('masuk', 'keluar') then
    select jenis into v_jenis_kategori from kategori where id = new.kategori_id;
    if v_jenis_kategori is distinct from new.jenis then
      raise exception 'Kategori tidak sesuai dengan jenis transaksi';
    end if;
  end if;

  -- saldo tidak boleh minus untuk pengeluaran dan isi ulang
  if new.jenis in ('keluar', 'transfer') then
    -- kunci per dompet supaya dua transaksi bersamaan tidak lolos bareng
    perform pg_advisory_xact_lock(hashtext('kas_' || new.sumber_kas));
    select saldo into v_saldo from saldo_kas where kas = new.sumber_kas;
    if v_saldo < new.nominal then
      raise exception 'Saldo kas % tidak cukup (sisa Rp%)', new.sumber_kas, v_saldo;
    end if;
  end if;

  return new;
end;
$$;

create trigger transaksi_cek_baru
  before insert on public.transaksi
  for each row execute function public.cek_transaksi_baru();

-- ---------- 7. TRIGGER: transaksi permanen, tidak bisa diubah atau dihapus ----------
create function public.jaga_update_transaksi()
returns trigger
language plpgsql
as $$
begin
  raise exception 'Transaksi bersifat permanen: tidak bisa diubah atau dihapus';
end;
$$;

create trigger transaksi_jaga_update
  before update on public.transaksi
  for each row execute function public.jaga_update_transaksi();

create trigger transaksi_jaga_hapus
  before delete on public.transaksi
  for each row execute function public.jaga_update_transaksi();

-- ---------- 8. ROW LEVEL SECURITY ----------
create function public.role_saya()
returns text
language sql
stable
security definer
set search_path = public
as $$
  select role from profiles where id = (select auth.uid()) and aktif
$$;

alter table public.profiles       enable row level security;
alter table public.kategori       enable row level security;
alter table public.pengaturan_kas enable row level security;
alter table public.transaksi      enable row level security;

-- profiles: lihat diri sendiri; Pemilik lihat semua
create policy profiles_select on public.profiles for select to authenticated
  using (id = (select auth.uid()) or (select public.role_saya()) = 'pemilik');

-- kategori & pengaturan kas: semua yang login boleh lihat; hanya Pemilik yang ubah
create policy kategori_select on public.kategori for select to authenticated using (true);
create policy kategori_ubah   on public.kategori for all to authenticated
  using ((select public.role_saya()) = 'pemilik')
  with check ((select public.role_saya()) = 'pemilik');

create policy kas_select on public.pengaturan_kas for select to authenticated using (true);

-- transaksi: lihat
--   Pemilik & Kasir = semua, Karyawan = hanya miliknya
create policy transaksi_select on public.transaksi for select to authenticated
  using (
    (select public.role_saya()) in ('pemilik', 'kasir')
    or dibuat_oleh = (select auth.uid())
  );

-- transaksi: tambah
--   Pemilik = semua jenis, Kasir = masuk/keluar, Karyawan = pengeluaran Kas Kecil saja
create policy transaksi_insert on public.transaksi for insert to authenticated
  with check (
    dibuat_oleh = (select auth.uid())
    and (
      (select public.role_saya()) = 'pemilik'
      or ((select public.role_saya()) = 'kasir' and jenis in ('masuk', 'keluar'))
      or ((select public.role_saya()) = 'karyawan' and jenis = 'keluar' and sumber_kas = 'kecil')
    )
  );

-- transaksi: TIDAK ada policy update dan delete = tidak ada yang bisa mengubah atau menghapus.

-- view saldo: hanya untuk yang sudah login
revoke all on public.saldo_kas from anon;
grant select on public.saldo_kas to authenticated;

-- ---------- 9. DATA AWAL (referensi, bukan dummy) ----------
insert into public.pengaturan_kas (kas, saldo_awal) values
  ('tangan', 1500000),  -- dummy: ganti dengan saldo kas di tangan asli saat go-live
  ('bank',    500000),  -- dummy: ganti dengan saldo rekening asli saat go-live
  ('kecil',   500000);  -- saldo awal Kas Kecil sesuai kesepakatan

insert into public.kategori (nama, jenis, akun_kode) values
  ('Penjualan Tunai',                      'masuk',  '4-101'),
  ('Penjualan QRIS',                       'masuk',  '4-101'),
  ('Penjualan Online (GoFood/ShopeeFood)', 'masuk',  '4-102'),
  ('Pesanan Event',                        'masuk',  '4-103'),
  ('Bahan Baku (teh, gula, es batu)',      'keluar', '5-101'),
  ('Kemasan (gelas, plastik, sedotan)',    'keluar', '5-102'),
  ('Gaji',                                 'keluar', '5-201'),
  ('Listrik/Sewa',                         'keluar', '5-202'),
  ('Operasional Lain',                     'keluar', '5-203');
