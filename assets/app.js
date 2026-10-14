"use strict";
(function () {
  var PAGE_SIZE = 50;
  var state = { q: "", location: "", unit: "", category: "", subcategory: "", sort: "name", desc: false, page: 1 };
  var data = [];
  var filtered = [];

  var $ = function (id) { return document.getElementById(id); };
  var tbody = $("tbl").getElementsByTagName("tbody")[0];
  var headers = $("tbl").getElementsByTagName("th");

  function fillSelect(id, values) {
    var sel = $(id);
    values.forEach(function (v) {
      var o = document.createElement("option");
      o.value = v; o.textContent = v;
      sel.appendChild(o);
    });
  }

  function uniq(key) {
    var seen = Object.create(null);
    var out = [];
    data.forEach(function (d) {
      var v = d[key];
      if (v && !seen[v]) { seen[v] = true; out.push(v); }
    });
    out.sort(function (a, b) { return a.localeCompare(b, undefined, { numeric: true }); });
    return out;
  }

  function apply() {
    var q = state.q.trim().toLowerCase();
    var loc = state.location, unit = state.unit, cat = state.category, sub = state.subcategory;
    filtered = data.filter(function (d) {
      if (loc && d.location !== loc) return false;
      if (unit && d.unit !== unit) return false;
      if (cat && d.category !== cat) return false;
      if (sub && d.subcategory !== sub) return false;
      if (q) {
        var hay = (d.name + " " + d.uuid + " " + d.category + " " + d.subcategory + " " + (d.location || "")).toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
    var k = state.sort;
    filtered.sort(function (a, b) {
      var va = a[k] || "", vb = b[k] || "";
      var c = String(va).localeCompare(String(vb), undefined, { numeric: true, sensitivity: "base" });
      return state.desc ? -c : c;
    });
    state.page = Math.min(state.page, Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)));
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function link(d, label) {
    return '<a href="/bafu-dev/process/' + d.uuid + '/">' + esc(label) + "</a>";
  }

  function render() {
    var start = (state.page - 1) * PAGE_SIZE;
    var rows = filtered.slice(start, start + PAGE_SIZE);
    var html = rows.map(function (d) {
      return "<tr>" +
        '<td class="name">' + link(d, d.name) + "</td>" +
        "<td>" + esc(d.location) + "</td>" +
        "<td>" + esc(d.unit) + "</td>" +
        "<td>" + esc(d.category) + "</td>" +
        "<td>" + esc(d.subcategory) + "</td>" +
        "<td>" + esc(d.start) + "</td>" +
        '<td class="uuid">' + link(d, d.uuid) + "</td>" +
        "</tr>";
    }).join("");
    tbody.innerHTML = html;
    $("count").textContent = filtered.length.toLocaleString() + " of " + data.length.toLocaleString() + " processes";
    renderPagination();
    updateSortHeaders();
  }

  function renderPagination() {
    var pages = Math.ceil(filtered.length / PAGE_SIZE);
    var el = $("pagination");
    if (pages <= 1) { el.innerHTML = ""; return; }
    var html = '<button data-p="1"' + (state.page === 1 ? " disabled" : "") + ">&laquo;</button>";
    html += '<button data-p="' + Math.max(1, state.page - 1) + '"' + (state.page === 1 ? " disabled" : "") + ">&lsaquo;</button>";
    var lo = Math.max(1, state.page - 2), hi = Math.min(pages, state.page + 2);
    for (var p = lo; p <= hi; p++) {
      html += '<button data-p="' + p + '" class="' + (p === state.page ? "current" : "") + '">' + p + "</button>";
    }
    html += '<button data-p="' + Math.min(pages, state.page + 1) + '"' + (state.page === pages ? " disabled" : "") + ">&rsaquo;</button>";
    html += '<button data-p="' + pages + '"' + (state.page === pages ? " disabled" : "") + ">&raquo;</button>";
    html += '<span>' + state.page + " / " + pages + "</span>";
    el.innerHTML = html;
  }

  function updateSortHeaders() {
    Array.prototype.forEach.call(headers, function (th) {
      th.classList.remove("sort-asc", "sort-desc");
      if (th.getAttribute("data-key") === state.sort) {
        th.classList.add(state.desc ? "sort-desc" : "sort-asc");
      }
    });
  }

  function refresh() { apply(); render(); }

  $("q").addEventListener("input", function () { state.q = this.value; state.page = 1; refresh(); });
  ["location", "unit", "category", "subcategory"].forEach(function (id) {
    $(id).addEventListener("change", function () { state[id] = this.value; state.page = 1; refresh(); });
  });
  $("sort").addEventListener("change", function () { state.sort = this.value; refresh(); });
  $("desc").addEventListener("change", function () { state.desc = this.checked; refresh(); });
  Array.prototype.forEach.call(headers, function (th) {
    th.addEventListener("click", function () {
      var k = th.getAttribute("data-key");
      if (state.sort === k) { state.desc = !state.desc; } else { state.sort = k; state.desc = false; }
      refresh();
    });
  });
  $("pagination").addEventListener("click", function (e) {
    var p = e.target.getAttribute && e.target.getAttribute("data-p");
    if (p && !e.target.disabled) { state.page = parseInt(p, 10); apply(); render(); window.scrollTo(0, 0); }
  });

  fetch("/bafu-dev/assets/index.json")
    .then(function (r) { return r.json(); })
    .then(function (d) {
      data = d;
      fillSelect("location", uniq("location"));
      fillSelect("unit", uniq("unit"));
      fillSelect("category", uniq("category"));
      fillSelect("subcategory", uniq("subcategory"));
      refresh();
    })
    .catch(function (err) {
      $("count").textContent = "Failed to load index: " + err;
    });
})();
