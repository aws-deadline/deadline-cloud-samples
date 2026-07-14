#!/usr/bin/env python3
"""Aggregate per-task inference results into a single output JSONL and generate results.html."""
import argparse
import json
import os
import re
import sys


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>vLLM Batch Inference — Results</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #1a1a2e; padding: 2rem; }
  .container { max-width: 900px; margin: 0 auto; }
  h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
  .subtitle { color: #666; margin-bottom: 1.5rem; font-size: 0.9rem; }
  .stats { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
  .stat { background: #fff; border-radius: 8px; padding: 1rem 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  .stat-value { font-size: 1.4rem; font-weight: 600; color: #4a90d9; }
  .stat-label { font-size: 0.75rem; color: #888; margin-top: 0.2rem; }
  .controls { margin-bottom: 1rem; display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
  .search { padding: 0.5rem 0.75rem; border: 1px solid #ddd; border-radius: 6px; font-size: 0.9rem; width: 250px; }
  .search:focus { outline: none; border-color: #4a90d9; }
  .btn { padding: 0.5rem 1rem; border: none; border-radius: 6px; font-size: 0.85rem; cursor: pointer; font-weight: 500; background: #e8ecf0; color: #333; }
  .btn:hover { background: #dde2e8; }
  .card { background: #fff; border-radius: 8px; padding: 1.25rem; margin-bottom: 0.75rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
  .card-id { font-size: 0.75rem; color: #999; font-family: monospace; }
  .card-meta { font-size: 0.7rem; color: #aaa; display: flex; gap: 0.75rem; }
  .prompt-label { font-size: 0.7rem; font-weight: 600; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.25rem; }
  .prompt-text { font-size: 0.9rem; color: #333; margin-bottom: 0.75rem; white-space: pre-wrap; }
  .response-text { font-size: 0.9rem; color: #1a1a2e; white-space: pre-wrap; line-height: 1.5; background: #f8fafb; border-radius: 4px; padding: 0.75rem; border-left: 3px solid #4a90d9; }
  .hidden { display: none; }
  .count { font-size: 0.85rem; color: #666; }
</style>
</head>
<body>
<div class="container">
  <h1>vLLM Batch Inference — Results</h1>
  <p class="subtitle">Generated with AWS Deadline Cloud</p>
  <div class="stats">
    <div class="stat"><div class="stat-value" id="totalCount">0</div><div class="stat-label">Total Prompts</div></div>
    <div class="stat"><div class="stat-value" id="totalPromptTokens">0</div><div class="stat-label">Prompt Tokens</div></div>
    <div class="stat"><div class="stat-value" id="totalCompTokens">0</div><div class="stat-label">Completion Tokens</div></div>
    <div class="stat"><div class="stat-value" id="avgCompLen">0</div><div class="stat-label">Avg Response Tokens</div></div>
  </div>
  <div class="controls">
    <input type="text" class="search" id="search" placeholder="Search prompts or responses...">
    <button class="btn" onclick="exportCSV()">Export CSV</button>
    <span class="count" id="showing"></span>
  </div>
  <div id="results"></div>
</div>
<script>
const DATA = __DATA_PLACEHOLDER__;
function render(filter = '') {
  const lower = filter.toLowerCase();
  const filtered = filter ? DATA.filter(d => (d.prompt||'').toLowerCase().includes(lower) || (d.generated_text||'').toLowerCase().includes(lower)) : DATA;
  document.getElementById('showing').textContent = filter ? `Showing ${filtered.length} of ${DATA.length}` : '';
  document.getElementById('results').innerHTML = filtered.map((d, i) => `
    <div class="card">
      <div class="card-header">
        <span class="card-id">${esc(d.id || '#' + (DATA.indexOf(d) + 1))}</span>
        <div class="card-meta"><span>${esc(d.prompt_tokens||'?')} in</span><span>${esc(d.completion_tokens||'?')} out</span><span>${esc(d.finish_reason||'')}</span></div>
      </div>
      <div class="prompt-label">Prompt</div>
      <div class="prompt-text">${esc(d.prompt||d.text||'')}</div>
      <div class="prompt-label">Response</div>
      <div class="response-text">${esc(d.generated_text||'(no response)')}</div>
    </div>`).join('');
}
function esc(s) { const el = document.createElement('span'); el.textContent = s == null ? '' : String(s); return el.innerHTML.replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }
function csvSafe(c) { const s = String(c); return /^[=+\\-@]/.test(s) ? "\\t" + s : s; }
function exportCSV() {
  const rows = [['id','prompt','generated_text','prompt_tokens','completion_tokens','finish_reason']];
  DATA.forEach(d => rows.push([d.id||'',d.prompt||'',d.generated_text||'',d.prompt_tokens||'',d.completion_tokens||'',d.finish_reason||'']));
  const csv = rows.map(r => r.map(c => '"'+csvSafe(c).replace(/"/g,'""')+'"').join(',')).join('\\n');
  const blob = new Blob([csv],{type:'text/csv'}); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'results.csv'; a.click();
}
document.getElementById('totalCount').textContent = DATA.length;
const pt = DATA.reduce((s,d) => s+(d.prompt_tokens||0), 0);
const ct = DATA.reduce((s,d) => s+(d.completion_tokens||0), 0);
document.getElementById('totalPromptTokens').textContent = pt.toLocaleString();
document.getElementById('totalCompTokens').textContent = ct.toLocaleString();
document.getElementById('avgCompLen').textContent = DATA.length ? Math.round(ct/DATA.length) : 0;
document.getElementById('search').addEventListener('input', e => render(e.target.value));
render();
</script>
</body>
</html>"""


def _index_from_filename(name):
    """Extract the first integer from a filename for stable sorting.
    e.g. 'result_10.jsonl' -> 10, 'result_2.jsonl' -> 2, 'foo.jsonl' -> 0."""
    m = re.search(r"\d+", name)
    return int(m.group()) if m else 0


def main():
    parser = argparse.ArgumentParser(description="Aggregate per-task results")
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if not os.path.exists(args.results_dir):
        print(f"ERROR: results dir {args.results_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    # Collect all result_N.jsonl files in order
    results = []
    for filename in sorted(os.listdir(args.results_dir), key=_index_from_filename):
        if not filename.endswith(".jsonl"):
            continue
        filepath = os.path.join(args.results_dir, filename)
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))

    # Write JSONL
    with open(args.output, "w") as out:
        for r in results:
            out.write(json.dumps(r) + "\n")

    print(f"Aggregated {len(results)} results into {args.output}")

    # Generate results.html
    output_dir = os.path.dirname(os.path.abspath(args.output))
    html_path = os.path.join(output_dir, "results.html")
    data_json = json.dumps(results, ensure_ascii=False)
    html_content = HTML_TEMPLATE.replace("__DATA_PLACEHOLDER__", data_json)
    with open(html_path, "w") as f:
        f.write(html_content)

    print(f"Generated results viewer: {html_path}")


if __name__ == "__main__":
    main()
