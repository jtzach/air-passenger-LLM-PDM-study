"""Remove provider-returned account identifiers before publishing API archives."""
import hashlib
import json
from pathlib import Path
from run_experiment import sanitize

ROOT = Path(__file__).resolve().parents[1]
changes = []
for folder in (ROOT / "results/raw", ROOT / "results/smoke"):
    for path in folder.glob("*.json"):
        old = path.read_bytes()
        obj = json.loads(old)
        cleaned = sanitize(obj)
        if cleaned != obj:
            new = (json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n").encode()
            path.write_bytes(new)
            changes.append({"file": path.relative_to(ROOT).as_posix(),
                            "before_sha256": hashlib.sha256(old).hexdigest(),
                            "after_sha256": hashlib.sha256(new).hexdigest()})
audit = ROOT / "results/account_metadata_redaction.json"
if changes or not audit.exists():
    audit.write_text(json.dumps({"reason": "Remove API-account identifiers; retain scientific results and error status", "changed_files": changes}, indent=2) + "\n", encoding="utf-8")
print(f"Removed private account metadata from {len(changes)} archive files.")
