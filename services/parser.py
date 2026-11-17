import re
from typing import Any, Dict, Optional, Tuple
from config import CATEGORIES

# Keyword dictionary untuk pencocokan kategori otomatis yang cerdas
KEYWORD_MAPPINGS = {
    "makanan": [
        "makan", "minum", "kopi", "cafe", "kafe", "resto", "warteg", "bakso", "mie",
        "nasi", "sarapan", "lunch", "dinner", "snack", "jajan", "ayam", "sate", "pizza",
        "burger", "boba", "teh", "susu", "roti", "gofood", "grabfood", "shopeefood"
    ],
    "transport": [
        "transport", "bensin", "pertalite", "pertamax", "solar", "gojek", "goride", "gocar",
        "grab", "ojol", "parkir", "tol", "kereta", "krl", "mrt", "lrt", "busway", "transjakarta",
        "taksi", "angkot", "service", "bengkel", "cuci motor", "cuci mobil", "tambal ban"
    ],
    "belanja": [
        "belanja", "baju", "kaos", "celana", "sepatu", "tas", "indomaret", "alfamart",
        "supermarket", "minimarket", "mall", "shopee", "tokopedia", "tokped", "lazada",
        "tiktok shop", "skincare", "sabun", "shampo", "odol", "parfum"
    ],
    "tagihan": [
        "tagihan", "listrik", "pln", "token", "air", "pdam", "wifi", "indihome", "biznet",
        "firstmedia", "pulsa", "kuota", "paket data", "sewa", "kos", "kost", "kontrakan",
        "iuran", "bpjs", "asuransi", "cicilan", "kartu kredit", "pajak"
    ],
    "hiburan": [
        "hiburan", "nonton", "bioskop", "cinema", "xxi", "cgv", "game", "steam", "topup",
        "diamond", "spotify", "netflix", "youtube", "disney", "liburan", "hotel", "wisata",
        "tiket", "karaoke"
    ],
    "kesehatan": [
        "kesehatan", "obat", "dokter", "apotek", "vitamin", "klinik", "rumah sakit", "rs",
        "periksa", "tes lab", "masker", "terapi", "pijat"
    ],
    "pendidikan": [
        "buku", "kursus", "kuliah", "sekolah", "spp", "udemy", "course", "les", "seminar",
        "workshop", "alat tulis", "fotocopy"
    ],
    "pemasukan": [
        "gaji", "salary", "bonus", "freelance", "proyek", "project", "penjualan", "omzet",
        "transfer masuk", "dividen", "cashback", "refund", "pemasukan", "income"
    ]
}

def parse_amount(text: str) -> Tuple[Optional[float], str]:
    """
    Mengekstrak nilai nominal angka dari teks input.
    Mendukung format:
    - 25000, 25.000, 25,000
    - 25k, 25rb, 25 ribu
    - 1.5jt, 1.5 juta, 1,5jt, 2jt
    - 500
    Mengembalikan (nominal_float, sisa_teks_setelah_angka_dihapus).
    """
    clean_text = text.strip()

    # Pattern untuk mendeteksi nominal dengan variasi suffix (k, rb, ribu, jt, juta)
    # Contoh: 25.000, 25k, 1.5jt, 100rb, 25000
    pattern = re.compile(
        r'(?P<amount>\d+(?:[\.,]\d+)?)\s*(?P<suffix>ribu|rb|k|juta|jt|m|mio)?\b',
        re.IGNORECASE
    )

    match = pattern.search(clean_text)
    if not match:
        return None, clean_text

    amount_raw = match.group('amount').replace(',', '.')
    suffix = (match.group('suffix') or '').lower()

    # Jika ada lebih dari 1 titik pada format ribuan (misal: 1.500.000)
    if amount_raw.count('.') > 1:
        amount_raw = amount_raw.replace('.', '')
    elif '.' in amount_raw and not suffix:
        # Jika bentuknya 25.000 (3 digit setelah titik), biasanya pemisah ribuan
        parts = amount_raw.split('.')
        if len(parts) == 2 and len(parts[1]) == 3:
            amount_raw = "".join(parts)

    try:
        base_value = float(amount_raw)
    except ValueError:
        return None, clean_text

    # Multiplier kalkulasi
    multiplier = 1.0
    if suffix in ['k', 'rb', 'ribu']:
        multiplier = 1_000.0
    elif suffix in ['jt', 'juta', 'm', 'mio']:
        multiplier = 1_000_000.0

    final_amount = base_value * multiplier

    # Buang bagian angka dari teks untuk menyisakan deskripsi
    remaining_text = clean_text[:match.start()] + clean_text[match.end():]
    remaining_text = re.sub(r'\s+', ' ', remaining_text).strip()

    return final_amount, remaining_text

def detect_category_and_type(description: str, is_forced_income: bool = False) -> Tuple[str, str]:
    """
    Mendeteksi kategori dan tipe transaksi (expense/income) dari deskripsi kata.
    """
    lower_desc = description.lower()

    # Cek apakah transaksi pemasukan
    if is_forced_income or any(kw in lower_desc for kw in KEYWORD_MAPPINGS["pemasukan"]):
        return "pemasukan", "income"

    # Cocokkan dengan keyword kategori
    for cat_key, keywords in KEYWORD_MAPPINGS.items():
        if cat_key == "pemasukan":
            continue
        for kw in keywords:
            # Gunakan word boundary atau substring
            if re.search(r'\b' + re.escape(kw), lower_desc):
                return cat_key, "expense"

    # Default fallback
    return "lainnya", "expense"

def parse_financial_text(user_input: str) -> Dict[str, Any]:
    """
    Memproses teks pesan pengguna menjadi data keuangan terstruktur.
    Format yang didukung:
    - 'makan 25000'
    - 'transport 15k'
    - '+gaji 5000000' atau 'gaji 5jt'
    - '20rb bensin pertalite'
    """
    raw = user_input.strip()
    if not raw:
        return {"success": False, "error": "Pesan kosong."}

    # Cek apakah ada penanda pemasukan dengan tanda '+' di awal
    is_plus_income = raw.startswith("+")
    if is_plus_income:
        raw = raw.lstrip("+").strip()

    amount, desc = parse_amount(raw)

    if amount is None or amount <= 0:
        return {
            "success": False,
            "error": "Nominal angka tidak ditemukan atau tidak valid. Contoh format: `makan 25000` atau `kopi 25k`."
        }

    # Jika deskripsi kosong setelah angka diambil (cth: pengguna hanya mengetik "50000" atau "25k")
    if not desc:
        if is_plus_income:
            # Jika diawali '+', otomatis dianggap pemasukan
            cat_info = CATEGORIES.get("pemasukan", CATEGORIES["lainnya"])
            return {
                "success": True,
                "is_amount_only": False,
                "type": "income",
                "category_key": "pemasukan",
                "category_label": cat_info["label"],
                "category_icon": cat_info["icon"],
                "amount": amount,
                "description": "Pemasukan",
                "raw_input": user_input
            }
        else:
            # Pengguna hanya mengetik nominal -> Tampilkan Smart Category Picker!
            return {
                "success": True,
                "is_amount_only": True,
                "amount": amount,
                "raw_input": user_input
            }

    category_key, tx_type = detect_category_and_type(desc, is_forced_income=is_plus_income)
    cat_info = CATEGORIES.get(category_key, CATEGORIES["lainnya"])

    return {
        "success": True,
        "is_amount_only": False,
        "type": tx_type,
        "category_key": category_key,
        "category_label": cat_info["label"],
        "category_icon": cat_info["icon"],
        "amount": amount,
        "description": desc,
        "raw_input": user_input
    }
