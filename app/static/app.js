const state = { selectedFile: null, dashboard: null };

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const money = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const integer = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const asMoney = (value) => money.format(Number(value || 0));
const asPercent = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;
const shortDate = (value) => value ? new Date(`${String(value).slice(0, 10)}T00:00:00`).toLocaleDateString("en-US", { month: "short", year: "numeric" }) : "—";

async function fetchJson(path, options = {}) {
  const response = await fetch(path, options);
  if (response.status === 404) return null;
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try { detail = (await response.json()).detail || detail; } catch (_) { /* response was not JSON */ }
    throw new Error(detail);
  }
  return response.json();
}

function showMessage(text, isError = false) {
  const message = $("#message");
  message.textContent = text;
  message.classList.toggle("error", isError);
  message.hidden = false;
  if (!isError) window.setTimeout(() => { message.hidden = true; }, 9000);
}

function table(columns, rows) {
  if (!rows?.length) return '<div class="empty">No records match this view.</div>';
  const head = columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("");
  const body = rows.map((row) => `<tr>${columns.map((column) => {
    const rendered = column.render ? column.render(row[column.key], row) : escapeHtml(row[column.key]);
    return `<td>${rendered}</td>`;
  }).join("")}</tr>`).join("");
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function renderKpis(summary, runs) {
  const latestSource = runs?.items?.[0]?.source_file || "No file loaded";
  const cards = [
    ["Total revenue", asMoney(summary.total_revenue), "Validated sales value", true],
    ["Total profit", asMoney(summary.total_profit), "Across loaded sales lines"],
    ["Profit margin", asPercent(summary.profit_margin), "Profit ÷ revenue"],
    ["Total orders", integer.format(summary.total_orders), "Distinct order IDs"],
    ["Customers", integer.format(summary.unique_customers), "Distinct active customers"],
    ["Average order", asMoney(summary.average_order_value), "Revenue per order"],
    ["Units / order", Number(summary.average_units_per_order).toFixed(2), "Average basket volume"],
    ["Latest source", latestSource, "Most recent audited ETL run"],
  ];
  $("#kpi-grid").innerHTML = cards.map(([label, value, note, accent]) => `
    <article class="kpi ${accent ? "accent" : ""}">
      <span class="label">${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small>
    </article>`).join("");
}

function renderMonthly(rows) {
  const chart = $("#monthly-chart");
  if (!rows?.length) { chart.innerHTML = '<div class="empty">Upload data to see a trend.</div>'; return; }
  const maximum = Math.max(...rows.map((row) => Number(row.revenue)), 1);
  chart.innerHTML = rows.map((row) => {
    const height = Math.max(2, (Number(row.revenue) / maximum) * 100);
    return `<div class="chart-column" style="--height:${height}%" title="${escapeHtml(shortDate(row.month_start))}">
      <i style="height:${height}%"></i><span>${escapeHtml(shortDate(row.month_start))}: ${asMoney(row.revenue)}</span>
    </div>`;
  }).join("");
}

function renderRankList(target, rows, labelKey, valueKey, formatter = asMoney) {
  const element = $(target);
  if (!rows?.length) { element.innerHTML = '<div class="empty">No data available.</div>'; return; }
  const maximum = Math.max(...rows.map((row) => Math.abs(Number(row[valueKey]))), 1);
  element.innerHTML = rows.map((row) => {
    const width = Math.max(3, Math.abs(Number(row[valueKey])) / maximum * 100);
    return `<div class="rank-row"><span>${escapeHtml(row[labelKey])}</span><div class="track"><i style="width:${width}%"></i></div><strong>${escapeHtml(formatter(row[valueKey]))}</strong></div>`;
  }).join("");
}

function renderProducts(rows) {
  $("#products-table").innerHTML = table([
    { key: "product_name", label: "Product" }, { key: "category", label: "Category" },
    { key: "revenue", label: "Revenue", render: (v) => asMoney(v) },
    { key: "profit", label: "Profit", render: (v) => `<span class="money ${v < 0 ? "negative" : ""}">${asMoney(v)}</span>` },
    { key: "profit_margin", label: "Margin", render: (v) => asPercent(v) },
    { key: "units", label: "Units", render: (v) => integer.format(v) },
    { key: "average_discount", label: "Avg. discount", render: (v) => asPercent(v) },
  ], rows);
}

function renderCustomers(rows) {
  $("#customers-table").innerHTML = table([
    { key: "customer_name", label: "Customer" }, { key: "region", label: "Region" },
    { key: "lifetime_revenue", label: "Revenue", render: (v) => asMoney(v) },
    { key: "lifetime_profit", label: "Profit", render: (v) => `<span class="money ${v < 0 ? "negative" : ""}">${asMoney(v)}</span>` },
    { key: "purchase_frequency", label: "Orders" },
    { key: "rfm_segment", label: "RFM segment", render: (v) => `<span class="badge">${escapeHtml(v)}</span>` },
  ], rows);
}

function renderRegions(rows) {
  $("#regions-table").innerHTML = table([
    { key: "region", label: "Region" }, { key: "revenue", label: "Revenue", render: (v) => asMoney(v) },
    { key: "profit", label: "Profit", render: (v) => asMoney(v) },
    { key: "profit_margin", label: "Margin", render: (v) => asPercent(v) },
    { key: "orders", label: "Orders", render: (v) => integer.format(v) },
    { key: "customers", label: "Customers", render: (v) => integer.format(v) },
    { key: "units", label: "Units", render: (v) => integer.format(v) },
  ], rows);
}

function renderQuality(quality, runs) {
  const score = Number(quality?.quality_score || 0);
  $("#quality-score").style.setProperty("--score", `${score}%`);
  $("#quality-score").innerHTML = `<strong>${score.toFixed(1)}%</strong>`;
  $("#quality-details").innerHTML = [
    [quality?.total_rows || 0, "Total rows"], [quality?.valid_rows || 0, "Valid"], [quality?.invalid_rows || 0, "Rejected"],
  ].map(([value, label]) => `<div><strong>${integer.format(value)}</strong><small>${label}</small></div>`).join("");
  $("#runs-table").innerHTML = table([
    { key: "source_file", label: "Source" },
    { key: "status", label: "Status", render: (v) => `<span class="badge ${v === "failed" ? "warn" : ""}">${escapeHtml(v)}</span>` },
    { key: "total_rows", label: "Rows", render: (v) => integer.format(v) },
    { key: "quality_score", label: "Quality", render: (v) => v == null ? "—" : `${Number(v).toFixed(1)}%` },
    { key: "started_at", label: "Started", render: (v) => new Date(v).toLocaleString() },
  ], runs?.items || []);
}

function renderLeakage(rows) {
  $("#leakage-table").innerHTML = table([
    { key: "order_date", label: "Date" }, { key: "order_id", label: "Order" },
    { key: "product_name", label: "Product" }, { key: "region", label: "Region" },
    { key: "sales", label: "Sales", render: (v) => asMoney(v) },
    { key: "profit", label: "Profit", render: (v) => `<span class="money ${v < 0 ? "negative" : ""}">${asMoney(v)}</span>` },
    { key: "discount", label: "Discount", render: (v) => asPercent(v) },
    { key: "leakage_reason", label: "Reason", render: (v) => `<span class="badge warn">${escapeHtml(v)}</span>` },
  ], rows);
}

function renderDashboard(data) {
  renderKpis(data.summary, data.runs);
  renderMonthly(data.monthly);
  renderRankList("#region-bars", data.regions, "region", "revenue");
  renderProducts(data.products);
  renderCustomers(data.customers);
  renderRankList("#segments-list", data.segments, "rfm_segment", "revenue");
  renderRegions(data.regions);
  renderQuality(data.quality, data.runs);
  renderLeakage(data.leakage);
}

async function loadDashboard() {
  $("#loading").hidden = false;
  try {
    const [summary, monthly, products, customers, segments, regions, leakage, quality, runs] = await Promise.all([
      fetchJson("/api/v1/summary"), fetchJson("/api/v1/revenue/monthly"),
      fetchJson("/api/v1/products/top?limit=12&sort_by=revenue"), fetchJson("/api/v1/customers/top?limit=12"),
      fetchJson("/api/v1/customers/segments"), fetchJson("/api/v1/regions/performance"),
      fetchJson("/api/v1/profit-leakage?limit=30"), fetchJson("/api/v1/data-quality/latest"),
      fetchJson("/api/v1/etl-runs?limit=10&offset=0"),
    ]);
    state.dashboard = { summary, monthly, products, customers, segments, regions, leakage, quality, runs };
    renderDashboard(state.dashboard);
    $("#api-dot").classList.add("online");
    $("#api-label").textContent = "API connected";
  } catch (error) {
    showMessage(`Could not load analytics: ${error.message}`, true);
    $("#api-label").textContent = "API unavailable";
  } finally {
    $("#loading").hidden = true;
  }
}

function selectFile(file) {
  if (!file) return;
  const extension = file.name.split(".").pop().toLowerCase();
  if (!["csv", "xlsx"].includes(extension)) { showMessage("Choose a .csv or .xlsx file.", true); return; }
  if (file.size > 10 * 1024 * 1024) { showMessage("The file is larger than 10 MB.", true); return; }
  state.selectedFile = file;
  $("#file-label").textContent = file.name;
  $("#file-meta").textContent = `${(file.size / 1024).toFixed(1)} KB · Ready to process`;
  $("#upload-button").disabled = false;
}

async function uploadSelectedFile(event) {
  event.stopPropagation();
  if (!state.selectedFile) return;
  const button = $("#upload-button");
  const zone = $("#drop-zone");
  button.disabled = true;
  button.textContent = "Processing…";
  zone.classList.add("processing");
  try {
    const result = await fetchJson(`/api/v1/upload?filename=${encodeURIComponent(state.selectedFile.name)}`, {
      method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: state.selectedFile,
    });
    showMessage(`${result.message} Quality score: ${result.quality_score.toFixed(1)}%.`);
    button.textContent = "Processed";
    await loadDashboard();
  } catch (error) {
    showMessage(`Upload failed: ${error.message}`, true);
    button.disabled = false;
    button.textContent = "Try again";
  } finally {
    zone.classList.remove("processing");
  }
}

function setSection(sectionId) {
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.section === sectionId));
  $$(".dashboard-section").forEach((section) => section.classList.toggle("active-section", section.id === sectionId));
  const titles = { overview: "Executive overview", products: "Product intelligence", customers: "Customer intelligence", regions: "Regional performance", quality: "Data quality", leakage: "Profit leakage" };
  $("#page-title").textContent = titles[sectionId] || "RetailPulse";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function initialize() {
  const dropZone = $("#drop-zone");
  const fileInput = $("#file-input");
  dropZone.addEventListener("click", (event) => { if (event.target.id !== "upload-button") fileInput.click(); });
  dropZone.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) fileInput.click(); });
  fileInput.addEventListener("change", () => selectFile(fileInput.files[0]));
  ["dragenter", "dragover"].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.add("dragging"); }));
  ["dragleave", "drop"].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.remove("dragging"); }));
  dropZone.addEventListener("drop", (event) => selectFile(event.dataTransfer.files[0]));
  $("#upload-button").addEventListener("click", uploadSelectedFile);
  $("#refresh-button").addEventListener("click", loadDashboard);
  $$(".nav-item").forEach((item) => item.addEventListener("click", () => setSection(item.dataset.section)));
  loadDashboard();
}

document.addEventListener("DOMContentLoaded", initialize);
