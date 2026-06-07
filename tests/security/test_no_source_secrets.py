import re
from pathlib import Path


def test_source_does_not_contain_common_secret_assignments() -> None:
    pattern = re.compile(r"(?i)(client_secret|password|api_key)\s*=\s*['\"][^'\"]+")
    roots = [Path("apps"), Path("packages")]
    findings = []
    for root in roots:
        for path in root.rglob("*"):
            if path.suffix in {".py", ".ts", ".tsx"}:
                content = path.read_text(encoding="utf-8")
                if pattern.search(content):
                    findings.append(str(path))
    assert findings == []
