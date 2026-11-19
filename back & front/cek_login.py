import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ.get("SUPABASE_URL", "")
key = os.environ.get("SUPABASE_ANON_KEY", "")
print("URL        :", url)
print("Key awalan :", key[:15], "| panjang:", len(key))

sb = create_client(url, key)
try:
    r = sb.auth.sign_in_with_password(
        {"email": "pemilik@esteh.test", "password": "Demo12345!"}
    )
    print("LOGIN OK, user id:", r.user.id)
    sb.postgrest.auth(r.session.access_token)
    print("profiles  :", sb.table("profiles").select("nama,role,aktif").execute().data)
except Exception as e:
    print("ERROR:", type(e).__name__, "-", e)