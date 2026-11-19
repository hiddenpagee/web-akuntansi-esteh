-- Jalankan HANYA kalau 01_schema.sql versi lama sudah terlanjur dijalankan.
-- Menambah aturan: membatalkan pemasukan / isi ulang tidak boleh bikin saldo minus.
create function public.jaga_update_transaksi()
returns trigger
language plpgsql
as $$
declare
  v_kas   text;
  v_saldo bigint;
begin
  if old.status = 'batal' then
    raise exception 'Transaksi yang sudah dibatalkan tidak bisa diubah lagi';
  end if;

  if (new.tanggal, new.jenis, new.kategori_id, new.nominal, new.metode,
      new.sumber_kas, new.tujuan_kas, new.keterangan, new.dibuat_oleh)
     is distinct from
     (old.tanggal, old.jenis, old.kategori_id, old.nominal, old.metode,
      old.sumber_kas, old.tujuan_kas, old.keterangan, old.dibuat_oleh) then
    raise exception 'Transaksi tidak bisa diedit, hanya bisa dibatalkan';
  end if;

  if new.status = 'batal' then
    if new.batal_alasan is null or length(trim(new.batal_alasan)) = 0 then
      raise exception 'Alasan pembatalan wajib diisi';
    end if;

    -- membatalkan pemasukan / isi ulang mengurangi saldo; jangan sampai jadi minus
    v_kas := case old.jenis when 'masuk' then 'utama' when 'transfer' then 'kecil' end;
    if v_kas is not null then
      perform pg_advisory_xact_lock(hashtext('kas_' || v_kas));
      select saldo into v_saldo from saldo_kas where kas = v_kas;
      if v_saldo < old.nominal then
        raise exception 'Pembatalan ditolak: saldo kas % akan menjadi minus', v_kas;
      end if;
    end if;

    new.batal_oleh := auth.uid();
    new.batal_at   := now();
  end if;

  return new;
end;
$$;

