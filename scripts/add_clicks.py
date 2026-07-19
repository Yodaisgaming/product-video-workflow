import json
import subprocess
import sys

from _common import ffmpeg_bin, ffprobe_bin

FF = ffmpeg_bin()
FP = ffprobe_bin()

USAGE = "usage: add_clicks.py <src> <out> <marks.json> <ss> <click.wav> [offset]"


def has_audio(path):
    r = subprocess.run(
        [FP, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    return bool(r.stdout.strip())


def duration(path):
    r = subprocess.run(
        [FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def main():
    if len(sys.argv) < 6:
        sys.exit(USAGE)
    src = sys.argv[1]
    out = sys.argv[2]
    marks_json = sys.argv[3]
    ss = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
    click = sys.argv[5]
    offset = float(sys.argv[6]) if len(sys.argv) > 6 else 0.0

    with open(marks_json) as f:
        marks = json.load(f)
    times = [round(m - ss + offset, 3) for m in marks if (m - ss + offset) >= 0.05]
    if not times:
        subprocess.run([FF, "-y", "-loglevel", "error", "-i", src, "-c", "copy", out], check=True)
        print("WROTE", out, "(no clicks)")
        return

    src_has_audio = has_audio(src)
    inputs = ["-i", src, "-i", click]
    if src_has_audio:
        base = "[0:a]"
    else:
        vdur = duration(src) or 60.0
        inputs += ["-f", "lavfi", "-t", f"{vdur:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
        base = "[2:a]"

    n = len(times)
    parts = [f"[1:a]asplit={n}" + "".join(f"[s{i}]" for i in range(n))]
    for i, t in enumerate(times):
        ms = int(t * 1000)
        parts.append(f"[s{i}]adelay={ms}|{ms}[d{i}]")
    mix_in = base + "".join(f"[d{i}]" for i in range(n))
    parts.append(f"{mix_in}amix=inputs={n + 1}:normalize=0:duration=first[a]")
    fc = ";".join(parts)

    cmd = [
        FF, "-y", "-loglevel", "error",
        *inputs,
        "-filter_complex", fc,
        "-map", "0:v", "-c:v", "copy",
        "-map", "[a]", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", out,
    ]
    subprocess.run(cmd, check=True)
    print("WROTE", out, "clicks at", times)


if __name__ == "__main__":
    main()
