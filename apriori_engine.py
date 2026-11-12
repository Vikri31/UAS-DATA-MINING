from collections import defaultdict
from itertools import combinations


def load_transactions(conn, start_date=None, end_date=None):
    """Ambil transaksi dari database sebagai list of set, opsional difilter rentang tanggal."""
    clauses = []
    params = []
    if start_date:
        clauses.append("t.tanggal >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("t.tanggal <= ?")
        params.append(end_date)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        SELECT i.id_transaksi, i.nama_item
        FROM item_transaksi i
        JOIN transaksi t ON t.id = i.id_transaksi
        {where_sql}
        """,
        params,
    ).fetchall()

    data = defaultdict(set)
    for r in rows:
        data[r["id_transaksi"]].add(r["nama_item"])
    return list(data.values())


def jalankan_apriori(transactions, min_support, min_confidence):
    """
    Algoritma Apriori implementasi manual (tanpa mlxtend).
    Mengembalikan: (itemsets, rules, n)
      itemsets : list of dict {itemset, k, count, support}
      rules    : list of dict {antecedent, consequent, support, confidence, lift}
      n        : total transaksi
    """
    n = len(transactions)
    if n == 0:
        return [], [], 0

    # Petakan tiap item ke himpunan transaction ID (TID)
    item_tids = defaultdict(set)
    for tid, trx in enumerate(transactions):
        for item in trx:
            item_tids[item].add(tid)

    # 1. Cari Frequent 1-itemset (L1)
    # Gunakan itemset sebagai frozenset
    current_l = {}
    itemset_counts = {}

    for item, tids in item_tids.items():
        count = len(tids)
        sup = count / n
        if sup >= min_support:
            fset = frozenset([item])
            current_l[fset] = tids
            itemset_counts[fset] = count

    all_frequent_itemsets = dict(itemset_counts)
    k = 2

    # 2. Iterasi untuk k >= 2 (Apriori join & prune)
    while current_l:
        prev_itemsets = list(current_l.keys())
        prev_set = set(prev_itemsets)
        candidates = set()

        # Join step: gabungkan dua itemset di L(k-1)
        # Untuk efisiensi, urutkan item
        sorted_prev = [sorted(list(fs)) for fs in prev_itemsets]
        num_prev = len(sorted_prev)

        for i in range(num_prev):
            for j in range(i + 1, num_prev):
                # Jika memiliki k-2 item pertama yang sama
                if sorted_prev[i][: k - 2] == sorted_prev[j][: k - 2]:
                    candidate = frozenset(sorted_prev[i] + [sorted_prev[j][k - 2]])
                    if len(candidate) == k:
                        # Prune step: semua (k-1)-subset dari candidate harus ada di prev_set
                        subsets_valid = True
                        for subset in combinations(candidate, k - 1):
                            if frozenset(subset) not in prev_set:
                                subsets_valid = False
                                break
                        if subsets_valid:
                            candidates.add(candidate)

        # Hitung support untuk kandidat menggunakan irisan TID
        next_l = {}
        for cand in candidates:
            # Cari irisan dari elemen-elemen candidate
            # Bisa dioptimalkan dengan mengiris TID dari item pertama dan item berikutnya
            cand_items = list(cand)
            tids = item_tids[cand_items[0]]
            for itm in cand_items[1:]:
                tids = tids & item_tids[itm]
                if not tids:
                    break

            count = len(tids)
            sup = count / n
            if sup >= min_support:
                next_l[cand] = tids
                itemset_counts[cand] = count
                all_frequent_itemsets[cand] = count

        current_l = next_l
        k += 1

    # Format output itemsets
    itemsets = []
    for fs, count in all_frequent_itemsets.items():
        items = sorted(list(fs))
        sup = count / n
        itemsets.append(
            {
                "itemset": items,
                "k": len(items),
                "count": count,
                "support": round(sup, 4),
            }
        )
    # Urutkan berdasarkan k menaik, lalu support menurun
    itemsets.sort(key=lambda x: (x["k"], -x["support"]))

    # 3. Bentuk Association Rules
    rules = []
    for fs, count in all_frequent_itemsets.items():
        if len(fs) < 2:
            continue
        items = list(fs)
        itemset_sup = count / n

        # Semua kemungkinan non-empty antecedent A subset dari fs
        for r in range(1, len(fs)):
            for ante_tuple in combinations(items, r):
                ante = frozenset(ante_tuple)
                conseq = fs - ante
                ante_count = all_frequent_itemsets.get(ante)
                conseq_count = all_frequent_itemsets.get(conseq)

                if not ante_count or not conseq_count:
                    continue

                ante_sup = ante_count / n
                conseq_sup = conseq_count / n
                confidence = count / ante_count

                if confidence >= min_confidence:
                    lift = confidence / conseq_sup if conseq_sup > 0 else 0
                    rules.append(
                        {
                            "antecedent": sorted(list(ante)),
                            "consequent": sorted(list(conseq)),
                            "support": round(itemset_sup, 4),
                            "confidence": round(confidence, 4),
                            "lift": round(lift, 4),
                        }
                    )

    # Urutkan berdasarkan lift menurun, lalu confidence menurun
    rules.sort(key=lambda x: (x["lift"], x["confidence"]), reverse=True)

    return itemsets, rules, n

