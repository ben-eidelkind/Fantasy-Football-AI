"""Convert WHAT'S-NEW.md into JSON for the web client."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_markdown(markdown: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in markdown.splitlines():
        if line.startswith("## "):
            if current:
                entries.append(current)
            current = {"title": line[3:].strip(), "body": "", "date": ""}
        elif line.startswith("### ") and current is not None:
            if "date" in current and not current["date"]:
                current["date"] = line[4:].strip()
            else:
                current["body"] += f"\n{line[4:].strip()}"
        else:
            if current is not None:
                current["body"] += ("\n" if current["body"] else "") + line.strip()
    if current:
        entries.append(current)
    cleaned = []
    for entry in entries:
        body = re.sub(r"^[-*]\s+", "", entry.get("body", ""), flags=re.MULTILINE)
        cleaned.append(
            {
                "title": entry.get("title", ""),
                "body": body.strip(),
                "date": entry.get("date", ""),
            }
        )
    return cleaned


def main() -> None:
    markdown_path = ROOT / "WHAT'S-NEW.md"
    output_path = ROOT / "public" / "whats-new.json"
    markdown = markdown_path.read_text(encoding="utf-8")
    entries = parse_markdown(markdown)
    output_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
