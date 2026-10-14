"use strict";
(function () {
  var PAGE_SIZE = 50;
  var state = { q: "", dataset: "", location: "", unit: "", category: "", subcategory: "", sort: "name", desc: false, page: 1 };
  var data = [];
  var filtered = [];

  var $ = function (id) { return document.getElementById(id); };
  var tbody = $("tbl").getElementsByTagName("tbody")[0];
  var headers = $("tbl").getElementsByTagName("th");

  var datasetLabels = {};

  function label(d) {
    var m = /^(bafu_\d{4}_v\d+)$/.exec(d || "");
    if (!m) return d || "";
    if (!datasetLabels[d]) {
      var p = d.split("_");
      datasetLabels[d] = "BAFU " + p[1] + " v" + p[2].replace(/^v/, "");
    }
    return datasetLabels[d];
  }

  function datasetOrder(d) {
    var m = /^bafu_(\d{4})_v(\d+)$/.exec(d || "");
    return m ? (parseInt(m[1], 10) * 1000 + parseInt(m[2], 10)) : 0;
  }

  function fillSelect(id, values, labelText) {
    var sel = $(id);
    values.forEach(function (v) {
      var o = document.createElement("option");
      o.value = v;
      o.textContent = labelText ? labelText(v) : v;
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
    return out;
  }

  function uniqDatasets() {
    var seen = Object.create(null);
    var out = [];
    data.forEach(function (d) {
      if (!seen[d.dataset]) { seen[d.dataset] = true; out.push(d.dataset); }
    });
    out.sort(function (a, b) { return datasetOrder(a) - datasetOrder(b); });
    return out;
  }

  function apply() {
    var q = state.q.trim().toLowerCase();
    filtered = data.filter(function (d) {
      if (state.dataset && d.dataset !== state.dataset) return false;
      if (state.location && d.location !== state.location) return false;
      if (state.unit && d.unit !== state.unit) return false;
      if (state.category && d.category !== state.category) return false;
      if (state.subcategory && d.subcategory !== state.subcategory) return false;
      if (q) {
        var hay = (d.name + " " + d.uuid + " " + d.dataset + " " + d.category + " " + d.subcategory + " " + (d.location || "")).toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
    var k = state.sort;
    filtered.sort(function (a, b) {
      var c;
      if (k === "dataset") {
        c = datasetOrder(a.dataset) - datasetOrder(b.dataset);
      } else {
        var va = a[k] || "", vb = b[k] || "";
        c = String(va).localeCompare(String(vb), undefined, { numeric: true, sensitivity: "base" });
      }
      if (c === 0 && a.uuid !== b.uuid) {
        c = String(a.uuid).localeCompare(String(b.uuid));
      }
      return state.desc ? -c : c;
    });
    state.page = Math.min(state.page, Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)));
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function link(d, dlabel) {
    return '<a href="/bafu-dev/pages/' + d.dataset + "/process/" + d.uuid + '/">' + esc(dlabel) + "</a>";
  }

  function render() {
    var start = (state.page - 1) * PAGE_SIZE;
    var rows = filtered.slice(start, start + PAGE_SIZE);
    var html = rows.map(function (d) {
      return "<tr>" +
        '<td class="name">' + link(d, d.name) + "</td>" +
        "<td>" + link(d, label(d.dataset)) + "</td>" +
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
  ["dataset", "location", "unit", "category", "subcategory"].forEach(function (id) {
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

  var preset = new URLSearchParams(window.location.search).get("dataset");
  if (preset) { state.dataset = preset; }

  fetch("/bafu-dev/assets/index.json")
    .then(function (r) { return r.json(); })
    .then(function (d) {
      data = d;
      fillSelect("dataset", uniqDatasets(), label);
      $("dataset").value = state.dataset;
      fillSelect("location", uniq("location").sort(function (a, b) { return a.localeCompare(b, undefined, { numeric: true }); }));
      fillSelect("unit", uniq("unit").sort(function (a, b) { return a.localeCompare(b, undefined, { numeric: true }); }));
      fillSelect("category", uniq("category").sort(function (a, b) { return a.localeCompare(b, undefined, { numeric: true }); }));
      fillSelect("subcategory", uniq("subcategory").sort(function (a, b) { return a.localeCompare(b, undefined, { numeric: true }); }));
      refresh();
    })
    .catch(function (err) {
      $("count").textContent = "Failed to load index: " + err;
    });
})();
