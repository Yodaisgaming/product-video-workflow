import json
import os
import subprocess
import sys

from _common import ffmpeg_bin

FF = ffmpeg_bin()

VW, VH = 2560, 1600
FPS = 30
EASE = 0.44
ZMUL = 1.0
ZBASE = 1.0
US = 2


def pw(var, pts):
    xs = [p[0] for p in pts]
    vs = [p[1] for p in pts]
    expr = f"{vs[-1]:.4f}"
    for i in range(len(pts) - 1, 0, -1):
        a, b = xs[i - 1], xs[i]
        va, vb = vs[i - 1], vs[i]
        span = max(1e-4, b - a)
        u = f"clip(({var}-{a:.4f})/{span:.4f},0,1)"
        s = f"({u})*({u})*(3-2*({u}))"
        seg = f"({va:.4f}+({vb - va:.4f})*({s}))"
        expr = f"if(lt({var},{b:.4f}),{seg},{expr})"
    return expr


def keyframes(cam, base=1.0, cx0=None, y0=None):
    x0 = cx0 if cx0 is not None else VW / 2
    yy0 = y0 if y0 is not None else VH / 2
    pts = [{"t": 0.0, "x": x0, "y": yy0, "z": base}]
    prev = pts[0]
    for c in cam:
        t_hold = max(pts[-1]["t"] + 0.03, c["t"])
        pts.append({"t": t_hold, "x": prev["x"], "y": prev["y"], "z": prev["z"]})
        pts.append({"t": t_hold + EASE, "x": c["x"], "y": c["y"], "z": c["z"]})
        prev = {"x": c["x"], "y": c["y"], "z": c["z"]}
    out = [pts[0]]
    for p in pts[1:]:
        if p["t"] <= out[-1]["t"]:
            p["t"] = out[-1]["t"] + 0.02
        out.append(p)
    return out


def main():
    global EASE
    if len(sys.argv) < 4:
        sys.exit("usage: zoom_pass.py <raw> <cam.json> <out> [offset] [zmul] [ease] [cx_fixed|none] [zbase]")
    raw = sys.argv[1]
    cam_json = sys.argv[2]
    out = sys.argv[3]
    off = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
    zmul = float(sys.argv[5]) if len(sys.argv) > 5 else ZMUL
    if len(sys.argv) > 6:
        EASE = float(sys.argv[6])
    cx_fixed = float(sys.argv[7]) if len(sys.argv) > 7 and sys.argv[7] not in ("", "none") else None
    zbase = float(sys.argv[8]) if len(sys.argv) > 8 else ZBASE

    with open(cam_json) as f:
        cam = json.load(f)
    for c in cam:
        c["t"] = c["t"] + off
        if c["z"] > 1.0:
            c["z"] = 1.0 + (c["z"] - 1.0) * zmul
        c["z"] = max(zbase, c["z"])
        if cx_fixed is not None:
            c["x"] = cx_fixed

    y0 = cam[0]["y"] if cam else None
    kf = keyframes(cam, base=zbase, cx0=cx_fixed, y0=y0)
    t = "(on/%d)" % FPS
    zexpr = pw(t, [(p["t"], p["z"]) for p in kf])
    cxexpr = pw(t, [(p["t"], p["x"] * US) for p in kf])
    cyexpr = pw(t, [(p["t"], p["y"] * US) for p in kf])

    xexpr = f"({cxexpr})-(iw/zoom)/2"
    yexpr = f"({cyexpr})-(ih/zoom)/2"

    fc = (
        f"scale=iw*{US}:ih*{US}:flags=lanczos,fps={FPS},"
        f"zoompan=z='{zexpr}':x='{xexpr}':y='{yexpr}'"
        f":d=1:s={VW}x{VH}:fps={FPS}"
    )
    cmd = [
        FF, "-y", "-loglevel", "error", "-i", raw,
        "-vf", fc,
        "-c:v", "libx264", "-crf", "16", "-preset", "slow",
        "-pix_fmt", "yuv420p", "-an", out,
    ]
    subprocess.run(cmd, check=True)
    print("ZOOMED", out, os.path.getsize(out) // 1024, "KB", f"{len(kf)} keyframes")


if __name__ == "__main__":
    main()
