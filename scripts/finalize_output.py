import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter

from _common import ffmpeg_bin, out_dir

FF = ffmpeg_bin()
U = out_dir()

CW, CH = 1680, 1110
PORTRAIT_H = 968
PORTRAIT_W = round(PORTRAIT_H * 9 / 16)
PX = (CW - PORTRAIT_W) // 2
PY = (CH - PORTRAIT_H) // 2
RAD = 28


def build(light=True):
    if light:
        base, tintc, stroke = (236, 237, 241), (223, 227, 238), (10, 12, 20)
    else:
        base, tintc, stroke = (8, 8, 10), (26, 30, 46), (255, 255, 255)
    bg = Image.new("RGB", (CW, CH), base)
    glow = Image.new("L", (CW, CH), 0)
    ImageDraw.Draw(glow).ellipse([CW * 0.18, -CH * 0.35, CW * 0.82, CH * 0.9], fill=68)
    glow = glow.filter(ImageFilter.GaussianBlur(200))
    bg = Image.composite(Image.new("RGB", (CW, CH), tintc), bg, glow)
    bgp = os.path.join(U, "_out_bg.png")
    bg.save(bgp)

    mask = Image.new("L", (PORTRAIT_W, PORTRAIT_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, PORTRAIT_W - 1, PORTRAIT_H - 1], radius=RAD, fill=255)
    mp = os.path.join(U, "_out_mask.png")
    mask.save(mp)

    sh = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([PX, PY + 24, PX + PORTRAIT_W, PY + 24 + PORTRAIT_H], radius=RAD, fill=(0, 0, 0, 78))
    sh = sh.filter(ImageFilter.GaussianBlur(48))
    sp = os.path.join(U, "_out_shadow.png")
    sh.save(sp)

    st = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    ImageDraw.Draw(st).rounded_rectangle([PX, PY, PX + PORTRAIT_W - 1, PY + PORTRAIT_H - 1], radius=RAD, outline=(*stroke, 45), width=2)
    stp = os.path.join(U, "_out_stroke.png")
    st.save(stp)
    return bgp, mp, sp, stp


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: finalize_output.py <raw> <out> [dur] [light|dark]")
    raw = sys.argv[1]
    out = sys.argv[2]
    dur = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] not in ("", "none") else None
    style = sys.argv[4] if len(sys.argv) > 4 else "light"
    bgp, mp, sp, stp = build(style == "light")
    fadecol = ":color=white" if style == "light" else ""

    loop = ["-stream_loop", "-1"] if dur else []
    inputs = ["-i", bgp, "-i", sp] + loop + ["-i", raw, "-i", mp, "-i", stp]
    if dur:
        fo = max(0.1, float(dur) - 0.6)
        vfade = f",fade=t=in:st=0:d=0.5{fadecol},fade=t=out:st={fo}:d=0.6{fadecol}"
    else:
        vfade = ""

    fc = (
        f"[2:v]scale={PORTRAIT_W}:{PORTRAIT_H}:flags=lanczos,format=rgba[pv];"
        f"[pv][3:v]alphamerge[rp];"
        f"[2:v]scale={CW}:{CH}:force_original_aspect_ratio=increase,crop={CW}:{CH},boxblur=42:2,eq=brightness=0.12:saturation=1.05,format=rgba,colorchannelmixer=aa=0.30[fill];"
        f"[0:v][fill]overlay=0:0[b1];[b1][1:v]overlay=0:0[b2];"
        f"[b2][rp]overlay={PX}:{PY}[b3];[b3][4:v]overlay=0:0,format=yuv420p{vfade}[vo]"
    )
    cmd = [FF, "-y", "-loglevel", "error", *inputs, "-filter_complex", fc, "-map", "[vo]", "-an",
           "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-movflags", "+faststart"]
    if dur:
        cmd += ["-t", dur]
    cmd += [out]
    subprocess.run(cmd, check=True)
    print("WROTE", out, os.path.getsize(out) // 1024, "KB", f"{CW}x{CH}")


if __name__ == "__main__":
    main()
