# Panduan Membuat Sistem Data Mining Asosiasi (Apriori + mlxtend)

Sistem web untuk analisis *market basket* dengan algoritma **Apriori**.
Pengolahan data dan algoritma memakai **Python** (library `mlxtend` dan `pandas`), antarmuka memakai **Flask + HTML + CSS + JavaScript**.

---

## 1. Fitur Sistem

| No | Fitur | Keterangan |
|----|-------|------------|
| 1 | List dataset | Menampilkan seluruh transaksi (dengan pagination) |
| 2 | CRUD transaksi | Tambah, ubah, hapus transaksi dan item di dalamnya |
| 3 | Pencarian | Cari berdasarkan nama item atau ID transaksi |
| 4 | Komputasi | Input *minimum support* dan *minimum confidence*, lalu jalankan Apriori |
| 5 | Hasil relasi | Tabel frequent itemset dan association rules (support, confidence, lift) |
| 6 | Grafik | Top item, scatter support vs confidence, top rules berdasarkan lift |

---

## 2. Teknologi

- **Python 3.10+**
- **Flask**: web framework
- **SQLite** (bawaan Python, modul `sqlite3`): penyimpanan data
- **pandas**: mengolah data transaksi menjadi tabel
- **mlxtend**: menjalankan algoritma Apriori dan membentuk association rules
- **Chart.js** (lewat CDN): grafik di sisi frontend
- **Dataset**: `groceries.csv` (9.835 transaksi, format wide)

---

## 3. Struktur Proyek

```
apriori-app/
├── app.py                  # Aplikasi Flask (route, CRUD, API komputasi)
├── database.py             # Koneksi dan skema database
├── import_data.py          # Skrip import groceries.csv ke SQLite
├── apriori_engine.py       # Pemanggilan Apriori (mlxtend) + format hasil
├── requirements.txt
├── data/
│   └── groceries.csv       # Dataset asli
├── templates/
│   ├── base.html           # Layout dasar + navbar
│   ├── index.html          # List dataset + pencarian
│   ├── form.html           # Form tambah / ubah transaksi
│   └── compute.html        # Halaman komputasi + hasil + grafik
└── static/
    ├── css/style.css
    └── js/compute.js
```

---

## 4. Persiapan Lingkungan

```bash
mkdir apriori-app && cd apriori-app
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install flask pandas mlxtend
pip freeze > requirements.txt

mkdir data templates static static/css static/js
```

Letakkan `groceries.csv` di folder `data/`.

---

## 5. Desain Database

Dua tabel. Satu transaksi punya banyak item (relasi 1-ke-banyak).

```
transaksi                     item_transaksi
---------                     --------------
id (PK, auto)                 id (PK, auto)
tanggal                       id_transaksi (FK -> transaksi.id, ON DELETE CASCADE)
                              nama_item
```

### `database.py`

```python
import sqlite3

DB_PATH = "data.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS transaksi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal TEXT DEFAULT (date('now'))
        );

        CREATE TABLE IF NOT EXISTS item_transaksi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_transaksi INTEGER NOT NULL,
            nama_item TEXT NOT NULL,
            FOREIGN KEY (id_transaksi) REFERENCES transaksi(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_item_transaksi ON item_transaksi(id_transaksi);
        CREATE INDEX IF NOT EXISTS idx_item_nama ON item_transaksi(nama_item);
        """
    )
    conn.commit()
    conn.close()
```

---

## 6. Import Dataset

Dataset asli berformat *wide*: kolom `Item(s)` lalu `Item 1` sampai `Item 32`, banyak sel kosong, dan tidak ada ID transaksi. Skrip ini:

1. membuat ID transaksi otomatis,
2. mengubah format wide menjadi long (satu baris = satu item),
3. membersihkan item (hapus spasi, huruf kecil, buang sel kosong dan duplikat).

### `import_data.py`

```python
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
```

Jalankan sekali:

```bash
python import_data.py
```

Hasil yang diharapkan: `Import selesai: 9835 transaksi.`

---

## 7. Algoritma Apriori dengan mlxtend

### 7.1 Konsep (penting untuk presentasi)

Walaupun perhitungannya dikerjakan library, kamu tetap perlu bisa menjelaskan alurnya:

1. Hitung support tiap item (1-itemset), simpan yang memenuhi *min support* → **L1**.
2. Gabungkan itemset di L(k-1) menjadi kandidat k-itemset (**join**).
3. Buang kandidat yang punya subset tidak frequent (**prune**, sifat anti-monotone Apriori).
4. Hitung support kandidat, simpan yang lolos → **Lk**.
5. Ulangi sampai tidak ada itemset baru.
6. Dari semua frequent itemset, bentuk aturan `A → B` dan hitung **support, confidence, lift**.

Rumus:

- Support(A ∪ B) = jumlah transaksi berisi A dan B / total transaksi
- Confidence(A → B) = Support(A ∪ B) / Support(A)
- Lift(A → B) = Confidence(A → B) / Support(B)

### 7.2 Peran tiap bagian kode

| Langkah di kode | Penjelasan |
|---|---|
| `TransactionEncoder` | Mengubah transaksi menjadi tabel *one-hot* (baris = transaksi, kolom = item, nilai True/False) |
| `apriori(...)` | Menjalankan langkah 1 sampai 5 di atas dan menghasilkan frequent itemset |
| `association_rules(...)` | Menjalankan langkah 6, yaitu membentuk rules dan menghitung support, confidence, lift |

### 7.3 `apriori_engine.py`

```python
from collections import defaultdict

import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder


def load_transactions(conn):
    """Ambil semua transaksi dari database sebagai list of set."""
    rows = conn.execute(
        "SELECT id_transaksi, nama_item FROM item_transaksi"
    ).fetchall()

    data = defaultdict(set)
    for r in rows:
        data[r["id_transaksi"]].add(r["nama_item"])
    return list(data.values())


def jalankan_apriori(transactions, min_support, min_confidence):
    """
    Mengembalikan: (itemsets, rules, n)
      itemsets : list of dict {itemset, k, count, support}
      rules    : list of dict {antecedent, consequent, support, confidence, lift}
      n        : total transaksi
    """
    n = len(transactions)

    # 1. Ubah transaksi menjadi tabel one-hot (baris = transaksi, kolom = item)
    te = TransactionEncoder()
    array = te.fit(transactions).transform(transactions)
    df = pd.DataFrame(array, columns=te.columns_)

    # 2. Cari frequent itemset
    frequent_df = apriori(df, min_support=min_support, use_colnames=True)

    itemsets = []
    for _, row in frequent_df.iterrows():
        items = sorted(row["itemsets"])
        itemsets.append(
            {
                "itemset": items,
                "k": len(items),
                "count": int(round(row["support"] * n)),
                "support": round(float(row["support"]), 4),
            }
        )
    itemsets.sort(key=lambda x: (x["k"], -x["support"]))

    # 3. Bentuk association rules (hanya jika ada itemset berisi >= 2 item)
    rules = []
    if any(i["k"] >= 2 for i in itemsets):
        try:
            # mlxtend versi baru meminta parameter num_itemsets
            rules_df = association_rules(
                frequent_df,
                num_itemsets=n,
                metric="confidence",
                min_threshold=min_confidence,
            )
        except TypeError:
            # mlxtend versi lama tidak punya parameter num_itemsets
            rules_df = association_rules(
                frequent_df,
                metric="confidence",
                min_threshold=min_confidence,
            )

        for _, r in rules_df.iterrows():
            rules.append(
                {
                    "antecedent": sorted(r["antecedents"]),
                    "consequent": sorted(r["consequents"]),
                    "support": round(float(r["support"]), 4),
                    "confidence": round(float(r["confidence"]), 4),
                    "lift": round(float(r["lift"]), 4),
                }
            )
        rules.sort(key=lambda x: (x["lift"], x["confidence"]), reverse=True)

    return itemsets, rules, n
```

### 7.4 Uji cepat lewat terminal (sebelum membuat halaman web)

Setelah `import_data.py` berhasil, jalankan:

```bash
python -c "from database import get_conn; from apriori_engine import load_transactions, jalankan_apriori; t = load_transactions(get_conn()); i, r, n = jalankan_apriori(t, 0.01, 0.3); print('transaksi:', n, '| itemset:', len(i), '| rules:', len(r)); print(r[:3])"
```

Hasil yang wajar: jumlah transaksi 9835, ada puluhan sampai ratusan itemset, dan ada beberapa rules. Jika `itemset` dan `rules` bernilai 0, ada yang salah pada import data.

> Catatan performa: mlxtend jauh lebih cepat dibanding implementasi manual, tetapi jika *min support* diturunkan di bawah 0,003 jumlah itemset bisa membengkak dan memakai banyak memori.

---

## 8. Aplikasi Flask

### `app.py`

```python
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
```

---

## 9. Template HTML

### `templates/base.html`

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Sistem Apriori{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
  <nav class="navbar">
    <span class="brand">Apriori Miner</span>
    <div class="links">
      <a href="{{ url_for('index') }}">Dataset</a>
      <a href="{{ url_for('tambah') }}">Tambah Data</a>
      <a href="{{ url_for('komputasi') }}">Komputasi</a>
    </div>
  </nav>

  <main class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% for kategori, pesan in messages %}
        <div class="alert {{ kategori }}">{{ pesan }}</div>
      {% endfor %}
    {% endwith %}

    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

### `templates/index.html`

```html
{% extends "base.html" %}
{% block title %}Dataset{% endblock %}

{% block content %}
<h1>Dataset Transaksi</h1>

<form class="search" method="get" action="{{ url_for('index') }}">
  <input type="text" name="q" value="{{ q }}" placeholder="Cari item atau ID transaksi...">
  <button type="submit">Cari</button>
  {% if q %}<a href="{{ url_for('index') }}">Reset</a>{% endif %}
  <a class="btn" href="{{ url_for('tambah') }}">+ Tambah Transaksi</a>
</form>

<p class="muted">Total: {{ total }} transaksi</p>

<table>
  <thead>
    <tr><th>ID</th><th>Tanggal</th><th>Item</th><th>Jumlah</th><th>Aksi</th></tr>
  </thead>
  <tbody>
    {% for r in rows %}
    <tr>
      <td>T{{ '%04d' % r.id }}</td>
      <td>{{ r.tanggal or '-' }}</td>
      <td>{{ r['items'] }}</td>
      <td>{{ r.jumlah }}</td>
      <td class="aksi">
        <a href="{{ url_for('ubah', tid=r.id) }}">Ubah</a>
        <form method="post" action="{{ url_for('hapus', tid=r.id) }}"
              onsubmit="return confirm('Hapus transaksi ini?')">
          <button type="submit" class="danger">Hapus</button>
        </form>
      </td>
    </tr>
    {% else %}
    <tr><td colspan="5" class="muted">Data tidak ditemukan.</td></tr>
    {% endfor %}
  </tbody>
</table>

<div class="pagination">
  {% if page > 1 %}
    <a href="{{ url_for('index', page=page-1, q=q) }}">&laquo; Sebelumnya</a>
  {% endif %}
  <span>Halaman {{ page }} / {{ total_page }}</span>
  {% if page < total_page %}
    <a href="{{ url_for('index', page=page+1, q=q) }}">Berikutnya &raquo;</a>
  {% endif %}
</div>
{% endblock %}
```

### `templates/form.html`

```html
{% extends "base.html" %}
{% block title %}{{ 'Tambah' if mode == 'tambah' else 'Ubah' }} Transaksi{% endblock %}

{% block content %}
<h1>{{ 'Tambah' if mode == 'tambah' else 'Ubah' }} Transaksi</h1>

<form method="post" class="card">
  <label>Tanggal</label>
  <input type="date" name="tanggal" value="{{ data.tanggal if data else '' }}">

  <label>Item (pisahkan dengan koma)</label>
  <textarea name="items" rows="4" required
            placeholder="contoh: whole milk, yogurt, rolls/buns">{{ data['items'] if data else '' }}</textarea>

  <div class="actions">
    <button type="submit">Simpan</button>
    <a href="{{ url_for('index') }}">Batal</a>
  </div>
</form>
{% endblock %}
```

### `templates/compute.html`

```html
{% extends "base.html" %}
{% block title %}Komputasi Apriori{% endblock %}

{% block content %}
<h1>Komputasi Apriori</h1>

<form id="form-komputasi" class="card inline">
  <div>
    <label>Minimum Support (0 - 1)</label>
    <input type="number" name="min_support" step="0.001" min="0.001" max="1" value="0.01" required>
  </div>
  <div>
    <label>Minimum Confidence (0 - 1)</label>
    <input type="number" name="min_confidence" step="0.01" min="0.01" max="1" value="0.3" required>
  </div>
  <button type="submit" id="btn-proses">Proses</button>
</form>

<p id="status" class="muted"></p>

<section id="hasil" hidden>
  <div id="ringkasan" class="summary"></div>

  <h2>Frequent Itemset</h2>
  <div class="scroll">
    <table id="tbl-itemset">
      <thead><tr><th>Itemset</th><th>k</th><th>Jumlah</th><th>Support</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <h2>Association Rules</h2>
  <div class="scroll">
    <table id="tbl-rules">
      <thead><tr><th>Antecedent</th><th></th><th>Consequent</th><th>Support</th><th>Confidence</th><th>Lift</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <h2>Grafik</h2>
  <div class="charts">
    <div class="card"><h3>Top 10 Item Terlaris</h3><canvas id="chart-top-item"></canvas></div>
    <div class="card"><h3>Support vs Confidence (warna = lift)</h3><canvas id="chart-scatter"></canvas></div>
    <div class="card wide"><h3>Top 10 Rules berdasarkan Lift</h3><canvas id="chart-lift"></canvas></div>
  </div>
</section>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script src="{{ url_for('static', filename='js/compute.js') }}"></script>
{% endblock %}
```

---

## 10. JavaScript

### `static/js/compute.js`

```javascript
const form = document.getElementById("form-komputasi");
const statusEl = document.getElementById("status");
const hasilEl = document.getElementById("hasil");
const charts = {};

// Cegah XSS: item berasal dari input pengguna
function esc(teks) {
  const d = document.createElement("div");
  d.textContent = teks;
  return d.innerHTML;
}

function gambar(id, config) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), config);
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("btn-proses");
  btn.disabled = true;
  statusEl.textContent = "Memproses...";

  try {
    const res = await fetch("/api/komputasi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        min_support: parseFloat(form.min_support.value),
        min_confidence: parseFloat(form.min_confidence.value),
      }),
    });
    const data = await res.json();

    if (!res.ok) {
      statusEl.textContent = data.error || "Terjadi kesalahan.";
      hasilEl.hidden = true;
      return;
    }

    statusEl.textContent = "";
    tampilkan(data);
  } catch (err) {
    statusEl.textContent = "Gagal menghubungi server.";
  } finally {
    btn.disabled = false;
  }
});

function tampilkan(d) {
  hasilEl.hidden = false;

  document.getElementById("ringkasan").innerHTML = `
    <div><b>${d.total_transaksi}</b><span>Transaksi</span></div>
    <div><b>${d.itemsets.length}</b><span>Frequent Itemset</span></div>
    <div><b>${d.rules.length}</b><span>Rules</span></div>
    <div><b>${d.durasi} s</b><span>Waktu proses</span></div>`;

  // Tabel itemset
  document.querySelector("#tbl-itemset tbody").innerHTML = d.itemsets
    .map(
      (r) => `<tr>
        <td>${esc(r.itemset.join(", "))}</td>
        <td>${r.k}</td><td>${r.count}</td><td>${r.support}</td></tr>`
    )
    .join("") || `<tr><td colspan="4" class="muted">Tidak ada itemset. Turunkan minimum support.</td></tr>`;

  // Tabel rules
  document.querySelector("#tbl-rules tbody").innerHTML = d.rules
    .map(
      (r) => `<tr>
        <td>${esc(r.antecedent.join(", "))}</td><td>&rarr;</td>
        <td>${esc(r.consequent.join(", "))}</td>
        <td>${r.support}</td><td>${r.confidence}</td><td>${r.lift}</td></tr>`
    )
    .join("") || `<tr><td colspan="6" class="muted">Tidak ada rule. Turunkan support atau confidence.</td></tr>`;

  // Grafik 1: top item
  gambar("chart-top-item", {
    type: "bar",
    data: {
      labels: d.top_items.map((x) => x.item),
      datasets: [{ label: "Jumlah transaksi", data: d.top_items.map((x) => x.jumlah) }],
    },
    options: { indexAxis: "y", plugins: { legend: { display: false } } },
  });

  // Grafik 2: scatter support vs confidence (warna berdasarkan lift)
  const maxLift = Math.max(1, ...d.rules.map((r) => r.lift));
  gambar("chart-scatter", {
    type: "scatter",
    data: {
      datasets: [{
        label: "Rules",
        data: d.rules.map((r) => ({ x: r.support, y: r.confidence, lift: r.lift })),
        pointRadius: 5,
        backgroundColor: d.rules.map(
          (r) => `hsl(${220 - 220 * (r.lift / maxLift)}, 80%, 50%)`
        ),
      }],
    },
    options: {
      scales: {
        x: { title: { display: true, text: "Support" } },
        y: { title: { display: true, text: "Confidence" } },
      },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (c) => `lift: ${c.raw.lift}` } },
      },
    },
  });

  // Grafik 3: top 10 rules berdasarkan lift
  const top = d.rules.slice(0, 10);
  gambar("chart-lift", {
    type: "bar",
    data: {
      labels: top.map((r) => `${r.antecedent.join(", ")} → ${r.consequent.join(", ")}`),
      datasets: [{ label: "Lift", data: top.map((r) => r.lift) }],
    },
    options: { indexAxis: "y", plugins: { legend: { display: false } } },
  });
}
```

---

## 11. CSS

### `static/css/style.css`

```css
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, sans-serif; background: #f5f6fa; color: #222; }

.navbar { display: flex; justify-content: space-between; align-items: center;
          background: #1f2d5c; color: #fff; padding: 12px 24px; }
.navbar .brand { font-weight: 700; font-size: 18px; }
.navbar a { color: #dfe6ff; margin-left: 16px; text-decoration: none; }
.navbar a:hover { color: #fff; }

.container { max-width: 1100px; margin: 24px auto; padding: 0 16px; }
.muted { color: #777; }

.card { background: #fff; padding: 16px; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-bottom: 16px; }
.card.inline { display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap; }
.card label { display: block; font-size: 13px; margin-bottom: 4px; }
.card input, .card textarea { width: 100%; padding: 8px; border: 1px solid #ccd; border-radius: 6px; }

button, .btn { background: #2f54eb; color: #fff; border: 0; padding: 8px 14px;
               border-radius: 6px; cursor: pointer; text-decoration: none; font-size: 14px; }
button:disabled { opacity: .6; cursor: wait; }
button.danger { background: #d9363e; }

.search { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
.search input { flex: 1; min-width: 200px; padding: 8px; border: 1px solid #ccd; border-radius: 6px; }

table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; }
th, td { padding: 8px 10px; border-bottom: 1px solid #eee; text-align: left; font-size: 14px; vertical-align: top; }
th { background: #eef1fb; }
.aksi { display: flex; gap: 8px; align-items: center; }
.aksi form { margin: 0; }

.scroll { max-height: 380px; overflow: auto; margin-bottom: 16px; }

.pagination { display: flex; gap: 16px; justify-content: center; margin: 16px 0; }

.alert { padding: 10px 14px; border-radius: 6px; margin-bottom: 12px; }
.alert.success { background: #e6f7ec; color: #1b6b3a; }
.alert.error { background: #fde8e8; color: #9b1c1c; }

.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px; }
.summary div { background: #fff; padding: 14px; border-radius: 8px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.summary b { display: block; font-size: 22px; color: #2f54eb; }
.summary span { font-size: 12px; color: #666; }

.charts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.charts .wide { grid-column: 1 / -1; }
@media (max-width: 800px) { .charts { grid-template-columns: 1fr; } }
```

---

## 12. Menjalankan Sistem

```bash
# 1. (sekali saja) import dataset
python import_data.py

# 2. jalankan aplikasi
python app.py
```

Buka `http://127.0.0.1:5000`.

---

## 13. Alur Pengujian

1. **Import**: pastikan muncul `Import selesai: 9835 transaksi.`
2. **Uji Apriori lewat terminal**: jalankan perintah di bagian 7.4.
3. **List dataset**: pastikan muncul 9.835 transaksi dan pagination berjalan.
4. **Pencarian**: ketik `whole milk`, hasilnya hanya transaksi yang memuat item itu.
5. **Tambah**: buat transaksi baru, mis. `roti, susu, telur`, lalu cek muncul di akhir list.
6. **Ubah dan hapus**: edit item, lalu hapus transaksi tadi.
7. **Komputasi**: coba `support = 0.01` dan `confidence = 0.3`, pastikan tabel dan 3 grafik muncul.
8. **Validasi**: isi support `0` atau `2`, harus muncul pesan error.
9. **Kasus kosong**: isi support `0.5`, harus muncul pesan "tidak ada itemset".

Parameter awal yang disarankan untuk dataset ini:

| Parameter | Nilai awal | Keterangan |
|-----------|------------|------------|
| Min support | 0.01 – 0.02 | Dataset sparse, jangan terlalu tinggi |
| Min confidence | 0.2 – 0.5 | Naikkan untuk aturan yang lebih kuat |

---

## 14. Masalah Umum dan Solusinya

| Masalah | Penyebab | Solusi |
|---|---|---|
| `ModuleNotFoundError: mlxtend` | Library belum terpasang atau venv belum aktif | Aktifkan venv, lalu `pip install mlxtend pandas` |
| Error soal `num_itemsets` pada `association_rules` | Beda versi mlxtend | Sudah ditangani dengan `try/except` di `apriori_engine.py`. Jika masih error, jalankan `pip install --upgrade mlxtend` |
| `itemset` dan `rules` kosong | Support terlalu tinggi, atau import gagal | Turunkan support ke 0.01, lalu cek hasil import |
| Grafik tidak muncul | Tidak ada internet (Chart.js dari CDN) | Unduh `chart.min.js` ke `static/js/` dan ganti `src` di `compute.html` |
| Proses komputasi lama atau memori penuh | Support terlalu rendah | Naikkan minimum support |
| `jinja2.exceptions.TemplateNotFound` | Folder atau nama template salah | Pastikan folder bernama `templates` dan berada sejajar dengan `app.py` |

---

## 15. Cara Membaca Hasil (untuk Laporan / Presentasi)

- **Support**: seberapa sering kombinasi item muncul di seluruh transaksi.
- **Confidence**: dari transaksi yang berisi A, berapa persen yang juga berisi B.
- **Lift**:
  - `> 1` → A dan B cenderung dibeli bersamaan (asosiasi positif)
  - `= 1` → tidak ada hubungan
  - `< 1` → cenderung tidak dibeli bersamaan

Contoh interpretasi: *"Jika pelanggan membeli yogurt, ada 40% kemungkinan ia juga membeli whole milk (lift 1,6), artinya kombinasi ini 1,6 kali lebih sering dari kebetulan."*

---

## 16. Checklist Pengerjaan

- [ ] Siapkan lingkungan dan struktur folder, lalu install `flask pandas mlxtend`
- [ ] `database.py` dan `import_data.py`, lalu jalankan import
- [ ] `apriori_engine.py`, uji lewat terminal (bagian 7.4)
- [ ] Route list dataset + pencarian
- [ ] Route CRUD (tambah, ubah, hapus)
- [ ] Halaman komputasi + API
- [ ] Grafik (Chart.js)
- [ ] Styling dan validasi input
- [ ] Pengujian dan dokumentasi (screenshot untuk laporan)

---

## 17. Pengembangan Lanjutan (Opsional, Nilai Tambah)

- Tombol **ekspor hasil rules ke CSV**
- Opsi pembanding **FP-Growth** (dosen memakainya sebagai contoh). Di mlxtend cukup mengganti `apriori` dengan `fpgrowth` dari `mlxtend.frequent_patterns`, lalu bandingkan waktu proses
- Filter rules berdasarkan item tertentu
- Upload CSV baru dari halaman web
- Penjelasan langkah per iterasi (L1, L2, ...) untuk keperluan presentasi

---

## 18. Prompt untuk AI Agent (Antigravity)

Salin prompt ini ke agent setelah file panduan ini dan `groceries.csv` ada di folder proyek:

```
Baca file PANDUAN_SISTEM_APRIORI.md di folder proyek ini, lalu bangun sistemnya persis sesuai panduan tersebut.

Langkah yang harus kamu lakukan:
1. Buat semua file dan folder sesuai bagian "Struktur Proyek" (app.py, database.py, import_data.py, apriori_engine.py, requirements.txt, templates/, static/).
2. File groceries.csv sudah ada di folder proyek. Jika belum berada di data/groceries.csv, pindahkan ke sana.
3. Buat virtual environment, lalu install flask, pandas, dan mlxtend, dan perbarui requirements.txt.
4. Jalankan import_data.py dan pastikan hasilnya "Import selesai: 9835 transaksi."
5. Jalankan uji Apriori lewat terminal (bagian 7.4 panduan) dan pastikan menghasilkan itemset dan rules.
6. Jalankan aplikasi Flask dan uji semua langkah di bagian "Alur Pengujian".
7. Jika ada error, perbaiki sendiri sampai semuanya berjalan.

Aturan:
- Pakai mlxtend untuk Apriori, jangan menulis ulang algoritmanya secara manual.
- Pakai Flask + SQLite + HTML/CSS/JS biasa, jangan ganti framework.
- Jangan ubah struktur database dan fitur di panduan, kecuali untuk memperbaiki bug.

Setelah selesai, beri ringkasan singkat: file yang dibuat, hasil pengujian tiap langkah, dan cara menjalankan aplikasi.
```
