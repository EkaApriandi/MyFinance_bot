# 💰 Telegram Personal Finance Tracker Bot (Interactive Edition)

Bot Telegram pintar dan interaktif untuk mencatat pengeluaran dan pemasukan harian secara instan, visual, dan fleksibel. Dilengkapi dashboard ringkasan saldo, diagram lingkaran visual (*donut chart*), tombol kategori cepat (*Smart Tap*), target batas budget bulanan, tombol Undo, serta riwayat interaktif.

---

## 🌟 Fitur-Fitur Interaktif Unggulan

1. **⚡ Smart Category Tap Grid (Ketik Angka Saja):**
   - Malas mengetik deskripsi? Cukup ketik nominalnya saja (misal: `50000` atau `25k`).
   - Bot otomatis memunculkan **Grid Tombol Kategori** (🍔 Makanan, 🚗 Transport, 🛍️ Belanja, 💡 Tagihan, dll.). Cukup *tap* 1 tombol, transaksi langsung tersimpan!
2. **🎛️ Dashboard Saldo & Kontrol (`/menu`):**
   - Menampilkan ringkasan pemasukan, pengeluaran, sisa kas, progres budget bulanan, dan tombol navigasi cepat.
3. **📊 Laporan Donut Chart & Filter Periode Real-Time (`/rekap`):**
   - Diagram donat (*donut chart*) beresolusi tinggi yang digambar menggunakan `matplotlib`.
   - Tombol ganti rentang waktu secara instan: **`[ Hari Ini ]`**, **`[ 7 Hari ]`**, **`[ Bulan Ini ]`**, **`[ Bulan Lalu ]`** tanpa perlu ketik ulang.
4. **🎯 Sistem Target Budget Bulanan (`/budget`):**
   - Pasang batas anggaran bulanan (contoh: `/budget 3000000` atau `/budget 3jt`).
   - Menampilkan visual progres bar budget.
   - Peringatan otomatis jika pengeluaran telah mencapai **80%** atau **melebihi 100%** dari anggaran.
5. **📜 Interactive History Manager (`/riwayat`):**
   - Menampilkan daftar 6 transaksi terakhir Anda dengan tombol **`[ 🗑 Hapus #ID ]`** pada tiap baris.
6. **🗑️ Tombol Undo Instan:**
   - Setiap transaksi yang baru dicatat menyertakan tombol **`[ 🗑 Batalkan Catatan (Undo) ]`** untuk koreksi instan.
7. **📥 Ekspor CSV Siap Excel (`/export`):**
   - Mengunduh seluruh riwayat pembukuan dalam file `.csv`.

---

## 📋 Daftar Perintah Bot

| Perintah | Deskripsi |
| :--- | :--- |
| `/menu` | Membuka Dashboard ringkasan keuangan & navigasi tombol |
| `/rekap` | Laporan Donut Chart visual dengan tombol pemilih periode |
| `/riwayat` | Melihat riwayat transaksi terakhir & tombol hapus per transaksi |
| `/budget [nominal]` | Mengatur atau melihat status target batas budget bulanan |
| `/export` | Mengunduh file spreadsheet `.csv` |
| `/kategori` | Melihat daftar kategori pengeluaran dan kata kuncinya |
| `/help` | Menampilkan panduan format teks dan fitur |

---

## 🚀 Panduan Menjalankan

1. Pastikan token BotFather Anda sudah ada di file `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=8924812566:AAHQt0OVjixqGBAwXYKwwitKwtMRAFCLN6c
   ```
2. Jalankan bot di terminal:
   ```powershell
   python main.py
   ```
3. Buka bot di Telegram: **[@DailyEconomy_Tracker_bot](https://t.me/DailyEconomy_Tracker_bot)** dan ketik `/menu` atau coba ketik `50000`!
