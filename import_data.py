import csv
from database import get_conn, init_db

CSV_PATH = "data/groceries.csv"


def clean(teks):
    return teks.strip().lower()


def main():
    init_db()
    conn = get_conn()

    # Kosongkan data lama agar import bisa diulang
    conn.execute("DELETE FROM item_transaksi")
    conn.execute("DELETE FROM transaksi")

    jumlah = 0
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # lewati header

        for row in reader:
            # row[0] = kolom Item(s), item sebenarnya mulai dari row[1]
            items = sorted({clean(x) for x in row[1:] if x.strip()})
            if not items:
                continue

            cur = conn.execute("INSERT INTO transaksi DEFAULT VALUES")
            tid = cur.lastrowid
            conn.executemany(
                "INSERT INTO item_transaksi (id_transaksi, nama_item) VALUES (?, ?)",
                [(tid, item) for item in items],
            )
            jumlah += 1

    conn.commit()
    conn.close()
    print(f"Import selesai: {jumlah} transaksi.")


if __name__ == "__main__":
    main()

