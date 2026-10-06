import os
import sqlite3
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta, timezone

# Leer desde el .env o usar valores por defecto seguros para evitar cuelgues
SECRET_KEY = os.environ.get("KIKOS_SECRET_KEY", "kikos_default_secret_do_not_use_in_prod")
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthManager:
    def __init__(self, db_path="core/kikos_users.db"):
        self.db_path = db_path
        self.admin_user = os.environ.get("KIKOS_ADMIN_USER", "admin")
        self.admin_pass = os.environ.get("KIKOS_ADMIN_PASS", "admin123")
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)")
        cursor.execute("SELECT * FROM users WHERE username=?", (self.admin_user,))
        if not cursor.fetchone():
            hash_pw = pwd_context.hash(self.admin_pass)
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (self.admin_user, hash_pw))
        conn.commit()
        conn.close()

    # ... (el resto del código de auth.py se queda exactamente igual) ...
    def verify_password(self, plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    def authenticate_user(self, username, password):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE username=?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row and self.verify_password(password, row[0]):
            return True
        return False

    def create_token(self, username: str):
        expire = datetime.now(timezone.utc) + timedelta(hours=24)
        to_encode = {"sub": username, "exp": int(expire.timestamp())}
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    def verify_token(self, token: str):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload.get("sub")
        except:
            return None
