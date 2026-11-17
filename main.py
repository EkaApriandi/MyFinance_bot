import sys
import logging
from pathlib import Path

# Pastikan folder bot masuk ke sys.path agar impor modul berjalan mulus dari direktori mana pun
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from config import TELEGRAM_BOT_TOKEN, DB_PATH, GOOGLE_SHEET_ID
from handlers import (
    start_command,
    help_command,
    menu_command,
    rekap_command,
    riwayat_command,
    budget_command,
    export_command,
    kategori_command,
    rekap_callback_handler,
    handle_text_message,
    interactive_callback_handler
)

# Konfigurasi Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("FinanceBot")

def main():
    """Fungsi utama untuk menjalankan Bot Telegram Keuangan."""
    print("=" * 60)
    print("🤖 MEMULAI TELEGRAM PERSONAL FINANCE BOT")
    print("=" * 60)

    # Validasi Token
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        print("\n❌ ERROR: Token Bot Telegram belum diisi!")
        print("Silakan ikuti langkah berikut:")
        print("1. Buka file '.env' di folder proyek ini.")
        print("2. Masukkan token bot yang didapatkan dari @BotFather pada baris:")
        print("   TELEGRAM_BOT_TOKEN=token_anda_disini\n")
        sys.exit(1)

    print(f"📁 Database SQLite: {DB_PATH}")
    if GOOGLE_SHEET_ID:
        print(f"📊 Google Sheets Sync: AKTIF (Sheet ID: {GOOGLE_SHEET_ID[:6]}...)")
    else:
        print("📊 Google Sheets Sync: NONAKTIF (Menggunakan SQLite lokal + Ekspor CSV)")

    # Inisialisasi Aplikasi Telegram Bot
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Daftarkan Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("rekap", rekap_command))
    app.add_handler(CommandHandler("riwayat", riwayat_command))
    app.add_handler(CommandHandler("budget", budget_command))
    app.add_handler(CommandHandler("export", export_command))
    app.add_handler(CommandHandler("kategori", kategori_command))
    app.add_handler(CommandHandler("help", help_command))

    # Daftarkan Callback Query Handlers (Undo, Filter Periode, Smart Category, Navigasi)
    app.add_handler(CallbackQueryHandler(rekap_callback_handler, pattern=r"^rekap:"))
    app.add_handler(CallbackQueryHandler(interactive_callback_handler, pattern=r"^(undo:|cat_pick:|cat_cancel|del_hist:|nav:|export_csv)"))

    # Daftarkan Message Handler untuk input teks biasa (cth: 'makan 25000')
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    print("\n✅ Bot berhasil diinisialisasi dan siap menerima pesan!")
    print("👉 Tekan Ctrl + C di terminal untuk menghentikan bot.")
    print("=" * 60)

    # Mulai polling
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
