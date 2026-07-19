# Tool landscape (researched 2026-07)

How other people build high-quality "playable" product-demo videos of a web UI, and why this repo
lands on scripted live-capture + ffmpeg. Findings verified against docs/repos/release notes.

## Options considered

| Tool / approach | What it is | Verdict for this use case |
| --- | --- | --- |
| **Cap** (cap.so, OSS) | Loom/Screen-Studio-style recorder, native Windows, "Studio Mode" auto-zoom-to-click + smooth cursor, local mp4 export. Very active. | Best turnkey polish on Windows. Downsides: manual screen-record, de-brand must happen live, can't be scripted headlessly. AGPLv3 core (MIT crates). |
| **Screen Studio** | The polish benchmark (auto cinematic zoom, eased cursor, backgrounds). | macOS-only, closed, paid. Used only as the quality target. |
| **Playwright video** | Records real app. | Its recorder captures at **CSS-pixel viewport size and ignores deviceScaleFactor**; unset `record_video_size` downscales to 800x800 — the softness. Fix: large native viewport, `record_video_size == viewport`, then downscale. No bitrate control. |
| **Screenshots-per-frame -> ffmpeg** | Deterministic frames at DPR 2, supersampled. | Sharpest, but only suits a synthetic stage, not real-time live interaction (screenshots too slow for 30fps). |
| **Remotion** | React programmatic video, most active/polished code route. | Source-available, paid Company License at 4+ people — licensing risk. Revideo (MIT) is the free fork. |
| **Motion Canvas / Revideo** | Code-driven animation; Revideo is the maintained MIT fork. | Good for composited motion; heavier build than needed here. |
| **rrweb + rrvideo** | Real-DOM record/replay (MIT); editable event stream for de-brand. | Great for capturing messy real sessions and redacting them, but export sharpness is uncontrolled. |
| **Arcade / Supademo / Storylane / Navattic** | Interactive-demo SaaS. | Not open-source; host interactive iframes, no clean standalone mp4 export. Wrong tool for a self-hosted video LP. |

## Landing-page best practice

- Dominant embed: self-hosted **autoplay muted loop MP4 (H.264)**, one short clip per section.
- Authenticity vs polish: for a portfolio, keep it **real-recording based** and layer polish on top.
- **Auto-zoom + eased cursor** is the top "studio-made" signal — worth replicating.
- Encode: `-an` for the page copy (muted anyway), poster frame, <=2-4MB, lazy-load below the fold.

## Why this repo's pipeline

Scripted live-capture (Playwright) + ffmpeg gives: real UI (authentic), frame-perfect de-brand
control, reproducibility,
zero install beyond Playwright/ffmpeg, and — by reproducing the zoom-to-click and framed-backdrop
effects in post — the same premium look as the dedicated recorders.
