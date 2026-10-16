"""Builds every graphic in the Victor Studios GitHub profile README.

Each SVG is self-contained: fonts are subset and embedded, images are inlined,
so nothing breaks when GitHub proxies the file. Run: python3 tools/build.py
Outputs go to assets/dark and assets/light (the hero and CTA are shared).
"""
import base64
import io
import os
import re
from html import escape

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image
import logging
logging.getLogger('fontTools').setLevel(logging.ERROR)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
OUT = os.path.join(ROOT, "assets")
DOCS = "/Users/salmanali/Documents"
CP = f"{DOCS}/contra-portfolio"

# victorstudios.org palette
ORANGE = "#ff6a00"
INK = "#0b0c10"
CREAM = "#f7f0dc"
INDIGO = "#2a1b72"
INDIGO_DEEP = "#1e1670"
PINK = "#f472b6"
VIOLET = "#a855f7"
CYAN = "#22d3ee"

THEMES = {
    "dark": dict(bg="#0e0f14", card="#13141b", card2="#181a23", line="rgba(255,255,255,0.09)",
                 text="#f7f0dc", muted="#9aa0ad", chip="#1d1f2a", chiptext="#d9dbe2", tile="#1b1d27"),
    "light": dict(bg="#fbf8f1", card="#ffffff", card2="#f6f1e4", line="rgba(11,12,16,0.10)",
                  text="#0b0c10", muted="#5d6270", chip="#f2ecdd", chiptext="#2a2d36", tile="#f4efe3"),
}

# ---------------------------------------------------------------- fonts

FONT_SRC = {
    "geist": os.path.join(TOOLS, "fonts", "Geist.ttf"),
    "mono": os.path.join(TOOLS, "fonts", "GeistMono.ttf"),
    "oxanium": os.path.join(TOOLS, "fonts", "Oxanium.ttf"),
}
_static = {}


def static_font(key, weight):
    k = (key, weight)
    if k not in _static:
        f = TTFont(FONT_SRC[key])
        _static[k] = instancer.instantiateVariableFont(f, {"wght": weight})
    return _static[k]


def text_width(s, key, weight, size, spacing=0.0):
    f = static_font(key, weight)
    cmap = f.getBestCmap()
    hmtx = f["hmtx"]
    upm = f["head"].unitsPerEm
    w = 0
    for ch in s:
        g = cmap.get(ord(ch))
        w += hmtx[g][0] if g else upm * 0.5
    return w * size / upm + spacing * len(s)


def font_face(key, weight, family, chars):
    f = static_font(key, weight)
    buf = io.BytesIO()
    f.save(buf)
    buf.seek(0)
    sub = TTFont(buf)
    opts = subset.Options()
    opts.flavor = "woff"
    opts.layout_features = ["kern", "liga"]
    s = subset.Subsetter(opts)
    s.populate(text="".join(sorted(set(chars))) + " ")
    s.subset(sub)
    out = io.BytesIO()
    sub.flavor = "woff"
    sub.save(out)
    b64 = base64.b64encode(out.getvalue()).decode()
    return f"@font-face{{font-family:'{family}';src:url(data:font/woff;base64,{b64}) format('woff');}}"


# family name -> (font key, weight)
FAMILIES = {
    "G4": ("geist", 400), "G5": ("geist", 500), "G6": ("geist", 600), "G8": ("geist", 800),
    "M5": ("mono", 500), "X7": ("oxanium", 700),
}


class Svg:
    """Collects text per font family so only the used glyphs get embedded."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.parts = []
        self.defs = []
        self.css = []
        self.used = {}

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, fam, size, fill, anchor="start", spacing=0, extra="", cls=""):
        self.used.setdefault(fam, set()).update(s)
        ls = f' letter-spacing="{spacing}"' if spacing else ""
        c = f' class="{cls}"' if cls else ""
        self.add(f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" fill="{fill}" '
                 f'text-anchor="{anchor}"{ls}{c} {extra}>{escape(s)}</text>')

    def render(self):
        faces = "".join(font_face(*FAMILIES[f], f, chars) for f, chars in self.used.items())
        return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                f'width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">'
                f'<defs><style>{faces}{"".join(self.css)}</style>{"".join(self.defs)}</defs>'
                f'{"".join(self.parts)}</svg>')


def save(svg, *path):
    p = os.path.join(OUT, *path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    data = svg.render() if isinstance(svg, Svg) else svg
    with open(p, "w") as fh:
        fh.write(data)
    return len(data)


# ---------------------------------------------------------------- images & icons

def img_uri(path, w, h=None, crop=None, fmt="JPEG", q=82, cover=True):
    im = Image.open(path)
    im = im.convert("RGBA" if fmt in ("PNG", "WEBP") else "RGB")
    if crop:
        im = im.crop(crop)
    if h:
        if cover:
            sc = max(w / im.width, h / im.height)
            im = im.resize((round(im.width * sc), round(im.height * sc)), Image.LANCZOS)
            l, t = (im.width - w) // 2, 0
            im = im.crop((l, t, l + w, t + h))
        else:
            im.thumbnail((w, h), Image.LANCZOS)
    else:
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, fmt, quality=q, method=6) if fmt == "WEBP" else im.save(buf, fmt, quality=q, optimize=True)
    mime = {"JPEG": "jpeg", "PNG": "png", "WEBP": "webp"}[fmt]
    return f"data:image/{mime};base64,{base64.b64encode(buf.getvalue()).decode()}", im.size


def icon_path(name):
    src = open(os.path.join(TOOLS, "icons", f"{name}.svg")).read()
    return re.search(r'<path d="([^"]+)"', src).group(1)


def icon(name, x, y, size, fill):
    s = size / 24
    return f'<path transform="translate({x} {y}) scale({s})" d="{icon_path(name)}" fill="{fill}"/>'


GLOBE = ("M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm6.9 6h-2.95a15.7 15.7 0 0 0-1.38-3.56A8.03 8.03 0 0 1 "
         "18.9 8ZM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82c.43-1.43 1.08-2.76 1.91-3.96ZM4.26 14a8.2 8.2 0 0 1 "
         "0-4h3.38a16.5 16.5 0 0 0 0 4H4.26Zm.84 2h2.95c.32 1.25.78 2.45 1.38 3.56A7.99 7.99 0 0 1 5.1 16Zm2.95-8"
         "H5.1a7.99 7.99 0 0 1 4.33-3.56A15.7 15.7 0 0 0 8.05 8ZM12 19.96A14.1 14.1 0 0 1 10.09 16h3.82A14.1 14.1 0 "
         "0 1 12 19.96ZM14.34 14H9.66a14.7 14.7 0 0 1 0-4h4.68a14.7 14.7 0 0 1 0 4Zm.25 5.56c.6-1.11 1.06-2.31 1.38"
         "-3.56h2.95a8.03 8.03 0 0 1-4.33 3.56ZM16.36 14a16.5 16.5 0 0 0 0-4h3.38a8.2 8.2 0 0 1 0 4h-3.38Z")
PEN = "M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25ZM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83Z"


def raw_icon(d, x, y, size, fill):
    return f'<path transform="translate({x} {y}) scale({size / 24})" d="{d}" fill="{fill}"/>'


def wrap(s, key, weight, size, maxw):
    words, lines, cur = s.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if text_width(t, key, weight, size) > maxw and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- hero (shared)

def hero():
    W, H = 1280, 560
    s = Svg(W, H)
    s.defs.append(f'''
<clipPath id="frame"><rect width="{W}" height="{H}" rx="28"/></clipPath>
<radialGradient id="gIndigo" cx="0.22" cy="0.05" r="0.75"><stop offset="0" stop-color="#3b22b8" stop-opacity="0.95"/>
 <stop offset="0.45" stop-color="{INDIGO_DEEP}" stop-opacity="0.55"/><stop offset="1" stop-color="{INK}" stop-opacity="0"/></radialGradient>
<radialGradient id="gOrange" cx="0.62" cy="1.05" r="0.55"><stop offset="0" stop-color="{ORANGE}" stop-opacity="0.75"/>
 <stop offset="0.5" stop-color="#b8430a" stop-opacity="0.25"/><stop offset="1" stop-color="{INK}" stop-opacity="0"/></radialGradient>
<radialGradient id="gHalo" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{ORANGE}" stop-opacity="0.55"/>
 <stop offset="1" stop-color="{ORANGE}" stop-opacity="0"/></radialGradient>
<linearGradient id="gName" x1="0" x2="1"><stop offset="0" stop-color="{ORANGE}"/><stop offset="0.55" stop-color="{PINK}"/><stop offset="1" stop-color="{VIOLET}"/></linearGradient>
<pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse"><path d="M48 0H0V48" fill="none" stroke="#ffffff" stroke-opacity="0.045"/></pattern>
<linearGradient id="fadeBottom" x1="0" y1="0" x2="0" y2="1"><stop offset="0.72" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<mask id="photoMask"><rect width="{W}" height="{H}" fill="url(#fadeBottom)"/></mask>''')
    s.css.append('''
.up{opacity:0;animation:up .9s cubic-bezier(.2,.7,.2,1) forwards}
@keyframes up{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
.float{animation:float 6s ease-in-out infinite}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
.pulse{animation:pulse 2s ease-out infinite;transform-origin:center;transform-box:fill-box}
@keyframes pulse{0%{opacity:.8;transform:scale(1)}100%{opacity:0;transform:scale(2.6)}}
.blink{animation:blink 1s steps(1) infinite}@keyframes blink{50%{opacity:0}}
''')
    s.add('<g clip-path="url(#frame)">')
    s.add(f'<rect width="{W}" height="{H}" fill="{INK}"/><rect width="{W}" height="{H}" fill="url(#grid)"/>')
    s.add(f'<rect width="{W}" height="{H}" fill="url(#gIndigo)"/><rect width="{W}" height="{H}" fill="url(#gOrange)"/>')
    # photo with halo
    s.add(f'<circle cx="1010" cy="330" r="260" fill="url(#gHalo)"/>')
    uri, (pw, ph) = img_uri(f"{CP}/assets/victor-hero.webp", 470, fmt="WEBP", q=80)
    s.add(f'<image href="{uri}" x="{1240 - pw}" y="{H - ph + 40}" width="{pw}" height="{ph}" mask="url(#photoMask)"/>')
    # floating chips around the photo
    chips = [("Framer", "framer", 770, 190, 0), ("Flutter", "flutter", 1120, 150, 1.5),
             ("Solidity", "solidity", 790, 400, 3), ("AI agents", "openai", 1090, 455, 4.5)]
    for label, ic, x, y, d in chips:
        w = text_width(label, "geist", 600, 17) + 58
        s.add(f'<g class="float" style="animation-delay:-{d}s">'
              f'<rect x="{x}" y="{y}" width="{w}" height="44" rx="22" fill="#ffffff" fill-opacity="0.08" stroke="#ffffff" stroke-opacity="0.18"/>'
              + icon(ic, x + 16, y + 12, 20, CREAM))
        s.text(x + 44, y + 28, label, "G6", 17, CREAM)
        s.add('</g>')
    # top bar
    luri, _ = img_uri(f"{CP}/assets/victor-logo-square.png", 96, 96, fmt="PNG")
    s.add(f'<rect x="48" y="40" width="48" height="48" rx="14" fill="#ffffff"/><image href="{luri}" x="50" y="42" width="44" height="44"/>')
    s.text(112, 61, "VICTOR STUDIOS", "M5", 15, CREAM, spacing=3)
    s.text(112, 82, "victorstudios.org", "M5", 13, "#b9b3c9")
    s.add(f'<g><rect x="936" y="44" width="296" height="40" rx="20" fill="#000" fill-opacity="0.35" stroke="#ffffff" stroke-opacity="0.15"/>'
          f'<circle cx="960" cy="64" r="5" fill="#25d366"/><circle class="pulse" cx="960" cy="64" r="5" fill="#25d366"/></g>')
    s.text(976, 69, "Available for new projects", "G5", 15, CREAM)
    # headline
    s.add('<g class="up" style="animation-delay:.1s">')
    s.text(56, 158, "DESIGN + ENGINEERING STUDIO", "M5", 15, ORANGE, spacing=3)
    s.add('</g><g class="up" style="animation-delay:.25s">')
    s.text(52, 262, "Meet", "G8", 104, CREAM, spacing=-3)
    mx = 52 + text_width("Meet ", "geist", 800, 104, -3)
    s.text(mx, 262, "Victor", "G8", 104, "url(#gName)", spacing=-3)
    s.add('</g>')
    # typewriter line
    prefix = "I design & build "
    s.text(56, 322, prefix, "G5", 32, "#d6d2e4")
    px = 56 + text_width(prefix, "geist", 500, 32)
    phrases = ["Framer websites", "AI agents & automations", "full AI web & mobile apps", "Web3 & NFT platforms"]
    period, slot = 16, 4
    for i, ph in enumerate(phrases):
        widths = [text_width(ph[:k], "geist", 600, 32) for k in range(len(ph) + 1)]
        n = len(ph)
        t_type, t_hold, t_del = 1.6, 3.0, 3.6   # seconds inside the 4s slot
        vals, keys = [], []
        for k in range(n + 1):
            vals.append(widths[k]); keys.append(t_type * k / n)
        vals.append(widths[n]); keys.append(t_hold)
        for k in range(n, -1, -1):
            vals.append(widths[k]); keys.append(t_hold + (t_del - t_hold) * (n - k) / n)
        vals.append(0); keys.append(period)
        kt = ";".join(f"{k / period:.4f}" for k in keys)
        vv = ";".join(f"{v:.1f}" for v in vals)
        s.defs.append(f'<clipPath id="tw{i}"><rect x="{px}" y="290" height="44" width="0">'
                      f'<animate attributeName="width" values="{vv}" keyTimes="{kt}" calcMode="discrete" dur="{period}s" begin="{i * slot}s" repeatCount="indefinite"/></rect></clipPath>')
        s.add(f'<g clip-path="url(#tw{i})">')
        s.text(px, 322, ph, "G6", 32, ORANGE)
        s.add('</g>')
        cx = ";".join(f"{px + v + 3:.1f}" for v in vals)
        s.add(f'<rect x="-20" y="296" width="3" height="34" fill="{ORANGE}" opacity="0">'
              f'<animate attributeName="x" values="{cx}" keyTimes="{kt}" calcMode="discrete" dur="{period}s" begin="{i * slot}s" repeatCount="indefinite"/>'
              f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;{t_del / period:.4f};{t_del / period + 0.001:.4f};1" calcMode="discrete" dur="{period}s" begin="{i * slot}s" repeatCount="indefinite"/></rect>')
    # intro
    for j, ln in enumerate(["7+ years designing and shipping websites, AI products",
                            "and Web3 platforms for startups and brands worldwide."]):
        s.text(56, 374 + j * 30, ln, "G4", 20, "#b9b3c9")
    # stats
    stats = [("7+", "YEARS"), ("200+", "PROJECTS"), ("150+", "HAPPY CLIENTS"), ("40+", "TEAMS")]
    for k, (n, lab) in enumerate(stats):
        x = 56 + k * 168
        s.add(f'<g class="up" style="animation-delay:{.5 + k * .12:.2f}s">')
        s.add(f'<rect x="{x}" y="446" width="152" height="80" rx="16" fill="#ffffff" fill-opacity="0.06" stroke="#ffffff" stroke-opacity="0.12"/>')
        s.text(x + 18, 488, n, "X7", 34, CREAM)
        s.text(x + 18, 512, lab, "M5", 11, "#b9b3c9", spacing=1.5)
        s.add('</g>')
    s.add('</g>')
    s.add(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="28" fill="none" stroke="#ffffff" stroke-opacity="0.10"/>')
    return s


# ---------------------------------------------------------------- themed pieces

def section(t, num, label, title, note):
    W, H = 1280, 116
    s = Svg(W, H)
    s.defs.append(f'<linearGradient id="ln" x1="0" x2="1"><stop offset="0" stop-color="{ORANGE}"/><stop offset="0.35" stop-color="{ORANGE}" stop-opacity="0.25"/><stop offset="1" stop-color="{ORANGE}" stop-opacity="0"/></linearGradient>')
    s.text(4, 34, f"{num} / {label}", "M5", 15, ORANGE, spacing=3)
    s.text(0, 86, title, "G8", 44, t["text"], spacing=-1)
    s.text(W - 4, 86, note, "G4", 18, t["muted"], anchor="end")
    s.add(f'<rect x="0" y="108" width="{W}" height="2" fill="url(#ln)"/>')
    return s


def card_frame(s, t, w, h, r=24):
    s.defs.append(f'<clipPath id="cf"><rect width="{w}" height="{h}" rx="{r}"/></clipPath>')
    s.add(f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="{r}" fill="{t["card"]}" stroke="{t["line"]}"/>')


def chip_row(s, t, x, y, items, size=13):
    for it in items:
        w = text_width(it, "mono", 500, size) + 22
        s.add(f'<rect x="{x}" y="{y}" width="{w}" height="28" rx="14" fill="{t["chip"]}"/>')
        s.text(x + 11, y + 19, it, "M5", size, t["chiptext"])
        x += w + 8
    return x


def product_card(t, name, img, tagline, chips, url_label, accent):
    W, H = 412, 560
    s = Svg(W, H)
    card_frame(s, t, W, H)
    uri, _ = img_uri(img, 618, 464)
    s.add(f'<g clip-path="url(#cf)"><image href="{uri}" x="0" y="0" width="{W}" height="309" preserveAspectRatio="xMidYMid slice"/></g>')
    s.add(f'<rect x="0" y="309" width="{W}" height="1" fill="{t["line"]}"/>')
    s.add(f'<rect x="28" y="336" width="8" height="30" rx="4" fill="{accent}"/>')
    s.text(48, 362, name, "X7", 32, t["text"], spacing=1)
    for j, ln in enumerate(wrap(tagline, "geist", 400, 17, W - 56)[:3]):
        s.text(28, 398 + j * 25, ln, "G4", 17, t["muted"])
    chip_row(s, t, 28, 470, chips)
    s.text(28, 532, url_label, "G6", 17, ORANGE)
    s.add(f'<path d="M{W - 50} 520 l12 0 m0 0 l0 12 m0 -12 l-14 14" stroke="{ORANGE}" stroke-width="2.4" fill="none" stroke-linecap="round"/>')
    return s


def service_card(t, title, desc, icons, foot):
    W, H = 412, 236
    s = Svg(W, H)
    card_frame(s, t, W, H, 22)
    x = 26
    for ic in icons:
        s.add(f'<rect x="{x}" y="26" width="52" height="52" rx="14" fill="{t["tile"]}" stroke="{t["line"]}"/>')
        if ic == "pen":
            s.add(raw_icon(PEN, x + 14, 40, 24, ORANGE))
        elif ic == "coin":
            s.add(f'<circle cx="{x + 26}" cy="52" r="12" fill="none" stroke="{ORANGE}" stroke-width="2.4"/>')
            s.text(x + 26, 58, "$", "G8", 16, ORANGE, anchor="middle")
        else:
            s.add(icon(ic, x + 14, 40, 24, ORANGE))
        x += 62
    s.text(26, 116, title, "G6", 22, t["text"])
    for j, ln in enumerate(wrap(desc, "geist", 400, 16, W - 52)[:2]):
        s.text(26, 146 + j * 23, ln, "G4", 16, t["muted"])
    s.add(f'<rect x="26" y="188" width="{W - 52}" height="1" fill="{t["line"]}"/>')
    s.text(26, 216, foot, "M5", 13, ORANGE, spacing=1)
    s.add(f'<path d="M{W - 42} 202 l9 0 m0 0 l0 9 m0 -9 l-11 11" stroke="{ORANGE}" stroke-width="2" fill="none" stroke-linecap="round"/>')
    return s


def work_card(t, title, kind, img):
    W, H = 412, 336
    s = Svg(W, H)
    card_frame(s, t, W, H, 22)
    uri, _ = img_uri(img, 618, 400, crop=None)
    s.add(f'<g clip-path="url(#cf)"><image href="{uri}" x="0" y="0" width="{W}" height="266" preserveAspectRatio="xMidYMin slice"/></g>')
    s.add(f'<rect x="0" y="266" width="{W}" height="1" fill="{t["line"]}"/>')
    s.text(24, 306, title, "G6", 20, t["text"])
    s.text(W - 24, 306, kind, "M5", 12, t["muted"], anchor="end", spacing=1)
    return s


def pill(t, label, ic):
    w = int(text_width(label, "geist", 600, 16) + 66)
    s = Svg(w, 46)
    s.add(f'<rect x="0.5" y="0.5" width="{w - 1}" height="45" rx="23" fill="{t["card"]}" stroke="{t["line"]}"/>')
    if ic == "globe":
        s.add(raw_icon(GLOBE, 18, 13, 20, ORANGE))
    elif ic == "contra":
        s.add(f'<circle cx="28" cy="23" r="10" fill="{ORANGE}"/>')
        s.text(28, 28, "C", "G8", 13, "#ffffff", anchor="middle")
    else:
        s.add(icon(ic, 18, 13, 20, ORANGE))
    s.text(46, 29, label, "G6", 16, t["text"])
    return s


def now_strip(t):
    W, H = 1280, 76
    s = Svg(W, H)
    s.css.append('.pulse{animation:pulse 2s ease-out infinite;transform-origin:center;transform-box:fill-box}'
                 '@keyframes pulse{0%{opacity:.8;transform:scale(1)}100%{opacity:0;transform:scale(2.6)}}')
    s.add(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="38" fill="{t["card"]}" stroke="{t["line"]}"/>')
    s.add(f'<rect x="14" y="14" width="96" height="48" rx="24" fill="{ORANGE}"/>')
    s.text(62, 44, "NOW", "M5", 16, "#ffffff", anchor="middle", spacing=3)
    s.add(f'<circle cx="140" cy="38" r="5" fill="#25d366"/><circle class="pulse" cx="140" cy="38" r="5" fill="#25d366"/>')
    msg = "Shipping SYVO, a personal AI agent, in private pilot. Open for Framer, AI and Web3 projects."
    s.text(160, 44, msg, "G5", 18, t["text"])
    return s


def stack(t):
    W, H = 1280, 150
    names = [("figma", "Figma"), ("framer", "Framer"), ("react", "React"), ("nextdotjs", "Next.js"),
             ("typescript", "TypeScript"), ("tailwindcss", "Tailwind"), ("flutter", "Flutter"),
             ("nodedotjs", "Node.js"), ("python", "Python"), ("supabase", "Supabase"), ("firebase", "Firebase"),
             ("openai", "OpenAI"), ("claude", "Claude"), ("n8n", "n8n"), ("solidity", "Solidity"),
             ("ethereum", "Ethereum"), ("solana", "Solana"), ("wordpress", "WordPress"), ("shopify", "Shopify")]
    step = 132
    span = step * len(names)
    s = Svg(W, H)
    s.defs.append(f'<clipPath id="sc"><rect width="{W}" height="{H}" rx="24"/></clipPath>'
                  f'<linearGradient id="edge" x1="0" x2="1"><stop offset="0" stop-color="{t["card"]}"/><stop offset="0.07" stop-color="{t["card"]}" stop-opacity="0"/>'
                  f'<stop offset="0.93" stop-color="{t["card"]}" stop-opacity="0"/><stop offset="1" stop-color="{t["card"]}"/></linearGradient>')
    s.css.append(f'.mq{{animation:mq 38s linear infinite}}@keyframes mq{{from{{transform:translateX(0)}}to{{transform:translateX(-{span}px)}}}}')
    s.add(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="24" fill="{t["card"]}" stroke="{t["line"]}"/>')
    s.add('<g clip-path="url(#sc)"><g class="mq">')
    for rep in range(2):
        for k, (ic, lab) in enumerate(names):
            x = 30 + rep * span + k * step
            s.add(f'<rect x="{x}" y="26" width="64" height="64" rx="18" fill="{t["tile"]}" stroke="{t["line"]}"/>')
            s.add(icon(ic, x + 18, 44, 28, t["text"]))
            s.text(x + 32, 120, lab, "M5", 13, t["muted"], anchor="middle")
    s.add('</g></g>')
    s.add(f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="24" fill="url(#edge)"/>')
    return s


def cta():
    W, H = 1280, 300
    s = Svg(W, H)
    s.defs.append(f'''<clipPath id="cc"><rect width="{W}" height="{H}" rx="28"/></clipPath>
<radialGradient id="ca" cx="0.15" cy="0" r="0.8"><stop offset="0" stop-color="#3b22b8" stop-opacity="0.9"/><stop offset="1" stop-color="{INK}" stop-opacity="0"/></radialGradient>
<radialGradient id="cb" cx="0.85" cy="1.1" r="0.7"><stop offset="0" stop-color="{ORANGE}" stop-opacity="0.8"/><stop offset="1" stop-color="{INK}" stop-opacity="0"/></radialGradient>
<pattern id="cg" width="48" height="48" patternUnits="userSpaceOnUse"><path d="M48 0H0V48" fill="none" stroke="#fff" stroke-opacity="0.045"/></pattern>
<linearGradient id="cn" x1="0" x2="1"><stop offset="0" stop-color="{ORANGE}"/><stop offset="0.55" stop-color="{PINK}"/><stop offset="1" stop-color="{VIOLET}"/></linearGradient>''')
    s.css.append('.sh{animation:sh 3.2s ease-in-out infinite}@keyframes sh{0%,100%{transform:translateX(0)}50%{transform:translateX(6px)}}')
    s.add(f'<g clip-path="url(#cc)"><rect width="{W}" height="{H}" fill="{INK}"/><rect width="{W}" height="{H}" fill="url(#cg)"/>'
          f'<rect width="{W}" height="{H}" fill="url(#ca)"/><rect width="{W}" height="{H}" fill="url(#cb)"/></g>')
    s.text(64, 92, "HAVE A PROJECT IN MIND?", "M5", 16, ORANGE, spacing=3)
    s.text(60, 168, "Let's build it", "G8", 72, CREAM, spacing=-2)
    s.text(60 + text_width("Let's build it ", "geist", 800, 72, -2), 168, "together.", "G8", 72, "url(#cn)", spacing=-2)
    s.text(64, 222, "Websites, AI agents, full apps and Web3 products, from first sketch to launch.", "G4", 20, "#c9c3d8")
    bx, by = 960, 196
    s.add(f'<g class="sh"><rect x="{bx}" y="{by}" width="256" height="60" rx="30" fill="{ORANGE}"/>')
    s.text(bx + 34, by + 38, "Get a quote", "G6", 21, "#ffffff")
    s.add(f'<path d="M{bx + 206} {by + 24} l12 0 m0 0 l0 12 m0 -12 l-14 14" stroke="#fff" stroke-width="2.6" fill="none" stroke-linecap="round"/></g>')
    s.text(1216, 92, "victorstudios.org", "M5", 15, "#c9c3d8", anchor="end")
    s.add(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="28" fill="none" stroke="#fff" stroke-opacity="0.1"/>')
    return s


# ---------------------------------------------------------------- content

LK = f"{DOCS}/launch-kit"
BH = f"{CP}/behance"

PRODUCTS = [
    ("xoxi", "XOXI", f"{CP}/products/xoxi-cover.jpg",
     "Your CV becomes a verified portfolio you can apply with. AI match scores for the teams hiring.",
     ["Web", "iOS", "Android", "AI"], "Visit xoxi.me", "#3b82f6"),
    ("syvo", "SYVO", f"{CP}/products/syvo-cover.jpg",
     "A personal AI agent. Ask in plain words and it finds, books or sells for you, then waits for your OK.",
     ["AI agent", "Flutter", "Web"], "Visit syvo.si", "#4ade80"),
    ("lovii", "LOVII", f"{CP}/products/lovii-cover.jpg",
     "A private journal for couples. One short note a day, drawn by AI as an illustrated card.",
     ["iOS", "Android", "AI art"], "Visit lovii.app", PINK),
]

SERVICES = [
    ("framer", "Framer websites", "Responsive sites with real scroll motion, CMS and SEO, from Figma or from scratch.", ["framer"]),
    ("agents", "AI agents & automations", "Chatbots, n8n and Make workflows and custom agents that do real work.", ["n8n", "openai"]),
    ("aiapps", "Full AI web & mobile apps", "Website, web app and iOS + Android apps, designed and built end to end.", ["flutter", "react"]),
    ("uiux", "UI/UX design", "Websites, dashboards and mobile apps in Figma with clickable prototypes.", ["figma"]),
    ("wpshop", "WordPress & Shopify", "Business sites and online stores that are easy to run after launch.", ["wordpress", "shopify"]),
    ("nftweb", "NFT & Web3 websites", "Marketplaces, mint pages and landing pages that make wallets feel simple.", ["ethereum"]),
    ("dapp", "Smart contracts & dApps", "NFT minting dApps and contracts on Ethereum, Polygon and Solana.", ["solidity", "solana"]),
    ("memecoin", "Meme coin websites", "Loud, fun coin sites with tokenomics, presale pages and buy flows.", ["coin", "solana"]),
    ("brand", "Logo & brand identity", "Minimal logos and brand kits for startups, products and Web3 projects.", ["pen"]),
]

WORK = [
    ("medelz", "Medelz", "MUSIC PLATFORM"), ("smartforum", "Smart Forum", "IT SERVICES"),
    ("satholler", "SatHoller", "NFT AUCTIONS"), ("metaadsfirm", "MetaAdsFirm", "WEB3 AGENCY"),
    ("blackmomento", "The Black Momento", "E-COMMERCE"), ("blckbuster", "Blckbuster", "WEB3 MARKETPLACE"),
]

PILLS = [("site", "Website", "globe"), ("contra", "Contra", "contra"), ("fiverr", "Fiverr", "fiverr"),
         ("upwork", "Upwork", "upwork"), ("behance", "Behance", "behance"), ("dribbble", "Dribbble", "dribbble"),
         ("linkedin", "LinkedIn", "linkedin"), ("framer", "Framer", "framer")]


def main():
    sizes = {}
    sizes["hero.svg"] = save(hero(), "hero.svg")
    sizes["cta.svg"] = save(cta(), "cta.svg")
    for name, t in THEMES.items():
        sizes[f"{name}/now"] = save(now_strip(t), name, "now.svg")
        for key, label, title, note in [("01", "PRODUCTS", "Products I've built", "Designed, built and shipped in-house"),
                                        ("02", "SERVICES", "What I can do for you", "Every card opens the matching gig"),
                                        ("03", "SELECTED WORK", "Selected client work", "Full case studies on Behance"),
                                        ("04", "STACK", "Tools I ship with", "Design, code, AI and Web3"),
                                        ("05", "ACTIVITY", "Building in public", "Updated daily by GitHub Actions")]:
            sizes[f"{name}/s{key}"] = save(section(t, key, label, title, note), name, f"s{key}.svg")
        for slug, nm, img, tag, chips, url, acc in PRODUCTS:
            sizes[f"{name}/p-{slug}"] = save(product_card(t, nm, img, tag, chips, url, acc), name, f"p-{slug}.svg")
        for slug, title, desc, icons in SERVICES:
            sizes[f"{name}/sv-{slug}"] = save(service_card(t, title, desc, icons, "VIEW ON FIVERR"), name, f"sv-{slug}.svg")
        for slug, title, kind in WORK:
            sizes[f"{name}/w-{slug}"] = save(work_card(t, title, kind, f"{BH}/{slug}/01.png"), name, f"w-{slug}.svg")
        for slug, label, ic in PILLS:
            sizes[f"{name}/l-{slug}"] = save(pill(t, label, ic), name, f"l-{slug}.svg")
        sizes[f"{name}/stack"] = save(stack(t), name, "stack.svg")
    total = sum(sizes.values())
    big = sorted(sizes.items(), key=lambda kv: -kv[1])[:6]
    print(f"{len(sizes)} files, {total / 1e6:.2f} MB total; largest: " + ", ".join(f"{k} {v // 1024}KB" for k, v in big))


if __name__ == "__main__":
    main()
