/* 押金记账官网脚本：界面示意（可点的四个页面）和下载清单。示意里的规则与程序保持一致。 */

(function () {
  "use strict";

  function $(id) { return document.getElementById(id); }
  function each(list, fn) { Array.prototype.forEach.call(list, fn); }

  function formatYuan(cents) {
    var sign = cents < 0 ? "−" : "";
    var abs = Math.abs(cents);
    return sign + Math.floor(abs / 100) + "." + ("0" + (abs % 100)).slice(-2);
  }

  /* 和程序一样：最多两位小数、不能为负。不合法时返回 null。 */
  function parseYuan(text) {
    var value = String(text || "").trim();
    if (!/^\d+(\.\d{0,2})?$/.test(value)) return null;
    var parts = value.split(".");
    return parseInt(parts[0], 10) * 100 + parseInt(((parts[1] || "") + "00").slice(0, 2), 10);
  }

  /* ---------- 标签切换 ---------- */

  var tabs = Array.prototype.slice.call(document.querySelectorAll(".tab"));
  var statusText = $("status-text");
  var STATUS = {
    players: "本机账本 · 6 位玩家 · 总押金 334.00 元",
    session: "",
    ledger: "东子 · 当前押金 118.00 元 · 共 46 条流水",
    handover: "导出的是整个账本文件 · 导入前自动备份"
  };

  function selectTab(name) {
    tabs.forEach(function (tab) {
      var active = tab.getAttribute("data-tab") === name;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
      var pane = $("pane-" + tab.getAttribute("data-tab"));
      if (pane) pane.classList.toggle("is-active", active);
    });
    closeDialog();
    if (name === "session") refreshSession();
    else if (statusText && STATUS[name]) statusText.textContent = STATUS[name];
  }

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () { selectTab(tab.getAttribute("data-tab")); });
    tab.addEventListener("keydown", function (event) {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      var index = tabs.indexOf(tab);
      var next = event.key === "ArrowRight" ? (index + 1) % tabs.length : (index - 1 + tabs.length) % tabs.length;
      tabs[next].focus();
      selectTab(tabs[next].getAttribute("data-tab"));
    });
  });

  /* ---------- 玩家库：搜索定位 ---------- */

  var searchInput = $("demo-search");
  var searchHint = $("demo-search-hint");
  var playerRows = Array.prototype.slice.call(document.querySelectorAll("#players-table tbody tr"));
  var hits = [];
  var hitPos = -1;

  /* 游戏 id 完全一致的排第一，其余按 id 或备注包含关键字 */
  function findRows(keyword) {
    keyword = keyword.trim().toLowerCase();
    if (!keyword) return [];
    var exact = [];
    var partial = [];
    playerRows.forEach(function (row) {
      var id = (row.getAttribute("data-id") || "").toLowerCase();
      var remark = (row.getAttribute("data-remark") || "").toLowerCase();
      if (id === keyword) exact.push(row);
      else if (id.indexOf(keyword) >= 0 || remark.indexOf(keyword) >= 0) partial.push(row);
    });
    return exact.concat(partial);
  }

  function showHit() {
    playerRows.forEach(function (row) { row.classList.remove("is-hit"); });
    searchHint.classList.remove("miss");
    if (!searchInput.value.trim()) { searchHint.textContent = ""; return; }
    if (!hits.length) { searchHint.textContent = "没找到"; searchHint.classList.add("miss"); return; }
    hits[hitPos].classList.add("is-hit");
    searchHint.textContent = (hitPos + 1) + "/" + hits.length;
  }

  if (searchInput) {
    searchInput.addEventListener("input", function () {
      hits = findRows(searchInput.value);
      hitPos = hits.length ? 0 : -1;
      showHit();
    });
    searchInput.addEventListener("keydown", function (event) {
      if (event.key !== "Enter") return;
      event.preventDefault();
      if (!hits.length) return;
      hitPos = (hitPos + 1) % hits.length;
      showHit();
    });
  }

  /* ---------- 开一局：点一行勾选、选前10个、实时算扣后押金 ---------- */

  var sessionRows = Array.prototype.slice.call(document.querySelectorAll("#session-table tbody tr"));
  var teaInput = $("demo-tea");
  var countLabel = $("demo-count");
  var negativeNote = $("demo-negative");

  function teaCents() { return parseYuan(teaInput ? teaInput.value : "2.00"); }

  function refreshSession() {
    var tea = teaCents();
    var picked = 0;
    var negative = [];
    sessionRows.forEach(function (row) {
      var cells = row.children;
      var on = row.classList.contains("picked");
      var before = parseInt(row.getAttribute("data-cents"), 10);
      cells[0].setAttribute("aria-checked", on ? "true" : "false");
      if (!on) {
        cells[3].textContent = "—"; cells[4].textContent = "—";
        cells[5].textContent = "未选"; cells[5].className = "mute";
        return;
      }
      picked += 1;
      if (tea === null) {
        cells[3].textContent = "—"; cells[4].textContent = "—";
        cells[5].textContent = "金额有误"; cells[5].className = "warn";
        return;
      }
      var after = before - tea;
      cells[3].textContent = formatYuan(-tea);
      cells[4].textContent = formatYuan(after);
      if (after < 0) {
        cells[5].textContent = "记为负数"; cells[5].className = "warn";
        negative.push(row.getAttribute("data-id"));
      } else {
        cells[5].textContent = "可以扣"; cells[5].className = "ok";
      }
    });
    if (countLabel) countLabel.textContent = "已选 " + picked + " 人";
    if (negativeNote) negativeNote.textContent = negative.length ? "以下玩家扣完后押金为负数：" + negative.join("、") : "";
    if (statusText && $("pane-session").classList.contains("is-active")) {
      statusText.textContent = "本局已选 " + picked + " 人 · 茶水 " + (tea === null ? "—" : formatYuan(tea)) + " 元 · 确认后写入流水";
    }
  }

  sessionRows.forEach(function (row) {
    row.setAttribute("tabindex", "0");
    row.addEventListener("click", function () {
      row.classList.toggle("picked");
      refreshSession();
    });
    row.addEventListener("keydown", function (event) {
      if (event.key !== " " && event.key !== "Enter") return;
      event.preventDefault();
      row.classList.toggle("picked");
      refreshSession();
    });
  });

  /* 与程序相同：前 N 个（最多 10 个）正好全选且其余未选时，再点就取消；否则勾上前 N 个 */
  var firstButton = $("demo-first");
  if (firstButton) {
    firstButton.addEventListener("click", function () {
      var count = Math.min(10, sessionRows.length);
      var already = count > 0 && sessionRows.every(function (row, index) {
        return row.classList.contains("picked") === (index < count);
      });
      sessionRows.forEach(function (row, index) {
        row.classList.toggle("picked", !already && index < count);
      });
      refreshSession();
    });
  }
  if (teaInput) teaInput.addEventListener("input", refreshSession);
  refreshSession();

  /* ---------- 押金记录：弹窗默认金额 ---------- */

  var dialog = $("demo-dialog");
  var BALANCE = 11800;

  function openDialog(kind) {
    if (!dialog) return;
    var title = $("demo-dialog-title");
    var amount = $("demo-dialog-amount");
    var target = $("demo-dialog-target");
    var hint = $("demo-dialog-hint");
    var tea = teaCents();
    target.hidden = kind !== "transfer";
    if (kind === "refund") {
      title.textContent = "退押金 · 东子";
      amount.innerHTML = "<mark>" + formatYuan(BALANCE) + "</mark>";
      hint.textContent = "默认填全部余额，已经选中，直接输入就能改。退押金不能超过当前余额。";
    } else if (kind === "transfer") {
      var cents = tea === null ? 2000 : tea * 10;
      title.textContent = "划给其他人押金 · 东子";
      amount.innerHTML = "<mark>" + formatYuan(cents) + "</mark>";
      hint.textContent = "默认是本局茶水的 10 倍（" + formatYuan(tea === null ? 200 : tea) + " × 10）。余额不够也能划，划完为负数前会再确认一次。";
    } else {
      title.textContent = "加押金 · 东子";
      amount.innerHTML = "<span class=\"placeholder\">0.00</span>";
      hint.textContent = "填收到的金额，确认后记一条「加押金」流水。";
    }
    dialog.hidden = false;
  }

  function closeDialog() { if (dialog) dialog.hidden = true; }

  each(document.querySelectorAll("[data-dialog]"), function (button) {
    button.addEventListener("click", function () { openDialog(button.getAttribute("data-dialog")); });
  });
  if (dialog) {
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog || event.target.hasAttribute("data-close")) closeDialog();
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeDialog();
    });
  }

  /* 允许 ?tab=session 之类的地址直接停在某个页面，方便单独介绍 */
  var wanted = (location.search.match(/[?&]tab=(players|session|ledger|handover)/) || [])[1];
  if (wanted) selectTab(wanted);

  /* ---------- 下载清单 ---------- */

  function formatSize(bytes) {
    var mb = bytes / 1024 / 1024;
    return (mb >= 100 ? mb.toFixed(0) : mb.toFixed(1)) + " MB";
  }

  function setText(id, value) {
    var el = $(id);
    if (el && value) el.textContent = value;
  }

  var buttons = [$("download-btn"), $("download-btn-2")];

  fetch("downloads/manifest.json", { cache: "no-store" })
    .then(function (response) {
      if (!response.ok) throw new Error("manifest " + response.status);
      return response.json();
    })
    .then(function (data) {
      if (!data || !data.file) return;
      var url = "downloads/" + data.file;

      buttons.forEach(function (button) {
        if (!button) return;
        button.setAttribute("href", url);
        button.setAttribute("download", "押金记账-" + (data.version || "") + ".zip");
      });

      setText("dl-size", formatSize(data.size_bytes));
      setText("dl-size-2", formatSize(data.size_bytes));
      setText("dl-files", data.file_count + " 个");
      setText("hero-files", data.file_count);
      setText("dl-version", data.version);
      setText("hero-version", data.version);
      setText("new-version", data.version);
      setText("dl-built", data.built_at);

      var hashEl = $("dl-hash");
      if (hashEl && data.sha256) {
        hashEl.textContent = data.sha256.slice(0, 16) + "…";
        hashEl.title = "完整 SHA-256：" + data.sha256 + "（点击复制）";
        hashEl.addEventListener("click", function () {
          var done = function () { hashEl.textContent = "已复制"; };
          var restore = function () { hashEl.textContent = data.sha256.slice(0, 16) + "…"; };
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(data.sha256).then(done).catch(restore);
          } else {
            var textarea = document.createElement("textarea");
            textarea.value = data.sha256;
            document.body.appendChild(textarea);
            textarea.select();
            try { document.execCommand("copy"); done(); } catch (error) { restore(); }
            document.body.removeChild(textarea);
          }
          setTimeout(restore, 1600);
        });
      }
    })
    .catch(function () {
      /* 用 file:// 直接预览时读不到清单，页面上的默认数字留着就行。 */
    });

  var year = $("year");
  if (year) year.textContent = new Date().getFullYear();
})();
