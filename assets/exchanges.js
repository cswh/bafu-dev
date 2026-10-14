"use strict";
(function () {
  var dataEl = document.getElementById("ex-data");
  if (!dataEl) return;
  var payload = JSON.parse(dataEl.textContent);
  var rows = payload.rows;
  var details = payload.details;
  var urls = payload.urls;

  var labels = { eco: "EcoSpold1" };
  rows.forEach(function (r) {
    if (r.raw && r.raw[0] && !labels[r.raw[0]]) labels[r.raw[0]] = r.source;
  });

  var $ = function (id) { return document.getElementById(id); };
  var tbody = document.querySelector("#ex-table tbody");
  var headers = document.querySelectorAll("#ex-table th");

  var state = { q: "", source: "", direction: "", sphere: "", sort: "group", desc: false };

  function fillSources() {
    var sel = $("ex-source");
    var seen = {};
    rows.forEach(function (r) {
      if (!seen[r.source]) { seen[r.source] = true; }
    });
    Object.keys(seen).sort().forEach(function (s) {
      var o = document.createElement("option");
      o.value = s; o.textContent = s;
      sel.appendChild(o);
    });
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function apply() {
    var q = state.q.trim().toLowerCase();
    return rows.filter(function (r) {
      if (state.source && r.source !== state.source) return false;
      if (state.direction && r.direction !== state.direction) return false;
      if (state.sphere && r.sphere !== state.sphere) return false;
      if (q) {
        var hay = [r.name, r.source, r.direction, r.amount, r.unit, r.cat, r.location, r.sphere].join(" ").toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
  }

  function render() {
    var view = apply();
    var k = state.sort;
    view.sort(function (a, b) {
      var c;
      if (k === "group") {
        c = (a.group == null ? 1e9 : a.group) - (b.group == null ? 1e9 : b.group);
        if (c === 0) c = a.source.localeCompare(b.source);
      } else if (k === "amount") {
        var va = parseFloat(a.amount), vb = parseFloat(b.amount);
        if (isNaN(va)) va = -Infinity;
        if (isNaN(vb)) vb = -Infinity;
        c = va - vb;
      } else {
        c = String(a[k] == null ? "" : a[k]).localeCompare(String(b[k] == null ? "" : b[k]), undefined, { numeric: true });
      }
      return state.desc ? -c : c;
    });
    tbody.innerHTML = view.map(function (r) {
      var srcCls = r.source === "EcoSpold1" ? "src-eco" : "src-ilcd";
      var rowCls = r.group == null ? ' class="orphan"' : (r.ref ? ' class="refrow"' : "");
      var rawBtn = r.raw && (r.raw[1] !== null && r.raw[1] !== undefined)
        ? '<button class="detail-btn" data-src="' + esc(r.raw[0]) + '" data-idx="' + r.raw[1] + '">raw</button>'
        : "";
      return "<tr" + rowCls + ">" +
        "<td>" + esc(r.name) + "</td>" +
        '<td class="' + srcCls + '">' + esc(r.source) + "</td>" +
        "<td>" + esc(r.direction) + "</td>" +
        "<td>" + esc(r.amount) + "</td>" +
        "<td>" + esc(r.unit) + "</td>" +
        "<td>" + esc(r.cat) + "</td>" +
        "<td>" + esc(r.location) + "</td>" +
        "<td>" + esc(r.sphere) + "</td>" +
        "<td>" + rawBtn + "</td>" +
        "</tr>";
    }).join("");
    $("ex-count").textContent = view.length + " of " + rows.length + " rows";
    updateHeaders();
  }

  function updateHeaders() {
    Array.prototype.forEach.call(headers, function (th) {
      th.classList.remove("sort-asc", "sort-desc");
      if (th.getAttribute("data-key") === state.sort) {
        th.classList.add(state.desc ? "sort-desc" : "sort-asc");
      }
    });
  }

  $("ex-q").addEventListener("input", function () { state.q = this.value; render(); });
  $("ex-source").addEventListener("change", function () { state.source = this.value; render(); });
  $("ex-direction").addEventListener("change", function () { state.direction = this.value; render(); });
  $("ex-sphere").addEventListener("change", function () { state.sphere = this.value; render(); });
  $("ex-sort").addEventListener("change", function () { state.sort = this.value; render(); });
  $("ex-desc").addEventListener("change", function () { state.desc = this.checked; render(); });
  Array.prototype.forEach.call(headers, function (th) {
    th.addEventListener("click", function () {
      var k = th.getAttribute("data-key");
      if (!k) return;
      if (state.sort === k) { state.desc = !state.desc; } else { state.sort = k; state.desc = false; }
      render();
    });
  });

  var box = $("ex-detail");
  var panes = $("detail-panes");
  var cache = {};

  function extractNth(xmlText, n) {
    var doc = new DOMParser().parseFromString(xmlText, "application/xml");
    var els = doc.getElementsByTagName("exchange");
    return els.length > n ? new XMLSerializer().serializeToString(els[n]) : null;
  }

  tbody.addEventListener("click", function (e) {
    var btn = e.target.closest ? e.target.closest(".detail-btn") : null;
    if (!btn) return;
    var src = btn.getAttribute("data-src");
    var idx = parseInt(btn.getAttribute("data-idx"), 10);
    var url = urls[src];
    if (!url) return;
    panes.innerHTML = '<div><h3>' + esc(labels[src] || src) + " exchange (raw)</h3><pre>loading...</pre></div>";
    box.hidden = false;
    var pre = panes.querySelector("pre");
    if (cache[url]) {
      pre.textContent = extractNth(cache[url], idx) || "(exchange not found)";
      return;
    }
    fetch(url).then(function (r) { return r.text(); }).then(function (t) {
      cache[url] = t;
      pre.textContent = extractNth(t, idx) || "(exchange not found)";
    }).catch(function () { pre.textContent = "(failed to load raw file)"; });
  });

  $("ex-detail-close").addEventListener("click", function () { box.hidden = true; });

  fillSources();
  render();
})();
