#!/usr/bin/env python3
"""Aggregate per-task image metadata into output.jsonl + gallery.html.

Reads OutputDir/output/metadata/image_NNNN.json sidecars produced by
run_task.py and builds:
  - OutputDir/output/output.jsonl   — one line per generated image (metadata)
  - OutputDir/output/gallery.html   — self-contained gallery viewer that
                                       references images/image_NNNN.png by
                                       relative path

The gallery.html is a single static HTML file; open it from the downloaded
OutputDir/output/ directory in any browser, no server needed.
"""
import argparse
import json
import os
import re
import sys


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>text_to_image_batch — Gallery</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #1a1a2e; padding: 2rem; }
  .container { max-width: 1200px; margin: 0 auto; }
  h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
  .subtitle { color: #666; margin-bottom: 1.5rem; font-size: 0.9rem; }
  .stats { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
  .stat { background: #fff; border-radius: 8px; padding: 1rem 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  .stat-value { font-size: 1.4rem; font-weight: 600; color: #4a90d9; }
  .stat-label { font-size: 0.75rem; color: #888; margin-top: 0.2rem; }
  .controls { margin-bottom: 1rem; display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
  .search { padding: 0.5rem 0.75rem; border: 1px solid #ddd; border-radius: 6px; font-size: 0.9rem; width: 280px; }
  .search:focus { outline: none; border-color: #4a90d9; }
  .btn { padding: 0.5rem 1rem; border: none; border-radius: 6px; font-size: 0.85rem; cursor: pointer; font-weight: 500; background: #e8ecf0; color: #333; }
  .btn:hover { background: #dde2e8; }
  .count { font-size: 0.85rem; color: #666; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; }
  .card { background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; }
  .card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
  .card img { width: 100%; height: auto; display: block; background: #f0f0f0; }
  .card-info { padding: 0.75rem; }
  .card-id { font-size: 0.7rem; color: #999; font-family: monospace; margin-bottom: 0.25rem; }
  .card-prompt { font-size: 0.8rem; color: #333; line-height: 1.4; max-height: 4.2em; overflow: hidden; }
  .modal { position: fixed; inset: 0; background: rgba(0,0,0,0.85); display: flex; align-items: center; justify-content: center; z-index: 100; padding: 2rem; }
  .modal.hidden { display: none; }
  .modal-content { max-width: 90vw; max-height: 95vh; display: flex; flex-direction: column; gap: 0.75rem; align-items: center; }
  .modal-content img { max-width: 100%; max-height: 75vh; border-radius: 4px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }
  .modal-info { background: rgba(255,255,255,0.95); border-radius: 6px; padding: 0.75rem 1rem; font-size: 0.85rem; max-width: 800px; }
  .modal-info-row { margin-bottom: 0.4rem; }
  .modal-info-row:last-child { margin-bottom: 0; }
  .modal-info-label { font-size: 0.7rem; font-weight: 600; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-right: 0.5rem; }
  .modal-info-value { white-space: pre-wrap; word-break: break-word; }
  .modal-meta { display: flex; gap: 1rem; font-size: 0.75rem; color: #666; }
  .close-hint { color: rgba(255,255,255,0.6); font-size: 0.8rem; }
</style>
</head>
<body>
<div class="container">
  <h1>text_to_image_batch — Gallery</h1>
  <p class="subtitle">Generated with AWS Deadline Cloud</p>

  <div class="stats">
    <div class="stat"><div class="stat-value" id="totalCount">0</div><div class="stat-label">Total Images</div></div>
    <div class="stat"><div class="stat-value" id="totalTime">0s</div><div class="stat-label">Total Generation Time</div></div>
    <div class="stat"><div class="stat-value" id="avgTime">0s</div><div class="stat-label">Avg per Image</div></div>
    <div class="stat"><div class="stat-value" id="resolution">—</div><div class="stat-label">Resolution</div></div>
  </div>

  <div class="controls">
    <input type="text" class="search" id="search" placeholder="Search prompts...">
    <button class="btn" onclick="exportCsv()">Export CSV</button>
    <span class="count" id="showing"></span>
  </div>

  <div class="grid" id="grid"></div>
</div>

<div class="modal hidden" id="modal" onclick="closeModal(event)">
  <div class="modal-content" onclick="event.stopPropagation()">
    <img id="modalImg" src="" alt="">
    <div class="modal-info">
      <div class="modal-info-row">
        <span class="modal-info-label">ID</span>
        <span class="modal-info-value" id="modalId"></span>
      </div>
      <div class="modal-info-row">
        <span class="modal-info-label">Final prompt</span>
        <span class="modal-info-value" id="modalPrompt"></span>
      </div>
      <div class="modal-info-row modal-meta">
        <span><strong id="modalSize"></strong> px</span>
        <span><strong id="modalSteps"></strong> steps</span>
        <span>guidance <strong id="modalGuidance"></strong></span>
        <span>seed <strong id="modalSeed"></strong></span>
        <span><strong id="modalTime"></strong></span>
      </div>
    </div>
    <div class="close-hint">click anywhere outside to close</div>
  </div>
</div>

<script>
const DATA = __DATA_PLACEHOLDER__;

function esc(s) {
  const el = document.createElement('span');
  el.textContent = s == null ? '' : String(s);
  return el.innerHTML.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function render(filter) {
  const lower = (filter || '').toLowerCase();
  const filtered = lower
    ? DATA.filter(d =>
        (d.final_prompt || '').toLowerCase().includes(lower) ||
        (d.prompt || '').toLowerCase().includes(lower) ||
        (d.generated_text || '').toLowerCase().includes(lower) ||
        (d.id || '').toLowerCase().includes(lower))
    : DATA;
  document.getElementById('showing').textContent = lower ? `Showing ${filtered.length} of ${DATA.length}` : '';
  document.getElementById('grid').innerHTML = filtered.map(d => {
    const i = DATA.indexOf(d);
    const caption = d.final_prompt || d.prompt || d.generated_text || '';
    return `
      <div class="card" onclick="openModal(${i})">
        <img src="images/${esc(d.image)}" alt="${esc(caption.slice(0, 80))}" loading="lazy">
        <div class="card-info">
          <div class="card-id">${esc(d.id || '#' + (d.index || i + 1))}</div>
          <div class="card-prompt">${esc(caption)}</div>
        </div>
      </div>`;
  }).join('');
}

function openModal(i) {
  const d = DATA[i];
  document.getElementById('modalImg').src = 'images/' + d.image;
  document.getElementById('modalId').textContent = d.id || '#' + (d.index || i + 1);
  document.getElementById('modalPrompt').textContent = d.final_prompt || d.prompt || d.generated_text || '(no prompt)';
  document.getElementById('modalSize').textContent = `${d.width || '?'}×${d.height || '?'}`;
  document.getElementById('modalSteps').textContent = d.inference_steps || '?';
  document.getElementById('modalGuidance').textContent = d.guidance_scale != null ? d.guidance_scale : '?';
  document.getElementById('modalSeed').textContent = d.seed != null ? d.seed : '?';
  document.getElementById('modalTime').textContent = d.elapsed_seconds != null ? d.elapsed_seconds.toFixed(1) + 's' : '';
  document.getElementById('modal').classList.remove('hidden');
}

function closeModal(e) {
  // Only close on background click; clicks on the inner content stop propagation.
  document.getElementById('modal').classList.add('hidden');
}

function csvSafe(c) { const s = String(c); return /^[=+\-@]/.test(s) ? "\t" + s : s; }
function exportCsv() {
  const rows = [['id', 'image', 'final_prompt', 'width', 'height', 'inference_steps', 'guidance_scale', 'seed', 'elapsed_seconds']];
  DATA.forEach(d => rows.push([
    d.id || '', d.image || '', d.final_prompt || d.prompt || '',
    d.width || '', d.height || '', d.inference_steps || '',
    d.guidance_scale == null ? '' : d.guidance_scale,
    d.seed == null ? '' : d.seed,
    d.elapsed_seconds == null ? '' : d.elapsed_seconds,
  ]));
  const csv = rows.map(r => r.map(c => '"' + csvSafe(c).replace(/"/g, '""') + '"').join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'gallery.csv';
  a.click();
}

// Initial stats
document.getElementById('totalCount').textContent = DATA.length;
const totalSeconds = DATA.reduce((s, d) => s + (d.elapsed_seconds || 0), 0);
document.getElementById('totalTime').textContent = totalSeconds.toFixed(1) + 's';
document.getElementById('avgTime').textContent = (DATA.length ? (totalSeconds / DATA.length).toFixed(1) : '0') + 's';
const sizes = new Set(DATA.map(d => `${d.width}×${d.height}`));
document.getElementById('resolution').textContent = sizes.size === 1 ? [...sizes][0] : (sizes.size + ' sizes');

document.getElementById('search').addEventListener('input', e => render(e.target.value));
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
render('');
</script>
</body>
</html>
"""


def _index_from_filename(name):
    m = re.search(r"\d+", name)
    return int(m.group()) if m else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Job's OutputDir; aggregate reads from OutputDir/output/metadata/ "
             "and writes OutputDir/output/{output.jsonl,gallery.html}",
    )
    args = parser.parse_args()

    # All artifacts live under OutputDir/output/ — keeps each job's results
    # grouped so multiple runs can share an OutputDir without clobbering.
    output_root = os.path.join(args.output_dir, "output")
    metadata_dir = os.path.join(output_root, "metadata")
    images_dir = os.path.join(output_root, "images")

    if not os.path.isdir(metadata_dir):
        print(f"ERROR: metadata dir does not exist: {metadata_dir}", file=sys.stderr)
        sys.exit(1)

    items = []
    for filename in sorted(os.listdir(metadata_dir), key=_index_from_filename):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(metadata_dir, filename)
        with open(path) as f:
            try:
                items.append(json.load(f))
            except json.JSONDecodeError as e:
                print(f"WARN: skipping malformed {filename}: {e}", file=sys.stderr)

    if not items:
        print(
            f"ERROR: no metadata files found in {metadata_dir} — did the Generate step succeed?",
            file=sys.stderr,
        )
        sys.exit(1)

    # output.jsonl — one line per image, easy to grep / pipe into other tools.
    output_jsonl = os.path.join(output_root, "output.jsonl")
    with open(output_jsonl, "w") as f:
        for item in items:
            f.write(json.dumps(item) + "\n")
    print(f"Aggregated {len(items)} items into {output_jsonl}")

    # gallery.html — the human-friendly viewer. References images/ relatively
    # (sibling directory inside output/).
    gallery_path = os.path.join(output_root, "gallery.html")
    data_json = json.dumps(items, ensure_ascii=False)
    html = HTML_TEMPLATE.replace("__DATA_PLACEHOLDER__", data_json)
    with open(gallery_path, "w") as f:
        f.write(html)
    print(f"Generated gallery: {gallery_path}")

    # Sanity check that referenced images exist (warn, don't fail).
    missing = [i["image"] for i in items if not os.path.exists(os.path.join(images_dir, i.get("image", "")))]
    if missing:
        print(
            f"WARN: {len(missing)} referenced image(s) missing from {images_dir}: "
            f"{missing[:5]}{'...' if len(missing) > 5 else ''}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
