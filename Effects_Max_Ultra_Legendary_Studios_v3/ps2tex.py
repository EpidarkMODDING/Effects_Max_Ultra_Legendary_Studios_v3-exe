# -*- coding: utf-8 -*-
"""Texturas de PS2 (PSMT8 / PSMT4) usadas nos DBT do BT3: decodificar, reduzir cores e recodificar."""
import struct


def _map8(w, h):
    """Índice no buffer (enviado como CT32) de cada pixel (x, y) de uma textura PSMT8."""
    m = [0] * (w * h)
    for y in range(h):
        for x in range(w):
            block = (y & ~0xF) * w + (x & ~0xF) * 2
            swap = (((y + 2) >> 2) & 1) * 4
            posy = (((y & ~3) >> 1) + (y & 1)) & 7
            col = posy * w * 2 + ((x + swap) & 7) * 4
            bn = ((y >> 1) & 1) + ((x >> 2) & 2)
            m[y * w + x] = block + col + bn
    return m


def _map4(w, h):
    """(índice do byte, nibble alto?) de cada pixel de uma textura PSMT4."""
    m = [None] * (w * h)
    pages_h = (w + 127) // 128
    pages_v = (h + 127) // 128
    for y in range(h):
        for x in range(w):
            page_n = (y // 128) * pages_h + (x // 128)
            p32y = (page_n // pages_v) * 32
            p32x = (page_n % pages_v) * 64
            page_loc = p32y * h * 2 + p32x * 4
            lx, ly = x & 0x7F, y & 0x7F
            block = ((lx & ~0x1F) >> 1) * h + (ly & ~0xF) * 2
            swap = (((y + 2) >> 2) & 1) * 4
            posy = (((y & ~3) >> 1) + (y & 1)) & 7
            col = posy * h * 2 + ((x + swap) & 7) * 4
            bn = (x >> 3) & 3
            m[y * w + x] = (page_loc + block + col + bn, (y >> 1) & 1)
    return m


def _clut256_order():
    """Ordem CSM1 da paleta de 256 cores (troca dos blocos 8-15 com 16-23)."""
    o = list(range(256))
    for i in range(256):
        if (i & 0x18) == 8:
            o[i], o[i + 8] = i + 8, i
    return o


def decode(pix, clut, w, h, psm):
    """Devolve (índices, paleta RGBA com alfa PS2 0-128) em ordem linear."""
    if psm == 0x13:
        mp = _map8(w, h)
        idx = [pix[mp[i]] for i in range(w * h)]
        order = _clut256_order()
        pal = [tuple(clut[order[i] * 4: order[i] * 4 + 4]) for i in range(256)]
    else:
        mp = _map4(w, h)
        idx = []
        for i in range(w * h):
            b, hi = mp[i]
            v = pix[b] if b < len(pix) else 0
            idx.append((v >> 4) & 0xF if hi else v & 0xF)
        pal = [tuple(clut[i * 4: i * 4 + 4]) for i in range(16)]
    return idx, pal


def encode4(idx, pal16, w, h):
    """Índices lineares (0-15) + paleta de 16 cores → (pixels PSMT4 embaralhados, CLUT 64 bytes)."""
    mp = _map4(w, h)
    buf = bytearray(w * h // 2)
    for i, v in enumerate(idx):
        b, hi = mp[i]
        if hi:
            buf[b] = (buf[b] & 0x0F) | ((v & 0xF) << 4)
        else:
            buf[b] = (buf[b] & 0xF0) | (v & 0xF)
    clut = bytearray()
    for k in range(16):
        c = pal16[k] if k < len(pal16) else (0, 0, 0, 0)
        clut += bytes(c)
    return bytes(buf), bytes(clut)


def quantize16(idx, pal):
    return quantizeN(idx, pal, 16)


def quantizeN(idx, pal, N):
    """Reduz uma imagem indexada para N cores. K-means ponderado sobre as cores da paleta,
    em espaço pré-multiplicado pelo alfa (evita manchas escuras em brilhos e degradês)."""
    from collections import Counter
    used = sorted(set(idx))
    if len(used) <= N:
        remap = {u: k for k, u in enumerate(used)}
        return [remap[i] for i in idx], [pal[u] for u in used]
    cnt = Counter(idx)

    def feat(c):
        a = min(c[3], 128) / 128.0
        return (c[0] * a, c[1] * a, c[2] * a, c[3] * 2.0)
    pts = [(feat(pal[i]), n, i) for i, n in cnt.items()]
    d2 = lambda p, q: sum((p[t] - q[t]) ** 2 for t in range(4))
    # inicialização: cor mais usada (normalmente o fundo) + transparente total, FIXAS (não se movem):
    # assim o fundo não ganha cor/alfa de outro grupo (era o 'quadrado' que aparecia em volta do brilho)
    first = max(pts, key=lambda t: t[1])[0]
    cent = [first]
    transp = [p[0] for p in pts if p[0][3] == 0]
    if transp and first[3] != 0:
        cent.append((0.0, 0.0, 0.0, 0.0))
    fixed = len(cent)
    mind = [min(d2(p[0], c) for c in cent) for p in pts]          # distância mínima incremental
    while len(cent) < N:
        k = max(range(len(pts)), key=lambda j: pts[j][1] ** 0.5 * mind[j])
        if mind[k] == 0:
            break
        c = pts[k][0]
        cent.append(c)
        mind = [min(mind[j], d2(pts[j][0], c)) for j in range(len(pts))]
    for _ in range(20 if N <= 32 else 10):
        acc = [[0.0] * 5 for _ in cent]
        for f, n, _i in pts:
            k = min(range(len(cent)), key=lambda j: d2(f, cent[j]))
            for t in range(4):
                acc[k][t] += f[t] * n
            acc[k][4] += n
        new = [cent[j] if j < fixed else (tuple(a[t] / a[4] for t in range(4)) if a[4] else cent[j])
               for j, a in enumerate(acc)]
        if new == cent:
            break
        cent = new
    near = {i: min(range(len(cent)), key=lambda j: d2(f, cent[j])) for f, n, i in pts}
    pal16 = []
    for c in cent:
        a = c[3] / 2.0
        k = 128.0 / a if a > 0.5 else 0.0
        pal16.append(tuple(int(max(0, min(255, round(v)))) for v in (c[0] * k, c[1] * k, c[2] * k)) + (int(round(max(0, min(128, a)))),))
    return [near[i] for i in idx], pal16


def encode8(idx, pal, w, h):
    """Índices lineares (0-255) + paleta → (pixels PSMT8 embaralhados, CLUT 1 KB em ordem CSM1)."""
    mp = _map8(w, h)
    buf = bytearray(w * h)
    for i, v in enumerate(idx):
        buf[mp[i]] = v & 0xFF
    order = _clut256_order()
    clut = bytearray(1024)
    for i in range(256):
        c = pal[i] if i < len(pal) else (0, 0, 0, 0)
        clut[order[i] * 4: order[i] * 4 + 4] = bytes(c)
    return bytes(buf), bytes(clut)


def visible(c):
    """Quanto a cor aparece quando o jogo SOMA a luz (brilho × alfa), de 0 a 255."""
    return max(c[0], c[1], c[2]) * min(c[3], 128) / 128.0


def transparency_broken(idx_a, pal_a, idx_b, pal_b):
    """Compara a imagem antes (a) e depois (b) da redução: True se partes que eram transparentes/invisíveis
       passaram a aparecer (ou o contrário) em mais de 2% dos pixels — o efeito viraria um 'quadrado'."""
    n = len(idx_a)
    if not n:
        return False
    bad = bg = 0
    lift = 0.0
    for i in range(0, n, 3):
        va = visible(pal_a[idx_a[i]])
        vb = visible(pal_b[idx_b[i]])
        if (va < 6 and vb > 20) or (va > 40 and vb < 6) or abs(va - vb) > 70:
            bad += 1
        if va < 3:
            bg += 1
            lift += vb
    m = n / 3.0
    if bad > 0.02 * m:
        return True
    # fundo que era invisível ganhou um 'véu' (aparece como um quadrado em volta do brilho)
    return bg > 0.15 * m and lift / bg > 3.0
