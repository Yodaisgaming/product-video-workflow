import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter

from _common import ffmpeg_bin, out_dir

FF = ffmpeg_bin()
U = out_dir()

CANVAS_W = 1680
PAD = 80
SRC_AR = 2560 / 1600
CONTENT_W = CANVAS_W - 2 * PAD
CONTENT_H = round(CONTENT_W / SRC_AR)
CANVAS_H = CONTENT_H + 2 * PAD
RADIUS = 24


def build_assets(style, tag):
    light = style == "light"
    if light:
        base, tintc, glow_fill, sh_alpha = (236, 237, 241), (224, 228, 238), 60, 55
    elif style == "flat":
        base, tintc, glow_fill, sh_alpha = (18, 19, 24), (30, 33, 42), 20, 110
    else:
        base, tintc, glow_fill, sh_alpha = (8, 8, 10), (26, 30, 46), 40, 150

    bg = Image.new("RGB", (CANVAS_W, CANVAS_H), base)
    glow = Image.new("L", (CANVAS_W, CANVAS_H), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([CANVAS_W * 0.15, -CANVAS_H * 0.4, CANVAS_W * 0.85, CANVAS_H * 0.9], fill=glow_fill)
    glow = glow.filter(ImageFilter.GaussianBlur(180))
    tint = Image.new("RGB", (CANVAS_W, CANVAS_H), tintc)
    bg = Image.composite(tint, bg, glow)
    bgp = os.path.join(U, f"_frame_bg_{tag}.png")
    bg.save(bgp)

    mask = Image.new("L", (CONTENT_W, CONTENT_H), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, CONTENT_W - 1, CONTENT_H - 1], radius=RADIUS, fill=255)
    mp = os.path.join(U, f"_frame_mask_{tag}.png")
    mask.save(mp)

    shadow = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([PAD, PAD + 22, PAD + CONTENT_W, PAD + 22 + CONTENT_H], radius=RADIUS, fill=(0, 0, 0, min(255, sh_alpha + 30)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(48))
    sd2 = ImageDraw.Draw(shadow)
    sd2.rounded_rectangle([PAD, PAD + 8, PAD + CONTENT_W, PAD + 8 + CONTENT_H], radius=RADIUS, fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    sp = os.path.join(U, f"_frame_shadow_{tag}.png")
    shadow.save(sp)

    stroke = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    strd = ImageDraw.Draw(stroke)
    sc = (10, 12, 20) if light else (255, 255, 255)
    strd.rounded_rectangle([PAD, PAD, PAD + CONTENT_W - 1, PAD + CONTENT_H - 1], radius=RADIUS, outline=(*sc, 46), width=2)
    strd.rounded_rectangle([PAD + 1, PAD + 1, PAD + CONTENT_W - 2, PAD + CONTENT_H - 2], radius=RADIUS - 1, outline=(*sc, 18), width=1)
    stp = os.path.join(U, f"_frame_stroke_{tag}.png")
    stroke.save(stp)
    return bgp, mp, sp, stp


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: finalize_framed.py <raw> <out> [bed.wav|none] [ss] [dur] [glow|flat|light]")
    raw = sys.argv[1]
    out = sys.argv[2]
    bed = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] not in ("", "none") else None
    ss = sys.argv[4] if len(sys.argv) > 4 else "0"
    dur = sys.argv[5] if len(sys.argv) > 5 else None
    style = sys.argv[6] if len(sys.argv) > 6 else "glow"

    tag = str(os.getpid())
    bgp, mp, sp, stp = build_assets(style, tag)

    trim = ["-ss", ss] + (["-t", dur] if dur else [])
    inputs = ["-i", bgp, "-i", sp] + trim + ["-i", raw, "-i", mp, "-i", stp]
    if bed:
        inputs += ["-i", bed]

    if dur:
        fo = max(0.1, float(dur) - 0.55)
        fc_col = ":color=white" if style == "light" else ""
        vfade = f",fade=t=in:st=0:d=0.45{fc_col},fade=t=out:st={fo}:d=0.55{fc_col}"
        afade = f",afade=t=out:st={fo}:d=0.55"
    else:
        vfade, afade = "", ""

    fc = (
        f"[2:v]scale={CONTENT_W}:{CONTENT_H}:flags=lanczos,format=rgba[v];"
        f"[v][3:v]alphamerge[rv];"
        f"[0:v][1:v]overlay=0:0[bs];"
        f"[bs][rv]overlay={PAD}:{PAD}[comp];"
        f"[comp][4:v]overlay=0:0,format=yuv420p{vfade}[vo]"
    )
    cmd = [FF, "-y", "-loglevel", "error", *inputs]
    if bed:
        fc += f";[5:a]afade=t=in:st=0:d=0.8,volume=0.3{afade}[a]"
        cmd += ["-filter_complex", fc, "-map", "[vo]", "-map", "[a]",
                "-c:a", "aac", "-b:a", "128k", "-shortest"]
    else:
        cmd += ["-filter_complex", fc, "-map", "[vo]", "-an"]
    cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    for p in (bgp, mp, sp, stp):
        try:
            os.remove(p)
        except OSError:
            pass
    print("WROTE", out, os.path.getsize(out) // 1024, "KB", f"{CANVAS_W}x{CANVAS_H}")


if __name__ == "__main__":
    main()
