import os, sys, uuid
from types import SimpleNamespace as NS

import pytest
from postgrest.exceptions import APIError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-key")

import app as app_module  # noqa: E402
import qris  # noqa: E402
import supa  # noqa: E402


class FakeQuery:
    """Query builder palsu: cukup untuk memeriksa logika backend tanpa Supabase."""

    def __init__(self, db, tabel):
        self.db, self.t = db, tabel
        self.f, self.ord, self.rng, self.op, self.payload, self.count = [], [], None, "select", None, None

    def select(self, kolom="*", count=None):
        self.count = count
        return self

    def _flt(self, k, op, v):
        self.f.append((k, op, v))
        return self

    def eq(self, k, v): return self._flt(k, "eq", v)
    def gte(self, k, v): return self._flt(k, "gte", v)
    def lte(self, k, v): return self._flt(k, "lte", v)
    def lt(self, k, v): return self._flt(k, "lt", v)
    def in_(self, k, v): return self._flt(k, "in", v)

    def order(self, k, desc=False):
        self.ord.append((k, desc))
        return self

    def range(self, a, b):
        self.rng = (a, b)
        return self

    def limit(self, n):
        self.rng = (0, n - 1)
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def _cocok(self, r):
        ops = {"eq": lambda a, b: a == b, "gte": lambda a, b: a >= b,
               "lte": lambda a, b: a <= b, "lt": lambda a, b: a < b, "in": lambda a, b: a in b}
        return all(ops[op](r.get(k), v) for k, op, v in self.f)

    def execute(self):
        rows = self.db.data.setdefault(self.t, [])
        self.db.log.append((self.t, self.op, self.payload, list(self.f)))
        if self.op == "insert":
            if self.db.on_insert:
                self.db.on_insert(self.t, self.payload)
            baru = {"id": str(uuid.uuid4()), "created_at": "2026-11-09T10:00:00", **self.payload}
            rows.append(baru)
            return NS(data=[baru], count=None)
        cocok = [r for r in rows if self._cocok(r)]
        if self.op == "update":
            for r in cocok:
                r.update(self.payload)
            return NS(data=[dict(r) for r in cocok], count=None)
        for k, desc in reversed(self.ord):
            cocok.sort(key=lambda r: (r.get(k) is None, r.get(k)), reverse=desc)
        total = len(cocok)
        if self.rng:
            cocok = cocok[self.rng[0]: self.rng[1] + 1]
        return NS(data=[dict(r) for r in cocok], count=total if self.count else None)


class FakeDB:
    def __init__(self):
        self.data, self.log, self.on_insert = {}, [], None


class FakeAuth:
    def __init__(self, db):
        self.db = db

    def sign_in_with_password(self, cred):
        from supabase_auth.errors import AuthApiError
        u = self.db.users.get(cred["email"])
        if not u or u["password"] != cred["password"]:
            raise AuthApiError("Invalid login credentials", 400, "invalid_credentials")
        return NS(user=NS(id=u["id"]), session=NS(
            access_token=f"tok-{u['id']}", refresh_token="ref", expires_at=self.db.expires_at, expires_in=3600))

    def refresh_session(self, token):
        self.db.refresh_dipanggil += 1
        return NS(session=NS(access_token="tok-baru", refresh_token="ref2", expires_at=9999999999, expires_in=3600))

    def set_session(self, a, b): self.db.set_session_dipanggil = True
    def sign_out(self, opts=None): self.db.sign_out_opts = opts


class FakeClient:
    def __init__(self, db):
        self.db = db
        self.auth = FakeAuth(db)
        self.postgrest = NS(auth=lambda token: setattr(db, "token_terakhir", token))

    def table(self, nama):
        return FakeQuery(self.db, nama)


@pytest.fixture
def db(monkeypatch):
    d = FakeDB()
    d.refresh_dipanggil, d.expires_at, d.token_terakhir = 0, 9999999999, None
    ids = {r: f"00000000-0000-0000-0000-00000000000{i}" for i, r in enumerate(("pemilik", "kasir", "karyawan"), 1)}
    d.ids = ids
    d.users = {f"{r}@esteh.test": {"id": i, "password": "rahasia123"} for r, i in ids.items()}
    d.data["profiles"] = [{"id": i, "nama": r.title(), "role": r, "aktif": True} for r, i in ids.items()]
    d.data["pengaturan_kas"] = [{"kas": "tangan", "saldo_awal": 1500000}, {"kas": "bank", "saldo_awal": 500000}, {"kas": "kecil", "saldo_awal": 500000}]
    d.data["saldo_kas"] = [{"kas": "tangan", "saldo": 3000000}, {"kas": "bank", "saldo": 2000000}, {"kas": "kecil", "saldo": 85000}]
    monkeypatch.setattr(supa, "anon_client", lambda: FakeClient(d))
    qris._sesi.update(klien=None, uid=None, exp=0)       # sesi akun sistem tidak boleh bocor antar tes
    qris._riwayat_ip.clear()
    return d


@pytest.fixture
def client(db):
    a = app_module.create_app({"TESTING": True, "SECRET_KEY": "x" * 32, "SESSION_COOKIE_SECURE": False})
    return a.test_client()


def login(client, role):
    r = client.post("/api/login", json={"email": f"{role}@esteh.test", "password": "rahasia123", "role": role})
    assert r.status_code == 200, r.get_json()
    return r


def api_error(code, msg):
    return APIError({"message": msg, "code": code, "hint": None, "details": None})
