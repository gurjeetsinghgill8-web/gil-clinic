# pa_asgi.py - PythonAnywhere ASGI entry point for GIL CLINIC
#
# PythonAnywhere Web tab -> ASGI application file -> is file ka path do:
#   /home/<your-username>/gil-clinic/pa_asgi.py
#
# Ye file main_v2 import karne se PEHLE env vars set karti hai (DB path etc),
# taaki data hamesha project folder ki ghos_prod.db mein rahe.
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# DB path — PythonAnywhere home dir (username se badlein zaroorat nahi, auto-detect hai)
_DB = "sqlite:///" + os.path.join(BASE_DIR, "ghos_prod.db")
os.environ.setdefault("GHOS_DB_URL", _DB)
os.environ.setdefault(
    "GHOS_DB_URL_ASYNC", "sqlite+aiosqlite:///" + os.path.join(BASE_DIR, "ghos_prod.db")
)

from main_v2 import app  # noqa: E402

application = app
