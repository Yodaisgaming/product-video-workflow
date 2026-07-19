import json
import os


def ffmpeg_bin():
    return os.environ.get("FFMPEG", "ffmpeg")


def ffprobe_bin():
    return os.environ.get("FFPROBE", "ffprobe")


def out_dir():
    d = os.environ.get("OUT_DIR", "out")
    os.makedirs(d, exist_ok=True)
    return d


_ALLOWED_FLAGS = set("gimsuy")


def load_debrand():
    path = os.environ.get("DEBRAND_CONFIG") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "debrand.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    subs = data.get("substitutions", [])
    for i, s in enumerate(subs):
        if not isinstance(s, list) or len(s) < 2 or not isinstance(s[0], str) or not isinstance(s[1], str):
            raise ValueError(f"{path}: substitution {i} must be [pattern, replacement, flags?] of strings")
        if len(s) > 2 and (not isinstance(s[2], str) or set(s[2]) - _ALLOWED_FLAGS):
            raise ValueError(f"{path}: substitution {i} has invalid regex flags {s[2]!r} (allowed: {''.join(sorted(_ALLOWED_FLAGS))})")
    return subs
