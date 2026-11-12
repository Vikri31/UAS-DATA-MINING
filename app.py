import calendar
from datetime import datetime
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

NAMA_BULAN = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}


def parse_items(raw):
    """'Susu, roti , Susu' -> ['roti', 'susu'] (bersih, unik, terurut)."""
    return sorted({x.strip().lower() for x in raw.split(",") if x.strip()})


def format_month_label(ym):
    """'2025-01' -> 'Januari 2025'."""
    try:
        dt = datetime.strptime(ym, "%Y-%m")
        return f"{NAMA_BULAN[dt.month]} {dt.year}"
    except ValueError:
        return ym


def get_month_options(conn):
    """Ambil daftar bulan unik (YYYY-MM) yang ada di tabel transaksi."""
    rows = conn.execute(
        """
        SELECT DISTINCT substr(tanggal, 1, 7) AS ym
        FROM transaksi
        WHERE tanggal IS NOT NULL AND length(tanggal) >= 7
        ORDER BY ym ASC
        """
    ).fetchall()
    return [{"value": r["ym"], "label": format_month_label(r["ym"])} for r in rows]


def resolve_date_range(start_date_raw, end_date_raw, start_month_raw="", end_month_raw=""):
    """
    Validasi dan konversi filter bulan (YYYY-MM) / tanggal (YYYY-MM-DD) menjadi (start_date, end_date, error).
    Tanggal spesifik lebih diprioritaskan jika keduanya terisi.
    """
    start_date = (start_date_raw or "").strip() or None
    end_date = (end_date_raw or "").strip() or None
    start_month = (start_month_raw or "").strip()
    end_month = (end_month_raw or "").strip()

    if not start_date and start_month:
        try:
            dt = datetime.strptime(start_month, "%Y-%m")
            start_date = f"{dt.year:04d}-{dt.month:02d}-01"
        except ValueError:
            return None, None, "Format bulan mulai tidak valid (gunakan YYYY-MM)."

    if not end_date and end_month:
        try:
            dt = datetime.strptime(end_month, "%Y-%m")
            last_day = calendar.monthrange(dt.year, dt.month)[1]
            end_date = f"{dt.year:04d}-{dt.month:02d}-{last_day:02d}"
        except ValueError:
            return None, None, "Format bulan akhir tidak valid (gunakan YYYY-MM)."

    for label, val in [("tanggal mulai", start_date), ("tanggal akhir", end_date)]:
        if val:
            try:
                datetime.strptime(val, "%Y-%m-%d")
            except ValueError:
                return None, None, f"Format {label} tidak valid (gunakan YYYY-MM-DD)."

    if start_date and end_date and start_date > end_date:
        return start_date, end_date, "Tanggal mulai tidak boleh lebih besar daripada tanggal akhir."

    return start_date, end_date, None


# ------------------------------------------------------------------
# 1. LIST DATASET + PENCARIAN + FILTER PERIODE + SORTING
# ------------------------------------------------------------------
@app.route("/")
def index():
    q_raw = request.args.get("q", "").strip()
    q_lower = q_raw.lower()
    sort = request.args.get("sort", "desc").strip().lower()
    start_month = request.args.get("start_month", "").strip()
    end_month = request.args.get("end_month", "").strip()
    start_date_raw = request.args.get("start_date", "").strip()
    end_date_raw = request.args.get("end_date", "").strip()

    start_date, end_date, date_err = resolve_date_range(
        start_date_raw, end_date_raw, start_month, end_month
    )
    if date_err:
        flash(date_err, "error")

    conn = get_conn()
    month_options = get_month_options(conn)

    where_clauses = []
    params = []
    if q_raw:
        # Cek apakah pencarian berupa ID transaksi (misal: "T9838", "t9838", "T0001", "9838")
        clean_id = None
        q_id_candidate = q_lower.lstrip("t").strip()
        if q_id_candidate.isdigit():
            clean_id = int(q_id_candidate)

        if clean_id is not None:
            where_clauses.append(
                """(t.id = ? OR t.id IN (
                    SELECT id_transaksi FROM item_transaksi WHERE nama_item LIKE ?
                ))"""
            )
            params.extend([clean_id, f"%{q_lower}%"])
        else:
            where_clauses.append(
                """t.id IN (
                    SELECT id_transaksi FROM item_transaksi WHERE nama_item LIKE ?
                )"""
            )
            params.append(f"%{q_lower}%")

    if start_date:
        where_clauses.append("t.tanggal >= ?")
        params.append(start_date)
    if end_date:
        where_clauses.append("t.tanggal <= ?")
        params.append(end_date)

    kondisi = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    total = conn.execute(
        f"SELECT COUNT(*) FROM transaksi t {kondisi}", params
    ).fetchone()[0]

    total_page = max((total + PER_PAGE - 1) // PER_PAGE, 1)
    try:
        req_page = int(request.args.get("page", 1))
    except (ValueError, TypeError):
        req_page = 1
    page = min(max(req_page, 1), total_page)
    offset = (page - 1) * PER_PAGE

    order_map = {
        "desc": "ORDER BY t.id DESC",
        "asc": "ORDER BY t.id ASC",
        "date_desc": "ORDER BY t.tanggal DESC, t.id DESC",
        "date_asc": "ORDER BY t.tanggal ASC, t.id ASC",
    }
    order_by = order_map.get(sort, "ORDER BY t.id DESC")

    rows = conn.execute(
        f"""
        SELECT t.id, t.tanggal,
               GROUP_CONCAT(i.nama_item, ', ') AS items,
               COUNT(i.id) AS jumlah
        FROM transaksi t
        LEFT JOIN item_transaksi i ON i.id_transaksi = t.id
        {kondisi}
        GROUP BY t.id
        {order_by}
        LIMIT ? OFFSET ?
        """,
        params + [PER_PAGE, offset],
    ).fetchall()
    conn.close()

    return render_template(
        "index.html",
        rows=rows,
        q=q_raw,
        page=page,
        total=total,
        total_page=total_page,
        sort=sort,
        start_month=start_month,
        end_month=end_month,
        start_date=start_date or "",
        end_date=end_date or "",
        month_options=month_options,
    )


# ------------------------------------------------------------------
# 2. CRUD
# ------------------------------------------------------------------
@app.route("/transaksi/tambah", methods=["GET", "POST"])
def tambah():
    conn = get_conn()
    all_items = [r[0] for r in conn.execute("SELECT DISTINCT nama_item FROM item_transaksi ORDER BY nama_item").fetchall()]

    if request.method == "POST":
        items = parse_items(request.form.get("items", ""))
        tanggal = request.form.get("tanggal") or None

        if len(items) < 1:
            conn.close()
            flash("Isi minimal satu item.", "error")
            return render_template("form.html", mode="tambah", data=None, all_items=all_items)

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

    conn.close()
    return render_template("form.html", mode="tambah", data=None, all_items=all_items)


@app.route("/transaksi/<int:tid>/ubah", methods=["GET", "POST"])
def ubah(tid):
    conn = get_conn()
    all_items = [r[0] for r in conn.execute("SELECT DISTINCT nama_item FROM item_transaksi ORDER BY nama_item").fetchall()]
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
    return render_template("form.html", mode="ubah", data=data, all_items=all_items)


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
    conn = get_conn()
    stats = conn.execute(
        "SELECT COUNT(*) AS total, MIN(tanggal) AS min_date, MAX(tanggal) AS max_date FROM transaksi"
    ).fetchone()
    month_options = get_month_options(conn)
    conn.close()
    return render_template(
        "compute.html",
        total_trx=stats["total"] or 0,
        min_date=stats["min_date"] or "",
        max_date=stats["max_date"] or "",
        month_options=month_options,
    )


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

    start_date, end_date, date_err = resolve_date_range(
        body.get("start_date", ""),
        body.get("end_date", ""),
        body.get("start_month", ""),
        body.get("end_month", ""),
    )
    if date_err:
        return jsonify(error=date_err), 400

    conn = get_conn()
    transactions = load_transactions(conn, start_date=start_date, end_date=end_date)
    if not transactions:
        conn.close()
        return jsonify(error="Tidak ada transaksi pada rentang periode yang dipilih."), 400

    mulai = time.perf_counter()
    itemsets, rules, n = jalankan_apriori(transactions, min_support, min_conf)
    durasi = round(time.perf_counter() - mulai, 3)

    where_clauses = []
    params = []
    if start_date:
        where_clauses.append("t.tanggal >= ?")
        params.append(start_date)
    if end_date:
        where_clauses.append("t.tanggal <= ?")
        params.append(end_date)
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    top_items = conn.execute(
        f"""
        SELECT i.nama_item AS item, COUNT(*) AS jumlah
        FROM item_transaksi i
        JOIN transaksi t ON t.id = i.id_transaksi
        {where_sql}
        GROUP BY i.nama_item
        ORDER BY jumlah DESC LIMIT 10
        """,
        params,
    ).fetchall()
    conn.close()

    return jsonify(
        total_transaksi=n,
        durasi=durasi,
        min_support=min_support,
        min_confidence=min_conf,
        start_date=start_date,
        end_date=end_date,
        itemsets=itemsets,
        rules=rules,
        top_items=[dict(r) for r in top_items],
    )


if __name__ == "__main__":
    app.run(debug=True)
