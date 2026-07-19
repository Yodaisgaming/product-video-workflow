import json
import os
import subprocess
import sys

from _common import ffmpeg_bin

FF = ffmpeg_bin()


def main():
    if len(sys.argv) < 9:
        sys.exit("usage: cut_segment.py <raw.webm> <cam.json> <marks.json> <c0> <c1> <out_raw> <out_cam> <out_marks>")
    raw = sys.argv[1]
    cam_p = sys.argv[2]
    marks_p = sys.argv[3]
    c0 = float(sys.argv[4])
    c1 = float(sys.argv[5])
    out_raw = sys.argv[6]
    out_cam = sys.argv[7]
    out_marks = sys.argv[8]
    gap = c1 - c0

    subprocess.run([FF, "-y", "-loglevel", "error", "-i", raw, "-filter_complex",
                    f"[0:v]trim=0:{c0},setpts=PTS-STARTPTS[a];"
                    f"[0:v]trim={c1},setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1[o]",
                    "-map", "[o]", "-c:v", "libx264", "-crf", "16", "-preset", "medium", out_raw], check=True)

    with open(cam_p) as f:
        cam = json.load(f)
    ncam = []
    for k in cam:
        t = k["t"]
        if t <= c0:
            ncam.append(k)
        elif t >= c1:
            ncam.append({**k, "t": round(t - gap, 3)})
    with open(out_cam, "w") as f:
        json.dump(ncam, f)

    with open(marks_p) as f:
        marks = json.load(f)
    nmarks = [m for m in marks if m <= c0] + [round(m - gap, 3) for m in marks if m >= c1]
    with open(out_marks, "w") as f:
        json.dump(nmarks, f)

    print("CUT", os.path.basename(out_raw), "removed", round(gap, 1), "s | cam", len(ncam), "marks", nmarks)


if __name__ == "__main__":
    main()
