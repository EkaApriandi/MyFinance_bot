import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from config import DB_PATH

class DatabaseManager:
    """Mengelola koneksi dan operasi database SQLite lokal."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Membuat tabel dan indeks jika belum ada."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    tx_type TEXT NOT NULL DEFAULT 'expense', -- 'expense' atau 'income'
                    category TEXT NOT NULL,
                    amount REAL NOT NULL,
                    description TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_created ON transactions(user_id, created_at)")
            
            # Tabel pengaturan pengguna (target budget bulanan)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    monthly_budget REAL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def set_user_budget(self, user_id: int, budget: float) -> None:
        """Menyimpan batas budget bulanan pengguna."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_settings (user_id, monthly_budget, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    monthly_budget = excluded.monthly_budget,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, budget))
            conn.commit()

    def get_user_budget(self, user_id: int) -> float:
        """Mengambil batas budget bulanan pengguna (default: 0 jika belum disetel)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT monthly_budget FROM user_settings WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return float(row["monthly_budget"]) if row and row["monthly_budget"] else 0.0

    def add_transaction(
        self,
        user_id: int,
        tx_type: str,
        category: str,
        amount: float,
        description: str,
        created_at: Optional[str] = None
    ) -> int:
        """Menyimpan transaksi baru dan mengembalikan ID baris yang dibuat."""
        if not created_at:
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO transactions (user_id, tx_type, category, amount, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, tx_type, category, amount, description, created_at))
            conn.commit()
            return cursor.lastrowid or 0

    def delete_transaction(self, tx_id: int, user_id: int) -> bool:
        """Menghapus transaksi tertentu berdasarkan ID dan User ID (untuk fitur Undo / Hapus)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM transactions 
                WHERE id = ? AND user_id = ?
            """, (tx_id, user_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_transaction(self, tx_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Mendapatkan data satu transaksi."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM transactions 
                WHERE id = ? AND user_id = ?
            """, (tx_id, user_id))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_recent_transactions(self, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Mendapatkan daftar transaksi terakhir milik pengguna."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM transactions
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            """, (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    def _resolve_period_dates(self, period: str) -> Tuple[str, str, str]:
        """Menentukan rentang tanggal (start_str, end_str, label) berdasarkan kode periode."""
        now = datetime.now()
        if period == "today":
            start = now.strftime("%Y-%m-%d 00:00:00")
            end = now.strftime("%Y-%m-%d 23:59:59")
            label = "Hari Ini"
        elif period == "week":
            start = (now - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00")
            end = now.strftime("%Y-%m-%d 23:59:59")
            label = "7 Hari Terakhir"
        elif period == "prev_month":
            first_this_month = now.replace(day=1)
            last_prev_month = first_this_month - timedelta(days=1)
            first_prev_month = last_prev_month.replace(day=1)
            start = first_prev_month.strftime("%Y-%m-%d 00:00:00")
            end = last_prev_month.strftime("%Y-%m-%d 23:59:59")
            label = first_prev_month.strftime("%B %Y")
        else:  # default 'month'
            first_day = now.replace(day=1)
            start = first_day.strftime("%Y-%m-%d 00:00:00")
            end = now.strftime("%Y-%m-%d 23:59:59")
            label = now.strftime("%B %Y")
        return start, end, label

    def get_period_summary(self, user_id: int, period: str = "month") -> Dict[str, Any]:
        """Menghitung ringkasan transaksi berdasarkan periode dinamis (today, week, month, prev_month)."""
        start_date, end_date, title = self._resolve_period_dates(period)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total Pengeluaran
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM transactions
                WHERE user_id = ? AND tx_type = 'expense' AND created_at >= ? AND created_at <= ?
            """, (user_id, start_date, end_date))
            total_expense = cursor.fetchone()[0]

            # Total Pemasukan
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM transactions
                WHERE user_id = ? AND tx_type = 'income' AND created_at >= ? AND created_at <= ?
            """, (user_id, start_date, end_date))
            total_income = cursor.fetchone()[0]

            # Rincian Pengeluaran per Kategori
            cursor.execute("""
                SELECT category, SUM(amount) as cat_total, COUNT(id) as count
                FROM transactions
                WHERE user_id = ? AND tx_type = 'expense' AND created_at >= ? AND created_at <= ?
                GROUP BY category
                ORDER BY cat_total DESC
            """, (user_id, start_date, end_date))
            category_breakdown = [
                {"category": row["category"], "total": row["cat_total"], "count": row["count"]}
                for row in cursor.fetchall()
            ]

            return {
                "period": period,
                "title": title,
                "start_date": start_date,
                "end_date": end_date,
                "total_expense": total_expense,
                "total_income": total_income,
                "balance": total_income - total_expense,
                "breakdown": category_breakdown
            }

    def get_all_transactions_for_export(self, user_id: int) -> List[Dict[str, Any]]:
        """Mengambil seluruh data transaksi pengguna untuk keperluan ekspor CSV."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, created_at, tx_type, category, amount, description
                FROM transactions
                WHERE user_id = ?
                ORDER BY created_at ASC
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]
