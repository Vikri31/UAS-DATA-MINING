import time

from flask import (
    Flask, flash, jsonify, redirect, render_template, request, url_for
)

from apriori_engine import jalankan_apriori, load_transactions
from database import get_conn, init_db

app = Flask(__name__)
app.secret_key = "ganti-dengan-secret-key-kamu"

PER_PAGE = 20
init_db()


def parse_items(raw):
    """'Susu, roti , Susu' -> ['roti', 'susu'] (bersih, unik, terurut)."""
    return sorted({x.strip().lower() for x in raw.split(",") if x.strip()})


# ------------------------------------------------------------------
# 1. LIST DATASET + PENCARIAN
# ------------------------------------------------------------------
@app.route("/")
def index():
    q = request.args.get("q", "").strip().lower()
    page = max(request.args.get("page", 1, type=int), 1)
    offset = (page - 1) * PER_PAGE

    conn = get_conn()

    kondisi = ""
    params = []
    if q:
        kondisi = """
            WHERE t.id IN (
                SELECT id_transaksi FROM item_transaksi WHERE nama_item LIKE ?
            ) OR CAST(t.id AS TEXT) = ?
        """
        params = [f"%{q}%", q]

    total = conn.execute(
        f"SELECT COUNT(*) FROM transaksi t {kondisi}", params
    ).fetchone()[0]

    rows = conn.execute(
        f"""
        SELECT t.id, t.tanggal,
               GROUP_CONCAT(i.nama_item, ', ') AS items,
               COUNT(i.id) AS jumlah
        FROM transaksi t
        LEFT JOIN item_transaksi i ON i.id_transaksi = t.id
        {kondisi}
        GROUP BY t.id
        ORDER BY t.id
        LIMIT ? OFFSET ?
        """,
        params + [PER_PAGE, offset],
    ).fetchall()
    conn.close()

    total_page = max((total + PER_PAGE - 1) // PER_PAGE, 1)
    return render_template(
        "index.html", rows=rows, q=q, page=page, total=total, total_page=total_page
    )


# ------------------------------------------------------------------
# 2. CRUD
# ------------------------------------------------------------------
@app.route("/transaksi/tambah", methods=["GET", "POST"])
def tambah():
    if request.method == "POST":
        items = parse_items(request.form.get("items", ""))
        tanggal = request.form.get("tanggal") or None

        if len(items) < 1:
            flash("Isi minimal satu item.", "error")
            return render_template("form.html", mode="tambah", data=None)

        conn = get_conn()
        if tanggal:
            cur = conn.execute("INSERT INTO transaksi (tanggal) VALUES (?)", (tanggal,))
        else:
            cur = conn.execute("INSERT INTO transaksi DEFAULT VALUES")
        tid = cur.lastrowid
        conn.executemany(
            "INSERT INTO item_transaksi (id_transaksi, nama_item) VALUES (?, ?)",
            [(tid, i) for i in items],
        )
        conn.commit()
        conn.close()

        flash("Transaksi berhasil ditambahkan.", "success")
        return redirect(url_for("index"))

    return render_template("form.html", mode="tambah", data=None)


@app.route("/transaksi/<int:tid>/ubah", methods=["GET", "POST"])
def ubah(tid):
    conn = get_conn()
    trx = conn.execute("SELECT * FROM transaksi WHERE id = ?", (tid,)).fetchone()
    if trx is None:
        conn.close()
        flash("Transaksi tidak ditemukan.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        items = parse_items(request.form.get("items", ""))
        tanggal = request.form.get("tanggal") or trx["tanggal"]

        if len(items) < 1:
            flash("Isi minimal satu item.", "error")
        else:
            conn.execute("UPDATE transaksi SET tanggal = ? WHERE id = ?", (tanggal, tid))
            conn.execute("DELETE FROM item_transaksi WHERE id_transaksi = ?", (tid,))
            conn.executemany(
                "INSERT INTO item_transaksi (id_transaksi, nama_item) VALUES (?, ?)",
                [(tid, i) for i in items],
            )
            conn.commit()
            conn.close()
            flash("Transaksi berhasil diubah.", "success")
            return redirect(url_for("index"))

    items = conn.execute(
        "SELECT nama_item FROM item_transaksi WHERE id_transaksi = ? ORDER BY nama_item",
        (tid,),
    ).fetchall()
    conn.close()

    data = {
        "id": tid,
        "tanggal": trx["tanggal"],
        "items": ", ".join(r["nama_item"] for r in items),
    }
    return render_template("form.html", mode="ubah", data=data)


@app.route("/transaksi/<int:tid>/hapus", methods=["POST"])
def hapus(tid):
    conn = get_conn()
    conn.execute("DELETE FROM transaksi WHERE id = ?", (tid,))  # item ikut terhapus (CASCADE)
    conn.commit()
    conn.close()
    flash("Transaksi berhasil dihapus.", "success")
    return redirect(url_for("index"))


# ------------------------------------------------------------------
# 3. KOMPUTASI APRIORI
# ------------------------------------------------------------------
@app.route("/komputasi")
def komputasi():
    return render_template("compute.html")


@app.route("/api/komputasi", methods=["POST"])
def api_komputasi():
    body = request.get_json(silent=True) or {}

    try:
        min_support = float(body.get("min_support"))
        min_conf = float(body.get("min_confidence"))
    except (TypeError, ValueError):
        return jsonify(error="Support dan confidence harus berupa angka."), 400

    if not (0 < min_support <= 1) or not (0 < min_conf <= 1):
        return jsonify(error="Nilai harus di antara 0 dan 1 (contoh: 0.01)."), 400

    conn = get_conn()
    transactions = load_transactions(conn)
    if not transactions:
        conn.close()
        return jsonify(error="Dataset kosong."), 400

    mulai = time.perf_counter()
    itemsets, rules, n = jalankan_apriori(transactions, min_support, min_conf)
    durasi = round(time.perf_counter() - mulai, 3)

    top_items = conn.execute(
        """
        SELECT nama_item AS item, COUNT(*) AS jumlah
        FROM item_transaksi GROUP BY nama_item
        ORDER BY jumlah DESC LIMIT 10
        """
    ).fetchall()
    conn.close()

    return jsonify(
        total_transaksi=n,
        durasi=durasi,
        min_support=min_support,
        min_confidence=min_conf,
        itemsets=itemsets,
        rules=rules,
        top_items=[dict(r) for r in top_items],
    )


if __name__ == "__main__":
    app.run(debug=True)

