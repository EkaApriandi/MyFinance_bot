from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import CATEGORIES, format_rupiah
from database.db_manager import DatabaseManager
from services.parser import parse_financial_text
from services.sheets_sync import SheetsSyncService
from handlers.commands import (
    rekap_command,
    send_rekap,
    export_command,
    help_command,
    kategori_command,
    menu_command,
    riwayat_command,
    budget_command
)

db = DatabaseManager()
sheets_service = SheetsSyncService()

def build_category_picker_keyboard(amount: float) -> InlineKeyboardMarkup:
    amount_int = int(amount)
    buttons = [
        [
            InlineKeyboardButton("🍔 Makanan", callback_data=f"cat_pick:makanan:{amount_int}"),
            InlineKeyboardButton("🚗 Transport", callback_data=f"cat_pick:transport:{amount_int}")
        ],
        [
            InlineKeyboardButton("🛍️ Belanja", callback_data=f"cat_pick:belanja:{amount_int}"),
            InlineKeyboardButton("💡 Tagihan", callback_data=f"cat_pick:tagihan:{amount_int}")
        ],
        [
            InlineKeyboardButton("🎮 Hiburan", callback_data=f"cat_pick:hiburan:{amount_int}"),
            InlineKeyboardButton("💊 Kesehatan", callback_data=f"cat_pick:kesehatan:{amount_int}")
        ],
        [
            InlineKeyboardButton("💰 Pemasukan", callback_data=f"cat_pick:pemasukan:{amount_int}"),
            InlineKeyboardButton("📦 Lain-lain", callback_data=f"cat_pick:lainnya:{amount_int}")
        ],
        [
            InlineKeyboardButton("Batal", callback_data="cat_cancel")
        ]
    ]
    return InlineKeyboardMarkup(buttons)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    user_id = update.effective_user.id

    # Navigasi cepat dari Reply Keyboard
    nav_map = {
        "⚡ Dashboard": menu_command,
        "📊 Rekap": rekap_command,
        "📜 Riwayat": riwayat_command,
        "🎯 Budget": budget_command,
        "📥 Ekspor CSV": export_command,
        "💡 Bantuan": help_command
    }
    if text in nav_map:
        await nav_map[text](update, context)
        return

    result = parse_financial_text(text)
    if not result.get("success"):
        await update.message.reply_text(
            f"<i>{result.get('error')}</i>\n\n"
            f"Contoh format:\n"
            f"• <code>makan 25k</code>\n"
            f"• <code>50000</code>\n"
            f"• <code>+gaji 5jt</code>",
            parse_mode=ParseMode.HTML
        )
        return

    # User hanya mengetik angka -> Tampilkan pemilih kategori
    if result.get("is_amount_only"):
        amount = result["amount"]
        await update.message.reply_text(
            f"Nominal <b>{format_rupiah(amount)}</b>. Pilih kategori:",
            parse_mode=ParseMode.HTML,
            reply_markup=build_category_picker_keyboard(amount)
        )
        return

    tx_type = result["type"]
    category_key = result["category_key"]
    category_label = result["category_label"]
    category_icon = result["category_icon"]
    amount = result["amount"]
    description = result["description"]
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    tx_id = db.add_transaction(
        user_id=user_id,
        tx_type=tx_type,
        category=category_key,
        amount=amount,
        description=description,
        created_at=created_at
    )

    sheets_service.append_transaction(
        tx_id=tx_id,
        user_id=user_id,
        tx_type=tx_type,
        category=category_label,
        amount=amount,
        description=description,
        created_at=created_at
    )

    # Cek batas budget
    budget = db.get_user_budget(user_id)
    summary = db.get_period_summary(user_id, "month")
    budget_alert = ""
    if tx_type == "expense" and budget > 0:
        pct = (summary["total_expense"] / budget) * 100.0
        if pct >= 100.0:
            budget_alert = "\n⚠️ <i>Batas budget bulanan telah terlampaui!</i>"
        elif pct >= 80.0:
            budget_alert = f"\n⚠️ <i>Pengeluaran telah mencapai {pct:.0f}% dari budget bulanan.</i>"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Batalkan", callback_data=f"undo:{tx_id}")]
    ])

    tipe_label = "Pemasukan" if tx_type == "income" else "Pengeluaran"
    waktu = datetime.now().strftime("%d %b, %H:%M")

    balasan = (
        f"<b>Catatan Disimpan</b>\n\n"
        f"{category_icon} <b>{category_label}</b> · {tipe_label}\n"
        f"💰 <code>{format_rupiah(amount)}</code> · {description}\n"
        f"🕒 {waktu}{budget_alert}"
    )

    await update.message.reply_text(balasan, parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def interactive_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    user_id = query.from_user.id

    if data.startswith("cat_pick:"):
        parts = data.split(":")
        cat_key = parts[1]
        amount = float(parts[2])
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        tx_type = "income" if cat_key == "pemasukan" else "expense"
        cat_info = CATEGORIES.get(cat_key, CATEGORIES["lainnya"])
        description = cat_info["label"]

        tx_id = db.add_transaction(
            user_id=user_id,
            tx_type=tx_type,
            category=cat_key,
            amount=amount,
            description=description,
            created_at=created_at
        )

        sheets_service.append_transaction(
            tx_id=tx_id,
            user_id=user_id,
            tx_type=tx_type,
            category=cat_info["label"],
            amount=amount,
            description=description,
            created_at=created_at
        )

        await query.answer("Disimpan")

        tipe_label = "Pemasukan" if tx_type == "income" else "Pengeluaran"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Batalkan", callback_data=f"undo:{tx_id}")]
        ])

        balasan = (
            f"<b>Catatan Disimpan</b>\n\n"
            f"{cat_info['icon']} <b>{cat_info['label']}</b> · {tipe_label}\n"
            f"💰 <code>{format_rupiah(amount)}</code>\n"
            f"🕒 {datetime.now().strftime('%d %b, %H:%M')}"
        )
        if query.message:
            await query.message.edit_text(balasan, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    elif data == "cat_cancel":
        await query.answer("Dibatalkan")
        if query.message:
            await query.message.edit_text("<i>Pencatatan dibatalkan.</i>", parse_mode=ParseMode.HTML)

    elif data.startswith("undo:"):
        try:
            tx_id = int(data.split(":")[1])
        except ValueError:
            await query.answer("ID tidak valid.", show_alert=True)
            return

        tx_data = db.get_transaction(tx_id, user_id)
        if not tx_data:
            await query.answer("Transaksi tidak ditemukan.", show_alert=True)
            if query.message:
                await query.message.edit_reply_markup(reply_markup=None)
            return

        if db.delete_transaction(tx_id, user_id):
            await query.answer("Transaksi dibatalkan.")
            if query.message:
                await query.message.edit_text(
                    f"🗑️ <i>Transaksi {tx_data['description']} ({format_rupiah(tx_data['amount'])}) telah dihapus.</i>",
                    parse_mode=ParseMode.HTML
                )
        else:
            await query.answer("Gagal membatalkan.", show_alert=True)

    elif data.startswith("del_hist:"):
        try:
            tx_id = int(data.split(":")[1])
        except ValueError:
            await query.answer("ID tidak valid.", show_alert=True)
            return

        if db.delete_transaction(tx_id, user_id):
            await query.answer(f"Transaksi #{tx_id} dihapus.")
            fake_update = Update(update.update_id, callback_query=query)
            await riwayat_command(fake_update, context)
        else:
            await query.answer("Transaksi tidak ditemukan.", show_alert=True)

    elif data.startswith("nav:"):
        target = data.split(":")[1]
        await query.answer()
        fake_update = Update(update.update_id, callback_query=query)
        nav_actions = {
            "menu": lambda: menu_command(fake_update, context),
            "rekap": lambda: send_rekap(user_id, query.message, period="month", is_callback=True) if query.message else None,
            "riwayat": lambda: riwayat_command(fake_update, context),
            "budget": lambda: budget_command(fake_update, context),
            "kategori": lambda: kategori_command(fake_update, context),
            "help": lambda: help_command(fake_update, context)
        }
        if target in nav_actions and nav_actions[target]:
            res = nav_actions[target]()
            if res:
                await res

    elif data == "export_csv":
        await query.answer()
        fake_update = Update(update.update_id, message=query.message, callback_query=query)
        await export_command(fake_update, context)
