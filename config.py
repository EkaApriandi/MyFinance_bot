import os
from pathlib import Path

# Load .env dengan python-dotenv atau fallback parser sederhana
BASE_DIR = Path(__file__).resolve().parent
env_file = BASE_DIR / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(env_file)
except ImportError:
    # Fallback parser sederhana jika python-dotenv belum terpasang
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# Database Path
raw_db_path = os.getenv("DATABASE_PATH", "database/finance.db")
db_p = Path(raw_db_path)
DB_PATH = db_p if db_p.is_absolute() else (BASE_DIR / db_p)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Google Sheets Config (Opsional)
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
GOOGLE_CREDENTIALS_FILE = BASE_DIR / os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")

# Kategori Pengeluaran & Icon Mapping
CATEGORIES = {
    "makanan": {"label": "Makanan & Minuman", "icon": "🍔"},
    "transport": {"label": "Transportasi", "icon": "🚗"},
    "belanja": {"label": "Belanja & Kebutuhan", "icon": "🛍️"},
    "tagihan": {"label": "Tagihan & Utilitas", "icon": "💡"},
    "hiburan": {"label": "Hiburan & Hobi", "icon": "🎮"},
    "kesehatan": {"label": "Kesehatan & Medis", "icon": "💊"},
    "pendidikan": {"label": "Pendidikan & Buku", "icon": "📚"},
    "pemasukan": {"label": "Pemasukan / Gaji", "icon": "💰"},
    "lainnya": {"label": "Lain-lain", "icon": "📦"},
}

def format_rupiah(nominal: float | int) -> str:
    """Format angka menjadi format mata uang Rupiah standar."""
    if nominal < 0:
        return f"-Rp {abs(nominal):,.0f}".replace(",", ".")
    return f"Rp {nominal:,.0f}".replace(",", ".")
