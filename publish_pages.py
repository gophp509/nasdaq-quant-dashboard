from __future__ import annotations

import json
from pathlib import Path

SUMMARY_SOURCE = Path("outputs/summary.json")
DASHBOARD_SOURCE = Path("outputs/dashboard.html")
ROOT_SUMMARY = Path("summary.json")
INDEX_PATH = Path("index.html")
V15_PATH = Path("v15.html")
V2_PATH = Path("v2.html")


def main() -> None:
    summary = json.loads(SUMMARY_SOURCE.read_text(encoding="utf-8"))
    ROOT_SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    html = DASHBOARD_SOURCE.read_text(encoding="utf-8")
    INDEX_PATH.write_text(html, encoding="utf-8")
    V15_PATH.write_text(html, encoding="utf-8")
    V2_PATH.write_text(html, encoding="utf-8")
    print(INDEX_PATH)
    print(V15_PATH)
    print(V2_PATH)
    print(ROOT_SUMMARY)


if __name__ == "__main__":
    main()
