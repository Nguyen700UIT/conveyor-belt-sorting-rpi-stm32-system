"use strict";
const $ = id => document.getElementById(id);
const labels = ["green", "riped", "damaged"];
const outcomes = {pending: "Đang chờ", accepted: "ACK · Đã nhận", rejected: "Bị từ chối", not_sent: "Chưa gửi", unknown: "Không rõ"};
const countFormat = new Intl.NumberFormat("vi-VN");
let zone = "Asia/Bangkok";
let connected = false;
let viewing = false;
let cameraActive = false;
let refreshTimer = null;
let refreshing = false;
let refreshAgain = false;
let followingToday = true;

function today() {
  const parts = new Intl.DateTimeFormat("en-US", {timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit"}).formatToParts(new Date());
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}
function daysBefore(day, amount) {
  const date = new Date(`${day}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() - amount);
  return date.toISOString().slice(0, 10);
}
function error(message) { $("error").textContent = message; $("error").hidden = !message; }
async function json(url) {
  const response = await fetch(url, {cache: "no-store"});
  if (!response.ok) throw new Error(`Không tải được dữ liệu (HTTP ${response.status}). Kiểm tra ngày và khoảng tối đa 366 ngày.`);
  return response.json();
}
function cell(value) { const element = document.createElement("td"); element.textContent = value; return element; }
function renderHistory(rows) {
  $("daily").replaceChildren(); $("chart").replaceChildren();
  const max = Math.max(1, ...rows.map(row => row.total));
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.append(cell(row.date), ...labels.map(label => cell(countFormat.format(row.counts[label]))), cell(countFormat.format(row.total)));
    $("daily").append(tr);
    const line = document.createElement("div"); line.className = "chart-row";
    const date = document.createElement("span"); date.textContent = row.date;
    const bar = document.createElement("div"); bar.className = "bar";
    for (const label of labels) {
      const segment = document.createElement("span"); segment.className = label === "riped" ? "ripe" : label;
      segment.style.width = `${row.counts[label] * 100 / max}%`; bar.append(segment);
    }
    const total = document.createElement("span"); total.textContent = countFormat.format(row.total);
    line.append(date, bar, total); $("chart").append(line);
  }
}
async function refresh() {
  if (refreshing) { refreshAgain = true; return; }
  refreshing = true;
  try {
    if (followingToday && $("day").value !== today()) {
      $("day").value = today(); $("end").value = today(); $("start").value = daysBefore(today(), 6);
    }
    const selected = $("day").value, start = $("start").value, end = $("end").value;
    if (!selected || !start || !end) throw new Error("Vui lòng chọn đủ ngày.");
    const [summary, rows] = await Promise.all([
      json(`/api/summary?date=${encodeURIComponent(selected)}`),
      json(`/api/daily?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`)
    ]);
    if (selected !== $("day").value || start !== $("start").value || end !== $("end").value) { refreshAgain = true; return; }
    zone = summary.timezone; $("timezone").textContent = zone;
    $("total").textContent = countFormat.format(summary.total);
    for (const label of labels) { $(label).textContent = countFormat.format(summary.counts[label]); $(`${label}-ratio`).textContent = `${summary.percentages[label]}%`; }
    $("outcomes").replaceChildren();
    for (const [key, text] of Object.entries(outcomes)) {
      const item = document.createElement("div"); item.className = "outcome";
      const number = document.createElement("strong"); number.textContent = countFormat.format(summary.outcomes[key]);
      item.append(document.createTextNode(text), number); $("outcomes").append(item);
    }
    renderHistory(rows); error("");
    $("updated").textContent = `Cập nhật ${new Date().toLocaleTimeString("vi-VN")}`;
  } catch (exc) { error(exc.message); }
  finally { refreshing = false; if (refreshAgain) { refreshAgain = false; scheduleRefresh(); } }
}
function scheduleRefresh() { if (refreshTimer === null) refreshTimer = setTimeout(() => { refreshTimer = null; refresh(); }, 200); }
function stopCamera() {
  viewing = false; $("camera-image").removeAttribute("src"); $("camera-image").hidden = true;
  $("camera-placeholder").hidden = false; $("camera-toggle").textContent = "Bật xem camera";
}
$("camera-toggle").onclick = () => {
  if (viewing) { stopCamera(); return; }
  if (!connected || !cameraActive) return;
  viewing = true; $("camera-image").src = `/camera/stream?t=${Date.now()}`;
  $("camera-image").hidden = false; $("camera-placeholder").hidden = true; $("camera-toggle").textContent = "Tắt xem camera";
};
$("camera-image").onerror = () => { stopCamera(); $("camera-status").textContent = "Stream đã ngắt hoặc chưa có frame mới. Bấm bật để thử lại."; };
$("day").value = today(); $("end").value = today(); $("start").value = daysBefore(today(), 6);
$("day").onchange = () => { followingToday = false; scheduleRefresh(); };
$("today").onclick = () => { followingToday = true; $("day").value = today(); scheduleRefresh(); };
$("history").onclick = scheduleRefresh;
const events = new EventSource("/api/events");
events.onopen = () => { connected = true; $("connection").textContent = "● Đã kết nối"; scheduleRefresh(); };
events.onmessage = event => {
  const state = JSON.parse(event.data); cameraActive = state.camera.active;
  zone = state.timezone;
  $("camera-status").textContent = state.camera.message; $("camera-toggle").disabled = !cameraActive;
  if (!cameraActive) stopCamera(); scheduleRefresh();
};
events.onerror = () => { connected = false; $("connection").textContent = "● Mất kết nối · đang kết nối lại"; $("camera-toggle").disabled = true; stopCamera(); };
// Chỉ đặt một timer tại mốc đổi ngày; không polling dữ liệu.
function scheduleMidnight() {
  const now = new Date();
  const local = new Intl.DateTimeFormat("en-GB", {timeZone: zone, hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23"}).formatToParts(now);
  const p = Object.fromEntries(local.map(part => [part.type, part.value]));
  const remaining = 86400 - Number(p.hour) * 3600 - Number(p.minute) * 60 - Number(p.second);
  setTimeout(() => { if (followingToday) scheduleRefresh(); scheduleMidnight(); }, remaining * 1000 + 100);
}
scheduleMidnight();
