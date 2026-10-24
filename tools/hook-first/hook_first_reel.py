#!/usr/bin/env python3
"""hook_first_reel.py SPEC.json OUT.mp4 [--frames DIR]: a silent 1080x1920 hook-first text Reel in Gloock (Oct 24, 2026).

Built after the Oct 23 Instagram insight on the DP-F8 "darkness" Reel: 70.2% of viewers skipped in the first 3 s
because frame 1 was empty parchment and the second line did not land until about 5 s.

Hook-first rules this script enforces:
  * His hook lines are fully on screen at frame 0, at full opacity. No fade-in, no word-by-word reveal.
  * Motion starts at frame 1: a slow camera push (whole frame, about its text block) and a warm light that
    flickers in during 0-1.2 s and keeps growing ("bring in a little light").
  * Every word stays inside the 9:16 platform-safe zone (top 270, bottom 672, sides 120, right rail 300 px
    from y 840), checked on every frame, including at full push. Out of bounds stops the render.
  * Words stay cream (#EEE3CD) at >= 4.5:1 over the brightest ground pixel behind them, checked on every frame.
  * Opens on the deep tone of the spec's color family and closes on it with the Gloock wordmark end card.

SPEC.json: {"rows": [[row, ...], ...], "family": "smoke", "font_px": 74, "wordmark": PNG, "font": TTF}
Each inner list is one of his lines; a line split across rows keeps every word in order (the split is his call).
"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
INK, CREAM, GOLD = (0x14, 0x0F, 0x0E), (0xEE, 0xE3, 0xCD), (0xB0, 0x8D, 0x57)
DEEP = {"smoke": (0x36, 0x38, 0x3F), "amber": (0x5B, 0x4B, 0x13), "rose": (0x8E, 0x26, 0x35)}
LIGHT = (0xE8, 0xB8, 0x6A)                       # warm lamp light, the gold family pushed toward flame
SAFE = dict(top=270, bottom=H - 672, left=120, right=W - 120, rail_x=W - 300, rail_y=840)
X0, TEXT_TOP = 146, 490
HOLD_END, OUT, TOTAL = 8.4, 0.6, 12.0             # words hold to 8.4 s, end card 9.0-12.0 s
PUSH = 0.04                                       # 1.00 -> 1.04 over the hold


def ease_out(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def lum(c):
    c = np.asarray(c, np.float64) / 255
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


def contrast(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


class Ground:
    def __init__(self, deep):
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        self.base = np.array(INK, np.float32) * 0.45 + np.array(deep, np.float32) * 0.55
        d = np.sqrt((xx - W * 0.18) ** 2 + ((yy - H * 0.20) * 0.85) ** 2) / (W * 1.15)
        self.lamp = (np.clip(1 - d, 0, 1) ** 2)[..., None]
        d2 = np.sqrt((xx - W * 0.5) ** 2 + ((yy - H * 0.42) * 0.8) ** 2) / (W * 0.95)
        self.halo = (np.clip(1 - d2, 0, 1) ** 2)[..., None]
        self.deep = np.array(deep, np.float32)
        vy = (yy / H - 0.5) * 2; vx = (xx / W - 0.5) * 2
        self.vig = (1 - 0.28 * np.clip(vx ** 2 + vy ** 2, 0, 1.6) / 1.6)[..., None]

    def at(self, t):
        # light: flickers in over 0-1.2 s (frame 1 already moving), then keeps rising slowly; dims for the close
        rise = ease_out(t / 1.2) * 0.30 + 0.22 * ease_out((t - 1.2) / 7.0)
        flick = 0.06 * math.sin(t * 17.0) * math.exp(-t * 1.6) + 0.025 * math.sin(t * 5.3 + 1.1) * (t < HOLD_END)
        a = max(0.0, rise + flick)
        close = ease_out((t - HOLD_END) / 1.2)
        a *= 1 - 0.75 * close
        g = self.base + (np.array(LIGHT, np.float32) - self.base) * (self.lamp * a)
        g = g + (self.deep - g) * (self.halo * 0.55 * close)
        return np.clip(g * self.vig, 0, 255)


def layout(rows, size, font_path):
    f = ImageFont.truetype(font_path, size)
    lh, gap = round(size * 1.22), round(size * 0.62)
    placed, y = [], TEXT_TOP
    for li, line in enumerate(rows):
        for row in line:
            placed.append((row, X0, y)); y += lh
        y += gap
    return f, placed


def push_matrix(s, cx, cy):
    # inverse affine for PIL: output (x, y) samples input ((x - cx) / s + cx, (y - cy) / s + cy)
    return (1 / s, 0, cx - cx / s, 0, 1 / s, cy - cy / s)


def text_bbox(alpha):
    ys, xs = np.nonzero(alpha > 24)
    return (xs.min(), ys.min(), xs.max(), ys.max()) if len(xs) else None


def check_safe(alpha, t):
    bb = text_bbox(alpha)
    if bb is None:
        return
    x0, y0, x1, y1 = bb
    bad = x0 < SAFE["left"] or x1 > SAFE["right"] or y0 < SAFE["top"] or y1 > SAFE["bottom"]
    rail = alpha[SAFE["rail_y"]:, SAFE["rail_x"]:]
    if bad or (rail > 24).any():
        sys.exit(f"SAFE-ZONE FAIL at {t:.2f}s: words at {bb}")


def main(spec_path, out, frames_dir=None):
    spec = json.load(open(spec_path, encoding="utf-8"))
    rows, deep = spec["rows"], DEEP[spec.get("family", "smoke")]
    font, placed = layout(rows, spec.get("font_px", 74), spec["font"])
    small = ImageFont.truetype(spec["font"], 40)
    ground = Ground(deep)

    words = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(words)
    for row, x, y in placed:
        d.text((x, y), row, font=font, fill=255)
    bb = text_bbox(np.asarray(words))
    cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2

    wm = Image.open(spec["wordmark"]).convert("RGBA")
    wm = wm.resize((600, round(600 * wm.height / wm.width)), Image.LANCZOS)
    hw = small.getlength("labeau.ink")

    n, worst = int(TOTAL * FPS), 99.0
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                             "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    for k in range(n):
        t = k / FPS
        g = ground.at(t)
        s = 1 + PUSH * min(t / HOLD_END, 1.0)                       # linear: visibly moving from frame 1
        m = push_matrix(s, cx, cy)
        frame = Image.fromarray(g.astype(np.uint8), "RGB").transform((W, H), Image.AFFINE, m, Image.BICUBIC)
        wa = 1.0 if t <= HOLD_END else 1 - ease_out((t - HOLD_END) / OUT)
        if wa > 0:
            mask = words.transform((W, H), Image.AFFINE, m, Image.BICUBIC)
            ma = np.asarray(mask)
            check_safe(ma, t)
            behind = np.asarray(frame)[ma > 24]
            worst = min(worst, contrast(CREAM, behind.max(axis=0)))
            frame.paste(Image.new("RGB", (W, H), CREAM), (0, 0), mask.point(lambda v: int(v * wa)))
        ea = ease_out((t - HOLD_END - OUT) / 0.9)
        if ea > 0:
            rgba = frame.convert("RGBA")
            w2 = wm.copy(); w2.putalpha(w2.getchannel("A").point(lambda v: int(v * ea)))
            rgba.alpha_composite(w2, (W // 2 - w2.width // 2, 700 - w2.height // 2))
            lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(lay).text((W / 2 - hw / 2, 820), "labeau.ink", font=small, fill=GOLD + (int(235 * ea),))
            frame = Image.alpha_composite(rgba, lay).convert("RGB")
        if frames_dir and k in (0, 1, 15, 30, 45, 90, 150, 240, 285, 330, 359):
            frame.save(os.path.join(frames_dir, f"f{k:03d}.png"))
        proc.stdin.write(frame.tobytes())
    proc.stdin.close(); proc.wait()
    print(f"font {font.size}px, {TOTAL:.1f}s, worst word contrast {worst:.2f}:1, safe zone PASS every frame")
    if worst < 4.5:
        sys.exit("CONTRAST FAIL: under 4.5:1")
    return proc.returncode


if __name__ == "__main__":
    a = sys.argv[1:]
    fd = a[a.index("--frames") + 1] if "--frames" in a else None
    if fd: os.makedirs(fd, exist_ok=True)
    sys.exit(main(a[0], a[1], fd))
