"""Share images (Open Graph, 1200x630) for rice.ag pages, drawn at build time with today's numbers.

LINE and Facebook show this picture when someone shares a link, so the price is visible before the click.
Needs Pillow; if Pillow or the fonts are missing, build.py falls back to the one static image.
Fonts: IBM Plex Sans Thai (Thai + Latin merged), SIL Open Font License, in og/.
"""
from pathlib import Path

ROOT = Path(__file__).parent
BG, INK, MUTED, GREEN, GOLD, LINE = '#F6F1E7', '#1D261E', '#5A6558', '#2E5B3A', '#A87A30', '#E2D8C6'


def _font(size, bold=True):
    from PIL import ImageFont
    return ImageFont.truetype(str(ROOT / 'og' / f"plex-sans-thai-{700 if bold else 500}.ttf"), size)


def _fit(draw, text, max_w, start, bold=True, min_size=28):
    size = start
    while size > min_size:
        f = _font(size, bold)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return _font(min_size, bold)


def _wrap(draw, text, font, max_w, max_lines=2):
    """Greedy wrap on spaces (Thai titles here are short and spaced)."""
    words, lines, cur = text.split(' '), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while draw.textlength(lines[-1] + '…', font=font) > max_w and ' ' in lines[-1]:
            lines[-1] = lines[-1].rsplit(' ', 1)[0]
        lines[-1] += '…'
    return lines


def card(out, title, big=None, unit='', sub='', tag=''):
    """Draw one card and save it as PNG at `out`."""
    from PIL import Image, ImageDraw
    W, H, P = 1200, 630, 72
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    # brand row
    try:
        icon = Image.open(ROOT / 'src' / 'root' / 'favicon.png').convert('RGBA').resize((48, 48))
        im.paste(icon, (P, P - 8), icon)
    except Exception:
        d.ellipse((P, P - 6, P + 44, P + 38), fill=GREEN)
    d.text((P + 60, P - 8), 'rice.ag', font=_font(40), fill=INK)
    if tag:
        f = _font(28, False)
        tw = d.textlength(tag, font=f)
        d.rounded_rectangle((W - P - tw - 36, P - 8, W - P, P + 40), radius=24, fill='#E3ECDF')
        d.text((W - P - tw - 18, P - 3), tag, font=f, fill=GREEN)
    # title
    tf = _font(56)
    y = P + 90
    for line in _wrap(d, title, tf, W - 2 * P):
        d.text((P, y), line, font=tf, fill=INK)
        y += 74
    # big number
    if big:
        y += 18
        bf = _fit(d, big, W - 2 * P - (d.textlength(unit, font=_font(44, False)) + 20 if unit else 0), 150)
        d.text((P, y), big, font=bf, fill=GREEN)
        if unit:
            bw = d.textlength(big, font=bf)
            asc = bf.getbbox(big)[3]
            d.text((P + bw + 20, y + asc - 52), unit, font=_font(44, False), fill=MUTED)
    # footer
    d.line((P, H - 96, W - P, H - 96), fill=LINE, width=2)
    if sub:
        d.text((P, H - 76), sub, font=_fit(d, sub, W - 2 * P, 34, bold=False, min_size=22), fill=MUTED)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    im.save(out, optimize=True)


def available():
    try:
        import PIL  # noqa: F401
        return (ROOT / 'og' / 'plex-sans-thai-700.ttf').exists()
    except Exception:
        return False
