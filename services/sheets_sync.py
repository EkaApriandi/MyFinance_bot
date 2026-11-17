import csv
import io
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from config import GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE

class SheetsSyncService:
    """Layanan sinkronisasi transaksi ke Google Sheets dan ekspor CSV."""

    def __init__(self):
        self.is_configured = False
        self.client = None
        self.sheet = None
        self._setup_google_sheets()

    def _setup_google_sheets(self) -> None:
        """Inisialisasi koneksi Google Sheets jika file credentials dan sheet ID tersedia."""
        if not GOOGLE_SHEET_ID or not os.path.exists(GOOGLE_CREDENTIALS_FILE):
            return

        try:
            import gspread
            from google.oauth2.service_account import Credentials

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            credentials = Credentials.from_service_account_file(
                GOOGLE_CREDENTIALS_FILE,
                scopes=scopes
            )
            self.client = gspread.authorize(credentials)
            self.sheet = self.client.open_by_key(GOOGLE_SHEET_ID).sheet1

            # Pastikan header kolom sudah ada
            headers = self.sheet.row_values(1)
            if not headers:
                self.sheet.append_row([
                    "ID Transaksi", "Waktu", "User ID", "Tipe", "Kategori", "Nominal", "Deskripsi"
                ])

            self.is_configured = True
            print("[Google Sheets] Terhubung dan tersinkronisasi.")
        except Exception as e:
            print(f"[Google Sheets Warning] Tidak dapat menghubungkan ke Google Sheets: {e}")
            self.is_configured = False

    def append_transaction(
        self,
        tx_id: int,
        user_id: int,
        tx_type: str,
        category: str,
        amount: float,
        description: str,
        created_at: str
    ) -> bool:
        """Menambahkan baris transaksi baru ke Google Sheets (jika aktif)."""
        if not self.is_configured or not self.sheet:
            return False

        try:
            row_data = [
                tx_id,
                created_at,
                str(user_id),
                tx_type,
                category,
                amount,
                description
            ]
            self.sheet.append_row(row_data)
            return True
        except Exception as e:
            print(f"[Google Sheets Error] Gagal menulis baris ke sheet: {e}")
            return False

    @staticmethod
    def generate_csv_export(transactions: List[Dict[str, Any]]) -> io.BytesIO:
        """Membuat file CSV dari riwayat transaksi untuk dikirimkan ke Telegram."""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header CSV
        writer.writerow(["ID", "Waktu", "Tipe", "Kategori", "Nominal", "Keterangan"])

        for tx in transactions:
            writer.writerow([
                tx.get("id", ""),
                tx.get("created_at", ""),
                tx.get("tx_type", "expense"),
                tx.get("category", ""),
                tx.get("amount", 0),
                tx.get("description", "")
            ])

        bytes_io = io.BytesIO(output.getvalue().encode("utf-8-sig"))
        bytes_io.seek(0)
        return bytes_io
