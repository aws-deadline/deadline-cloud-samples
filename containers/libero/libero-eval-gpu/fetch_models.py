"""Download the LIBERO assets and the policy weights into the image at build time."""

import os

from huggingface_hub import snapshot_download

snapshot_download(repo_id="lerobot/libero-assets", repo_type="dataset", local_dir="/opt/libero/assets")

for repo in os.environ["POLICIES"].split():
    snapshot_download(repo_id=repo)

# Backbone and tokenizer that the default policies load by name. Skip the ONNX
# exports, which are large and unused.
snapshot_download(
    repo_id="HuggingFaceTB/SmolVLM2-500M-Video-Instruct",
    allow_patterns=["*.json", "*.safetensors", "*.txt", "*.jinja", "*.model"],
    ignore_patterns=["onnx/*"],
)
snapshot_download(repo_id="facebook/bart-large", allow_patterns=["*.json", "*.txt"])
