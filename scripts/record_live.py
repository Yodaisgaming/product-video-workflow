import glob
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

from _common import load_debrand, out_dir

BASE = os.environ.get("APP_URL", "").rstrip("/")
LOGIN_PATH = os.environ.get("LOGIN_PATH", "")

VW, VH = 2560, 1600
MARKS = []
CAM = []
T0 = 0.0


def reg_env(name):
    if os.name != "nt":
        return None
    import winreg
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
        v, _ = winreg.QueryValueEx(k, name)
        return v
    except FileNotFoundError:
        return None


INIT = r"""
(() => {
  try {
    const bg = document.createElement('style');
    bg.textContent = 'html,body{background:__BG__ !important}';
    (document.head || document.documentElement).appendChild(bg);
  } catch (e) {}
  __FORCELIGHT__
  const add = () => {
    if (document.getElementById('__cur')) return;
    const st = document.createElement('style');
    st.textContent = `
      #__cur{position:fixed;left:-100px;top:-100px;width:30px;height:30px;z-index:2147483647;
        pointer-events:none;opacity:0;
        transition:left .55s cubic-bezier(.33,0,.15,1),top .55s cubic-bezier(.33,0,.15,1),opacity .25s ease;
        filter:drop-shadow(0 3px 6px rgba(0,0,0,.5));}
      #__rip{position:fixed;width:16px;height:16px;border-radius:50%;z-index:2147483646;
        pointer-events:none;background:rgba(124,157,255,.55);
        transform:translate(-50%,-50%) scale(0);opacity:0;}
      #__rip.go{animation:__r .55s ease-out;}
      @keyframes __r{0%{transform:translate(-50%,-50%) scale(0);opacity:.75;}
        100%{transform:translate(-50%,-50%) scale(9);opacity:0;}}
    `;
    document.documentElement.appendChild(st);
    const c = document.createElement('div'); c.id = '__cur';
    c.innerHTML = '<svg viewBox="0 0 24 24" width="30" height="30"><path d="M4 2l7 18 2.5-7.5L21 10z" fill="#fff" stroke="#111" stroke-width="1"/></svg>';
    document.body.appendChild(c);
    const r = document.createElement('div'); r.id = '__rip';
    document.body.appendChild(r);
  };
  window.__mk = add;
  window.__cur = (x, y) => { const c = document.getElementById('__cur'); if (c) { c.style.opacity = 1; c.style.left = (x - 5) + 'px'; c.style.top = (y - 3) + 'px'; } };
  window.__click = (x, y) => { const r = document.getElementById('__rip'); if (r) { r.style.left = x + 'px'; r.style.top = y + 'px'; r.classList.remove('go'); void r.offsetWidth; r.classList.add('go'); } };
  window.__DEBRAND_SUBS = __SUBS_JSON__;
  window.__debrand = () => {
    if (!document.body) return;
    const subs = [];
    for (const s of (window.__DEBRAND_SUBS || [])) {
      try { subs.push([new RegExp(s[0], s[2] || 'g'), s[1]]); } catch (e) {}
    }
    if (!subs.length) return;
    const apply = (str) => {
      let out = str, changed = false;
      for (const [re, to] of subs) { if (re.test(out)) { out = out.replace(re, to); changed = true; } }
      return changed ? out : null;
    };
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = w.nextNode())) { const r = apply(n.nodeValue); if (r !== null) n.nodeValue = r; }
    const els = document.body.querySelectorAll('input,textarea,[placeholder],[title],[alt],[aria-label]');
    for (const el of els) {
      if (typeof el.value === 'string' && el.value) { const r = apply(el.value); if (r !== null) el.value = r; }
      for (const attr of ['placeholder', 'title', 'alt', 'aria-label']) {
        const v = el.getAttribute && el.getAttribute(attr);
        if (v) { const r = apply(v); if (r !== null) el.setAttribute(attr, r); }
      }
    }
  };
  try { setInterval(() => { try { window.__debrand(); } catch (e) {} }, 350); } catch (e) {}
  try {
    const mo = new MutationObserver(() => { try { window.__debrand(); } catch (e) {} });
    const startMO = () => { if (document.body) mo.observe(document.body, { childList: true, subtree: true, characterData: true }); else setTimeout(startMO, 50); };
    startMO();
  } catch (e) {}
})();
"""


def load_light_css():
    """App-specific light CSS-token overrides, injected at document-create with !important.

    Point REC_LIGHT_CSS at a file whose body redefines the app's :root and dark-theme custom
    properties to their light values (mark them !important). This is what actually pins light from
    frame 0 — the attribute/observer force below is only a fallback, and on its own it flashes because
    many apps overwrite data-theme back to dark for one frame post-hydration.
    """
    path = os.environ.get("REC_LIGHT_CSS")
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    return ""


def build_init(light=False):
    if light:
        theme_key = os.environ.get("REC_THEME_KEY", "theme")
        theme_val = os.environ.get("REC_THEME_VALUE", "light")
        light_css = load_light_css()
        force_light = (
            "try { localStorage.setItem(%s, %s); } catch(e) {}\n"
            "try { const tok = document.createElement('style'); tok.textContent = %s;"
            "(document.head || document.documentElement).appendChild(tok); } catch(e) {}\n"
            "try { const fl = () => { if (document.documentElement.getAttribute('data-theme') !== 'light') "
            "document.documentElement.setAttribute('data-theme','light'); }; fl(); "
            "new MutationObserver(fl).observe(document.documentElement, {attributes:true, attributeFilter:['data-theme']}); "
            "setInterval(fl, 120); } catch(e) {}"
        ) % (json.dumps(theme_key), json.dumps(theme_val), json.dumps(light_css))
    else:
        force_light = ""
    return (INIT
            .replace("__SUBS_JSON__", json.dumps(load_debrand()))
            .replace("__BG__", "#ffffff" if light else "#0a0a0c")
            .replace("__FORCELIGHT__", force_light))


def prime(page):
    page.evaluate("window.__mk && window.__mk()")
    page.evaluate("window.__debrand && window.__debrand()")


def tap(page, loc, cx, cy):
    MARKS.append(round(time.monotonic() - T0, 3))
    page.evaluate("([x,y]) => window.__click(x,y)", [cx, cy])
    page.wait_for_timeout(120)


def cam_kf(x, y, z):
    CAM.append({"t": round(time.monotonic() - T0, 3), "x": round(x, 1), "y": round(y, 1), "z": z})


def center(loc):
    b = loc.bounding_box()
    if not b:
        return None
    return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2


def locate(page, loc, settle=200):
    loc.scroll_into_view_if_needed()
    page.wait_for_timeout(settle)
    return center(loc)


def point_cursor(page, x, y, settle=550):
    page.evaluate("([x,y]) => window.__cur(x,y)", [x, y])
    page.wait_for_timeout(settle)


def step(page, loc, cx, cy, z, settle=500, do_click=True):
    cam_kf(cx, cy, z)
    point_cursor(page, cx, cy, settle)
    tap(page, loc, cx, cy)
    if do_click:
        loc.click()


def example_scene(page):
    page.goto(BASE or "about:blank", wait_until="load", timeout=45000)
    page.wait_for_timeout(1500)
    prime(page)
    page.wait_for_timeout(350)

    field = page.get_by_role("textbox").first
    button = page.get_by_role("button").first

    if field.count():
        c = locate(page, field)
        if c:
            fx, fy = c
            cam_kf(fx, fy, 1.55)
            point_cursor(page, fx, fy, 520)
            tap(page, field, fx, fy)
            field.click()
            field.press_sequentially("your demo input goes here", delay=16)
            page.wait_for_timeout(320)

    if button.count():
        c = locate(page, button)
        if c:
            bx, by = c
            step(page, button, bx, by, 1.6, settle=440, do_click=False)
            page.wait_for_timeout(420)

    cam_kf(VW / 2, VH / 2, 1.0)
    page.wait_for_timeout(820)


SCENES = {"example": example_scene}


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "example"
    light = (len(sys.argv) > 2 and sys.argv[2] == "light") or os.environ.get("REC_THEME") == "light"
    if name not in SCENES:
        sys.exit(f"unknown scene '{name}'. defined: {', '.join(SCENES)}")
    if not BASE:
        sys.exit("set APP_URL to your deployed app, e.g. APP_URL=https://your-app.example")

    email = os.environ.get("APP_EMAIL") or reg_env("APP_EMAIL")
    pw_ = os.environ.get("APP_PASSWORD") or reg_env("APP_PASSWORD")
    rec = os.path.join(out_dir(), "rec_live_" + name)
    os.makedirs(rec, exist_ok=True)
    for old in glob.glob(os.path.join(rec, "*.webm")):
        os.remove(old)

    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        ctx = b.new_context(
            viewport={"width": VW, "height": VH},
            device_scale_factor=1,
            record_video_dir=rec,
            record_video_size={"width": VW, "height": VH},
        )
        ctx.add_init_script(build_init(light))
        if LOGIN_PATH and email and pw_:
            if not BASE.startswith("https://"):
                ctx.close()
                b.close()
                sys.exit("refusing to POST credentials over non-HTTPS APP_URL; use https or clear LOGIN_PATH")
            r = ctx.request.post(
                f"{BASE}{LOGIN_PATH}",
                data=json.dumps({"email": email, "password": pw_}),
                headers={"Content-Type": "application/json"},
            )
            print("LOGIN", r.status)
            if not r.ok:
                ctx.close()
                b.close()
                sys.exit(f"login failed ({r.status}); aborting so the run does not record a logged-out page")
        page = ctx.new_page()
        global T0
        T0 = time.monotonic()
        SCENES[name](page)
        ctx.close()
        b.close()

    with open(os.path.join(rec, "marks.json"), "w") as f:
        json.dump(MARKS, f)
    with open(os.path.join(rec, "cam.json"), "w") as f:
        json.dump(CAM, f)
    vids = sorted(glob.glob(os.path.join(rec, "*.webm")), key=os.path.getmtime)
    print("RAW", vids[-1] if vids else "NONE")
    print("MARKS", MARKS)
    print("CAM", CAM)


if __name__ == "__main__":
    main()
