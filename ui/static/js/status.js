let recentActivityCache = [];
let logFilterMode = "all"; // "all" | "ok" | "fail"
let logSearchTerm = "";

function renderLog() {
  const logBox = document.getElementById("recent-log");
  if (!logBox) return;
  let recent = recentActivityCache;
  if (logFilterMode === "ok") recent = recent.filter(e => e.ok);
  else if (logFilterMode === "fail") recent = recent.filter(e => !e.ok);
  if (logSearchTerm) {
    const term = logSearchTerm.toLowerCase();
    recent = recent.filter(e => (e.contact || "").toLowerCase().includes(term));
  }
  const countTag = document.getElementById("log-count");
  if (countTag) countTag.textContent = recent.length ? recent.length.toLocaleString("fa-IR") + " مورد" : "";
  if (recent.length === 0) {
    logBox.innerHTML = '<div class="empty">چیزی برای نمایش نیست</div>';
    return;
  }
  logBox.innerHTML = recent.map(e => {
    const time = e.ts ? new Date(e.ts * 1000).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "-";
    const label = e.ok ? (e.contact || "-") : `${e.contact || "-"} — ${e.error || "ناموفق"}`;
    const reward = e.reward_name ? `${e.reward_name}${e.slot ? " · " + e.slot : ""}` : "";
    return `<div class="log-row ${e.ok ? "ok" : "fail"}">
      <span class="log-time">${time}</span>
      <span class="log-contact" title="${label}">${label}</span>
      ${reward ? `<span class="log-reward" title="${reward}">${reward}</span>` : ""}
    </div>`;
  }).join("");
}

function fmtDuration(s) {
  if (s === null || s === undefined) return "-";
  s = Math.max(0, Math.floor(s));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  if (h) return h + "h " + m + "m";
  if (m) return m + "m " + sec + "s";
  return sec + "s";
}
const fmtUptime = fmtDuration;

function successClass(pct) {
  if (pct === null || pct === undefined) return "";
  if (pct >= 95) return "success-good";
  if (pct >= 70) return "success-mid";
  return "success-bad";
}

function renderCurrent(current) {
  if (!current) return "";
  if (current.phase === "rendering") {
    return '<div class="reward-current">در حال آماده‌سازی گزارش (دانلود/ساخت)...</div>';
  }
  const pct = current.percent === null || current.percent === undefined ? 0 : current.percent;
  const barClass = (current.failed > 0) ? "progress-fill failing" : "progress-fill";
  const etaText = current.eta_seconds === null ? "" : (" - تخمین باقی‌مانده: " + fmtDuration(current.eta_seconds));
  return `
    <div class="reward-current">
      اسلات ${current.slot || ""} در حال ارسال: ${current.ok + current.failed} از ${current.total}
      ${current.failed ? "(" + current.failed + " ناموفق)" : ""} - ${pct}%${etaText}
      <div class="progress-track"><div class="${barClass}" style="width:${Math.min(100, pct)}%"></div></div>
    </div>`;
}

function renderTodaySummaryTag(s) {
  if (!s) return "";
  const cls = successClass(s.success_pct);
  const tagCls = cls === "success-good" ? "success-good" : cls === "success-bad" ? "success-bad" : "success-mid";
  return `<span class="tag ${tagCls}">${s.slots_sent} اسلات - ${s.ok}/${s.total} (${s.success_pct}%)</span>`;
}

function renderUpcoming(upcoming, enabled, nextSlot) {
  if (upcoming && upcoming.length > 0) {
    const [next, ...rest] = upcoming;
    let html = `<div class="reward-current">نزدیک‌ترین اسلات: ${next.slot} (${fmtDuration(next.seconds_until)} دیگر)</div>`;
    if (rest.length) {
      html += '<div class="chip-row">' + rest.map(u => `<span class="chip">${u.slot} (${fmtDuration(u.seconds_until)} دیگر)</span>`).join("") + '</div>';
    }
    return html;
  }
  // No slot left today (2026-09-30, user decision - "پاداش‌های غیرفعال
  // نیازی به نمایش اسلات برای اجرا نیست"): a disabled reward shows nothing
  // at all here; an enabled one shows its real next occurrence (date+time),
  // computed server-side in dashboard_state._next_slot_after_today().
  if (!enabled) return "";
  if (nextSlot) {
    return `<div class="reward-current">اسلات بعدی: ${nextSlot.weekday} ${nextSlot.date} ساعت ${nextSlot.slot}</div>`;
  }
  return '<div class="reward-current">اسلات دیگری برای این پاداش پیدا نشد</div>';
}

// Today's finished slots as one compact wrap-row of pills (instead of one
// full-width line per slot) - the detail text moves into the hover title so
// a reward with many slots doesn't turn into a wall of text.
function renderPastSlots(pastSlots) {
  if (!pastSlots || pastSlots.length === 0) return "";
  const pills = pastSlots.map(s => {
    if (s.ok === undefined) {
      return `<span class="slot-pill muted" title="${s.detail || s.status}">${s.slot} · ${s.status}</span>`;
    }
    const cls = successClass(s.success_pct);
    const durationText = s.duration_sec === null ? "" : (" - " + fmtDuration(s.duration_sec));
    const title = `${s.total} پیام، ${s.ok} موفق، ${s.failed} ناموفق${durationText}`;
    return `<span class="slot-pill ${cls}" title="${title}">${s.slot} · ${s.total} پیام · ${s.success_pct}%</span>`;
  }).join("");
  return `<div class="slot-pills"><span class="slot-pills-label">امروز:</span>${pills}</div>`;
}

function renderRewardCard(r) {
  const running = !!r.current;
  const meta = [r.company, r.level].filter(Boolean).join(" · ");
  const stateCls = running ? "running" : (r.enabled ? "on" : "off");
  const statusText = running ? "در جریان" : (r.enabled ? "فعال" : "خاموش");
  const body = running ? renderCurrent(r.current) : renderUpcoming(r.upcoming, r.enabled, r.next_slot);
  return `
    <div class="reward-card ${stateCls}">
      <div class="reward-head">
        <span class="dot ${r.enabled || running ? 'on' : 'off'}"></span>
        <div class="reward-title">
          <div class="reward-name">${r.name}</div>
          ${meta ? `<div class="reward-meta">${meta}</div>` : ""}
        </div>
        ${renderTodaySummaryTag(r.today_summary)}
        <span class="status ${stateCls}">${statusText}</span>
      </div>
      ${body}
      ${renderPastSlots(r.past_slots)}
    </div>`;
}

function renderRewardGroup(title, rows) {
  if (!rows.length) return "";
  return `<div class="reward-group">
    <div class="reward-group-title">${title} <span>${rows.length.toLocaleString("fa-IR")}</span></div>
    ${rows.map(renderRewardCard).join("")}
  </div>`;
}

const BROADCAST_LABELS = {
  "padash-karshenasan-5040": "شرکت 5040",
  "padash-tamdid-karshenasan-hamkadeh": "شرکت همکده",
};

async function tickBroadcasts() {
  try {
    const res = await fetch("/api/broadcasts");
    const data = await res.json();
    const box = document.getElementById("broadcasts");
    const sections = Object.entries(data)
      .map(([id, history]) => ({ id, label: BROADCAST_LABELS[id] || id, latest: history[0] }))
      .filter(s => s.latest);

    if (sections.length === 0) {
      box.innerHTML = '<div class="empty">هنوز پیام انبوهی ثبت نشده</div>';
      return;
    }
    box.innerHTML = sections.map(s => {
      const total = s.latest.recipient_count || 0;
      const pct = total ? Math.round((s.latest.ok_count / total) * 1000) / 10 : null;
      const subject = s.latest.subject || (s.latest.text || "").split("\n")[0];
      return `
      <div class="broadcast-row" title="${s.latest.sent_at}">
        <div class="broadcast-line">
          <span class="broadcast-name">${s.label}</span>
          <span class="chip">${total} گیرنده</span>
          <span class="chip ${pct !== null && pct >= 90 ? "next" : "warn"}">${pct !== null ? pct + "%" : "-"}</span>
          ${s.latest.fail_count ? `<span class="chip warn">${s.latest.fail_count} ناموفق</span>` : ""}
        </div>
        <div class="broadcast-subject">${subject}</div>
      </div>`;
    }).join("");
  } catch (e) {
    // ساکت رد شو - این باکس فرعیه، نباید کل صفحه رو بابتش خراب کنه
  }
}

async function tick() {
  try {
    const res = await fetch("/api/state");
    const data = await res.json();

    document.getElementById("meta").textContent =
      "الان: " + data.now + "    آخرین فعالیت: " + data.last_activity_at +
      "    مدت اجرا: " + fmtUptime(data.uptime_seconds);

    document.getElementById("rewards-title").textContent =
      "پاداش‌ها (" + data.active_count + "/" + data.reward_status.length + " فعال)";

    const runningRows = data.reward_status.filter(r => r.current);
    const badge = document.getElementById("running-badge");
    document.getElementById("running-count").textContent = runningRows.length.toLocaleString("fa-IR");
    badge.classList.toggle("idle", runningRows.length === 0);
    badge.title = runningRows.length ? runningRows.map(r => r.name).join("\n") : "الان هیچ پاداشی در حال اجرا نیست";

    const box = document.getElementById("rewards");
    if (data.reward_status.length === 0) {
      box.innerHTML = '<div class="empty">config/rewards.csv خالی یا موجود نیست</div>';
    } else {
      const idleRows = data.reward_status.filter(r => !r.current);
      box.innerHTML =
        renderRewardGroup("در جریان", runningRows) +
        renderRewardGroup("فعال", idleRows.filter(r => r.enabled)) +
        renderRewardGroup("خاموش", idleRows.filter(r => !r.enabled));
    }

    const dlBox = document.getElementById("downloads");
    if (!data.downloads || data.downloads.length === 0) {
      dlBox.innerHTML = '<div class="empty">چیزی در حال دانلود نیست</div>';
    } else {
      dlBox.innerHTML = data.downloads.map(d => `
        <div class="row">
          <span class="dot on"></span>
          <span class="name">${d.downloader}</span>
          <span class="tag">${d.reward_name || d.reward_id}</span>
        </div>`).join("");
    }

    const tokBox = document.getElementById("tokens");
    const entries = Object.entries(data.token_status || {});
    if (entries.length === 0) {
      tokBox.innerHTML = '<div class="empty">هنوز هیچ چکی انجام نشده</div>';
    } else {
      tokBox.innerHTML = entries.map(([company, ok]) => `
        <div class="row">
          <span class="dot ${ok ? 'on' : 'off'}"></span>
          <span class="name">${company}</span>
          <span class="status ${ok ? 'on' : 'off'}">${ok ? 'سالم' : 'منقضی'}</span>
        </div>`).join("");
    }
    document.getElementById("tokens-title").textContent =
      "سلامت توکن‌ها (چک بعدی: " + fmtUptime(Math.max(0, data.next_token_check_in)) + ")";

    recentActivityCache = data.recent_activity || [];
    renderLog();
    if (recentActivityCache.length === 0 && logFilterMode === "all" && !logSearchTerm) {
      document.getElementById("recent-log").innerHTML = '<div class="empty">هنوز فعالیتی ثبت نشده</div>';
    }

    const errBox = document.getElementById("error");
    if (data.last_error) {
      errBox.className = "error";
      errBox.textContent = data.last_error.at + "  " + data.last_error.message;
    } else {
      errBox.className = "ok";
      errBox.textContent = "چیزی از زمان شروع رخ نداده";
    }
  } catch (e) {
    document.getElementById("meta").textContent = "اتصال به سرور محلی قطع شد...";
  }
}

(function () {
  const searchInput = document.getElementById("log-search");
  const okBtn = document.getElementById("log-filter-ok");
  const failBtn = document.getElementById("log-filter-fail");
  if (!searchInput || !okBtn || !failBtn) return;

  function syncButtons() {
    okBtn.classList.toggle("active", logFilterMode === "ok");
    failBtn.classList.toggle("active", logFilterMode === "fail");
  }
  searchInput.addEventListener("input", function () {
    logSearchTerm = searchInput.value.trim();
    renderLog();
  });
  okBtn.addEventListener("click", function () {
    logFilterMode = logFilterMode === "ok" ? "all" : "ok";
    syncButtons();
    renderLog();
  });
  failBtn.addEventListener("click", function () {
    logFilterMode = logFilterMode === "fail" ? "all" : "fail";
    syncButtons();
    renderLog();
  });
})();

tick();
setInterval(tick, 1000);

tickBroadcasts();
setInterval(tickBroadcasts, 30000);
