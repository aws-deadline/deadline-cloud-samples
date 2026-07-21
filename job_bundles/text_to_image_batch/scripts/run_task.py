#!/usr/bin/env python3
"""Generate one image from one JSONL line, then composite the slogan as
crisp typography over the result using PIL.

The diffusion pipeline is loaded by the step environment (DiffusersServer)
and served on http://localhost:8001. This script:

1. Reads line N (1-based) from the input JSONL.
2. Decides whether to overlay a caption (default: yes when the line has a
   "caption" or "generated_text" field).
3. Picks a font from the "vibe" of the style/prompt (auto), or honors an
   explicit FontStyle.
4. Builds the diffusion prompt — when overlaying, the slogan is *not* fed to
   the diffusion model (it'd render as gibberish anyway, and we're going to
   composite the real text on top).
5. POSTs to /generate, receives PNG bytes back.
6. Composites the caption over the image with a small font and a rounded
   pill backdrop.
7. Writes ``OutputDir/images/image_NNNN.png`` and a sidecar metadata JSON.
"""
import argparse
import io
import json
import os
import random
import re
import sys
import textwrap
import time
import urllib.error
import urllib.request


# ---------------------------------------------------------------------------
# Subject extraction from chained-from-vllm prompts
# ---------------------------------------------------------------------------

SLOGAN_REQUEST_PATTERN = re.compile(
    r"(?ix)"
    r"(?:write|generate|create|make|compose|craft|draft|design)\s+"
    r"(?:[\w-]+\s+){0,5}"
    r"(?:slogan|tagline|headline|caption|copy|jingle|hook|"
    r"ad|advert|advertisement|tweet|post|line|cta|"
    r"poem|haiku|verse|rhyme|description)"
    r"\s+(?:for|about)\s+"
    r"(?P<subject>.+?)"
    r"(?:\s+(?:targeting|aimed|focused|geared|intended|"
    r"for|in|on|to|with|by)\b|[.,;]|$)"
)


def extract_subject_from_prompt(prompt):
    """Pull the visual subject out of an LLM slogan-style request."""
    if not prompt:
        return None
    m = SLOGAN_REQUEST_PATTERN.search(prompt)
    if not m:
        return None
    subject = m.group("subject").strip().strip(",;:.")
    return subject or None


# ---------------------------------------------------------------------------
# Vibe -> font category mapping
# ---------------------------------------------------------------------------

VIBE_RULES = [
    ("script", re.compile(
        r"\b(handwritten|hand-drawn|hand drawn|rustic|warm|nostalgic|cozy|"
        r"homemade|heartfelt|calligraphy|cursive|signature|holiday|vintage)\b",
        re.I,
    )),
    ("display", re.compile(
        r"\b(playful|fun|cheerful|cartoon|colorful|vibrant|trendy|tiktok|"
        r"gen[\s-]?z|party|kids|chunky|bold typography|neon|graffiti|"
        r"bubble|kawaii)\b",
        re.I,
    )),
    ("mono", re.compile(
        r"\b(code|terminal|developer|cyberpunk|techwear|matrix|hacker|"
        r"console|monospace|retro[\s-]?tech)\b",
        re.I,
    )),
    ("serif", re.compile(
        r"\b(elegant|luxury|luxurious|wedding|bridal|editorial|magazine|"
        r"sophisticated|refined|classic|romantic|moody|high[\s-]?contrast|"
        r"timeless|premium|gala)\b",
        re.I,
    )),
    ("sans", re.compile(
        r"\b(modern|minimal|minimalist|clean|tech|product|photographic|"
        r"corporate|professional|brochure|flat|geometric)\b",
        re.I,
    )),
]


CATEGORY_TO_FILENAME = {
    "serif":   "PlayfairDisplay-Bold.ttf",
    "display": "Bungee-Regular.ttf",
    "script":  "Caveat-Bold.ttf",
    "mono":    "JetBrainsMono-Bold.ttf",
    "sans":    None,  # falls through to system DejaVu Sans Bold
}


SYSTEM_FALLBACK_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
]


def pick_font_category(style_text, prompt_text):
    """Return one of: sans, serif, display, script, mono. Default sans."""
    haystack = f"{style_text or ''} {prompt_text or ''}"
    for category, regex in VIBE_RULES:
        if regex.search(haystack):
            return category
    return "sans"


def resolve_font_path(font_style, style_text, prompt_text):
    """Resolve --font-style + per-line vibe to an actual TTF path."""
    if font_style and (font_style.startswith("/") or font_style.endswith((".ttf", ".otf"))):
        if os.path.exists(font_style):
            return font_style
        print(f"  WARN: font path not found: {font_style!r}, falling back to auto", flush=True)
        font_style = "auto"

    style_lc = (font_style or "auto").strip().lower()
    if style_lc == "auto" or style_lc not in CATEGORY_TO_FILENAME:
        category = pick_font_category(style_text, prompt_text)
    else:
        category = style_lc

    print(f"  font category: {category}", flush=True)

    # Try the bundled Google Font for this category — the cache dir is
    # exported by InstallDeps; default to a reasonable fallback path.
    font_dir = os.environ.get("TEXT_TO_IMAGE_FONT_DIR") or \
               os.path.expanduser("~/.cache/text_to_image_batch/fonts")
    filename = CATEGORY_TO_FILENAME.get(category)
    if filename:
        candidate = os.path.join(font_dir, filename)
        if os.path.exists(candidate):
            return candidate
        print(f"  WARN: bundled font missing ({candidate}), falling back to system", flush=True)

    for sysf in SYSTEM_FALLBACK_FONTS:
        if os.path.exists(sysf):
            return sysf

    return None


# ---------------------------------------------------------------------------
# Caption overlay
#
#   - Font ~3.5 % of min(W, H)
#   - Wraps to ~70 % of image width
#   - Rounded-rect "pill" backdrop sized just to fit the text + padding
#   - Backdrop opacity 140/255 for a light feel
# ---------------------------------------------------------------------------

def overlay_caption(png_bytes, caption, font_path, *, position="bottom"):
    """Composite caption text over a PNG with a subtle pill backdrop."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  WARN: Pillow not installed; skipping caption overlay", flush=True)
        return png_bytes

    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    width, height = img.size

    # Font sized to ~3.5 % of the smaller image dimension.
    font_size = max(14, int(min(width, height) * 0.035))
    font = None
    if font_path:
        try:
            font = ImageFont.truetype(font_path, font_size)
        except (OSError, IOError) as e:
            print(f"  WARN: could not load font {font_path}: {e}", flush=True)
    if font is None:
        try:
            # Pillow 10.1+: scalable bundled font
            font = ImageFont.load_default(size=font_size)
        except TypeError:
            font = ImageFont.load_default()

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Wrap to ~70% of image width — narrower band feels lighter.
    avg_char_w = max(5.0, font_size * 0.55)
    max_chars = max(15, int(width * 0.70 / avg_char_w))
    wrapped = textwrap.fill(caption.strip(), width=max_chars)

    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center", spacing=3)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    pad_x = font_size              # horizontal padding inside the pill
    pad_y = max(6, font_size // 2) # vertical padding inside the pill

    pill_w = text_w + 2 * pad_x
    pill_h = text_h + 2 * pad_y
    pill_x = (width - pill_w) // 2

    # Edge margin: ~1.5x the font size from the relevant edge.
    edge_margin = int(font_size * 1.5)
    if position == "top":
        pill_y = edge_margin
    elif position == "center":
        pill_y = (height - pill_h) // 2
    else:  # bottom (default — poster-style)
        pill_y = height - pill_h - edge_margin

    radius = pill_h // 2

    # Draw the rounded-rect pill. Falls back to a regular rectangle on very
    # old PIL versions that don't have rounded_rectangle (added in 8.2).
    try:
        draw.rounded_rectangle(
            [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
            radius=radius,
            fill=(0, 0, 0, 140),
        )
    except AttributeError:
        draw.rectangle(
            [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
            fill=(0, 0, 0, 140),
        )

    # Center the text inside the pill.
    text_x = pill_x + pad_x - bbox[0]
    text_y = pill_y + pad_y - bbox[1]
    draw.multiline_text(
        (text_x, text_y),
        wrapped,
        fill=(255, 255, 255, 255),
        font=font,
        align="center",
        spacing=3,
    )

    out = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Prompt construction (overlay-aware)
# ---------------------------------------------------------------------------

def get_prompt_by_index(input_file, index):
    with open(input_file) as f:
        for i, line in enumerate(f, 1):
            if i == index:
                line = line.strip()
                if not line:
                    return None
                return json.loads(line)
    return None


def _first_non_empty(prompt_data, *keys):
    for k in keys:
        v = prompt_data.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def build_prompt_and_caption(prompt_data, default_style, overlay_enabled):
    """Return (final_diffusion_prompt, caption_or_None).

    See README "Caption overlay" section for the layered fallback rules.
    """
    caption = None
    if overlay_enabled:
        caption = (
            _first_non_empty(prompt_data, "caption")
            or _first_non_empty(prompt_data, "generated_text")
        )

    if caption is not None:
        explicit_caption = bool(_first_non_empty(prompt_data, "caption"))
        if explicit_caption:
            visual = _first_non_empty(
                prompt_data, "description", "generated_text", "prompt", "text"
            ) or ""
            visual_source = "description/generated_text/prompt"
        else:
            visual = _first_non_empty(prompt_data, "description") or ""
            visual_source = "description field" if visual else None
            if not visual:
                extracted = extract_subject_from_prompt(
                    _first_non_empty(prompt_data, "prompt", "text") or ""
                )
                if extracted:
                    visual = extracted
                    visual_source = "auto-extracted from prompt"
            if not visual:
                # Last-ditch: use the slogan itself with an anti-text suffix so
                # the diffusion model favors imagery over rendering text. The
                # overlay covers the caption area regardless.
                visual = f"{caption} (scene only, no visible text)"
                visual_source = "slogan-as-vibe (no description or extracted subject)"
        if visual_source:
            print(f"  visual prompt source: {visual_source}", flush=True)
    else:
        # Chained-from-vllm logic with overlay disabled: prepend extracted
        # subject to the slogan, so chained runs without overlay still
        # produce on-topic imagery (with gibberish text).
        visual = _first_non_empty(prompt_data, "generated_text", "prompt", "text") or ""
        if prompt_data.get("generated_text") and prompt_data.get("prompt"):
            extracted = extract_subject_from_prompt(prompt_data["prompt"])
            if extracted:
                visual = f"{extracted}, {visual}"

    style_field = prompt_data.get("style")
    style = (style_field if style_field is not None else default_style)
    style = (style or "").strip()

    parts = [p for p in (visual, style) if p]
    return ", ".join(parts), caption


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

def call_diffusers(payload, port, attempts=3, attempt_timeout=600):
    data = json.dumps(payload).encode()
    url = f"http://localhost:{port}/generate"
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_err = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=attempt_timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"server returned HTTP {resp.status}")
                return resp.read()
        except urllib.error.HTTPError as e:
            body = b""
            try:
                body = e.read()
            except (OSError, AttributeError):
                pass  # best-effort read of error body; proceed with empty bytes
            try:
                err = json.loads(body)
                raise RuntimeError(
                    f"server error: {err.get('type', 'Error')}: {err.get('error', body)}"
                )
            except (json.JSONDecodeError, ValueError):
                raise RuntimeError(f"server error: HTTP {e.code}: {body[:500]!r}")
        except (urllib.error.URLError, OSError) as e:
            last_err = e
            if attempt < attempts - 1:
                print(f"  retry {attempt + 1}: {e}", flush=True)
                time.sleep(2)
            else:
                raise
    raise RuntimeError(f"unreachable: {last_err}")


def _truthy(v):
    return str(v).strip().lower() in ("true", "1", "yes", "on")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_range(range_str):
    """Parse an OpenJD IntRangeExpr into a sorted list of unique integers.

    Supports the full OpenJD range syntax from RFC 0001 (Task Chunking):
      - Single value:         "37"
      - Contiguous range:     "1-5"       -> 1,2,3,4,5
      - Stride range:         "1-10:2"    -> 1,3,5,7,9
      - Comma-separated:      "2,5,8-9"   -> 2,5,8,9
      - Combined:             "1-3,7-15:3"-> 1,2,3,7,10,13
    """
    indices = []
    for part in range_str.split(","):
        part = part.strip()
        if not part:
            continue
        step = 1
        if ":" in part:
            part, step_s = part.split(":", 1)
            step = int(step_s)
            if step < 1:
                raise ValueError(f"Stride must be >= 1, got {step} in {range_str!r}")
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            indices.extend(range(start, end + 1, step))
        else:
            indices.append(int(part))
    return sorted(set(indices))


def process_prompt(index, args, overlay_enabled, images_dir, metadata_dir):
    """Process one prompt: read it, generate the image, overlay caption, save outputs.

    Returns True on success (or if the line was missing / skipped), False on error.
    """
    prompt_data = get_prompt_by_index(args.input_file, index)
    if prompt_data is None:
        print(f"  Prompt {index}: not found in file, skipping.", flush=True)
        return True

    final_prompt, caption = build_prompt_and_caption(
        prompt_data, args.style_suffix, overlay_enabled
    )
    if not final_prompt:
        print(
            f"ERROR: line {index} has no usable visual prompt. "
            f"Each line needs a 'prompt', 'generated_text', 'description', or 'text' "
            f"field, or a job-level StyleSuffix.",
            file=sys.stderr,
        )
        return False

    width = int(prompt_data.get("width", args.width))
    height = int(prompt_data.get("height", args.height))
    steps = int(prompt_data.get("steps", args.inference_steps))

    raw_seed = prompt_data.get("seed", args.seed)
    seed = int(raw_seed)
    if seed < 0:
        rng = random.Random(index)
        seed = rng.randint(0, 2**31 - 1)

    payload = {
        "prompt": final_prompt,
        "width": width,
        "height": height,
        "inference_steps": steps,
        "guidance_scale": args.guidance_scale,
        "seed": seed,
    }

    print(f"  Prompt {index}: {final_prompt[:120]}", flush=True)
    print(
        f"    size={width}x{height} steps={steps} guidance={args.guidance_scale} "
        f"seed={seed} overlay={'on' if overlay_enabled and caption else 'off'}",
        flush=True,
    )

    started = time.time()
    png_bytes = call_diffusers(payload, args.port)
    gen_elapsed = time.time() - started

    overlay_meta = {"caption": None, "font_path": None}
    if overlay_enabled and caption:
        line_font = (prompt_data.get("font") or "").strip()
        font_arg = line_font or args.font_style
        style_for_vibe = (
            prompt_data.get("style") if prompt_data.get("style") is not None else args.style_suffix
        )
        font_path = resolve_font_path(
            font_arg,
            style_text=style_for_vibe,
            prompt_text=_first_non_empty(prompt_data, "prompt", "description") or "",
        )
        png_bytes = overlay_caption(png_bytes, caption, font_path)
        overlay_meta = {"caption": caption, "font_path": font_path}

    elapsed = time.time() - started

    image_filename = f"image_{index:04d}.png"
    image_path = os.path.join(images_dir, image_filename)
    with open(image_path, "wb") as f:
        f.write(png_bytes)

    metadata = {
        **prompt_data,
        "index": index,
        "image": image_filename,
        "final_prompt": final_prompt,
        "width": width,
        "height": height,
        "inference_steps": steps,
        "guidance_scale": args.guidance_scale,
        "seed": seed,
        "overlay_caption": overlay_meta["caption"],
        "overlay_font": overlay_meta["font_path"],
        "elapsed_seconds": round(elapsed, 2),
        "generation_seconds": round(gen_elapsed, 2),
    }
    metadata_path = os.path.join(metadata_dir, f"image_{index:04d}.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"    -> {image_filename} ({len(png_bytes):,} bytes, {elapsed:.1f}s)", flush=True)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--prompt-range", required=True,
                        help="OpenJD chunk range string, e.g. '1-5', '37', or '2,5,8-9'")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--style-suffix", default="")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--inference-steps", type=int, default=4)
    parser.add_argument("--guidance-scale", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--overlay-caption", default="true",
                        help='"true"/"false" (default: true). Composite the slogan via PIL '
                             'instead of feeding it to the diffusion model.')
    parser.add_argument("--font-style", default="auto",
                        help='"auto" (vibe-based), "sans"/"serif"/"display"/"script"/"mono", '
                             "or a path to a .ttf file.")
    args = parser.parse_args()

    overlay_enabled = _truthy(args.overlay_caption)

    # Lay out output as: OutputDir/output/{images,metadata}/image_NNNN.{png,json}
    # The "output/" wrapper keeps every job's artifacts grouped together so
    # multiple runs can share an OutputDir without clobbering one another.
    output_root = os.path.join(args.output_dir, "output")
    images_dir = os.path.join(output_root, "images")
    metadata_dir = os.path.join(output_root, "metadata")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(metadata_dir, exist_ok=True)

    indices = parse_range(args.prompt_range)
    print(f"Processing chunk with {len(indices)} prompts: {indices}", flush=True)
    chunk_start = time.time()

    failures = 0
    for idx in indices:
        ok = process_prompt(idx, args, overlay_enabled, images_dir, metadata_dir)
        if not ok:
            failures += 1

    chunk_elapsed = time.time() - chunk_start
    print(
        f"Chunk done in {chunk_elapsed:.1f}s "
        f"({len(indices)} prompts, {chunk_elapsed / max(len(indices), 1):.1f}s/prompt avg)",
        flush=True,
    )

    if failures > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
