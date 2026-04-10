"""OpenPeon sound effects plugin for Hermes Agent.

Plays random Orc Peon sound effects on session start/end events.
Reads sound pack configuration from openpeon.json and uses afplay (macOS)
to asynchronously play randomly selected sounds.

Config:
  OPENPEON_PACK_PATH  — path to openpeon.json (default: ~/.openpeon/packs/peon/openpeon.json)
  OPENPEON_MUTED      — set to "1" to mute all sounds
  OPENPEON_VOLUME     — volume 0.0-1.0 (default: 1.0, macOS only)
"""

from __future__ import annotations

import json
import logging
import os
import random
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_DEFAULT_PACK_PATH = os.path.expanduser("~/.openpeon/packs/peon/openpeon.json")

# Hermes hook → openpeon category mapping
_HOOK_CATEGORY_MAP = {
    "on_session_start": "session.start",
    "on_session_end": "task.complete",
    "pre_tool_call": "task.acknowledge",
    "post_llm_call": "task.complete",
}

_pack_cache: Optional[Dict[str, Any]] = None
_pack_cache_path: Optional[str] = None
_last_played: Dict[str, str] = {}  # category → last file played


def _get_pack_path() -> str:
    return os.environ.get("OPENPEON_PACK_PATH", _DEFAULT_PACK_PATH)


def _is_muted() -> bool:
    return os.environ.get("OPENPEON_MUTED", "").strip() in ("1", "true", "yes")


def _get_volume() -> float:
    try:
        return max(0.0, min(1.0, float(os.environ.get("OPENPEON_VOLUME", "1.0"))))
    except (ValueError, TypeError):
        return 1.0


def _load_pack() -> Optional[Dict[str, Any]]:
    """Load and cache the openpeon.json pack config."""
    global _pack_cache, _pack_cache_path
    pack_path = _get_pack_path()

    if _pack_cache is not None and _pack_cache_path == pack_path:
        return _pack_cache

    try:
        with open(pack_path, "r", encoding="utf-8") as f:
            _pack_cache = json.load(f)
        _pack_cache_path = pack_path
        logger.debug("OpenPeon: loaded pack from %s", pack_path)
        return _pack_cache
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("OpenPeon: failed to load pack %s: %s", pack_path, e)
        return None


def _resolve_sound_path(file_ref: str) -> Optional[str]:
    """Resolve a sound file path relative to the pack directory."""
    pack_path = _get_pack_path()
    pack_dir = os.path.dirname(pack_path)

    if os.path.isabs(file_ref):
        return file_ref if os.path.exists(file_ref) else None

    resolved = os.path.join(pack_dir, file_ref)
    return resolved if os.path.exists(resolved) else None


def _pick_sound(category: str) -> Optional[str]:
    """Pick a random sound for the given category, avoiding immediate repeats."""
    pack = _load_pack()
    if not pack:
        return None

    categories = pack.get("categories", {})
    cat_data = categories.get(category, {})
    sounds = cat_data.get("sounds", [])

    if not sounds:
        logger.debug("OpenPeon: no sounds for category '%s'", category)
        return None

    # Filter out the last played sound if there are alternatives
    last = _last_played.get(category)
    candidates = [s for s in sounds if s["file"] != last] if len(sounds) > 1 else sounds

    chosen = random.choice(candidates)
    _last_played[category] = chosen["file"]

    return _resolve_sound_path(chosen["file"])


def _play_sound(sound_path: str) -> None:
    """Play a sound file asynchronously using the system audio player."""
    if _is_muted():
        logger.debug("OpenPeon: muted, skipping %s", sound_path)
        return

    try:
        # macOS: afplay
        cmd = ["afplay", sound_path]
        volume = _get_volume()
        if volume < 1.0:
            # afplay doesn't support volume directly, but we can note it
            pass

        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.debug("OpenPeon: playing %s", os.path.basename(sound_path))
    except FileNotFoundError:
        logger.warning("OpenPeon: no audio player found (tried afplay)")
    except Exception as e:
        logger.warning("OpenPeon: playback failed: %s", e)


def _handle_hook(hook_name: str, **kwargs: Any) -> None:
    """Generic hook handler — maps hook to openpeon category and plays a sound."""
    category = _HOOK_CATEGORY_MAP.get(hook_name)
    if not category:
        logger.debug("OpenPeon: hook '%s' has no mapped category, skipping.", hook_name)
        return

    logger.info("OpenPeon: Hook '%s' triggered. Attempting to play sound for category '%s'.", hook_name, category)

    def _run():
        sound_path = _pick_sound(category)
        if sound_path:
            _play_sound(sound_path)

    # Fire and forget — don't block the agent
    threading.Thread(target=_run, daemon=True, name=f"openpeon-{hook_name}").start()


# ---------------------------------------------------------------------------
# Hook callbacks (one per registered hook)
# ---------------------------------------------------------------------------

def _on_session_start(**kwargs: Any) -> None:
    _handle_hook("on_session_start", **kwargs)


def _on_session_end(**kwargs: Any) -> None:
    _handle_hook("on_session_end", **kwargs)


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """Register OpenPeon hooks with the Hermes plugin system."""
    # Verify pack is loadable
    pack = _load_pack()
    if not pack:
        logger.warning("OpenPeon: pack not found at %s, hooks registered but will be silent",
                       _get_pack_path())
    else:
        cats = pack.get("categories", {})
        total = sum(len(c.get("sounds", [])) for c in cats.values())
        logger.info("OpenPeon: loaded pack '%s' (%d categories, %d sounds)",
                     pack.get("name", "?"), len(cats), total)

    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("on_session_end", _on_session_end)
    logger.info("OpenPeon: hooks registered (on_session_start, on_session_end)")
