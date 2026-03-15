import hashlib
import json
import os
import sys
import urllib.request
from typing import Dict, Any

# Current bootstrap versions (as found in scripts/init_system.sh)
MANIFEST_DEFAULTS = {
    "uv": {
        "version": "0.10.7",
        "url_template": "https://github.com/astral-sh/uv/releases/download/{version}/{asset}",
        "assets": {
            "x86_64-unknown-linux-gnu": "uv-x86_64-unknown-linux-gnu.tar.gz",
            "x86_64-unknown-linux-musl": "uv-x86_64-unknown-linux-musl.tar.gz",
            "aarch64-unknown-linux-gnu": "uv-aarch64-unknown-linux-gnu.tar.gz",
            "aarch64-unknown-linux-musl": "uv-aarch64-unknown-linux-musl.tar.gz",
        }
    },
    "opencode": {
        "version": "1.2.5",
        "url": "https://opencode.ai/install",
    }
}

def get_sha256(url: str) -> str:
    print(f"Fetching {url} for hashing...", file=sys.stderr)
    try:
        with urllib.request.urlopen(url) as response:
            data = response.read()
            return hashlib.sha256(data).hexdigest()
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return ""

def generate_manifest() -> Dict[str, Any]:
    manifest = {
        "version": "1.0",
        "timestamp": os.popen("date -u +'%Y-%m-%dT%H:%M:%SZ'").read().strip(),
        "assets": {}
    }

    # UV Assets
    uv_conf = MANIFEST_DEFAULTS["uv"]
    uv_assets = {}
    for arch_libc, asset_name in uv_conf["assets"].items():
        url = uv_conf["url_template"].format(version=uv_conf["version"], asset=asset_name)
        sha = get_sha256(url)
        uv_assets[arch_libc] = {
            "name": asset_name,
            "url": url,
            "sha256": sha
        }
    manifest["assets"]["uv"] = {
        "version": uv_conf["version"],
        "variants": uv_assets
    }

    # OpenCode Installer
    oc_conf = MANIFEST_DEFAULTS["opencode"]
    oc_sha = get_sha256(oc_conf["url"])
    manifest["assets"]["opencode"] = {
        "version": oc_conf["version"],
        "url": oc_conf["url"],
        "sha256": oc_sha
    }

    return manifest

if __name__ == "__main__":
    manifest_data = generate_manifest()
    print(json.dumps(manifest_data, indent=2))
