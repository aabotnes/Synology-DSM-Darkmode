#!/usr/bin/env python3
"""Generate dark overrides from the stylesheets installed on this NAS.

Reads every DSM and package stylesheet, finds each rule that sets a colour, and
writes the same selector again with a dark-mode colour: light backgrounds become
dark, dark text becomes light, light borders become dark. Images, sprites and
layout are never touched, so icons, photos and wallpapers keep their look.

Each override is prefixed with "html " so it outranks the original rule even
when that rule uses !important, regardless of which file loads first.

Usage: gen_dark.py [--bundle TGZ] OUTPUT CSS_ROOT [CSS_ROOT ...]
Must stay compatible with the Python 3.8 that ships with DSM 7.
"""

import colorsys
import gzip
import os
import posixpath
import re
import sys
import tarfile

NAMED = {
    "white": (255, 255, 255), "black": (0, 0, 0), "silver": (192, 192, 192),
    "gray": (128, 128, 128), "grey": (128, 128, 128), "lightgray": (211, 211, 211),
    "lightgrey": (211, 211, 211), "gainsboro": (220, 220, 220), "whitesmoke": (245, 245, 245),
    "darkgray": (169, 169, 169), "darkgrey": (169, 169, 169), "dimgray": (105, 105, 105),
    "dimgrey": (105, 105, 105), "snow": (255, 250, 250), "ivory": (255, 255, 240),
    "aliceblue": (240, 248, 255), "ghostwhite": (248, 248, 255), "azure": (240, 255, 255),
}

COLOR_RE = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)|\b(?:" + "|".join(NAMED) + r")\b",
    re.I,
)

BG_PROPS = {"background-color", "background", "background-image"}
TEXT_PROPS = {"color", "-webkit-text-fill-color", "caret-color"}
BORDER_PROPS = {
    "border-color", "border", "border-top", "border-right", "border-bottom", "border-left",
    "border-top-color", "border-right-color", "border-bottom-color", "border-left-color",
    "outline-color",
}
SKIP_AT_RULES = ("@keyframes", "@-webkit-keyframes", "@font-face", "@page", "@import", "@charset")


def parse_color(tok):
    t = tok.strip().lower()
    if t in NAMED:
        r, g, b = NAMED[t]
        return r, g, b, 1.0
    if t.startswith("#"):
        h = t[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) not in (6, 8):
            return None
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a
    m = re.match(r"(rgba?|hsla?)\((.*)\)", t)
    if not m:
        return None
    parts = [p for p in re.split(r"[\s,/]+", m.group(2).strip()) if p]
    if len(parts) < 3 or any("var(" in p for p in parts):
        return None
    try:
        a = parts[3] if len(parts) > 3 else "1"
        a = float(a[:-1]) / 100 if a.endswith("%") else float(a)
        if m.group(1).startswith("rgb"):
            vals = [float(p[:-1]) * 2.55 if p.endswith("%") else float(p) for p in parts[:3]]
            return vals[0], vals[1], vals[2], a
        hue = float(parts[0].rstrip("deg")) / 360
        sat = float(parts[1].rstrip("%")) / 100
        lig = float(parts[2].rstrip("%")) / 100
        r, g, b = colorsys.hls_to_rgb(hue, lig, sat)
        return r * 255, g * 255, b * 255, a
    except ValueError:
        return None


def fmt(r, g, b, a):
    r, g, b = (max(0, min(255, int(round(v)))) for v in (r, g, b))
    if a >= 0.999:
        return "#%02x%02x%02x" % (r, g, b)
    return "rgba(%d, %d, %d, %.3g)" % (r, g, b, a)


def hls(c):
    return colorsys.rgb_to_hls(c[0] / 255, c[1] / 255, c[2] / 255)


def from_hls(h, l, s, a):
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return fmt(r * 255, g * 255, b * 255, a)


def dark_bg(c):
    h, l, s = hls(c)
    # See-through white is a hover or selection highlight; it works on dark too.
    if c[3] <= 0.5:
        return None
    # Saturated mid-tone fills (buttons, badges, progress bars) keep their colour.
    if l < 0.35 or (s > 0.35 and l < 0.65):
        return None
    new_l = 0.11 + (1 - l) * 0.3
    return from_hls(h, new_l, min(s, 0.25) * 0.6, c[3])


def light_text(c):
    h, l, s = hls(c)
    if l >= 0.6:
        return None
    if s < 0.3:
        return from_hls(h, 0.9 - l * 0.4, s * 0.5, c[3])
    return from_hls(h, max(l, 0.68), s, c[3])


def dark_border(c):
    h, l, s = hls(c)
    if l < 0.45 or (s > 0.35 and l < 0.65):
        return None
    return from_hls(h, 0.2 + (1 - l) * 0.25, min(s, 0.2) * 0.5, c[3])


def recolor(value, fn):
    """Map every colour in value through fn; colours fn leaves alone stay as they are."""

    def sub(m):
        c = parse_color(m.group(0))
        if c is None or c[3] == 0:
            return m.group(0)
        return fn(c) or m.group(0)

    return COLOR_RE.sub(sub, value)


URL_RE = re.compile(r"url\((?:\"[^\"]*\"|'[^']*'|[^)]*)\)", re.I)
GRADIENT_RE = re.compile(r"(?:repeating-)?(?:linear|radial|conic)-gradient\((?:[^()]|\([^()]*\))*\)", re.I)


def first_color(value):
    for m in COLOR_RE.finditer(value):
        if parse_color(m.group(0)) is not None:
            return m.group(0)
    return None


KEYWORD_RE = re.compile(r"^(transparent|inherit|initial|unset|currentcolor)$", re.I)


def color_value(value, fn):
    """Dark value for a property that holds a single colour, or None if it holds none."""
    if KEYWORD_RE.match(value) or value.lower().startswith("var("):
        return value
    if first_color(value):
        return recolor(value, fn)
    return None


def convert_decl(prop, value, base=None):
    """Map one declaration to dark-mode declarations (list of (prop, value)).

    Colours that are already fine are emitted unchanged on purpose: every
    override is boosted, so leaving one out would let a boosted, less specific
    rule beat it (a blue button turning grey because .btn was boosted and
    .btn-blue wasn't).
    """
    prop = prop.strip().lower()
    value = re.sub(r"!\s*important", "", value, flags=re.I).strip()
    if prop.startswith("--"):
        if not first_color(value) or "url(" in value or "var(" in value:
            return []
        if re.search(r"bg|background|fill|surface|panel|mask", prop):
            fn = dark_bg
        elif re.search(r"border|line|divider|outline|stroke", prop):
            fn = dark_border
        elif re.search(r"color|text|font|fg|title|label", prop):
            fn = light_text
        else:
            return []
        return [(prop, recolor(value, fn))]
    if prop in TEXT_PROPS:
        new = color_value(value, light_text)
        return [(prop, new)] if new else []
    if prop == "background-color":
        new = color_value(value, dark_bg)
        return [(prop, new)] if new else []
    if prop == "background":
        # Only the colour. Re-emitting images or gradients from a boosted rule
        # replaces icons and sprites that more specific rules or inline styles
        # set, which breaks app and package icons.
        tail = GRADIENT_RE.sub("", URL_RE.sub("", value))
        col = first_color(tail)
        if col and "var(" not in value:
            return [("background-color", recolor(col, dark_bg))]
        if re.match(r"^(none|transparent)$", tail.strip(), re.I):
            return [("background-color", "transparent")]
        return []
    if prop in BORDER_PROPS:
        target = "border-color" if prop == "border" else prop if prop.endswith("-color") else prop + "-color"
        if prop.endswith("-color"):
            new = color_value(value, dark_border)
        else:
            col = first_color(value)
            new = recolor(col, dark_border) if col else None
        return [(target, new)] if new else []
    return []


def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def find_block_end(css, start):
    """Index of the '}' matching the '{' at css[start-1]."""
    depth = 1
    i = start
    n = len(css)
    while i < n:
        ch = css[i]
        if ch in "\"'":
            j = css.find(ch, i + 1)
            i = n if j < 0 else j + 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n


def split_decls(body):
    decls = []
    for part in re.split(r";(?![^(]*\))", body):
        if ":" in part:
            k, v = part.split(":", 1)
            decls.append((k, v))
    return decls


def prefix_selector(sel):
    out = []
    for s in sel.split(","):
        s = s.strip()
        if not s:
            continue
        out.append(s if s.lower().startswith(("html", ":root")) else "html " + s)
    return ", ".join(out)


def convert(css, out, base=None):
    i = 0
    n = len(css)
    while i < n:
        brace = css.find("{", i)
        if brace < 0:
            break
        head = css[i:brace].strip()
        semi = head.rfind(";")
        if semi >= 0 and head[:semi].lstrip().startswith("@"):
            head = head[semi + 1:].strip()
        end = find_block_end(css, brace + 1)
        body = css[brace + 1:end]
        i = end + 1
        low = head.lower()
        if low.startswith(SKIP_AT_RULES):
            continue
        if low.startswith(("@media", "@supports", "@layer", "@document")):
            inner = []
            convert(body, inner, base)
            if inner:
                out.append(head + " {\n" + "".join(inner) + "}\n")
            continue
        if low.startswith("@") or not head:
            continue
        decls = []
        for k, v in split_decls(body):
            decls.extend(convert_decl(k, v, base))
        if not decls:
            continue
        sel = prefix_selector(head)
        if not sel:
            continue
        lines = "".join("  %s: %s !important;\n" % (k, v) for k, v in decls)
        out.append(sel + " {\n" + lines + "}\n")


def css_files(roots):
    """Yield stylesheet paths under roots, following symlinks without looping."""
    visited = set()
    for root in roots:
        if os.path.isfile(root):
            yield root
            continue
        for d, dirs, files in os.walk(root, followlinks=True):
            real = os.path.realpath(d)
            if real in visited:
                dirs[:] = []
                continue
            visited.add(real)
            dirs[:] = sorted(x for x in dirs if x not in ("node_modules", ".git", "@eaDir", "DarkMode"))
            names = set(files)
            for f in sorted(files):
                if ".darkmode." in f:
                    continue
                # DSM ships some stylesheets only pre-compressed.
                if f.endswith(".css") or (f.endswith(".css.gz") and f[:-3] not in names):
                    yield os.path.join(d, f)


def read_css(path):
    if path.endswith(".gz"):
        with gzip.open(path, "rb") as fh:
            return fh.read().decode("utf-8", "replace")
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


WEB_ROOT = "/usr/syno/synoman"


def web_dir(path):
    """URL folder a stylesheet is served from, or None if it isn't served by DSM."""
    d = posixpath.dirname(path)
    if d == WEB_ROOT or d.startswith(WEB_ROOT + "/"):
        return d[len(WEB_ROOT):] or "/"
    m = re.match(r"^/var/packages/([^/]+)/target/ui(/.*)?$", d)
    if m:
        return "/webman/3rdparty/" + m.group(1) + (m.group(2) or "")
    return None


def main(argv):
    bundle = None
    if len(argv) > 2 and argv[1] == "--bundle":
        bundle, argv = argv[2], argv[:1] + argv[3:]
    if len(argv) < 3:
        print("usage: gen_dark.py [--bundle TGZ] OUTPUT CSS_ROOT [CSS_ROOT ...]", file=sys.stderr)
        return 2
    output, roots = argv[1], argv[2:]
    used = []
    seen = set()
    rules = []
    count = 0
    failed = 0
    per_root = {}
    for path in css_files(roots):
        real = os.path.realpath(path)
        if real in seen or "/DarkMode/" in real:
            continue
        seen.add(real)
        try:
            css = strip_comments(read_css(path))
            before = len(rules)
            convert(css, rules, web_dir(path))
        except Exception as exc:  # one odd file must not stop the whole theme
            failed += 1
            print("skipped %s: %s" % (path, exc), file=sys.stderr)
            continue
        count += 1
        used.append(path)
        top = "/".join(path.split("/")[:6])
        per_root[top] = per_root.get(top, 0) + len(rules) - before
    unique = list(dict.fromkeys(rules))
    tmp = output + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("/* Generated by DSM Dark Mode from %d stylesheets. */\n" % count)
        fh.writelines(unique)
    os.replace(tmp, output)
    if bundle:
        # A copy of every stylesheet read, for troubleshooting from the Dark Mode app.
        with tarfile.open(bundle + ".tmp", "w:gz") as tar:
            for path in used:
                tar.add(path, arcname=path.lstrip("/"))
        os.replace(bundle + ".tmp", bundle)
    print("generated %d rules from %d stylesheets (%d skipped)" % (len(unique), count, failed))
    for top, n in sorted(per_root.items(), key=lambda kv: -kv[1])[:15]:
        print("  %6d  %s" % (n, top))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
