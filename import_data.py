import csv
from datetime import date, timedelta
from database import get_conn, init_db

CSV_PATH = "data/groceries.csv"
START_DATE = date(2025, 1, 1)
TOTAL_DAYS = 365


def clean(teks):
    return teks.strip().lower()


def main():
    init_db()
    conn = get_conn()

    # Kosongkan data lama agar import bisa diulang dengan ID mulai dari 1
    conn.execute("DELETE FROM item_transaksi")
    conn.execute("DELETE FROM transaksi")
    conn.execute(
        "DELETE FROM sqlite_sequence WHERE name IN ('transaksi', 'item_transaksi')"
    )

    baskets = []
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # lewati header

        for row in reader:
            # row[0] = kolom Item(s), item sebenarnya mulai dari row[1]
            items = sorted({clean(x) for x in row[1:] if x.strip()})
            if items:
                baskets.append(items)

    total_rows = len(baskets)
    for idx, items in enumerate(baskets):
        # Distribusikan transaksi secara merata sepanjang 12 bulan (2025-01-01 s.d. 2025-12-31)
        day_offset = (idx * TOTAL_DAYS) // total_rows if total_rows else 0
        tgl = (START_DATE + timedelta(days=day_offset)).isoformat()

        cur = conn.execute("INSERT INTO transaksi (tanggal) VALUES (?)", (tgl,))
        tid = cur.lastrowid
        conn.executemany(
            "INSERT INTO item_transaksi (id_transaksi, nama_item) VALUES (?, ?)",
            [(tid, item) for item in items],
        )

    conn.commit()
    conn.close()
    print(f"Import selesai: {total_rows} transaksi (terdistribusi {START_DATE} s.d. {START_DATE + timedelta(days=TOTAL_DAYS - 1)}).")


if __name__ == "__main__":
    main()

