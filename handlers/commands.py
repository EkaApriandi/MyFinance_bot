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

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("⚡ Dashboard"), KeyboardButton("📊 Rekap")],
        [KeyboardButton("📜 Riwayat"), KeyboardButton("🎯 Budget")],
        [KeyboardButton("📥 Ekspor CSV"), KeyboardButton("💡 Bantuan")]
    ],
    resize_keyboard=True
)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    name = user.first_name if user else "Kawan"

    pesan = (
        f"<b>Halo, {name}.</b>\n\n"
        f"Ketik transaksi Anda langsung di chat:\n"
        f"• <code>makan 25k</code>\n"
        f"• <code>bensin 20rb</code>\n"
        f"• <code>+gaji 5jt</code> (pemasukan)\n\n"
        f"Atau ketik nominal saja (contoh: <code>50000</code>) untuk memilih kategori lewat tombol."
    )

    if update.message:
        await update.message.reply_text(pesan, parse_mode=ParseMode.HTML, reply_markup=MAIN_KEYBOARD)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    summary = db.get_period_summary(user.id, period="month")
    budget = db.get_user_budget(user.id)
    expense = summary["total_expense"]
    income = summary["total_income"]
    balance = summary["balance"]
    month_name = summary["title"]

    lines = [
        f"<b>Dashboard · {month_name}</b>\n",
        f"📈 Masuk:  <code>{format_rupiah(income)}</code>",
        f"📉 Keluar: <code>{format_rupiah(expense)}</code>",
        f"💰 Saldo:  <code>{format_rupiah(balance)}</code>\n"
    ]

    budget_info = generate_budget_progress(expense, budget)
    if budget_info:
        lines.append(budget_info + "\n")
    else:
        lines.append("<i>Batas budget belum disetel (/budget [nominal]).</i>\n")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Rekap Grafik", callback_data="nav:rekap"),
            InlineKeyboardButton("📜 Riwayat", callback_data="nav:riwayat")
        ],
        [
            InlineKeyboardButton("🎯 Atur Budget", callback_data="nav:budget"),
            InlineKeyboardButton("📥 Ekspor CSV", callback_data="export_csv")
        ],
        [
            InlineKeyboardButton("🏷️ Kategori", callback_data="nav:kategori"),
            InlineKeyboardButton("💡 Panduan", callback_data="nav:help")
        ]
    ])

    text = "\n".join(lines)
    if update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    elif update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def send_rekap(user_id: int, message_target, period: str = "month", is_callback: bool = False):
    summary = db.get_period_summary(user_id, period=period)
    expense = summary["total_expense"]
    income = summary["total_income"]
    balance = summary["balance"]
    breakdown = summary["breakdown"]
    title = summary["title"]

    lines = [
        f"<b>Rekap · {title}</b>\n",
        f"Masuk:  <code>{format_rupiah(income)}</code>",
        f"Keluar: <code>{format_rupiah(expense)}</code>",
        f"Saldo:  <code>{format_rupiah(balance)}</code>\n"
    ]

    if not breakdown:
        lines.append("<i>Belum ada pengeluaran pada periode ini.</i>")
    else:
        lines.append("<b>Rincian Kategori:</b>")
        for item in breakdown:
            cat_info = CATEGORIES.get(item["category"], {"label": item["category"].capitalize(), "icon": "📁"})
            pct = (item["total"] / expense * 100.0) if expense > 0 else 0
            bar = generate_text_progress_bar(pct, length=6)
            lines.append(f"{cat_info['icon']} {cat_info['label']}: {format_rupiah(item['total'])}\n   {bar}")

    text = "\n".join(lines)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{'• ' if period == 'today' else ''}Hari Ini", callback_data="rekap:today"),
            InlineKeyboardButton(f"{'• ' if period == 'week' else ''}7 Hari", callback_data="rekap:week")
        ],
        [
            InlineKeyboardButton(f"{'• ' if period == 'month' else ''}Bulan Ini", callback_data="rekap:month"),
            InlineKeyboardButton(f"{'• ' if period == 'prev_month' else ''}Bulan Lalu", callback_data="rekap:prev_month")
        ],
        [
            InlineKeyboardButton("⚡ Dashboard", callback_data="nav:menu"),
            InlineKeyboardButton("📥 Ekspor CSV", callback_data="export_csv")
        ]
    ])

    chart = generate_rekap_chart(breakdown, expense, period_title=title)

    if chart:
        if is_callback:
            try:
                await message_target.delete()
            except Exception:
                pass
            await message_target.get_bot().send_photo(
                chat_id=user_id,
                photo=chart,
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            await message_target.reply_photo(
                photo=chart,
                caption=text,
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
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            await message_target.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def rekap_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    await send_rekap(update.effective_user.id, update.message, period="month")

async def rekap_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    period = query.data.split(":")[1] if ":" in query.data else "month"
    await query.answer()
    if query.message:
        await send_rekap(query.from_user.id, query.message, period=period, is_callback=True)

async def riwayat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    recent = db.get_recent_transactions(user.id, limit=6)
    target = update.callback_query.message if (update.callback_query and update.callback_query.message) else update.message

    if not recent:
        if target:
            await target.reply_text("<i>Belum ada riwayat transaksi.</i>", parse_mode=ParseMode.HTML)
        return

    lines = ["<b>Riwayat Transaksi Terakhir:</b>\n"]
    buttons = []

    for tx in recent:
        cat_info = CATEGORIES.get(tx["category"], {"label": tx["category"].capitalize(), "icon": "📦"})
        sign = "+" if tx["tx_type"] == "income" else "-"
        waktu = tx["created_at"][5:16]

        lines.append(
            f"{cat_info['icon']} <b>{tx['description']}</b>\n"
            f"   <code>{sign}{format_rupiah(tx['amount'])}</code> · {waktu}"
        )
        buttons.append([
            InlineKeyboardButton(f"Hapus #{tx['id']} ({format_rupiah(tx['amount'])})", callback_data=f"del_hist:{tx['id']}")
        ])

    keyboard = InlineKeyboardMarkup(buttons)
    if target:
        await target.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    target = update.callback_query.message if (update.callback_query and update.callback_query.message) else update.message
    args = context.args if context else []

    if args:
        amount, _ = parse_amount(" ".join(args))
        if amount and amount > 0:
            db.set_user_budget(user.id, amount)
            summary = db.get_period_summary(user.id, "month")
            progress_str = generate_budget_progress(summary["total_expense"], amount)
            pesan = (
                f"<b>Budget Bulanan Disimpan</b>\n\n"
                f"Batas: <b>{format_rupiah(amount)}</b>/bulan\n\n"
                f"{progress_str or ''}"
            )
            if target:
                await target.reply_text(pesan, parse_mode=ParseMode.HTML)
            return

    current = db.get_user_budget(user.id)
    summary = db.get_period_summary(user.id, "month")

    if current > 0:
        progress_str = generate_budget_progress(summary["total_expense"], current)
        pesan = (
            f"<b>Status Budget Bulanan</b>\n\n"
            f"{progress_str}\n\n"
            f"<i>Ubah batas dengan: <code>/budget 4jt</code></i>"
        )
    else:
        pesan = (
            "<b>Target Budget Bulanan</b>\n\n"
            "Belum ada batas budget.\n"
            "Setel dengan: <code>/budget 3jt</code> atau <code>/budget 3000000</code>"
        )

    if target:
        await target.reply_text(pesan, parse_mode=ParseMode.HTML)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = update.callback_query.message if (update.callback_query and update.callback_query.message) else update.message
    pesan = (
        "<b>Panduan Input:</b>\n\n"
        "• <b>Pengeluaran:</b> <code>makan 25k</code>, <code>bensin 20rb</code>, <code>kopi 18.000</code>\n"
        "• <b>Nominal saja:</b> <code>50000</code> (pilih kategori via tombol)\n"
        "• <b>Pemasukan:</b> <code>+gaji 5jt</code>, <code>freelance 750k</code>\n\n"
        "• <b>Koreksi:</b> Klik tombol Batalkan pada transaksi, atau cek /riwayat."
    )
    if target:
        await target.reply_text(pesan, parse_mode=ParseMode.HTML)

async def kategori_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = update.callback_query.message if (update.callback_query and update.callback_query.message) else update.message
    lines = ["<b>Daftar Kategori:</b>\n"]
    for key, data in CATEGORIES.items():
        lines.append(f"{data['icon']} <b>{data['label']}</b> (<code>{key}</code>)")
    
    if target:
        await target.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    transactions = db.get_all_transactions_for_export(user.id)
    if not transactions:
        await chat.send_message("<i>Belum ada data untuk diekspor.</i>", parse_mode=ParseMode.HTML)
        return

    csv_buffer = sheets_service.generate_csv_export(transactions)
    filename = f"transaksi_{user.id}_{datetime.now().strftime('%Y%m%d')}.csv"

    await chat.send_document(
        document=csv_buffer,
        filename=filename,
        caption=f"<b>Ekspor Selesai</b> ({len(transactions)} baris).",
        parse_mode=ParseMode.HTML
    )
