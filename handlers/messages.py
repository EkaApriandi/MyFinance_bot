from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import CATEGORIES, format_rupiah
from database.db_manager import DatabaseManager
from services.parser import parse_financial_text
from services.sheets_sync import SheetsSyncService
from services.visualizer import generate_budget_progress
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
    """Membuat grid tombol interaktif untuk memilih kategori saat pengguna hanya mengetik nominal."""
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
            InlineKeyboardButton("❌ Batalkan", callback_data="cat_cancel")
        ]
    ]
    return InlineKeyboardMarkup(buttons)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk pesan teks biasa yang masuk dari pengguna."""
    if not update.effective_user or not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()
    user_id = update.effective_user.id

    # Cek apakah teks berasal dari Reply Keyboard Menu
    if user_text in ["⚡ Menu Dashboard", "Dashboard"]:
        await menu_command(update, context)
        return
    elif user_text in ["📊 Rekap Keuangan", "📊 Rekap Bulan Ini"]:
        await rekap_command(update, context)
        return
    elif user_text in ["📜 Riwayat Terakhir", "📜 Riwayat Catatan"]:
        await riwayat_command(update, context)
        return
    elif user_text in ["🎯 Atur Budget"]:
        await budget_command(update, context)
        return
    elif user_text in ["📥 Ekspor CSV"]:
        await export_command(update, context)
        return
    elif user_text in ["💡 Panduan & Format", "💡 Format Input"]:
        await help_command(update, context)
        return
    elif user_text in ["🏷️ Daftar Kategori"]:
        await kategori_command(update, context)
        return

    # Parsing teks keuangan
    result = parse_financial_text(user_text)

    if not result.get("success"):
        # Jika bukan format keuangan, berikan panduan santun
        await update.message.reply_text(
            f"🤔 {result.get('error')}\n\n"
            f"💡 <i>Contoh penulisan cepat:</i>\n"
            f"• <code>makan 25000</code> atau <code>kopi 25k</code>\n"
            f"• <b>Atau ketik nominal saja:</b> <code>50000</code>\n"
            f"• <code>+gaji 5000000</code> untuk pemasukan",
            parse_mode=ParseMode.HTML
        )
        return

    # JIKA PENGGUNA HANYA KETIK NOMINAL (Contoh: "50000" atau "25k")
    # Tampilkan Grid Tombol Kategori Cerdas!
    if result.get("is_amount_only"):
        amount = result["amount"]
        keyboard = build_category_picker_keyboard(amount)
        await update.message.reply_text(
            f"💰 Nominal <b>{format_rupiah(amount)}</b> terdeteksi!\n\n"
            f"Silakan pilih kategori pengeluaran Anda dengan sekali tap:",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        return

    # JIKA LENGKAP DENGAN KETERANGAN (Contoh: "makan 25000")
    tx_type = result["type"]
    category_key = result["category_key"]
    category_label = result["category_label"]
    category_icon = result["category_icon"]
    amount = result["amount"]
    description = result["description"]
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Simpan ke SQLite
    tx_id = db.add_transaction(
        user_id=user_id,
        tx_type=tx_type,
        category=category_key,
        amount=amount,
        description=description,
        created_at=created_at
    )

    # 2. Sinkronisasi ke Google Sheets (jika aktif)
    sheets_service.append_transaction(
        tx_id=tx_id,
        user_id=user_id,
        tx_type=tx_type,
        category=category_label,
        amount=amount,
        description=description,
        created_at=created_at
    )

    # 3. Cek Status Budget
    budget = db.get_user_budget(user_id)
    summary = db.get_period_summary(user_id, "month")
    budget_alert = ""
    if tx_type == "expense" and budget > 0:
        percent = (summary["total_expense"] / budget) * 100.0
        if percent >= 100.0:
            budget_alert = "\n\n🚨 <b>Peringatan:</b> Pengeluaran Anda telah melebihi batas budget bulanan!"
        elif percent >= 80.0:
            budget_alert = f"\n\n⚠️ <b>Perhatian:</b> Total pengeluaran bulan ini sudah mencapai {percent:.0f}% dari target budget!"

    # 4. Buat Tombol Inline Undo
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Batalkan Catatan (Undo)", callback_data=f"undo:{tx_id}")]
    ])

    tipe_badge = "🟢 PEMASUKAN" if tx_type == "income" else "🔴 PENGELUARAN"
    waktu_str = datetime.now().strftime("%d %b %Y, %H:%M WIB")

    balasan = (
        f"✅ <b>Catatan Berhasil Disimpan!</b>\n"
        f"────────────────────────\n"
        f"🏷 <b>Jenis:</b> {tipe_badge}\n"
        f"{category_icon} <b>Kategori:</b> {category_label}\n"
        f"💰 <b>Nominal:</b> <code>{format_rupiah(amount)}</code>\n"
        f"📝 <b>Keterangan:</b> <i>{description}</i>\n"
        f"📅 <b>Waktu:</b> {waktu_str}"
        f"{budget_alert}\n"
        f"────────────────────────\n"
        f"💡 <i>Salah catat? Klik tombol di bawah untuk membatalkan.</i>"
    )

    await update.message.reply_text(
        balasan,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )

async def interactive_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler terpusat untuk semua aksi interaktif tombol Telegram."""
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    user_id = query.from_user.id

    # 1. AKSI PILIH KATEGORI CEPAT DARI TOMBOL GRID
    if data.startswith("cat_pick:"):
        parts = data.split(":")
        cat_key = parts[1]
        amount = float(parts[2])
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        tx_type = "income" if cat_key == "pemasukan" else "expense"
        cat_info = CATEGORIES.get(cat_key, CATEGORIES["lainnya"])
        description = cat_info["label"]

        # Simpan transaksi
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

        await query.answer("✅ Transaksi disimpan!")

        # Ganti pesan menjadi kartu konfirmasi dengan tombol Undo
        tipe_badge = "🟢 PEMASUKAN" if tx_type == "income" else "🔴 PENGELUARAN"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Batalkan Catatan (Undo)", callback_data=f"undo:{tx_id}")]
        ])

        balasan = (
            f"✅ <b>Catatan Berhasil Disimpan!</b>\n"
            f"────────────────────────\n"
            f"🏷 <b>Jenis:</b> {tipe_badge}\n"
            f"{cat_info['icon']} <b>Kategori:</b> {cat_info['label']}\n"
            f"💰 <b>Nominal:</b> <code>{format_rupiah(amount)}</code>\n"
            f"📅 <b>Waktu:</b> {datetime.now().strftime('%d %b %Y, %H:%M WIB')}\n"
            f"────────────────────────\n"
            f"💡 <i>Klik tombol di bawah untuk membatalkan jika salah.</i>"
        )
        if query.message:
            await query.message.edit_text(balasan, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    # 2. BATALKAN PILIH KATEGORI
    elif data == "cat_cancel":
        await query.answer("Dibatalkan")
        if query.message:
            await query.message.edit_text("❌ <i>Pencatatan dibatalkan.</i>", parse_mode=ParseMode.HTML, reply_markup=None)

    # 3. TOMBOL UNDO DARI NOTIFIKASI BARU
    elif data.startswith("undo:"):
        try:
            tx_id = int(data.split(":")[1])
        except ValueError:
            await query.answer("ID Transaksi tidak valid.", show_alert=True)
            return

        tx_data = db.get_transaction(tx_id, user_id)
        if not tx_data:
            await query.answer("Transaksi ini sudah pernah dibatalkan atau tidak ditemukan.", show_alert=True)
            if query.message:
                await query.message.edit_reply_markup(reply_markup=None)
            return

        sukses = db.delete_transaction(tx_id, user_id)
        if sukses:
            await query.answer("✅ Transaksi berhasil dibatalkan!", show_alert=True)
            nom_formatted = format_rupiah(tx_data['amount'])
            if query.message:
                await query.message.edit_text(
                    f"🗑️ <b>Transaksi Dibatalkan!</b>\n"
                    f"Catatan <i>{tx_data['description']}</i> ({nom_formatted}) telah dihapus dari pembukuan.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=None
                )
        else:
            await query.answer("Gagal membatalkan transaksi.", show_alert=True)

    # 4. HAPUS TRANSAKSI DARI RIWAYAT (/riwayat)
    elif data.startswith("del_hist:"):
        try:
            tx_id = int(data.split(":")[1])
        except ValueError:
            await query.answer("ID tidak valid.", show_alert=True)
            return

        sukses = db.delete_transaction(tx_id, user_id)
        if sukses:
            await query.answer(f"✅ Transaksi #{tx_id} berhasil dihapus!", show_alert=True)
            # Muat ulang riwayat
            fake_update = Update(update.update_id, callback_query=query)
            await riwayat_command(fake_update, context)
        else:
            await query.answer("Transaksi tidak ditemukan.", show_alert=True)

    # 5. NAVIGASI DARI DASHBOARD (/menu)
    elif data.startswith("nav:"):
        target = data.split(":")[1]
        await query.answer()
        fake_update = Update(update.update_id, callback_query=query)
        if target == "menu":
            await menu_command(fake_update, context)
        elif target == "rekap":
            if query.message:
                await send_rekap(user_id, query.message, period="month", is_callback=True)
        elif target == "riwayat":
            await riwayat_command(fake_update, context)
        elif target == "budget":
            await budget_command(fake_update, context)
        elif target == "kategori":
            await kategori_command(fake_update, context)
        elif target == "help":
            await help_command(fake_update, context)

    # 6. EKSPOR CSV DARI TOMBOL INLINE
    elif data == "export_csv":
        await query.answer()
        fake_update = Update(update.update_id, message=query.message, callback_query=query)
        await export_command(fake_update, context)
