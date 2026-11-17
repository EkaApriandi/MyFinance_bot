import io
from typing import Dict, List, Optional
from config import CATEGORIES, format_rupiah

def generate_text_progress_bar(percent: float, length: int = 8) -> str:
    """Membuat visual progress bar berbasis teks Unicode."""
    filled_len = int(round(length * (percent / 100.0)))
    filled_len = max(0, min(length, filled_len))
    bar = "█" * filled_len + "░" * (length - filled_len)
    return f"`{bar}` {percent:.1f}%"

def generate_budget_progress(current_expense: float, monthly_budget: float) -> Optional[str]:
    """Menghasilkan teks status dan bar progres budget bulanan beserta peringatan jika mendekati batas."""
    if monthly_budget <= 0:
        return None

    percent = (current_expense / monthly_budget) * 100.0
    bar = generate_text_progress_bar(percent, length=8)
    
    if percent >= 100.0:
        alert = "\n🚨 <b>Peringatan:</b> Pengeluaran telah melebihi batas budget bulanan Anda!"
    elif percent >= 80.0:
        alert = "\n⚠️ <b>Perhatian:</b> Pengeluaran sudah mencapai 80%+ dari budget bulanan!"
    else:
        alert = ""

    return (
        f"🎯 <b>Target Budget:</b> {format_rupiah(current_expense)} / {format_rupiah(monthly_budget)}\n"
        f"   {bar}{alert}"
    )

def generate_rekap_chart(
    breakdown: List[Dict],
    total_expense: float,
    period_title: str = "Bulan Ini"
) -> Optional[io.BytesIO]:
    """
    Membuat grafik visual Donut Chart pengeluaran per kategori.
    Mengembalikan objek BytesIO berisi gambar PNG siap kirim ke Telegram.
    Jika matplotlib tidak tersedia, fungsi akan mengembalikan None secara aman.
    """
    if not breakdown or total_expense <= 0:
        return None

    try:
        import matplotlib
        matplotlib.use("Agg")  # Mode non-GUI backend
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    try:
        labels = []
        sizes = []
        colors = [
            "#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A",
            "#98D8C8", "#F7DC6F", "#BB8FCE", "#85929E"
        ]

        # Ambil top 6 kategori, sisanya digabung ke 'Lainnya'
        sorted_items = sorted(breakdown, key=lambda x: x["total"], reverse=True)
        top_items = sorted_items[:5]
        other_items = sorted_items[5:]

        for item in top_items:
            cat_key = item["category"]
            cat_info = CATEGORIES.get(cat_key, {"label": cat_key.capitalize()})
            labels.append(f"{cat_info['label']}\n({format_rupiah(item['total'])})")
            sizes.append(item["total"])

        if other_items:
            other_sum = sum(x["total"] for x in other_items)
            labels.append(f"Lainnya\n({format_rupiah(other_sum)})")
            sizes.append(other_sum)

        fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(aspect="equal"))
        
        # Donut Chart
        wedges, _ = ax.pie(
            sizes,
            colors=colors[:len(sizes)],
            startangle=90,
            wedgeprops=dict(width=0.4, edgecolor='white', linewidth=2)
        )

        # Teks di tengah lubang donat
        center_text = f"Total Pengeluaran\n{period_title}\n\n{format_rupiah(total_expense)}"
        ax.text(0, 0, center_text, ha='center', va='center', fontsize=12, fontweight='bold', color='#2C3E50')

        # Legenda di bagian bawah
        ax.legend(
            wedges,
            labels,
            title="Kategori Pengeluaran",
            loc="center left",
            bbox_to_anchor=(1, 0, 0.5, 1),
            fontsize=10,
            title_fontsize=11
        )

        plt.title(f"📊 Ringkasan Pengeluaran ({period_title})", fontsize=14, pad=20, fontweight='bold')
        plt.tight_layout()

        # Simpan ke buffer memory
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buffer.seek(0)
        return buffer
    except Exception as e:
        print(f"[Chart Error] Gagal merender grafik: {e}")
        return None
