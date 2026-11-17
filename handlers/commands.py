from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import CATEGORIES, format_rupiah
from database.db_manager import DatabaseManager
from services.parser import parse_amount
from services.visualizer import generate_rekap_chart, generate_text_progress_bar, generate_budget_progress
from services.sheets_sync import SheetsSyncService

db = DatabaseManager()
sheets_service = SheetsSyncService()

# Keyboard menu cepat di bagian bawah chat pengguna
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("⚡ Menu Dashboard"), KeyboardButton("📊 Rekap Keuangan")],
        [KeyboardButton("📜 Riwayat Terakhir"), KeyboardButton("🎯 Atur Budget")],
        [KeyboardButton("📥 Ekspor CSV"), KeyboardButton("💡 Panduan & Format")]
    ],
    resize_keyboard=True
)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk perintah /start."""
    user = update.effective_user
    name = user.first_name if user else "Kawan"

    pesan = (
        f"👋 <b>Halo, {name}!</b>\n"
        f"Selamat datang di <b>Bot Asisten Keuangan Pribadi Interaktif</b>.\n\n"
        f"Catat pengeluaran dan pemasukan harian Anda secara instan dan visual!\n\n"
        f"⚡ <b>Cara Penggunaan Cepat:</b>\n"
        f"• <code>makan 25000</code> atau <code>kopi 25k</code>\n"
        f"• <code>bensin 20rb</code> atau <code>service 150k</code>\n"
        f"• <b>Cuma ketik angka:</b> <code>50000</code> (bot akan munculkan pilihan tombol kategori!)\n"
        f"• <b>Pemasukan:</b> <code>+gaji 5000000</code> atau <code>freelance 1.5jt</code>\n\n"
        f"🎛️ <b>Perintah Utama:</b>\n"
        f"• /menu - Dashboard kontrol & ringkasan saldo\n"
        f"• /rekap - Laporan visual Donut Chart interaktif\n"
        f"• /riwayat - 5 Transaksi terakhir & tombol hapus\n"
        f"• /budget - Atur target batas pengeluaran bulanan\n"
        f"• /export - Unduh seluruh data ke file CSV / Excel\n\n"
        f"<i>Coba ketik sekarang: <code>makan 25000</code> atau cukup ketik <code>50000</code></i>"
    )

    if update.message:
        await update.message.reply_text(
            pesan,
            parse_mode=ParseMode.HTML,
            reply_markup=MAIN_KEYBOARD
        )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dashboard interaktif utama (/menu)."""
    user = update.effective_user
    if not user:
        return

    user_id = user.id
    month_summary = db.get_period_summary(user_id, period="month")
    budget = db.get_user_budget(user_id)
    total_expense = month_summary["total_expense"]
    total_income = month_summary["total_income"]
    balance = month_summary["balance"]

    nama_bulan = month_summary["title"]

    lines = [
        f"⚡ <b>DASHBOARD KEUANGAN ({nama_bulan})</b>",
        "────────────────────────",
        f"📈 <b>Pemasukan:</b>   <code>{format_rupiah(total_income)}</code>",
        f"📉 <b>Pengeluaran:</b> <code>{format_rupiah(total_expense)}</code>",
        f"💰 <b>Sisa Kas:</b>     <code>{format_rupiah(balance)}</code>",
        "────────────────────────"
    ]

    budget_info = generate_budget_progress(total_expense, budget)
    if budget_info:
        lines.append(budget_info)
        lines.append("────────────────────────")
    else:
        lines.append("💡 <i>Belum ada batas budget bulanan. Ketik <code>/budget 3jt</code> untuk memasang batas.</i>\n")

    lines.append("Pilih menu navigasi di bawah ini:")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Rekap Donut Chart", callback_data="nav:rekap"),
            InlineKeyboardButton("📜 Riwayat Catatan", callback_data="nav:riwayat")
        ],
        [
            InlineKeyboardButton("🎯 Atur Budget", callback_data="nav:budget"),
            InlineKeyboardButton("📥 Ekspor CSV", callback_data="export_csv")
        ],
        [
            InlineKeyboardButton("🏷️ Daftar Kategori", callback_data="nav:kategori"),
            InlineKeyboardButton("💡 Panduan Input", callback_data="nav:help")
        ]
    ])

    pesan_teks = "\n".join(lines)
    if update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(pesan_teks, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    elif update.message:
        await update.message.reply_text(pesan_teks, parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def send_rekap(user_id: int, message_target, period: str = "month", is_callback: bool = False):
    """Menghasilkan teks dan Donut Chart berdasarkan periode dinamis."""
    summary = db.get_period_summary(user_id, period=period)
    total_expense = summary["total_expense"]
    total_income = summary["total_income"]
    balance = summary["balance"]
    breakdown = summary["breakdown"]
    period_title = summary["title"]

    # Header Teks
    lines = [
        f"📊 <b>LAPORAN KEUANGAN: {period_title.upper()}</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"📈 <b>Pemasukan:</b>   <code>{format_rupiah(total_income)}</code>",
        f"📉 <b>Pengeluaran:</b> <code>{format_rupiah(total_expense)}</code>",
        f"💰 <b>Selisih Kas:</b>  <code>{format_rupiah(balance)}</code>",
        "━━━━━━━━━━━━━━━━━━━━━━\n",
        "📑 <b>Rincian per Kategori:</b>"
    ]

    if not breakdown:
        lines.append("<i>Belum ada catatan pengeluaran pada periode ini.</i>")
    else:
        for item in breakdown:
            cat_key = item["category"]
            cat_info = CATEGORIES.get(cat_key, {"label": cat_key.capitalize(), "icon": "📁"})
            cat_total = item["total"]
            percent = (cat_total / total_expense * 100.0) if total_expense > 0 else 0
            bar = generate_text_progress_bar(percent, length=7)
            lines.append(
                f"{cat_info['icon']} <b>{cat_info['label']}:</b> {format_rupiah(cat_total)}\n"
                f"   {bar}"
            )

    teks_laporan = "\n".join(lines)

    # Tombol Ganti Periode Real-time
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{'✅ ' if period == 'today' else ''}Hari Ini", callback_data="rekap:today"),
            InlineKeyboardButton(f"{'✅ ' if period == 'week' else ''}7 Hari", callback_data="rekap:week")
        ],
        [
            InlineKeyboardButton(f"{'✅ ' if period == 'month' else ''}Bulan Ini", callback_data="rekap:month"),
            InlineKeyboardButton(f"{'✅ ' if period == 'prev_month' else ''}Bulan Lalu", callback_data="rekap:prev_month")
        ],
        [
            InlineKeyboardButton("⚡ Dashboard", callback_data="nav:menu"),
            InlineKeyboardButton("📥 Ekspor CSV", callback_data="export_csv")
        ]
    ])

    # Buat visual donut chart
    chart_buffer = generate_rekap_chart(breakdown, total_expense, period_title=period_title)

    if chart_buffer:
        if is_callback:
            try:
                await message_target.delete()
            except Exception:
                pass
            await message_target.get_bot().send_photo(
                chat_id=user_id,
                photo=chart_buffer,
                caption=teks_laporan,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            await message_target.reply_photo(
                photo=chart_buffer,
                caption=teks_laporan,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
    else:
        if is_callback:
            try:
                await message_target.delete()
            except Exception:
                pass
            await message_target.get_bot().send_message(
                chat_id=user_id,
                text=teks_laporan,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            await message_target.reply_text(
                teks_laporan,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )

async def rekap_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk perintah /rekap."""
    if not update.effective_user or not update.message:
        return
    await send_rekap(update.effective_user.id, update.message, period="month")

async def rekap_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler tombol pengganti rentang waktu rekap real-time."""
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    period = data.split(":")[1] if ":" in data else "month"
    await query.answer(f"Memuat rekap {period}...")
    if query.message:
        await send_rekap(query.from_user.id, query.message, period=period, is_callback=True)

async def riwayat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menampilkan 6 transaksi terakhir lengkap dengan tombol hapus interaktif."""
    user = update.effective_user
    if not user:
        return

    recent = db.get_recent_transactions(user.id, limit=6)
    target = update.callback_query.message if (update.callback_query and update.callback_query.message) else update.message

    if not recent:
        if target:
            await target.reply_text("📜 <i>Belum ada riwayat transaksi yang tersimpan.</i>", parse_mode=ParseMode.HTML)
        return

    lines = ["📜 <b>6 TRANSAKSI TERAKHIR ANDA:</b>\n"]
    buttons = []

    for tx in recent:
        cat_key = tx["category"]
        cat_info = CATEGORIES.get(cat_key, {"label": cat_key.capitalize(), "icon": "📦"})
        icon = cat_info["icon"]
        tipe_mark = "+" if tx["tx_type"] == "income" else "-"
        waktu = tx["created_at"][5:16]  # MM-DD HH:MM

        lines.append(
            f"{icon} <b>{tx['description']}</b>\n"
            f"   Nominal: <code>{tipe_mark}{format_rupiah(tx['amount'])}</code> | {waktu} (ID #{tx['id']})"
        )
        buttons.append([
            InlineKeyboardButton(f"🗑 Hapus #{tx['id']} ({format_rupiah(tx['amount'])})", callback_data=f"del_hist:{tx['id']}")
        ])

    lines.append("\n💡 <i>Klik tombol di bawah untuk menghapus transaksi tertentu:</i>")
    keyboard = InlineKeyboardMarkup(buttons)

    if target:
        await target.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mengatur atau melihat target budget bulanan."""
    user = update.effective_user
    if not user:
        return

    user_id = user.id
    target = update.callback_query.message if (update.callback_query and update.callback_query.message) else update.message
    args = context.args if context else []

    # Jika ada argumen nominal (cth: /budget 3000000 atau /budget 3jt)
    if args:
        raw_budget = " ".join(args)
        amount, _ = parse_amount(raw_budget)
        if amount and amount > 0:
            db.set_user_budget(user_id, amount)
            summary = db.get_period_summary(user_id, "month")
            progress_str = generate_budget_progress(summary["total_expense"], amount)
            
            pesan = (
                f"✅ <b>Target Budget Bulanan Disimpan!</b>\n\n"
                f"Batas Pengeluaran: <b>{format_rupiah(amount)}</b> / bulan.\n\n"
                f"{progress_str or ''}\n\n"
                f"<i>Bot akan otomatis mengingatkan jika pengeluaran Anda sudah melewati batas.</i>"
            )
            if target:
                await target.reply_text(pesan, parse_mode=ParseMode.HTML)
            return

    # Jika tanpa argumen, tampilkan status budget saat ini
    current_budget = db.get_user_budget(user_id)
    summary = db.get_period_summary(user_id, "month")

    if current_budget > 0:
        progress_str = generate_budget_progress(summary["total_expense"], current_budget)
        pesan = (
            f"🎯 <b>STATUS TARGET BUDGET BULANAN</b>\n"
            f"────────────────────────\n"
            f"{progress_str}\n"
            f"────────────────────────\n"
            f"💡 Untuk mengubah batas budget, ketik:\n"
            f"<code>/budget 4jt</code> atau <code>/budget 4000000</code>"
        )
    else:
        pesan = (
            "🎯 <b>Pengaturan Target Budget Bulanan</b>\n\n"
            "Anda belum memasang batas target budget bulanan.\n\n"
            "💡 <b>Cara Pasang:</b>\n"
            "Ketik perintah <code>/budget [nominal]</code>\n"
            "Contoh:\n"
            "• <code>/budget 3000000</code>\n"
            "• <code>/budget 2.5jt</code>"
        )

    if target:
        await target.reply_text(pesan, parse_mode=ParseMode.HTML)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk panduan format input."""
    target = update.callback_query.message if (update.callback_query and update.callback_query.message) else update.message
    pesan = (
        "📖 <b>Panduan Format & Fitur Interaktif:</b>\n\n"
        "1️⃣ <b>Cepat Tanpa Kategori (Tombol Grid):</b>\n"
        "• Cukup ketik angka: <code>50000</code> atau <code>25k</code>\n"
        "• Bot otomatis memunculkan tombol pilihan kategori!\n\n"
        "2️⃣ <b>Format Pengeluaran Standar:</b>\n"
        "• <code>makan 35000</code>\n"
        "• <code>kopi 25k</code>\n"
        "• <code>bensin pertalite 20.000</code>\n"
        "• <code>beli baju di shopee 150rb</code>\n\n"
        "3️⃣ <b>Format Pemasukan:</b>\n"
        "• <code>+gaji 6000000</code> (diawali tanda +)\n"
        "• <code>freelance desain 750k</code>\n\n"
        "4️⃣ <b>Fitur Koreksi & Hapus:</b>\n"
        "• Setiap selesai mencatat ada tombol <b>[ 🗑 Batalkan (Undo) ]</b>.\n"
        "• Atau ketik /riwayat untuk menghapus transaksi sebelumnya."
    )
    if target:
        await target.reply_text(pesan, parse_mode=ParseMode.HTML)

async def kategori_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menampilkan daftar kategori yang tersedia."""
    target = update.callback_query.message if (update.callback_query and update.callback_query.message) else update.message
    lines = ["🏷️ <b>Daftar Kategori Otomatis:</b>\n"]
    for key, data in CATEGORIES.items():
        lines.append(f"{data['icon']} <b>{data['label']}</b> (kata kunci: <i>{key}</i>)")
    lines.append("\n💡 <i>Jika kata yang Anda ketik tidak cocok dengan kategori di atas, otomatis masuk ke 📦 <b>Lain-lain</b>.</i>")
    
    if target:
        await target.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk perintah /export (mengirim file CSV riwayat transaksi)."""
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    transactions = db.get_all_transactions_for_export(user.id)
    if not transactions:
        await chat.send_message(
            "⚠️ Anda belum memiliki riwayat catatan keuangan untuk diekspor.",
            parse_mode=ParseMode.HTML
        )
        return

    csv_buffer = sheets_service.generate_csv_export(transactions)
    filename = f"laporan_keuangan_{user.id}_{datetime.now().strftime('%Y%m%d')}.csv"

    caption = (
        f"📥 <b>Ekspor Data Berhasil!</b>\n"
        f"Total transaksi: <b>{len(transactions)} baris</b>.\n"
        f"File <code>.csv</code> ini dapat dibuka langsung menggunakan Microsoft Excel, Google Sheets, atau aplikasi spreadsheet lainnya."
    )

    await chat.send_document(
        document=csv_buffer,
        filename=filename,
        caption=caption,
        parse_mode=ParseMode.HTML
    )
