"""Synthetic rice sample generator with ground truth, for testing the rice.ag scanner."""
import json, math, random, sys
import numpy as np
from PIL import Image, ImageFilter

def make(seed=1, W=1800, H=1350, pxmm=12.0, n_whole=140, broken_ratios=None, n_chips=6,
         mode='dark', coin_mm=26.0, contaminants=True, touching_pairs=3, chalky_frac=0.15,
         out='sample.png', lighting_grad=0.25, noise=4.0, blur=0.8, length_mm=7.0, width_mm=2.1):
    rng = random.Random(seed); nrng = np.random.default_rng(seed)
    SS = 2  # supersample
    Wi, Hi = W * SS, H * SS
    if mode == 'dark':
        base = np.full((Hi, Wi, 3), (28, 26, 30), np.float32)
    else:
        base = np.full((Hi, Wi, 3), (238, 236, 232), np.float32)
    occ = []  # (x, y, r) in final px
    truth = []

    def place(r):
        for _ in range(4000):
            x = rng.uniform(r + 12, W - r - 12); y = rng.uniform(r + 12, H - r - 12)
            if all((x - a) ** 2 + (y - b) ** 2 > (r + c + 6) ** 2 for a, b, c in occ):
                occ.append((x, y, r)); return x, y
        return None

    def draw_kernel(x, y, L, Wd, ang, color, chalk=0.0, broken_keep=1.0, shape_p=2.4, kind='rice', rough=0.0):
        # L, Wd in final px; draw into base at supersampled resolution
        a = L / 2 * SS; b = Wd / 2 * SS
        R = int(max(a, b) + 4)
        cx, cy = int(x * SS), int(y * SS)
        ys, xs = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
        c, s = math.cos(ang), math.sin(ang)
        u = xs * c + ys * s; v = -xs * s + ys * c
        # broken: keep part of full kernel of length a_full, cut flat
        a_full = a / broken_keep
        u2 = u + (a_full - a)  # shift so remaining piece is centred
        m = (np.abs(u2 / a_full) ** shape_p + np.abs(v / b) ** 2.0) <= 1.0
        if broken_keep < 1.0:
            cut = a_full - 2 * a  # keep u2 >= cut
            jag = rough * SS * np.sin(v * 0.9)
            m &= u2 >= cut + jag
        if kind == 'stone':
            rr = np.sqrt(xs ** 2 + ys ** 2); th = np.arctan2(ys, xs)
            m = rr <= b * (1 + 0.18 * np.sin(3 * th + x) + 0.1 * np.sin(5 * th))
        y0, y1, x0, x1 = cy - R, cy + R + 1, cx - R, cx + R + 1
        if y0 < 0 or x0 < 0 or y1 > Hi or x1 > Wi:
            return
        patch = base[y0:y1, x0:x1]
        col = np.array(color, np.float32)
        if mode == 'dark':
            # translucent grain: body greyish, chalky belly bright
            shade = 0.85 + 0.15 * (1 - (v / b) ** 2).clip(0, 1)
            img = col[None, None, :] * shade[..., None]
            if chalk > 0:
                cm = (np.abs((u - a * 0.1) / (a * 0.9)) ** 2 + np.abs((v - b * 0.2) / (b * 0.8)) ** 2) <= chalk * 1.3
                img = np.where(cm[..., None], np.minimum(255, img * 1.12 + 12), img)
        else:
            # backlit: translucent passes light (bright-ish), chalky blocks (dark)
            img = np.broadcast_to(col[None, None, :], m.shape + (3,)).copy()
            if kind == 'rice' and chalk > 0:
                # chalky region occupies approx `chalk` of the area: band along u
                cutoff = np.quantile(u[m], chalk) if m.any() else 0
                cm = u <= cutoff
                img = np.where(cm[..., None], img * 0.38, img)
        patch[m] = img[m]

    rice_col = (212, 210, 200) if mode == 'dark' else (175, 172, 165)
    Lp, Wp = length_mm * pxmm, width_mm * pxmm

    # coin
    if coin_mm:
        r = coin_mm * pxmm / 2
        p = place(r + 2)
        if p:
            x, y = p
            yy, xx = np.mgrid[0:Hi, 0:Wi]
            m = (xx - x * SS) ** 2 + (yy - y * SS) ** 2 <= (r * SS) ** 2
            base[m] = (190, 185, 170) if mode == 'dark' else (60, 58, 55)
            truth.append(dict(kind='coin', x=x, y=y, d_mm=coin_mm))

    def add(kind, keep=1.0, color=None, chalk=0.0, Lmul=1.0, Wmul=1.0, **kw):
        L = Lp * keep * Lmul * rng.uniform(0.96, 1.04); Wd = Wp * Wmul * rng.uniform(0.95, 1.05)
        p = place(max(L, Wd) / 2 + 2)
        if not p: return
        x, y = p; ang = rng.uniform(0, math.pi)
        draw_kernel(x, y, L, Wd, ang, color or rice_col, chalk=chalk, broken_keep=keep, kind=kw.get('shape', 'rice'), rough=kw.get('rough', 1.5))
        truth.append(dict(kind=kind, x=x, y=y, L=L, W=Wd, keep=keep, chalk=chalk))

    for i in range(n_whole):
        ch = rng.uniform(0.8, 0.95) if (mode != 'dark' and rng.random() < chalky_frac) else (rng.uniform(0.0, 0.1) if mode != 'dark' else rng.uniform(0, 0.4))
        add('whole', 1.0, chalk=ch)
    for k in (broken_ratios or []):
        add('broken', k, chalk=0.0 if mode != 'dark' else 0.2)
    for i in range(n_chips):
        L = rng.uniform(1.2, 1.9) * pxmm; Wd = rng.uniform(0.8, 1.2) * pxmm
        p = place(L / 2 + 2)
        if p:
            draw_kernel(p[0], p[1], L, Wd, rng.uniform(0, 3.14), rice_col)
            truth.append(dict(kind='chip', x=p[0], y=p[1], L=L, W=Wd))
    if contaminants:
        # dark stone
        p = place(Wp * 1.3)
        if p:
            draw_kernel(p[0], p[1], Wp * 2.2, Wp * 2.2, 0, (95, 85, 75) if mode == 'dark' else (18, 17, 16), kind='stone')
            truth.append(dict(kind='stone_dark', x=p[0], y=p[1]))
        # rice-coloured stone (hard case)
        p = place(Wp * 1.3)
        if p:
            draw_kernel(p[0], p[1], Wp * 2.2, Wp * 2.2, 0, rice_col, kind='stone')
            truth.append(dict(kind='stone_ricecolor', x=p[0], y=p[1]))
        # yellow kernel
        add('yellow', 1.0, color=(215, 185, 95) if mode == 'dark' else (170, 140, 60))
        # paddy (unhusked, golden-brown, bigger)
        add('paddy', 1.0, color=(190, 140, 70) if mode == 'dark' else (120, 80, 30), Lmul=1.3, Wmul=1.25)
        # husk / straw sliver
        add('husk', 1.0, color=(170, 130, 80) if mode == 'dark' else (110, 80, 40), Lmul=1.05, Wmul=0.35)
    # touching pairs (side-by-side)
    for i in range(touching_pairs):
        p = place(Lp / 2 + Wp + 4)
        if p:
            x, y = p; ang = rng.uniform(0, math.pi)
            dx, dy = -math.sin(ang) * Wp * 0.48, math.cos(ang) * Wp * 0.48
            draw_kernel(x - dx, y - dy, Lp, Wp, ang, rice_col)
            draw_kernel(x + dx, y + dy, Lp, Wp, ang, rice_col)
            truth.append(dict(kind='clump', x=x, y=y, n=2))

    # lighting gradient + noise
    yy, xx = np.mgrid[0:Hi, 0:Wi].astype(np.float32)
    grad = 1 - lighting_grad * (xx / Wi * 0.7 + yy / Hi * 0.3)
    img = base * grad[..., None]
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    if blur: im = im.filter(ImageFilter.GaussianBlur(blur))
    arr = np.asarray(im).astype(np.float32) + nrng.normal(0, noise, (H, W, 3))
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    im.save(out, quality=92) if out.endswith('.jpg') else im.save(out)
    json.dump(dict(pxmm=pxmm, length_mm=length_mm, width_mm=width_mm, mode=mode, truth=truth), open(out + '.json', 'w'))
    return truth

if __name__ == '__main__':
    pass
