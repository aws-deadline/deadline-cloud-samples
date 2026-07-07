#!/usr/bin/env python3
"""Run inference for a chunk of prompts by hitting the local vLLM server.

The Task Chunking extension passes this script an integer range string (e.g.
"1-5", "6-10", "37" for a single value, or "2,5,8-9" if NONCONTIGUOUS).
This script parses that range and iterates over each prompt index, calling
the local vLLM server for each one and writing per-prompt result files.
"""
import argparse
import json
import os
import time
import urllib.request
import urllib.error


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

        # Split off optional stride ":N"
        step = 1
        if ":" in part:
            part, step_s = part.split(":", 1)
            step = int(step_s)
            if step < 1:
                raise ValueError(f"Stride must be >= 1, got {step} in {range_str!r}")

        # Split off optional range "M-N"
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            indices.extend(range(start, end + 1, step))
        else:
            # Single value - stride is meaningless but harmless
            indices.append(int(part))
    return sorted(set(indices))


def load_prompts(input_file, indices):
    """Load all requested lines (1-based) in a single pass over the file."""
    needed = set(indices)
    results = {}
    with open(input_file) as f:
        for i, line in enumerate(f, 1):
            if i in needed:
                line = line.strip()
                if line:
                    results[i] = json.loads(line)
                if len(results) == len(needed):
                    break
    return results


def call_vllm(prompt_text, model, max_tokens, temperature):
    """Send a chat completion request to the local vLLM server."""
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt_text}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()

    req = urllib.request.Request(
        "http://localhost:8000/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    # Retry up to 3 times for transient errors
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError) as e:
            last_err = e
            if attempt < 2:
                print(f"    retry {attempt + 1}: {e}", flush=True)
                time.sleep(2)
            else:
                raise
    raise RuntimeError(f"all retries failed: {last_err}")


def process_prompt(index, prompt_data, output_dir, model, default_max_tokens, default_temperature):
    """Process one prompt: call vLLM and write the result file."""
    if prompt_data is None:
        print(f"  Prompt {index}: not found in file, skipping.", flush=True)
        return

    prompt_text = prompt_data.get("prompt", prompt_data.get("text", ""))
    max_tokens = prompt_data.get("max_tokens", default_max_tokens)
    temperature = prompt_data.get("temperature", default_temperature)

    print(f"  Prompt {index}: {prompt_text[:80]}...", flush=True)

    response = call_vllm(prompt_text, model, max_tokens, temperature)

    choice = response["choices"][0]
    result = {
        **prompt_data,
        "generated_text": choice["message"]["content"],
        "finish_reason": choice["finish_reason"],
        "prompt_tokens": response["usage"]["prompt_tokens"],
        "completion_tokens": response["usage"]["completion_tokens"],
    }

    output_path = os.path.join(output_dir, f"result_{index}.jsonl")
    with open(output_path, "w") as f:
        f.write(json.dumps(result) + "\n")

    print(f"    → {result['completion_tokens']} tokens, finish: {result['finish_reason']}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--prompt-range", required=True,
                        help="Chunk range string, e.g. '1-5' or '2,5,8-9'")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    indices = parse_range(args.prompt_range)
    print(f"Processing chunk with {len(indices)} prompts: {indices}", flush=True)

    prompts = load_prompts(args.input_file, indices)
    chunk_start = time.time()

    for idx in indices:
        prompt_start = time.time()
        process_prompt(idx, prompts.get(idx), args.output_dir, args.model,
                       args.max_tokens, args.temperature)
        print(f"    ({time.time() - prompt_start:.1f}s)", flush=True)

    print(f"Chunk done in {time.time() - chunk_start:.1f}s "
          f"({len(indices)} prompts, {(time.time() - chunk_start) / max(len(indices), 1):.1f}s/prompt avg)",
          flush=True)


if __name__ == "__main__":
    main()
