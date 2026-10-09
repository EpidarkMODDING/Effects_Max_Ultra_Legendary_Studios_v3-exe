# -*- coding: utf-8 -*-
"""
Prévia visual dos mini-efeitos com as TEXTURAS reais (usada na aba Tamanho e tempo e no Editor 3D).
Cada parte vira um 'sprite': a imagem do DBT tingida pela cor do shader/V00/saída de luz, no tamanho do momento.
É uma aproximação (o jogo soma a luz, aqui a imagem é sobreposta), mas mostra forma, tamanho, crescimento e trajeto.
"""
import base64, math
import tkinter as tk
from tkinter import ttk
from bt3eff_core import mini_sprite, v00_sheet, shape05_particles
from lang import tr, class_label, stage_label

MAX_PX = 360


def _png(rgba, w, h):
    import texview
    return texview.png_encode(rgba, w, h)


class SpriteCache:
    """Guarda as imagens já tingidas e escaladas (Tk só escala por inteiros: zoom/subsample)."""

    def __init__(self, master):
        self.master = master
        self.base = {}      # (id_mini, sessão, cor) -> PhotoImage nativa
        self.scaled = {}    # (chave base, a, b) -> PhotoImage
        self.src = {}       # (id_mini, sessão) -> (rgba, w, h) ou None

    def clear(self):
        self.base.clear()
        self.scaled.clear()
        self.src.clear()

    def _source(self, eff, mini, session, cell=None):
        k = (id(mini), session, cell)
        if k not in self.src:
            if cell is None:
                self.src[k] = mini_sprite(eff, mini, session)
            else:
                full = self._source(eff, mini, session, None)
                sh = v00_sheet(mini, session) if mini.type == 0x0E else None
                if full is None or not sh:
                    self.src[k] = full
                else:
                    pix, w, h = full
                    cols, rows, _ = sh
                    cw, ch = max(1, w // cols), max(1, h // rows)
                    cx, cy = (cell % cols) * cw, ((cell // cols) % rows) * ch
                    self.src[k] = ([pix[(cy + y) * w + cx + x] for y in range(ch) for x in range(cw)], cw, ch)
        return self.src[k]

    def get(self, eff, mini, session, rgba, px, cell=None):
        s = self._source(eff, mini, session, cell)
        if s is None:
            return None
        pix, w, h = s
        q = tuple(int(min(255, max(0, c)) // 16) for c in rgba[:4])
        kb = (id(mini), session, cell, q)
        img = self.base.get(kb)
        if img is None:
            cr, cg, cb, ca = [(c * 16 + 8) / 128.0 for c in q]     # PS2: 128 = 1,0
            out = []
            ka = min(1.0, ca)
            for r, g, b, a in pix:
                nr, ng, nb = min(255, int(r * cr)), min(255, int(g * cg)), min(255, int(b * cb))
                # o jogo SOMA a luz: parte escura da textura não cobre o fundo (alfa pelo brilho)
                lum = max(nr, ng, nb) / 255.0
                out.append((nr, ng, nb, int(min(255, a * 2) * min(1.0, lum * 1.6) * ka)))
            try:
                img = tk.PhotoImage(master=self.master, data=base64.b64encode(_png(out, w, h)).decode())
            except tk.TclError:
                return None
            self.base[kb] = img
        px = max(4, min(MAX_PX, int(px)))
        best = (9e9, 1, 1)
        for b in range(1, 9):
            a = max(1, int(round(px * b / float(w))))
            if a > 24:
                continue
            err = abs(w * a / float(b) - px)
            if err < best[0]:
                best = (err, a, b)
        _, a, b = best
        ks = (kb, a, b)
        im = self.scaled.get(ks)
        if im is None:
            im = img.zoom(a) if a > 1 else img
            if b > 1:
                im = im.subsample(b)
            self.scaled[ks] = im
            if len(self.scaled) > 600:
                self.scaled.clear()
        return im


def sprite_cell(track, t):
    """Quadro da folha de sprites (V00 com textura animada) no tempo t (quadros da prévia)."""
    if track.mini.type != 0x0E or track.session is None:
        return None
    sh = v00_sheet(track.mini, track.session)
    if not sh:
        return None
    cols, rows, step = sh
    return int(max(0.0, t) / step) % (cols * rows)


def expand(track, d, t):
    """Uma ou várias cópias (partículas) do mini-efeito: [(dx, dy, dz, escala, cell)].
       Classe 05 com várias partículas: as cópias flutuam em volta do ponto (aproximação do emissor da forma)."""
    cell = sprite_cell(track, t)
    m = track.mini
    n = shape05_particles(m) if m.type == 0x05 else 1
    if n <= 1:
        return [(0.0, 0.0, 0.0, 1.0, cell)]
    size = max(abs(v) for v in d["size"]) or 1.0
    out = []
    seed = (track.index * 7919) % 997
    for k in range(n):
        ph = (seed + k * 137) % 360 / 57.3
        w1, w2 = 0.045 + (k % 5) * 0.011, 0.07 + (k % 3) * 0.017
        ang = 2 * math.pi * k / n + ph
        rad = 0.35 * size * (0.6 + 0.4 * math.sin(ph * 3))
        dx = math.cos(ang) * rad + 0.18 * size * math.sin(w1 * t + ph)
        dy = math.sin(ang) * rad + 0.18 * size * math.cos(w2 * t + ph * 1.7)
        dz = 0.12 * size * math.sin(w2 * t * 0.7 + ph)
        sc = 0.45 + 0.25 * (1 + math.sin(w1 * 2.3 * t + ph)) / 2
        out.append((dx, dy, dz, sc, cell))
    return out


class GrowthPreview(ttk.Frame):
    """Prévia 2D animada do crescimento dos mini-efeitos marcados/selecionado."""
    W, H, GH = 440, 300, 110

    def __init__(self, master, app):
        super().__init__(master)
        self.app, self.lang = app, app.lang
        self.cache = SpriteCache(self)
        self.tracks, self.time, self.playing = [], 0.0, False
        self.view = tk.StringVar(value="front")
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text=tr("prev_view", self.lang)).pack(side="left")
        for k in ("front", "top", "side"):
            ttk.Radiobutton(bar, text=tr("prev_" + k, self.lang), value=k, variable=self.view,
                            command=self.redraw).pack(side="left", padx=2)
        self.cv = tk.Canvas(self, width=self.W, height=self.H, bg="#0f1115", highlightthickness=0)
        self.cv.pack(fill="x", pady=4)
        tl = ttk.Frame(self)
        tl.pack(fill="x")
        self.btn = ttk.Button(tl, text="▶", width=3, command=self.toggle)
        self.btn.pack(side="left")
        self.tvar = tk.DoubleVar(value=0.0)
        self.sc = ttk.Scale(tl, from_=0, to=60, variable=self.tvar, orient="horizontal",
                            command=lambda v: self._set_time(float(v)))
        self.sc.pack(side="left", fill="x", expand=True, padx=4)
        self.lbl = ttk.Label(tl, text="t = 0", width=9)
        self.lbl.pack(side="left")
        ttk.Label(self, text=tr("prev_graph", self.lang), foreground="#8a8f99").pack(anchor="w", pady=(4, 0))
        self.gr = tk.Canvas(self, width=self.W, height=self.GH, bg="#16181d", highlightthickness=0)
        self.gr.pack(fill="x")
        self.gr.bind("<Button-1>", lambda e: self._graph_click(e.x))
        self.gr.bind("<B1-Motion>", lambda e: self._graph_click(e.x))
        self.anim_t = 0.0
        self.after(120, self._anim)

    def _animated(self):
        return any((t.mini.type == 0x0E and t.session is not None and v00_sheet(t.mini, t.session))
                   or (t.mini.type == 0x05 and shape05_particles(t.mini) > 1) for t in self.tracks)

    def _anim(self):
        """Relógio das texturas animadas e das partículas: roda sempre, mesmo com a linha do tempo parada."""
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        self.anim_t += 2.0
        if not self.playing and self.tracks and self.winfo_ismapped() and self._animated():
            self.redraw()
        self.after(66, self._anim)

    def set_minis(self, minis):
        import editor3d
        self.cache.clear()
        eff = self.app.eff
        self.tracks = editor3d.build_tracks(eff, only=minis) if eff and minis else []
        self.tmax = max([30.0] + [t.frame_of(k) * 1.1 + 4 for t in self.tracks for k in range(t.nkeys())])
        self.sc.config(to=self.tmax)
        self.time = min(self.time, self.tmax)
        self._fit()
        self.redraw()

    def _axes(self):
        return {"front": (0, 1), "top": (0, 2), "side": (2, 1)}[self.view.get()]

    def _fit(self):
        ax, ay = self._axes()
        pts = []
        for t in self.tracks:
            for k in range(t.nkeys()):
                d = t.key(k)
                pts.append((d["pos"][ax], d["pos"][ay], max(abs(x) for x in d["size"])))
        if not pts:
            self.cx, self.cy, self.scale = 0, 0, 10
            return
        x0 = min(p[0] - p[2] / 2 for p in pts); x1 = max(p[0] + p[2] / 2 for p in pts)
        y0 = min(p[1] - p[2] / 2 for p in pts); y1 = max(p[1] + p[2] / 2 for p in pts)
        self.cx, self.cy = (x0 + x1) / 2, (y0 + y1) / 2
        span = max(x1 - x0, y1 - y0, 1.0)
        self.scale = 0.85 * min(self.W, self.H) / span

    def _set_time(self, t):
        self.time = t
        self.redraw()

    def toggle(self):
        self.playing = not self.playing
        self.btn.config(text="⏸" if self.playing else "▶")
        if self.playing:
            self._tick()

    def _tick(self):
        if not self.playing or not self.winfo_exists():
            return
        self.time += 1
        if self.time > getattr(self, "tmax", 60):
            self.time = 0
        self.tvar.set(self.time)
        self.redraw()
        self.after(40, self._tick)

    def redraw(self):
        cv = self.cv
        cv.delete("all")
        self._fit_keep = True
        W, H = int(cv.winfo_width() or self.W), self.H
        if W < 50:
            W = self.W
        if not self.tracks:
            cv.create_text(W / 2, H / 2, text=tr("prev_none", self.lang), fill="#8a8f99", width=W - 40)
            self.gr.delete("all")
            return
        ax, ay = self._axes()
        ox, oy = W / 2 - self.cx * self.scale, H / 2 + self.cy * self.scale
        cv.create_line(0, oy, W, oy, fill="#22262e")
        cv.create_line(ox, 0, ox, H, fill="#22262e")
        eff = self.app.eff
        self._imgs = []
        seen = set()
        for t in self.tracks:
            d = t.sample(self.time)
            if d is None:
                continue
            base_px = max(abs(v) for v in d["size"]) * self.scale
            for dx, dy, dz, sc, cell in expand(t, d, self.time + self.anim_t):
                off = (dx, dy, dz)
                x = ox + (d["pos"][ax] + off[ax]) * self.scale
                y = oy - (d["pos"][ay] + off[ay]) * self.scale
                px = base_px * sc
                im = self.cache.get(eff, t.mini, t.session, d["rgba"], px, cell) if px > 1 else None
                if im is not None:
                    cv.create_image(x, y, image=im)
                    self._imgs.append(im)
                else:
                    r = max(3, px / 2)
                    col = "#%02x%02x%02x" % tuple(int(min(255, max(0, c))) for c in d["rgba"][:3])
                    cv.create_oval(x - r, y - r, x + r, y + r, outline=col)
            x = ox + d["pos"][ax] * self.scale
            y = oy - d["pos"][ay] * self.scale
            px = base_px
            if t.index not in seen:
                seen.add(t.index)
                cv.create_text(x, y - max(8, px / 2) - 6, text="#%d" % t.index, fill="#c8ccd4", font=("Segoe UI", 8))
        self.lbl.config(text="t = %.0f" % self.time)
        self._graph()

    def _graph(self):
        g = self.gr
        g.delete("all")
        W = int(g.winfo_width() or self.W)
        if W < 50:
            W = self.W
        H = self.GH
        smax = max([0.01] + [max(abs(v) for v in t.key(k)["size"]) for t in self.tracks for k in range(t.nkeys())])
        palette = ("#e8c34a", "#4a90d9", "#5cb85c", "#d9534f", "#b07cd8", "#4ac6c6", "#f08a4b", "#c8ccd4")
        for i, t in enumerate(self.tracks[:16]):
            pts = []
            for s in range(0, 101):
                tt = self.tmax * s / 100.0
                d = t.sample(tt)
                if d is None:
                    continue
                pts += [6 + (W - 12) * s / 100.0, H - 8 - (H - 16) * max(abs(v) for v in d["size"]) / smax]
            if len(pts) >= 4:
                g.create_line(*pts, fill=palette[i % len(palette)], width=2)
                g.create_text(pts[-2] - 2, pts[-1] - 7, text="#%d" % t.index, fill=palette[i % len(palette)],
                              font=("Segoe UI", 7), anchor="e")
        x = 6 + (W - 12) * self.time / self.tmax
        g.create_line(x, 0, x, H, fill="#d9534f", width=2)

    def _graph_click(self, x):
        W = int(self.gr.winfo_width() or self.W)
        self.time = max(0.0, min(self.tmax, (x - 6) * self.tmax / max(1, W - 12)))
        self.tvar.set(self.time)
        self.redraw()
