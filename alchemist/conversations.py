"""JSON-file-backed conversation persistence for Alchemist."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_\-]")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(conv_id: str) -> str:
    cleaned = _SAFE_ID_RE.sub("", conv_id)
    if not cleaned:
        raise ValueError("Invalid conversation id")
    return cleaned


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class ConversationStore:
    """Stores conversations as `<root>/<id>.json` and plot PNGs under
    `<root>/plots/<id>/<msg_idx>.png`.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "plots").mkdir(exist_ok=True)

    def _conv_path(self, conv_id: str) -> Path:
        return self.root / f"{_safe_id(conv_id)}.json"

    def _plot_dir(self, conv_id: str) -> Path:
        return self.root / "plots" / _safe_id(conv_id)

    def list(self) -> list[dict]:
        items: list[dict] = []
        for p in self.root.glob("*.json"):
            try:
                data = json.loads(p.read_text())
            except Exception:
                continue
            msgs = data.get("messages") or []
            first_user = next(
                (m.get("content", "") for m in msgs if m.get("role") == "user"),
                "",
            )
            preview = first_user.strip().replace("\n", " ")
            if len(preview) > 30:
                preview = preview[:30] + "..."
            items.append({
                "id": data.get("id", p.stem),
                "preview": preview or "(empty)",
                "messages": len(msgs),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
            })
        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return items

    def get(self, conv_id: str) -> dict | None:
        p = self._conv_path(conv_id)
        if not p.exists():
            return None
        return json.loads(p.read_text())

    def save(self, conv_id: str, messages: list[dict]) -> dict:
        existing = self.get(conv_id) or {}
        data = {
            "id": conv_id,
            "messages": messages,
            "created_at": existing.get("created_at") or _now(),
            "updated_at": _now(),
        }
        self._conv_path(conv_id).write_text(json.dumps(data, indent=2))
        return data

    def delete(self, conv_id: str) -> bool:
        p = self._conv_path(conv_id)
        plot_dir = self._plot_dir(conv_id)
        existed = p.exists()
        if existed:
            p.unlink()
        if plot_dir.exists():
            for child in plot_dir.iterdir():
                try:
                    child.unlink()
                except Exception:
                    pass
            try:
                plot_dir.rmdir()
            except OSError:
                pass
        return existed

    def save_plot(self, conv_id: str, msg_idx: int, png_bytes: bytes) -> Path:
        plot_dir = self._plot_dir(conv_id)
        plot_dir.mkdir(parents=True, exist_ok=True)
        path = plot_dir / f"{int(msg_idx)}.png"
        path.write_bytes(png_bytes)
        return path

    def plot_path(self, conv_id: str, msg_idx: int) -> Path | None:
        path = self._plot_dir(conv_id) / f"{int(msg_idx)}.png"
        return path if path.exists() else None


__all__ = ["ConversationStore", "new_id"]
