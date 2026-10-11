let originalSenderVersion = null;

function rowToHtml(row) {
  const warn = row.folder_exists === false
    ? '<span class="chip warn">پوشه ساخته نشده</span>'
    : "";
  const isEnabled = row.enabled === true || row.enabled === 1 || row.enabled === "1";
  return `
    <tr>
      <td><input type="text" data-field="id" value="${row.id || ""}"> ${warn}</td>
      <td><input type="text" data-field="name" value="${row.name || ""}"></td>
      <td><input type="text" data-field="company" value="${row.company || ""}"></td>
      <td><input type="text" data-field="level" value="${row.level || ""}"></td>
      <td><input type="text" data-field="valid_from" value="${row.valid_from || ""}"></td>
      <td><input type="text" data-field="valid_to" value="${row.valid_to || ""}"></td>
      <td><input type="checkbox" data-field="enabled" ${isEnabled ? "checked" : ""}></td>
      <td><button class="btn danger remove-row-btn" type="button">حذف</button></td>
    </tr>`;
}

function readRows() {
  const rows = [];
  document.querySelectorAll("#rewards-tbody tr").forEach(tr => {
    const get = (field) => tr.querySelector(`[data-field="${field}"]`);
    rows.push({
      id: get("id").value.trim(),
      name: get("name").value.trim(),
      company: get("company").value.trim(),
      level: get("level").value.trim(),
      valid_from: get("valid_from").value.trim(),
      valid_to: get("valid_to").value.trim(),
      enabled: get("enabled").checked ? "1" : "0",
    });
  });
  return rows;
}

function showBanner(kind, message) {
  document.getElementById("banner").innerHTML = `<div class="banner ${kind}">${message}</div>`;
}

function showConfirmModal(rowCount, senderVersion, onConfirm) {
  const root = document.getElementById("modal-root");
  root.innerHTML = `
    <div class="modal-overlay">
      <div class="modal-box">
        <div>${rowCount} ردیف پاداش + نسخه‌ی سندر ${senderVersion} ذخیره شود؟</div>
        <div class="toolbar">
          <button class="btn" id="modal-cancel">انصراف</button>
          <button class="btn primary" id="modal-confirm">تایید و ذخیره</button>
        </div>
      </div>
    </div>`;
  document.getElementById("modal-cancel").onclick = () => { root.innerHTML = ""; };
  document.getElementById("modal-confirm").onclick = () => { root.innerHTML = ""; onConfirm(); };
}

async function loadRewards() {
  const res = await fetch("/api/rewards");
  const data = await res.json();
  document.getElementById("rewards-tbody").innerHTML = data.rows.map(rowToHtml).join("");
  originalSenderVersion = data.sender_version;
  document.querySelectorAll('input[name="sender_version"]').forEach(el => {
    el.checked = (el.value === data.sender_version);
  });
  attachRowHandlers();
}

function showDisableConfirmModal(name, onConfirm, onCancel) {
  const root = document.getElementById("modal-root");
  root.innerHTML = `
    <div class="modal-overlay">
      <div class="modal-box">
        <div>پاداش «${name || "(بدون نام)"}» غیرفعال شود؟</div>
        <div class="toolbar">
          <button class="btn" id="modal-cancel">انصراف</button>
          <button class="btn danger" id="modal-confirm">تایید و غیرفعال کن</button>
        </div>
      </div>
    </div>`;
  document.getElementById("modal-cancel").onclick = () => { root.innerHTML = ""; onCancel(); };
  document.getElementById("modal-confirm").onclick = () => { root.innerHTML = ""; onConfirm(); };
}

function attachRowHandlers() {
  document.querySelectorAll(".remove-row-btn").forEach(btn => {
    btn.onclick = () => btn.closest("tr").remove();
  });
  document.querySelectorAll('#rewards-tbody input[data-field="enabled"]').forEach(cb => {
    cb.onchange = () => {
      const senderVersion = document.querySelector('input[name="sender_version"]:checked').value;
      if (cb.checked) {
        // enabling is non-destructive - save immediately, no confirm needed
        saveRows(readRows(), senderVersion);
        return;
      }
      const tr = cb.closest("tr");
      const name = tr.querySelector('[data-field="name"]').value.trim();
      cb.checked = true;
      showDisableConfirmModal(name, async () => {
        cb.checked = false;
        await saveRows(readRows(), senderVersion);
      }, () => { cb.checked = true; });
    };
  });
}

async function saveRows(rows, senderVersion) {
  try {
    const res = await fetch("/api/rewards", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({rows}),
    });
    const data = await res.json();
    if (!res.ok) { showBanner("error", data.error || "خطای نامشخص"); return; }

    if (senderVersion !== originalSenderVersion) {
      const res2 = await fetch("/api/sender_version", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({version: senderVersion}),
      });
      const data2 = await res2.json();
      if (!res2.ok) { showBanner("error", data2.error || "خطای نامشخص"); return; }
    }

    showBanner("ok", "ذخیره شد.");
    loadRewards();
  } catch (e) {
    showBanner("error", "اتصال به سرور برقرار نشد.");
  }
}

document.getElementById("add-row-btn").onclick = () => {
  document.getElementById("rewards-tbody").insertAdjacentHTML(
    "beforeend", rowToHtml({enabled: "1"})
  );
  attachRowHandlers();
};

document.getElementById("save-btn").onclick = () => {
  const rows = readRows();
  const senderVersion = document.querySelector('input[name="sender_version"]:checked').value;
  showConfirmModal(rows.length, senderVersion === "1" ? "۱" : "۲", () => saveRows(rows, senderVersion));
};

loadRewards();
