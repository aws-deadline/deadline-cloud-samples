#!/usr/bin/env python3
"""Run inference for a single prompt by hitting the local vLLM server."""
import argparse
import json
import os
import time
import urllib.request
import urllib.error


def get_prompt_by_index(input_file, index):
    """Read the Nth line (1-based) from the input JSONL file."""
    with open(input_file) as f:
        for i, line in enumerate(f, 1):
            if i == index:
                return json.loads(line.strip())
    return None


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
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError) as e:
            if attempt < 2:
                print(f"  Retry {attempt + 1}: {e}")
                time.sleep(2)
            else:
                raise
    raise RuntimeError("unreachable: retry loop exited without returning or raising")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--prompt-index", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    # Read the prompt for this task
    prompt_data = get_prompt_by_index(args.input_file, args.prompt_index)
    if prompt_data is None:
        print(f"No prompt at index {args.prompt_index}, skipping.")
        return

    prompt_text = prompt_data.get("prompt", prompt_data.get("text", ""))
    max_tokens = prompt_data.get("max_tokens", args.max_tokens)
    temperature = prompt_data.get("temperature", args.temperature)

    print(f"Task {args.prompt_index}: {prompt_text[:80]}...")

    # Call vLLM
    response = call_vllm(prompt_text, args.model, max_tokens, temperature)

    # Extract result
    choice = response["choices"][0]
    result = {
        **prompt_data,
        "generated_text": choice["message"]["content"],
        "finish_reason": choice["finish_reason"],
        "prompt_tokens": response["usage"]["prompt_tokens"],
        "completion_tokens": response["usage"]["completion_tokens"],
    }

    # Write per-task result file
    os.makedirs(args.output_dir, exist_ok=True)
    output_path = os.path.join(args.output_dir, f"result_{args.prompt_index}.jsonl")
    with open(output_path, "w") as f:
        f.write(json.dumps(result) + "\n")

    print(f"  → {result['completion_tokens']} tokens, finish: {result['finish_reason']}")


if __name__ == "__main__":
    main()
