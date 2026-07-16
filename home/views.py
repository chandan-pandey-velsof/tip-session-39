import json
import urllib.parse
import requests as http_requests
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


# ---------------------------------------------------------------------------
# API proxy — keeps the TIP API key server-side
# ---------------------------------------------------------------------------
@csrf_exempt
@require_http_methods(["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def tip_api_proxy(request, path):
    """Forward any /tip-api/<path> request to the TIP backend, attaching the API key."""
    upstream = f"{settings.TIP_API_URL}/{path}"

    # Preserve query string
    qs = request.META.get("QUERY_STRING", "")
    if qs:
        upstream += f"?{qs}"

    headers = {
        "x-api-key": settings.TIP_API_TOKEN,
    }

    # Forward content-type / body for POST etc.
    body = request.body if request.body else None
    if body:
        ct = request.META.get("CONTENT_TYPE", "")
        if ct:
            headers["Content-Type"] = ct

    try:
        resp = http_requests.request(
            method=request.method,
            url=upstream,
            headers=headers,
            data=body,
            timeout=30,
        )
        status_code = resp.status_code
        try:
            data = resp.json()
        except Exception:
            data = resp.text
        return JsonResponse(data, status=status_code, safe=False)
    except http_requests.exceptions.Timeout:
        return JsonResponse({"status": False, "message": "Upstream timeout"}, status=504)
    except http_requests.exceptions.ConnectionError:
        return JsonResponse({"status": False, "message": "Cannot reach TIP API"}, status=502)
    except Exception as exc:
        return JsonResponse({"status": False, "message": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Patent Lookup page
# ---------------------------------------------------------------------------
def index(request):
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Patent Lookup — TriangleIP</title>
<link rel='stylesheet' href='/static/tip_design.css'>
<style>
  /* ---- page-specific tweaks (only what tip_design.css doesn't cover) ---- */
  .search-box {
    position: relative;
    max-width: 640px;
    margin: 0 auto;
  }
  .search-box input {
    width: 100%;
    padding: 12px 16px;
    padding-right: 120px;
    font-size: 15px;
    border: 1px solid var(--tip-border, #d0d5dd);
    border-radius: 8px;
    outline: none;
    font-family: 'Be Vietnam Pro', sans-serif;
    box-sizing: border-box;
    transition: border-color .15s;
  }
  .search-box input:focus {
    border-color: var(--tip-primary);
    box-shadow: 0 0 0 3px rgba(59,130,246,.15);
  }
  .search-box .search-btn-wrap {
    position: absolute;
    right: 4px;
    top: 4px;
  }
  .suggestions {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: #fff;
    border: 1px solid var(--tip-border, #d0d5dd);
    border-radius: 8px;
    margin-top: 4px;
    max-height: 260px;
    overflow-y: auto;
    z-index: 100;
    box-shadow: 0 8px 24px rgba(0,0,0,.10);
    display: none;
  }
  .suggestions.open { display: block; }
  .suggestion-item {
    padding: 10px 14px;
    cursor: pointer;
    border-bottom: 1px solid #f0f0f0;
    font-size: 14px;
  }
  .suggestion-item:last-child { border-bottom: none; }
  .suggestion-item:hover { background: #f0f6ff; }
  .suggestion-item .sug-number {
    font-weight: 600;
    color: var(--tip-primary);
  }
  .suggestion-item .sug-title {
    color: var(--tip-text-secondary, #667085);
    margin-left: 8px;
    font-size: 13px;
    display: block;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .result-section { margin-top: 32px; }
  .result-section h2 {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 16px;
    color: var(--tip-text-primary, #101828);
  }
  .field-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }
  .field-card {
    background: #fff;
    border: 1px solid var(--tip-border, #d0d5dd);
    border-radius: 10px;
    padding: 16px 20px;
  }
  .field-card .field-label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: .5px;
    color: var(--tip-text-secondary, #667085);
    margin-bottom: 6px;
  }
  .field-card .field-value {
    font-size: 16px;
    font-weight: 600;
    color: var(--tip-text-primary, #101828);
    word-break: break-word;
  }
  .status-tag {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
  }
  .status-patented { background: #ecfdf3; color: #027a48; }
  .status-pending  { background: #fef3c7; color: #92400e; }
  .status-abandoned{ background: #fef2f2; color: #b91c1c; }
  .status-expired  { background: #f3f4f6; color: #4b5563; }
  .status-default  { background: #f3f4f6; color: #4b5563; }
  .spinner {
    display: inline-block;
    width: 18px; height: 18px;
    border: 2px solid var(--tip-border, #d0d5dd);
    border-top-color: var(--tip-primary);
    border-radius: 50%;
    animation: spin .6s linear infinite;
    vertical-align: middle;
    margin-right: 8px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .diagnostics-table td:first-child {
    font-weight: 600;
    white-space: nowrap;
    padding-right: 16px;
    color: var(--tip-text-secondary, #667085);
    vertical-align: top;
  }
  .diagnostics-table td {
    padding: 6px 0;
    font-size: 13px;
    vertical-align: top;
  }
  .diagnostics-table code {
    background: #f3f4f6;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 12px;
    word-break: break-all;
  }
  .quota-bar-bg {
    width: 100%;
    height: 8px;
    background: #f0f0f0;
    border-radius: 4px;
    overflow: hidden;
    margin-top: 6px;
  }
  .quota-bar-fill {
    height: 100%;
    border-radius: 4px;
    background: var(--tip-primary);
    transition: width .3s;
  }
</style>
</head>
<body>
<div class='tip-page'>

  <!-- Optional navbar -->
  <nav class='tip-navbar'>
    <a class='tip-navbar-brand' href='/'>TriangleIP</a>
  </nav>

  <h1 class='tip-page-title'>Patent Lookup</h1>
  <p style='text-align:center; color:var(--tip-text-secondary); margin-bottom:28px;'>
    Enter a US application, publication, or patent number to retrieve details.
  </p>

  <!-- Search box -->
  <div class='search-box'>
    <input
      id='patentInput'
      type='text'
      placeholder='e.g. 16/687,273 &nbsp;or&nbsp; US8623891 &nbsp;or&nbsp; EP1514569A1'
      autocomplete='off'
    />
    <div class='search-btn-wrap'>
      <button class='tip-btn tip-btn-primary' id='searchBtn' onclick='doSearch()'>Search</button>
    </div>
    <div class='suggestions' id='suggestions'></div>
  </div>

  <!-- Error card (hidden by default) -->
  <div id='errorCard' class='tip-card' style='display:none; margin-top:24px; max-width:640px; margin-left:auto; margin-right:auto; border-left:4px solid #b91c1c;'>
    <div id='errorText' style='color:#b91c1c; font-weight:600;'></div>
  </div>

  <!-- Results area -->
  <div id='resultsArea' class='result-section' style='display:none;'>
    <h2>Patent Details</h2>

    <!-- Summary stats row -->
    <div class='tip-stats-row' id='statsRow' style='margin-bottom:24px;'></div>

    <!-- Full detail grid -->
    <div class='field-grid' id='detailGrid'></div>

    <!-- Quota info -->
    <div class='tip-card' id='quotaCard' style='margin-top:24px; max-width:640px; margin-left:auto; margin-right:auto;'>
      <div style='font-size:13px; color:var(--tip-text-secondary);'>API Quota</div>
      <div id='quotaInfo' style='font-size:14px; margin-top:4px;'></div>
    </div>
  </div>

  <!-- Diagnostics -->
  <div class='tip-card' style='margin-top:48px;'>
    <details>
      <summary style='cursor:pointer; font-weight:600; font-size:15px;'>Diagnostics</summary>
      <div style='margin-top:16px;'>
        <table class='diagnostics-table' style='width:100%; border-collapse:collapse;'>
          <tr><td>Request</td><td id='diag-request'></td></tr>
          <tr><td>API Calls</td><td id='diag-calls'></td></tr>
          <tr><td>Input Parameters</td><td id='diag-input'></td></tr>
          <tr><td>Output Parameters</td><td id='diag-output'></td></tr>
          <tr><td>Field Mapping</td><td id='diag-mapping'></td></tr>
        </table>
      </div>
    </details>
  </div>

</div>

<script>
// ---- State ----
let debounceTimer = null;
const USER_REQUEST = "Look up a patent by its number and show title, status, filing date, with a search box.";

// ---- Suggest (type-ahead) ----
const patentInput = document.getElementById('patentInput');
const suggestionsEl = document.getElementById('suggestions');

patentInput.addEventListener('input', function() {
  const q = this.value.trim();
  clearTimeout(debounceTimer);
  if (q.length < 5) { suggestionsEl.classList.remove('open'); return; }
  debounceTimer = setTimeout(() => fetchSuggestions(q), 300);
});

patentInput.addEventListener('keydown', function(e) {
  if (e.key === 'Enter') { e.preventDefault(); doSearch(); }
});

// Close suggestions on outside click
document.addEventListener('click', function(e) {
  if (!e.target.closest('.search-box')) suggestionsEl.classList.remove('open');
});

async function fetchSuggestions(q) {
  try {
    const resp = await fetch('/tip-api/v1/patent-lookup/suggest?q=' + encodeURIComponent(q));
    const json = await resp.json();
    if (!json.status || !json.data || !json.data.results || json.data.results.length === 0) {
      suggestionsEl.classList.remove('open');
      return;
    }
    suggestionsEl.innerHTML = '';
    json.data.results.forEach(r => {
      const div = document.createElement('div');
      div.className = 'suggestion-item';
      div.innerHTML = '<span class="sug-number">' + escHtml(r.display) + '</span>' +
                      '<span class="sug-title">' + escHtml(r.title || '') + '</span>';
      div.addEventListener('click', () => {
        patentInput.value = r.display;
        suggestionsEl.classList.remove('open');
        doSearch();
      });
      suggestionsEl.appendChild(div);
    });
    suggestionsEl.classList.add('open');
  } catch (err) {
    // silently ignore suggest errors
  }
}

// ---- Search ----
async function doSearch() {
  const query = patentInput.value.trim();
  if (!query) return;

  suggestionsEl.classList.remove('open');
  document.getElementById('errorCard').style.display = 'none';
  document.getElementById('resultsArea').style.display = 'none';

  const btn = document.getElementById('searchBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Searching…';

  const startTime = performance.now();

  try {
    const resp = await fetch('/tip-api/v1/patent-lookup/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query })
    });
    const json = await resp.json();
    const elapsed = Math.round(performance.now() - startTime);

    if (!json.status) {
      showError(json.message || 'Unknown error from API');
      updateDiagnostics({
        query: query,
        searchType: '—',
        elapsed: elapsed,
        error: json.message || 'Unknown error',
        responseKeys: Object.keys(json)
      });
      return;
    }

    const summary = json.data.result.summary;
    const quota = json.data.quota || {};
    const searchType = json.data.search_type || 'auto';

    renderResults(summary, quota, searchType);
    updateDiagnostics({
      query: query,
      searchType: searchType,
      elapsed: elapsed,
      summary: summary,
      quota: quota,
      responseKeys: Object.keys(json.data)
    });

  } catch (err) {
    showError('Network error: ' + err.message);
    updateDiagnostics({
      query: query,
      searchType: '—',
      elapsed: Math.round(performance.now() - startTime),
      error: err.message,
      responseKeys: []
    });
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Search';
  }
}

// ---- Render results ----
function renderResults(s, quota, searchType) {
  // Stats row — top 3 key metrics
  const statsRow = document.getElementById('statsRow');
  statsRow.innerHTML = '' +
    statCard('Application Number', s.application_number || '—') +
    statCard('Patent Number', s.patent_number || '—') +
    statCard('Status', statusTag(s.status));

  // Detail grid
  const grid = document.getElementById('detailGrid');
  const fields = [
    ['Title', s.title],
    ['Application Type', s.application_type],
    ['Filing Date', s.filing_date],
    ['Status Date', s.status_date],
    ['Grant Date', s.grant_date],
    ['Examiner', s.examiner_name],
    ['Group Art Unit', s.group_art_unit],
    ['Class / Subclass', s.class_subclass],
    ['Entity Status', s.entity_status],
    ['First Inventor', s.first_inventor_name],
    ['First Applicant', s.first_applicant_name],
    ['Earliest Publication', (s.earliest_publication_number || '—') + (s.earliest_publication_date ? ' (' + s.earliest_publication_date + ')' : '')],
    ['Docket Number', s.docket_number],
    ['Confirmation #', s.confirmation_number],
  ];

  grid.innerHTML = fields.map(([label, value]) =>
    '<div class="field-card">' +
      '<div class="field-label">' + escHtml(label) + '</div>' +
      '<div class="field-value">' + (label === 'Status' ? statusTag(value) : escHtml(String(value || '—'))) + '</div>' +
    '</div>'
  ).join('');

  // Quota
  if (quota.used !== undefined) {
    const pct = Math.round((quota.used / quota.limit) * 100);
    document.getElementById('quotaInfo').innerHTML =
      '<strong>' + quota.used + '</strong> / ' + quota.limit + ' used &nbsp;(' + quota.remaining + ' remaining)' +
      '<div class="quota-bar-bg"><div class="quota-bar-fill" style="width:' + pct + '%"></div></div>';
    document.getElementById('quotaCard').style.display = '';
  } else {
    document.getElementById('quotaCard').style.display = 'none';
  }

  document.getElementById('resultsArea').style.display = '';
}

function statCard(label, valueHtml) {
  return '<div class="tip-card">' +
    '<div class="tip-card-value">' + valueHtml + '</div>' +
    '<div style="font-size:12px; color:var(--tip-text-secondary); margin-top:4px;">' + escHtml(label) + '</div>' +
  '</div>';
}

function statusTag(status) {
  if (!status) return '<span class="status-tag status-default">—</span>';
  const cls = status.toLowerCase().includes('patent') ? 'status-patented'
            : status.toLowerCase().includes('pend')  ? 'status-pending'
            : status.toLowerCase().includes('abandon') ? 'status-abandoned'
            : status.toLowerCase().includes('expir') ? 'status-expired'
            : 'status-default';
  return '<span class="status-tag ' + cls + '">' + escHtml(status) + '</span>';
}

function showError(msg) {
  const card = document.getElementById('errorCard');
  document.getElementById('errorText').textContent = msg;
  card.style.display = '';
}

// ---- Diagnostics ----
function updateDiagnostics(d) {
  document.getElementById('diag-request').textContent = USER_REQUEST;

  const callInfo = d.error
    ? '<code>POST /tip-api/v1/patent-lookup/search</code> → <strong style="color:#b91c1c;">ERROR</strong> (' + d.elapsed + ' ms)'
    : '<code>POST /tip-api/v1/patent-lookup/search</code> → 200 OK (' + d.elapsed + ' ms)';
  document.getElementById('diag-calls').innerHTML = callInfo;

  document.getElementById('diag-input').innerHTML =
    '<code>{ "query": "' + escHtml(d.query) + '" }</code>' +
    '<br><span style="color:var(--tip-text-secondary);">search_type: auto-detected</span>';

  if (d.error) {
    document.getElementById('diag-output').innerHTML =
      '<code>status: false</code><br><code>message: ' + escHtml(d.error) + '</code>';
  } else if (d.summary) {
    const s = d.summary;
    document.getElementById('diag-output').innerHTML =
      '<code>data.result.summary.title</code> = ' + escHtml(String(s.title || '—')) + '<br>' +
      '<code>data.result.summary.status</code> = ' + escHtml(String(s.status || '—')) + '<br>' +
      '<code>data.result.summary.filing_date</code> = ' + escHtml(String(s.filing_date || '—')) + '<br>' +
      '<code>data.result.summary.patent_number</code> = ' + escHtml(String(s.patent_number || '—')) + '<br>' +
      '<code>data.result.summary.application_number</code> = ' + escHtml(String(s.application_number || '—')) + '<br>' +
      '<code>data.result.summary.examiner_name</code> = ' + escHtml(String(s.examiner_name || '—')) + '<br>' +
      '<code>data.result.summary.group_art_unit</code> = ' + escHtml(String(s.group_art_unit || '—')) + '<br>' +
      '<code>data.result.summary.entity_status</code> = ' + escHtml(String(s.entity_status || '—')) + '<br>' +
      '<code>data.result.quota</code> = ' + escHtml(JSON.stringify(d.quota));
  } else {
    document.getElementById('diag-output').textContent = '—';
  }

  document.getElementById('diag-mapping').innerHTML =
    '<table class="tip-table" style="font-size:12px; margin-top:4px;">' +
    '<tr><th style="text-align:left;">Response Field</th><th style="text-align:left;">UI Element</th></tr>' +
    mappingRow('data.result.summary.title', 'Title field card') +
    mappingRow('data.result.summary.status', 'Status tag (stats row + detail)') +
    mappingRow('data.result.summary.filing_date', 'Filing Date field card') +
    mappingRow('data.result.summary.patent_number', 'Patent Number stat card') +
    mappingRow('data.result.summary.application_number', 'Application Number stat card') +
    mappingRow('data.result.summary.examiner_name', 'Examiner field card') +
    mappingRow('data.result.summary.group_art_unit', 'Group Art Unit field card') +
    mappingRow('data.result.summary.class_subclass', 'Class / Subclass field card') +
    mappingRow('data.result.summary.entity_status', 'Entity Status field card') +
    mappingRow('data.result.summary.first_inventor_name', 'First Inventor field card') +
    mappingRow('data.result.summary.first_applicant_name', 'First Applicant field card') +
    mappingRow('data.result.summary.earliest_publication_number', 'Earliest Publication field card') +
    mappingRow('data.result.summary.docket_number', 'Docket Number field card') +
    mappingRow('data.result.summary.confirmation_number', 'Confirmation # field card') +
    mappingRow('data.result.summary.grant_date', 'Grant Date field card') +
    mappingRow('data.result.summary.status_date', 'Status Date field card') +
    mappingRow('data.result.summary.application_type', 'Application Type field card') +
    mappingRow('data.quota', 'Quota progress bar') +
    '</table>';
}

function mappingRow(field, ui) {
  return '<tr><td><code>' + escHtml(field) + '</code></td><td>' + escHtml(ui) + '</td></tr>';
}

// ---- Helpers ----
function escHtml(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}
</script>
</body>
</html>"""
    return HttpResponse(html, content_type="text/html")
