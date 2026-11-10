# Dokumentasi & Cara Kerja Sistem Data Mining Asosiasi (Apriori Engine)

Sistem web ini dibangun untuk menganalisis pola keranjang belanja (*Market Basket Analysis*) pada dataset ritel menggunakan algoritma **Apriori** yang diimplementasikan secara mandiri (*pure Python*) dengan arsitektur web **Flask + SQLite + Chart.js**.

---

## 1. Arsitektur & Alur Kerja Sistem

Secara keseluruhan, alur kerja sistem terbagi menjadi 4 tahap utama:

```
[ Dataset CSV ] ──> [ import_data.py ] ──> [ SQLite: data.db ]
(Format Wide)          (ETL & Cleaning)     (transaksi & item_transaksi)
                                                        │
                                                        ▼
[ Frontend Web ] <── [ app.py (Flask) ] <── [ apriori_engine.py ]
(Dashboard & UI)        (Routing & API)      (Algoritma Apriori Manual)
```

---

## 2. Rincian Cara Kerja per Komponen

### 2.1 Dataset Mentah (`data/groceries.csv`)
* **Format Asli**: Dataset berformat *wide* yang terdiri dari kolom `Item(s)` dan `Item 1` s.d. `Item 32`.
* **Karakteristik**: Berisi 9.835 transaksi belanja tanpa ID unik bawaan, dengan banyak sel kosong (*null/empty*), serta format teks yang belum seragam.

### 2.2 Proses Ekstraksi & Transformasi Data (`import_data.py`)
Skrip ini bertindak sebagai modul ETL (*Extract, Transform, Load*):
1. **Membaca CSV**: Membaca file baris demi baris, melewati baris *header*.
2. **Pembersihan Data (*Data Cleaning*)**:
   * Menghilangkan spasi kosong di awal/akhir (*trimming*).
   * Menyeragamkan seluruh nama item menjadi huruf kecil (*lowercase*).
   * Membuang sel kosong dan menghapus duplikasi item dalam satu transaksi belanja.
3. **Restrukturisasi Relasional**:
   * Membuat ID transaksi unik otomatis di tabel `transaksi`.
   * Mengubah format *wide* menjadi format relasional 1-ke-banyak (*one-to-many*): satu transaksi dihubungkan dengan banyak baris di tabel `item_transaksi`.
4. **Output**: Menyimpan tepat **9.835 transaksi** ke dalam basis data `data.db`.

### 2.3 Skema Basis Data Relasional (`database.py`)
Menggunakan basis data SQLite lokal (`data.db`) dengan dua tabel berelasi:
* **Tabel `transaksi`**:
  * `id`: Integer (Primary Key, Auto Increment).
  * `tanggal`: Text (Default tanggal saat data dimasukkan).
* **Tabel `item_transaksi`**:
  * `id`: Integer (Primary Key, Auto Increment).
  * `id_transaksi`: Foreign Key yang merujuk ke `transaksi.id` dengan aturan `ON DELETE CASCADE` (jika transaksi dihapus, seluruh item di dalamnya otomatis ikut terhapus).
  * `nama_item`: Text (Nama produk belanja).
* **Indeks**: Dilengkapi indeks pada `id_transaksi` dan `nama_item` untuk mempercepat query pencarian dan join data.

### 2.4 Mesin Algoritma Apriori Manual (`apriori_engine.py`)
Algoritma Apriori diimplementasikan secara mandiri tanpa menggunakan library eksternal (seperti `mlxtend`):
1. **Representasi Inverted Index (TID Sets)**:
   * Setiap item belanja dipetakan ke himpunan ID transaksi tempat item tersebut muncul.
   * Hal ini membuat proses perhitungan frekuensi kombinasi item menjadi sangat cepat melalui operasi irisan himpunan (*set intersection*).
2. **Pembentukan Frequent 1-Itemset ($L_1$)**:
   * Menghitung nilai *Support* tiap item: $\text{Support}(I) = \frac{\text{Kemunculan } I}{\text{Total Transaksi}}$.
   * Menyimpan item yang memenuhi ambang batas $\text{Support} \ge \text{min\_support}$.
3. **Iterasi Kandidat & Pemangkasan Apriori ($L_k$, untuk $k \ge 2$)**:
   * **Join Step**: Menggabungkan dua itemset di $L_{k-1}$ yang memiliki $k-2$ elemen awal yang sama untuk menghasilkan kandidat $k$-itemset.
   * **Prune Step (*Anti-monotone property*)**: Memeriksa seluruh subset berukuran $k-1$ dari kandidat. Jika ada subset yang bukan merupakan *frequent itemset*, kandidat langsung dipangkas tanpa perlu dihitung.
   * **Support Counting**: Menghitung irisan TID untuk kandidat yang lolos dan menyimpan itemset yang memenuhi *minimum support*.
4. **Pembentukan Aturan Asosiasi (*Association Rules*)**:
   * Dari setiap *frequent itemset* ($k \ge 2$), dibentuk pasangan aturan $A \rightarrow B$ di mana $A \cap B = \emptyset$ dan $A \cup B = I$.
   * Menghitung nilai metrik:
     * $\text{Support}(A \rightarrow B) = \text{Support}(A \cup B)$
     * $\text{Confidence}(A \rightarrow B) = \frac{\text{Support}(A \cup B)}{\text{Support}(A)}$
     * $\text{Lift}(A \rightarrow B) = \frac{\text{Confidence}(A \rightarrow B)}{\text{Support}(B)}$
   * Menyaring aturan yang memenuhi $\text{Confidence} \ge \text{min\_confidence}$.
   * Aturan diurutkan berdasarkan nilai **Lift Ratio** tertinggi.

### 2.5 Server Web & API Flask (`app.py`)
Flask bertindak sebagai pengendali utama (*controller*):
* **Route `/` (Dataset Transaksi)**:
  * Mengambil data transaksi beserta item-itemnya dengan paginasi 20 baris per halaman.
  * Mendukung pencarian instan berdasarkan nama item atau ID transaksi.
  * Mendukung fitur **Sortir Data Terbaru** (`ORDER BY t.id DESC`) secara default maupun pengurutan terlama.
* **Route `/transaksi/tambah` & `/transaksi/<id>/ubah`**:
  * Menampilkan formulir input yang memuat **katalog 169 item lengkap** dari dataset, sehingga pengguna tinggal mengklik item yang dibeli tanpa perlu mengetik manual.
* **Route `/transaksi/<id>/hapus`**:
  * Menghapus transaksi dan seluruh relasi itemnya secara aman menggunakan cascade delete.
* **Route `/komputasi` & Endpoint API `/api/komputasi` (POST)**:
  * Menerima payload JSON parameter `min_support` dan `min_confidence` dari frontend.
  * Memanggil `jalankan_apriori()` dan mengembalikan ringkasan data, tabel frequent itemset, aturan asosiasi, serta 10 item terlaris dalam format JSON.

### 2.6 Antarmuka Pengguna / Frontend (`templates/` & `static/`)
* **Tema Visual**: *Emerald Retail Theme* (Aksen Hijau Emerald `#10B981` dipadukan dengan Dark Slate `#0F172A` dan tipografi Plus Jakarta Sans).
* **Sidebar Collapsible**:
  * Tombol toggle berada di dalam header sidebar.
  * Mendukung mode penuh (260px) dan mode mini/icon-only (72px) yang tetap dapat diklik langsung.
* **Halaman Komputasi & Visualisasi**:
  * Input *Minimum Support* dan *Minimum Confidence* menggunakan angka persentase (0-100%) dengan *shadow placeholder* (default 1% dan 30%).
  * **Filter Ukuran $k$**: Dropdown dinamis untuk menyaring tabel Frequent Itemset (1-itemset, 2-itemset, 3-itemset, dst.).
  * **Pencarian & Sorting Rules**: Kolom pencarian nama item pada aturan belanja serta dropdown sorting berdasarkan Lift Ratio, Confidence, atau Support.
  * **3 Grafik Interaktif Chart.js**:
    1. *Top 10 Item Terlaris* (Horizontal Bar Chart).
    2. *Scatter Plot Support vs Confidence* (dengan pewarnaan titik berdasarkan nilai Lift Ratio).
    3. *Top 10 Rules berdasarkan Lift Ratio* (Aturan asosiasi terkuat).

---

## 3. Struktur Direktori Proyek

```text
UAS DATA MINING/
├── app.py                  # Aplikasi server Flask (Routing, CRUD, dan API Komputasi)
├── database.py             # Inisialisasi skema SQLite (transaksi & item_transaksi)
├── import_data.py          # Skrip ETL import data/groceries.csv ke SQLite
├── apriori_engine.py       # Algoritma Apriori manual (TID Sets, Join & Prune)
├── requirements.txt        # Daftar dependensi Python minimal (Flask, Jinja2, Werkzeug)
├── data.db                 # Database SQLite lokal yang telah terisi data transaksi
├── data/
│   └── groceries.csv       # File dataset transaksi ritel asli
├── templates/
│   ├── base.html           # Layout utama: Sidebar collapsible, Topbar, Flash messages
│   ├── index.html          # Halaman daftar transaksi, pencarian, dan sortir terbaru
│   ├── form.html           # Halaman CRUD dengan katalog 169 item klik-klik
│   └── compute.html        # Halaman komputasi Apriori, tabel hasil, dan grafik
└── static/
    ├── css/style.css       # Emerald Retail Styling & responsivitas
    └── js/compute.js       # Logika AJAX komputasi, filter K, sorting rules, & Chart.js
```

---

## 4. Cara Menjalankan Sistem

### 4.1 Persiapan Awal
1. Buka terminal pada folder proyek ini.
2. Buat dan aktifkan virtual environment:
   * **Windows (PowerShell)**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   * **Windows (CMD)**:
     ```cmd
     python -m venv venv
     venv\Scripts\activate.bat
     ```
   * **macOS / Linux**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
3. Install dependensi:
   ```bash
   pip install -r requirements.txt
   ```

### 4.2 Menjalankan Aplikasi
1. *(Opsional)* Jika ingin mengimpor ulang data dari file CSV:
   ```bash
   python import_data.py
   ```
2. Jalankan server Flask:
   ```bash
   python app.py
   ```
3. Buka peramban di alamat: **`http://127.0.0.1:5000`**

---

## 5. Interpretasi Hasil Analisis Asosiasi

* **Support**: Seberapa sering kombinasi produk dibeli bersama dari total keseluruhan transaksi.
  * *Contoh*: Support 0.02 (2%) berarti kombinasi produk tersebut muncul pada minimal 2% transaksi belanja.
* **Confidence**: Tingkat kepastian bahwa pelanggan yang membeli produk A juga akan membeli produk B.
  * *Contoh*: Confidence 0.40 (40%) dari aturan $\{yogurt\} \rightarrow \{whole\ milk\}$ berarti 40% pembeli yogurt juga membeli whole milk.
* **Lift Ratio**: Kekuatan korelasi asosiasi antar produk.
  * $\text{Lift} > 1$: Asosiasi **positif** (produk saling mendorong pembelian satu sama lain, lebih sering dibeli bersama dibandingkan kebetulan acak).
  * $\text{Lift} = 1$: Independen (tidak ada hubungan asosiasi).
  * $\text{Lift} < 1$: Asosiasi **negatif** (produk cenderung tidak dibeli bersamaan).
