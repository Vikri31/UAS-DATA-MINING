/**
 * Groceries Data Miner - Frontend Analytics Engine
 * Enterprise Emerald Retail UI for Apriori Mining
 */

const form = document.getElementById("form-komputasi");
const statusEl = document.getElementById("status");
const hasilEl = document.getElementById("hasil");
const filterKEl = document.getElementById("filter-k");
const filterRuleItemEl = document.getElementById("filter-rule-item");
const sortRulesEl = document.getElementById("sort-rules");
const charts = {};

let currentItemsets = [];
let currentRules = [];

// Cegah XSS: escape karakter teks dari input pengguna
function esc(teks) {
  const d = document.createElement("div");
  d.textContent = teks;
  return d.innerHTML;
}

// Inisialisasi atau redraw canvas Chart.js
function gambar(id, config) {
  if (charts[id]) {
    charts[id].destroy();
  }
  const canvas = document.getElementById(id);
  if (canvas) {
    charts[id] = new Chart(canvas, config);
  }
}

// Event listener filter ukuran K pada Frequent Itemset
if (filterKEl) {
  filterKEl.addEventListener("change", (e) => {
    const selectedK = e.target.value;
    if (selectedK === "all") {
      renderItemsets(currentItemsets);
    } else {
      const kNum = parseInt(selectedK, 10);
      const filtered = currentItemsets.filter((item) => item.k === kNum);
      renderItemsets(filtered);
    }
  });
}

// Event listeners untuk filter item dan sorting Association Rules
if (filterRuleItemEl) {
  filterRuleItemEl.addEventListener("input", () => {
    renderRules();
  });
}

if (sortRulesEl) {
  sortRulesEl.addEventListener("change", () => {
    renderRules();
  });
}

// Fungsi render tabel Frequent Itemset
function renderItemsets(itemsetsToRender) {
  const tblItemsetBody = document.querySelector("#tbl-itemset tbody");
  const countBadge = document.getElementById("itemset-count-badge");

  if (countBadge) {
    if (filterKEl && filterKEl.value !== "all") {
      countBadge.textContent = `${itemsetsToRender.length} dari ${currentItemsets.length} Itemset (k = ${filterKEl.value})`;
    } else {
      countBadge.textContent = `${itemsetsToRender.length} Itemset Ditemukan`;
    }
  }

  if (itemsetsToRender.length > 0) {
    tblItemsetBody.innerHTML = itemsetsToRender
      .map((r) => {
        const itemPills = r.itemset
          .map((itm) => `<span class="badge-item-pill"><i class="fa-solid fa-tag text-muted me-1" style="font-size: 0.65rem;"></i>${esc(itm)}</span>`)
          .join(" ");

        return `<tr>
          <td>${itemPills}</td>
          <td style="text-align: center;">
            <span class="badge bg-light text-secondary border fw-bold">${r.k}-item</span>
          </td>
          <td style="text-align: center;" class="fw-semibold text-secondary">${r.count.toLocaleString()} trx</td>
          <td style="text-align: center;">
            <span class="badge-emerald" title="Support: ${r.support}">
              <i class="fa-solid fa-percent" style="font-size: 0.65rem;"></i> ${(r.support * 100).toFixed(2)}%
            </span>
          </td>
        </tr>`;
      })
      .join("");
  } else {
    tblItemsetBody.innerHTML = `<tr>
      <td colspan="4" class="text-center py-4 text-muted">
        <i class="fa-solid fa-circle-exclamation text-warning me-1"></i>
        Tidak ada itemset untuk filter ukuran k ini.
      </td>
    </tr>`;
  }
}

// Fungsi filter dan sorting Association Rules
function renderRules() {
  const tblRulesBody = document.querySelector("#tbl-rules tbody");
  const countBadge = document.getElementById("rules-count-badge");

  if (!tblRulesBody) return;

  const searchQuery = filterRuleItemEl ? filterRuleItemEl.value.trim().toLowerCase() : "";
  const sortMode = sortRulesEl ? sortRulesEl.value : "lift-desc";

  // 1. Filter berdasarkan pencarian item (baik di antecedent atau consequent)
  let filtered = currentRules.filter((r) => {
    if (!searchQuery) return true;
    const allItems = [...r.antecedent, ...r.consequent].map((x) => x.toLowerCase());
    return allItems.some((itm) => itm.includes(searchQuery));
  });

  // 2. Sorting sesuai pilihan dropdown
  filtered.sort((a, b) => {
    if (sortMode === "conf-desc") {
      return b.confidence - a.confidence || b.lift - a.lift;
    } else if (sortMode === "supp-desc") {
      return b.support - a.support || b.confidence - a.confidence;
    } else {
      // Default: lift-desc
      return b.lift - a.lift || b.confidence - a.confidence;
    }
  });

  // 3. Update counter badge
  if (countBadge) {
    if (searchQuery) {
      countBadge.textContent = `${filtered.length} dari ${currentRules.length} Aturan ("${esc(searchQuery)}")`;
    } else {
      countBadge.textContent = `${filtered.length} Aturan Terbentuk`;
    }
  }

  // 4. Render baris tabel
  if (filtered.length > 0) {
    tblRulesBody.innerHTML = filtered
      .map((r) => {
        const antePills = r.antecedent
          .map((itm) => `<span class="badge-item-pill"><i class="fa-solid fa-tag text-muted me-1" style="font-size: 0.65rem;"></i>${esc(itm)}</span>`)
          .join(" ");
        const conseqPills = r.consequent
          .map((itm) => `<span class="badge-item-pill"><i class="fa-solid fa-tag text-muted me-1" style="font-size: 0.65rem;"></i>${esc(itm)}</span>`)
          .join(" ");

        const liftHighlight = r.lift >= 2.0 
          ? `<span class="badge-lift" title="Korelasi Asosiasi Sangat Kuat"><i class="fa-solid fa-fire text-danger"></i> ${r.lift}</span>`
          : `<span class="badge-lift" title="Korelasi Asosiasi Positif"><i class="fa-solid fa-bolt"></i> ${r.lift}</span>`;

        return `<tr>
          <td>${antePills}</td>
          <td style="text-align: center;">
            <i class="fa-solid fa-arrow-right text-success" title="Maka cenderung membeli"></i>
          </td>
          <td>${conseqPills}</td>
          <td style="text-align: center;">
            <span class="badge-emerald" title="Support: ${r.support}">
              ${(r.support * 100).toFixed(2)}%
            </span>
          </td>
          <td style="text-align: center;">
            <span class="badge-amber" title="Confidence: ${r.confidence}">
              <i class="fa-solid fa-gauge-high" style="font-size: 0.65rem;"></i> ${(r.confidence * 100).toFixed(1)}%
            </span>
          </td>
          <td style="text-align: center;">
            ${liftHighlight}
          </td>
        </tr>`;
      })
      .join("");
  } else {
    tblRulesBody.innerHTML = `<tr>
      <td colspan="6" class="text-center py-4 text-muted">
        <i class="fa-solid fa-circle-exclamation text-warning me-1"></i>
        ${searchQuery ? `Tidak ada aturan asosiasi yang memuat item "${esc(searchQuery)}".` : "Tidak ada association rules yang memenuhi kriteria."}
      </td>
    </tr>`;
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("btn-proses");
  const originalBtnHtml = btn.innerHTML;

  // Nilai input dalam persen (0 - 100%)
  const supportPercent = parseFloat(form.min_support.value);
  const confidencePercent = parseFloat(form.min_confidence.value);

  // Validasi batas persentase di sisi client
  if (isNaN(supportPercent) || supportPercent <= 0 || supportPercent > 100) {
    statusEl.innerHTML = `
      <div class="alert-modern error">
        <i class="fa-solid fa-triangle-exclamation fs-5 text-danger"></i>
        <div><b>Nilai tidak valid:</b> Minimum Support harus berupa angka antara 0.1% dan 100%.</div>
      </div>`;
    return;
  }

  if (isNaN(confidencePercent) || confidencePercent <= 0 || confidencePercent > 100) {
    statusEl.innerHTML = `
      <div class="alert-modern error">
        <i class="fa-solid fa-triangle-exclamation fs-5 text-danger"></i>
        <div><b>Nilai tidak valid:</b> Minimum Confidence harus berupa angka antara 1% dan 100%.</div>
      </div>`;
    return;
  }

  // Konversi persen (0-100) ke desimal (0-1) untuk backend API
  const min_support = supportPercent / 100.0;
  const min_confidence = confidencePercent / 100.0;

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Menghitung Apriori...`;
  
  statusEl.innerHTML = `
    <div class="alert-modern bg-white border shadow-sm">
      <div class="spinner-border spinner-border-sm text-success me-2" role="status"></div>
      <span class="text-secondary fw-medium">Sedang memproses algoritma Apriori pada 9.835 transaksi (Support: ${supportPercent}%, Confidence: ${confidencePercent}%)...</span>
    </div>`;

  try {
    const res = await fetch("/api/komputasi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        min_support: min_support,
        min_confidence: min_confidence,
      }),
    });
    const data = await res.json();

    if (!res.ok) {
      statusEl.innerHTML = `
        <div class="alert-modern error">
          <i class="fa-solid fa-triangle-exclamation fs-5 text-danger"></i>
          <div><b>Gagal memproses data:</b> ${esc(data.error || "Terjadi kesalahan pada server.")}</div>
        </div>`;
      hasilEl.hidden = true;
      return;
    }

    statusEl.innerHTML = "";
    tampilkan(data);
    
    // Smooth scroll ke bagian hasil
    hasilEl.scrollIntoView({ behavior: 'smooth', block: 'start' });

  } catch (err) {
    statusEl.innerHTML = `
      <div class="alert-modern error">
        <i class="fa-solid fa-circle-exclamation fs-5 text-danger"></i>
        <div><b>Koneksi Terputus:</b> Gagal menghubungi endpoint server Flask.</div>
      </div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalBtnHtml;
  }
});

function tampilkan(d) {
  hasilEl.hidden = false;
  currentItemsets = d.itemsets;
  currentRules = d.rules;

  const supPercentStr = (d.min_support * 100).toFixed(1);
  const confPercentStr = (d.min_confidence * 100).toFixed(0);

  // 1. Ringkasan 4 Stat Cards
  const ringkasanEl = document.getElementById("ringkasan");
  ringkasanEl.innerHTML = `
    <!-- Card 1: Total Transaksi -->
    <div class="col-12 col-sm-6 col-xl-3">
      <div class="stat-card emerald">
        <div class="stat-content">
          <div class="stat-label">Total Transaksi</div>
          <div class="stat-value">${d.total_transaksi.toLocaleString()}</div>
          <div class="stat-desc text-muted">Basis transaksi groceries</div>
        </div>
        <div class="stat-icon-wrapper emerald">
          <i class="fa-solid fa-receipt"></i>
        </div>
      </div>
    </div>

    <!-- Card 2: Frequent Itemset -->
    <div class="col-12 col-sm-6 col-xl-3">
      <div class="stat-card slate">
        <div class="stat-content">
          <div class="stat-label">Frequent Itemset</div>
          <div class="stat-value">${d.itemsets.length.toLocaleString()}</div>
          <div class="stat-desc text-muted">Lolos support &ge; ${supPercentStr}%</div>
        </div>
        <div class="stat-icon-wrapper slate">
          <i class="fa-solid fa-layer-group"></i>
        </div>
      </div>
    </div>

    <!-- Card 3: Association Rules -->
    <div class="col-12 col-sm-6 col-xl-3">
      <div class="stat-card amber">
        <div class="stat-content">
          <div class="stat-label">Association Rules</div>
          <div class="stat-value">${d.rules.length.toLocaleString()}</div>
          <div class="stat-desc text-muted">Confidence &ge; ${confPercentStr}%</div>
        </div>
        <div class="stat-icon-wrapper amber">
          <i class="fa-solid fa-link"></i>
        </div>
      </div>
    </div>

    <!-- Card 4: Durasi Komputasi -->
    <div class="col-12 col-sm-6 col-xl-3">
      <div class="stat-card teal">
        <div class="stat-content">
          <div class="stat-label">Waktu Eksekusi</div>
          <div class="stat-value">${d.durasi} <span class="fs-6 text-muted fw-normal">detik</span></div>
          <div class="stat-desc text-muted">Komputasi Algoritma Apriori</div>
        </div>
        <div class="stat-icon-wrapper teal">
          <i class="fa-solid fa-stopwatch"></i>
        </div>
      </div>
    </div>
  `;

  // 2. Populasi Filter Dropdown K secara dinamis
  if (filterKEl) {
    const uniqueKs = [...new Set(d.itemsets.map((x) => x.k))].sort((a, b) => a - b);
    let optionsHtml = `<option value="all">Semua Ukuran (k)</option>`;
    uniqueKs.forEach((kVal) => {
      optionsHtml += `<option value="${kVal}">${kVal}-Itemset (k = ${kVal})</option>`;
    });
    filterKEl.innerHTML = optionsHtml;
    filterKEl.value = "all";
  }

  // 3. Render Tabel Frequent Itemset
  renderItemsets(currentItemsets);

  // 4. Render Tabel Association Rules
  if (filterRuleItemEl) filterRuleItemEl.value = "";
  if (sortRulesEl) sortRulesEl.value = "lift-desc";
  renderRules();

  // 5. Grafik 1: Top 10 Item Terlaris (Emerald Theme)
  gambar("chart-top-item", {
    type: "bar",
    data: {
      labels: d.top_items.map((x) => x.item),
      datasets: [
        {
          label: "Jumlah Transaksi",
          data: d.top_items.map((x) => x.jumlah),
          backgroundColor: "#10B981",
          hoverBackgroundColor: "#059669",
          borderRadius: 6,
          borderSkipped: false,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#0F172A",
          titleFont: { family: "Plus Jakarta Sans", size: 12, weight: "bold" },
          bodyFont: { family: "Plus Jakarta Sans", size: 12 },
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            label: (ctx) => ` Terjual di ${ctx.raw.toLocaleString()} transaksi`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: "#F1F5F9" },
          ticks: { font: { family: "Plus Jakarta Sans", size: 11 }, color: "#64748B" },
        },
        y: {
          grid: { display: false },
          ticks: { font: { family: "Plus Jakarta Sans", size: 11, weight: "600" }, color: "#334155" },
        },
      },
    },
  });

  // 6. Grafik 2: Scatter Support vs Confidence (Warna = Lift Ratio)
  const maxLift = Math.max(1, ...d.rules.map((r) => r.lift || 1));
  gambar("chart-scatter", {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Association Rules",
          data: d.rules.map((r) => ({
            x: r.support,
            y: r.confidence,
            lift: r.lift,
            ante: r.antecedent.join(", "),
            conseq: r.consequent.join(", "),
          })),
          pointRadius: 6,
          pointHoverRadius: 9,
          backgroundColor: d.rules.map((r) => {
            const ratio = Math.min(1, r.lift / maxLift);
            return `rgba(16, 185, 129, ${0.45 + 0.55 * ratio})`;
          }),
          borderColor: "#059669",
          borderWidth: 1.5,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#0F172A",
          titleFont: { family: "Plus Jakarta Sans", size: 12, weight: "bold" },
          bodyFont: { family: "Plus Jakarta Sans", size: 11 },
          padding: 12,
          cornerRadius: 8,
          callbacks: {
            title: (items) => {
              const raw = items[0].raw;
              return `${raw.ante} → ${raw.conseq}`;
            },
            label: (ctx) => [
              ` Support    : ${(ctx.raw.x * 100).toFixed(2)}% (${ctx.raw.x})`,
              ` Confidence : ${(ctx.raw.y * 100).toFixed(1)}% (${ctx.raw.y})`,
              ` Lift Ratio : ${ctx.raw.lift}`,
            ],
          },
        },
      },
      scales: {
        x: {
          title: { display: true, text: "Support Value", font: { family: "Plus Jakarta Sans", weight: "600" }, color: "#475569" },
          grid: { color: "#F1F5F9" },
          ticks: { font: { family: "Plus Jakarta Sans", size: 11 }, color: "#64748B" },
        },
        y: {
          title: { display: true, text: "Confidence Value", font: { family: "Plus Jakarta Sans", weight: "600" }, color: "#475569" },
          grid: { color: "#F1F5F9" },
          ticks: { font: { family: "Plus Jakarta Sans", size: 11 }, color: "#64748B" },
        },
      },
    },
  });

  // 7. Grafik 3: Top 10 Rules berdasarkan Lift Ratio
  const topRules = d.rules.slice(0, 10);
  gambar("chart-lift", {
    type: "bar",
    data: {
      labels: topRules.map((r) => `${r.antecedent.join(", ")} → ${r.consequent.join(", ")}`),
      datasets: [
        {
          label: "Lift Ratio",
          data: topRules.map((r) => r.lift),
          backgroundColor: topRules.map((_, idx) => idx < 3 ? "#059669" : "#10B981"),
          hoverBackgroundColor: "#047857",
          borderRadius: 6,
          borderSkipped: false,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#0F172A",
          titleFont: { family: "Plus Jakarta Sans", size: 12, weight: "bold" },
          bodyFont: { family: "Plus Jakarta Sans", size: 11 },
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            label: (ctx) => ` Lift Ratio: ${ctx.raw} (Kekuatan asosiasi)`,
          },
        },
      },
      scales: {
        x: {
          title: { display: true, text: "Lift Ratio", font: { family: "Plus Jakarta Sans", weight: "600" }, color: "#475569" },
          grid: { color: "#F1F5F9" },
          ticks: { font: { family: "Plus Jakarta Sans", size: 11 }, color: "#64748B" },
        },
        y: {
          grid: { display: false },
          ticks: { font: { family: "Plus Jakarta Sans", size: 10, weight: "600" }, color: "#334155" },
        },
      },
    },
  });
}
