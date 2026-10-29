/* 押金记账官网脚本：切换界面示意的四个页面，并把下载清单里的版本信息填到页面上。 */

(function () {
  "use strict";

  /* ---------- 界面示意：标签切换 ---------- */

  var tabs = Array.prototype.slice.call(document.querySelectorAll(".tab"));
  var statusText = document.getElementById("status-text");
  var STATUS = {
    players: "本机账本 · 12 位玩家 · 总押金 3 430.00 元",
    session: "本局已选 4 人 · 茶水 2.00 元 · 确认后写入流水",
    ledger: "东子 · 当前押金 118.00 元 · 共 46 条流水",
    handover: "导出的是整个账本文件 · 导入前自动备份"
  };

  function selectTab(name) {
    tabs.forEach(function (tab) {
      var active = tab.getAttribute("data-tab") === name;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
      var pane = document.getElementById("pane-" + tab.getAttribute("data-tab"));
      if (pane) pane.classList.toggle("is-active", active);
    });
    if (statusText && STATUS[name]) statusText.textContent = STATUS[name];
  }

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      selectTab(tab.getAttribute("data-tab"));
    });
    tab.addEventListener("keydown", function (event) {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      var index = tabs.indexOf(tab);
      var next = event.key === "ArrowRight" ? (index + 1) % tabs.length : (index - 1 + tabs.length) % tabs.length;
      tabs[next].focus();
      selectTab(tabs[next].getAttribute("data-tab"));
    });
  });

  /* 允许 ?tab=session 之类的地址直接停在某个页面，方便单独介绍 */
  var wanted = (location.search.match(/[?&]tab=(players|session|ledger|handover)/) || [])[1];
  if (wanted) selectTab(wanted);

  /* ---------- 下载清单 ---------- */

  function formatSize(bytes) {
    var mb = bytes / 1024 / 1024;
    return (mb >= 100 ? mb.toFixed(0) : mb.toFixed(1)) + " MB";
  }

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el && value) el.textContent = value;
  }

  var buttons = [document.getElementById("download-btn"), document.getElementById("download-btn-2")];

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
      setText("dl-built", data.built_at);

      var hashEl = document.getElementById("dl-hash");
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

  var year = document.getElementById("year");
  if (year) year.textContent = new Date().getFullYear();
})();
