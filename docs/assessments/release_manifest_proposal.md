# Proposal: Generative Bootstrap Asset Manifest and Project-level Release Manifest

## 1. Background
Currently, bootstrap assets (such as `uv` and `opencode` installer) are managed via hardcoded environment variables in `scripts/init_system.sh` and `scripts/init_system_uv_release_manifest.sh`. This approach makes it difficult to:
- Synchronize versions across multiple scripts.
- Validate asset integrity automatically during CI/CD.
- Support air-gapped environments where a local mirror of assets is required.

## 2. Proposed Solution
Implement a generative manifest system that decouples asset definitions from deployment logic.

### 2.1 Release Manifest Structure
A JSON-based manifest (`release_manifest.json`) that explicitly defines all external dependencies required for bootstrapping.

```json
{
  "version": "1.0",
  "timestamp": "2026-03-15T03:23:01Z",
  "assets": {
    "uv": {
      "version": "0.10.7",
      "variants": {
        "x86_64-unknown-linux-gnu": {
          "name": "uv-x86_64-unknown-linux-gnu.tar.gz",
          "url": "...",
          "sha256": "..."
        }
      }
    },
    "opencode": {
      "version": "1.2.5",
      "url": "...",
      "sha256": "..."
    }
  }
}
```

### 2.2 Generative Tooling
A Python script `scripts/gen_release_manifest.py` to automate the generation of this manifest. This script:
1. Fetches asset metadata from upstream sources.
2. Calculates SHA256 checksums.
3. Produces a machine-readable JSON file.

### 2.3 Consumption in Shell Scripts
Deployment scripts will be updated to consume the JSON manifest using `jq` (or a simple Python wrapper if `jq` is not available, though `jq` is standard in most ops environments).

Example usage in `init_system.sh`:
```bash
UV_VERSION=$(jq -r '.assets.uv.version' release_manifest.json)
UV_SHA256=$(jq -r '.assets.uv.variants["x86_64-unknown-linux-gnu"].sha256' release_manifest.json)
```

## 3. Implementation Plan
1. [x] Draft `scripts/gen_release_manifest.py`.
2. [x] Generate initial `release_manifest.json`.
3. [ ] Integrate manifest reading into `scripts/init_system.sh`.
4. [ ] Deprecate `scripts/init_system_uv_release_manifest.sh`.
5. [ ] Add a CI check to ensure `release_manifest.json` matches the generated output from the definitions in the script.

## 4. Architectural Reflection
- **Pros**: Single source of truth for dependencies; better security via verified checksums in a centralized place; easier to support private mirrors by rewriting URLs in the JSON.
- **Cons**: Adds a dependency on a JSON parser or a temporary Python invocation in shell scripts.
- **Decision**: The benefit of having a verifiable, project-level manifest outweighs the minor complexity of parsing JSON, especially as the project grows in scale.
