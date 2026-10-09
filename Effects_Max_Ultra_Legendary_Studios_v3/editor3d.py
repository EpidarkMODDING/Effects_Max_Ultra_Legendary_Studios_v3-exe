# -*- coding: utf-8 -*-
"""
Editor 3D (esquemático) dos mini-efeitos, com linha do tempo de quadros-chave.

• V00 (classe 0E): cada SESSÃO vira um objeto; cada ETAPA é um quadro-chave com posição, rotação,
  tamanho, cor e momento de aparição (5º byte da 4ª linha). A quantidade de etapas de cada sessão
  vem do byte +4 da entrada da sessão na parte inicial do V00 (confere em todos os V00 dos modelos).
• Demais classes: o mini-efeito é um objeto na posição X/Y/Z; os tamanhos 1→2→3 e os tempos
  formam os quadros-chave (tempo em unidades do jogo; a prévia usa 1 unidade = 30 quadros).

A vista é ESQUEMÁTICA: mostra posição, tamanho e cor (círculos), não o desenho real do efeito.
"""
import math, struct
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
from bt3eff_core import CLASS_NAMES, anim02_count, ANIM02_PART
from lang import tr, group_label, class_label, stage_label, dis_label, ori_label

FPS = 30.0


# ---------------------------------------------------------------- modelo de dados
class V00Track:
    """Uma sessão de um V00: lista de etapas (offsets no arquivo)."""
    def __init__(self, mini, index, session, steps):
        self.mini, self.index, self.session, self.steps = mini, index, session, steps
        self.kind = "v00"

    @property
    def buf(self):
        return self.mini.files[0]

    def key(self, k):
        o = self.steps[k]
        b = self.buf
        return {"pos": list(struct.unpack_from("<3f", b, o)), "rot": list(struct.unpack_from("<3f", b, o + 16)),
                "size": list(struct.unpack_from("<3f", b, o + 32)), "rgba": list(b[o + 48:o + 52]), "t": b[o + 52]}

    def set_key(self, k, d):
        o = self.steps[k]
        b = self.buf
        struct.pack_into("<3f", b, o, *d["pos"])
        struct.pack_into("<3f", b, o + 16, *d["rot"])
        struct.pack_into("<3f", b, o + 32, *d["size"])
        b[o + 48:o + 52] = bytes(max(0, min(255, int(round(v)))) for v in d["rgba"])
        b[o + 52] = max(0, min(255, int(round(d["t"]))))

    def nkeys(self):
        return len(self.steps)

    def frame_of(self, k):
        return float(self.key(k)["t"])

    def sample(self, t):
        keys = sorted((self.key(k) for k in range(self.nkeys())), key=lambda d: d["t"])
        if not keys:
            return None
        if t <= keys[0]["t"]:
            return keys[0]
        for a, b in zip(keys, keys[1:]):
            if a["t"] <= t <= b["t"]:
                u = 0 if b["t"] == a["t"] else (t - a["t"]) / float(b["t"] - a["t"])
                lerp = lambda x, y: [x[i] + (y[i] - x[i]) * u for i in range(len(x))]
                return {"pos": lerp(a["pos"], b["pos"]), "rot": lerp(a["rot"], b["rot"]),
                        "size": lerp(a["size"], b["size"]), "rgba": lerp(a["rgba"], b["rgba"]), "t": t}
        return keys[-1]

    def label(self, lang):
        return "#%d V00 · sessão %d (%d etapas) · %s" % (self.index, self.session + 1, self.nkeys(),
                                                        stage_label(self.mini.get("invoke"), lang, num=False))


class MiniTrack:
    """Mini-efeito comum: posição fixa + tamanhos 1→2→3 com tempos."""
    def __init__(self, mini, index):
        self.mini, self.index = mini, index
        self.kind = "mini"
        self.session = None

    def _sizes(self):
        m = self.mini
        s = [m.get("size1"), m.get("size2"), m.get("size3")]
        t1, t2 = m.get("time1"), m.get("time2")
        keys = [(0.0, s[0])]
        if s[1]:
            keys.append((t1 * FPS, s[1]))
            if s[2]:
                keys.append(((t1 + t2) * FPS, s[2]))
        return keys

    def nkeys(self):
        return len(self._sizes())

    def key(self, k):
        m = self.mini
        f, s = self._sizes()[k]
        c = m.read_rgba(m.color_rows()[0]) if m.color_rows() else [128, 128, 128, 128]
        if max(c[:3]) < 2:                       # 1ª linha preta: usa a linha mais forte
            rows = m.color_rows()
            if rows:
                c = max((m.read_rgba(r) for r in rows), key=lambda v: max(v[:3]))
        return {"pos": [m.get("pos_x"), m.get("pos_y"), m.get("pos_z")], "rot": [0, 0, 0],
                "size": [s, s, s], "rgba": [max(0, min(255, v)) for v in c], "t": f}

    def set_key(self, k, d):
        m = self.mini
        m.set("pos_x", d["pos"][0])
        m.set("pos_y", d["pos"][1])
        m.set("pos_z", d["pos"][2])
        m.set(("size1", "size2", "size3")[k], d["size"][0])
        if k == 1:
            m.set("time1", max(0.0, d["t"] / FPS))
        elif k == 2:
            m.set("time2", max(0.0, d["t"] / FPS - m.get("time1")))

    def frame_of(self, k):
        return self._sizes()[k][0]

    def sample(self, t):
        keys = self._sizes()
        base = self.key(0)
        s = keys[-1][1]
        if t <= keys[0][0]:
            s = keys[0][1]
        else:
            for (fa, sa), (fb, sb) in zip(keys, keys[1:]):
                if fa <= t <= fb:
                    s = sa + (sb - sa) * ((t - fa) / (fb - fa) if fb > fa else 1)
                    break
        base["size"] = [s, s, s]
        base["t"] = t
        return base

    def label(self, lang):
        m = self.mini
        return "#%d %s · %s" % (self.index, class_label(m.type, lang), stage_label(m.get("invoke"), lang, num=False))


class A02Track:
    """Saídas de Luz (classe 02), documentação do Vras: cada parte de 120 bytes tem início, meio e fim
       (tamanho em floats + cor RGBA) e os tempos 1→2 (+108) e 2→3 (+104)."""
    KEYS = (0, 16, 32)

    def __init__(self, mini, index, part):
        self.mini, self.index, self.part = mini, index, part
        self.kind = "a02"
        self.session = None
        self.base = part * ANIM02_PART

    @property
    def buf(self):
        return self.mini.files[0]

    def _times(self):
        b = self.buf
        t12 = struct.unpack_from("<f", b, self.base + 108)[0]
        t23 = struct.unpack_from("<f", b, self.base + 104)[0]
        start = b[self.base + 112]
        return start, t12, t23

    def nkeys(self):
        return 3

    def frame_of(self, k):
        start, t12, t23 = self._times()
        return float(start) + (0, t12 * FPS, (t12 + t23) * FPS)[k]

    def key(self, k):
        o = self.base + self.KEYS[k]
        b = self.buf
        l, w, h = struct.unpack_from("<3f", b, o)
        m = self.mini
        return {"pos": [m.get("pos_x"), m.get("pos_y"), m.get("pos_z")], "rot": [0, 0, 0],
                "size": [l, w, h], "rgba": list(b[o + 12:o + 16]), "t": self.frame_of(k)}

    def set_key(self, k, d):
        o = self.base + self.KEYS[k]
        b = self.buf
        struct.pack_into("<3f", b, o, *d["size"])
        b[o + 12:o + 16] = bytes(max(0, min(255, int(round(v)))) for v in d["rgba"])
        m = self.mini
        m.set("pos_x", d["pos"][0]); m.set("pos_y", d["pos"][1]); m.set("pos_z", d["pos"][2])
        start, t12, t23 = self._times()
        if k == 1:
            struct.pack_into("<f", b, self.base + 108, max(0.0, (d["t"] - start) / FPS))
        elif k == 2:
            struct.pack_into("<f", b, self.base + 104, max(0.0, (d["t"] - start) / FPS - t12))

    def sample(self, t):
        keys = [self.key(k) for k in range(3)]
        if t < keys[0]["t"]:
            return None
        for a, b in zip(keys, keys[1:]):
            if a["t"] <= t <= b["t"]:
                u = 0 if b["t"] == a["t"] else (t - a["t"]) / float(b["t"] - a["t"])
                lerp = lambda x, y: [x[i] + (y[i] - x[i]) * u for i in range(len(x))]
                return {"pos": a["pos"], "rot": [0, 0, 0], "size": lerp(a["size"], b["size"]),
                        "rgba": lerp(a["rgba"], b["rgba"]), "t": t}
        return None

    def label(self, lang):
        return tr("e3d_a02", lang, i=self.index, p=self.part + 1)


def v00_sessions(mini):
    """Divide as etapas do V00 em sessões usando o byte +4 de cada entrada da parte inicial."""
    v = mini.files[0]
    if len(v) < 32 or v[:4] != b"V000":
        return []
    n = v[4]
    start = struct.unpack_from("<H", v, 8)[0]
    total = (len(v) - start) // 64 if start <= len(v) else 0
    counts = [v[32 + 32 * i + 4] for i in range(n) if 32 + 32 * i + 4 < len(v)]
    if sum(counts) != total:
        counts = [3] * n if n * 3 == total else [total]
    out, k = [], 0
    for c in counts:
        out.append([start + 64 * (k + j) for j in range(c)])
        k += c
    return out


def build_tracks(eff, only=None):
    tracks = []
    ids = None if only is None else set(id(m) for m in only)
    for i, m in enumerate(eff.all_minis()):
        if m.type == 0x00 or (ids is not None and id(m) not in ids):
            continue
        if m.type == 0x02 and m.files:
            for p in range(anim02_count(m.files[0])):
                tracks.append(A02Track(m, i, p))
        elif m.type == 0x0E and m.files:
            for s, steps in enumerate(v00_sessions(m)):
                if steps:
                    tracks.append(V00Track(m, i, s, steps))
        else:
            tracks.append(MiniTrack(m, i))
    return tracks


# ---------------------------------------------------------------- janela
class Editor3D(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app, self.lang = app, app.lang
        self.title(tr("e3d_title", self.lang))
        self.geometry("1280x780")
        self.yaw, self.pitch, self.dist = math.pi / 2, 0.0, 60.0     # começa na vista de lado
        self.target = [0.0, 0.0, 0.0]
        self.time = 0.0
        self.sel, self.selkey = None, 0
        self.playing = False
        self.plane = tk.StringVar(value="xz")
        self.show_all = tk.BooleanVar(value=False)                   # começa mostrando só o selecionado
        self.anim_t = 0.0
        self.show_hit = tk.BooleanVar(value=True)
        self.show_tex = tk.BooleanVar(value=True)
        self.stage_vars = {}
        self._drag = None
        import previa
        self.cache = previa.SpriteCache(self)
        # layout
        left = ttk.Frame(self, padding=4)
        left.pack(side="left", fill="y")
        ttk.Label(left, text=tr("e3d_objects", self.lang), font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.lst = tk.Listbox(left, width=34, exportselection=False, activestyle="none")
        self.lst.pack(fill="y", expand=True)
        self.lst.bind("<<ListboxSelect>>", lambda e: self._pick_list())
        ttk.Checkbutton(left, text=tr("e3d_show_all", self.lang), variable=self.show_all, command=self.fit).pack(anchor="w")
        ttk.Checkbutton(left, text=tr("e3d_textures", self.lang), variable=self.show_tex, command=self.redraw).pack(anchor="w")
        ttk.Label(left, text=tr("e3d_stages", self.lang)).pack(anchor="w", pady=(4, 0))
        self.stage_box = ttk.Frame(left)
        self.stage_box.pack(fill="x")
        ttk.Button(left, text=tr("e3d_reload", self.lang), command=self.reload).pack(fill="x", pady=2)
        rnb = ttk.Notebook(self)
        rnb.pack(side="right", fill="y")
        right = ttk.Frame(rnb, padding=6)
        rnb.add(right, text=tr("e3d_tab_key", self.lang))
        hb = ttk.Frame(rnb, padding=6)
        rnb.add(hb, text=tr("e3d_tab_hit", self.lang))
        self._hitbox_tab(hb)
        self._hit_tab = hb
        self._rnb = rnb
        rnb.bind("<<NotebookTabChanged>>", lambda e: self.redraw())
        center = ttk.Frame(self)
        center.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(center)
        bar.pack(fill="x")
        ttk.Label(bar, text=tr("e3d_drag_plane", self.lang)).pack(side="left")
        for k in ("xz", "xy", "zy"):
            ttk.Radiobutton(bar, text=k.upper(), value=k, variable=self.plane).pack(side="left")
        for k, (yw, pt) in (("e3d_v_persp", (0.7, 0.45)), ("e3d_v_front", (0.0, 0.0)), ("e3d_v_side", (math.pi / 2, 0.0)),
                            ("e3d_v_top", (0.0, math.pi / 2 - 0.01))):
            ttk.Button(bar, text=tr(k, self.lang), command=lambda yw=yw, pt=pt: self._view(yw, pt)).pack(side="left", padx=1)
        ttk.Button(bar, text=tr("e3d_fit", self.lang), command=self.fit).pack(side="left", padx=4)
        ttk.Label(bar, text=tr("e3d_help", self.lang)).pack(side="left", padx=8)
        self.cv = tk.Canvas(center, bg="#16181d", highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", lambda e: self.redraw())
        self.cv.bind("<ButtonPress-1>", self._press)
        self.cv.bind("<B1-Motion>", self._move)
        self.cv.bind("<ButtonRelease-1>", self._release)
        self.cv.bind("<ButtonPress-3>", self._rpress)
        self.cv.bind("<B3-Motion>", self._rmove)
        self.cv.bind("<MouseWheel>", self._wheel)
        self.cv.bind("<Button-4>", lambda e: self._zoom(0.9))
        self.cv.bind("<Button-5>", lambda e: self._zoom(1.1))
        # linha do tempo
        tl = ttk.Frame(center, padding=(0, 4))
        tl.pack(fill="x")
        self.btn_play = ttk.Button(tl, text="▶", width=3, command=self._toggle_play)
        self.btn_play.pack(side="left")
        self.lbl_time = ttk.Label(tl, text="0", width=10)
        self.lbl_time.pack(side="left")
        self.tl = tk.Canvas(tl, height=54, bg="#22252c", highlightthickness=0)
        self.tl.pack(side="left", fill="x", expand=True)
        self.tl.bind("<Configure>", lambda e: self.draw_timeline())
        self.tl.bind("<ButtonPress-1>", self._tl_press)
        self.tl.bind("<B1-Motion>", self._tl_move)
        self.tl.bind("<ButtonRelease-1>", self._tl_release)
        # propriedades
        ttk.Label(right, text=tr("e3d_keyframe", self.lang), font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.lbl_key = ttk.Label(right, text="", wraplength=260)
        self.lbl_key.pack(anchor="w", pady=(0, 6))
        g = ttk.Frame(right)
        g.pack(fill="x")
        self.vars = {}
        rows = [("pos", tr("e3d_pos", self.lang), 3), ("rot", tr("e3d_rot", self.lang), 3),
                ("size", tr("e3d_size", self.lang), 3), ("rgba", "RGBA", 4)]
        r = 0
        for key, label, n in rows:
            ttk.Label(g, text=label).grid(row=r, column=0, sticky="w", pady=(6, 0))
            r += 1
            vs = []
            for j in range(n):
                v = tk.StringVar()
                ttk.Entry(g, textvariable=v, width=8).grid(row=r, column=j, padx=1)
                vs.append(v)
            self.vars[key] = vs
            r += 1
        self.sw = tk.Label(g, width=4, relief="solid", bd=1)
        self.sw.grid(row=r - 1, column=4, padx=4)
        self.sw.bind("<Button-1>", lambda e: self._pick_color())
        ttk.Label(g, text=tr("e3d_moment", self.lang)).grid(row=r, column=0, columnspan=3, sticky="w", pady=(6, 0))
        r += 1
        self.vars["t"] = [tk.StringVar()]
        ttk.Entry(g, textvariable=self.vars["t"][0], width=8).grid(row=r, column=0)
        r += 1
        ttk.Button(right, text=tr("apply", self.lang), command=self._apply_fields).pack(fill="x", pady=8)
        ttk.Button(right, text=tr("e3d_copy_prev", self.lang), command=self._copy_prev).pack(fill="x")
        ttk.Separator(right).pack(fill="x", pady=8)
        self.lbl_meta = ttk.Label(right, text="", wraplength=260, justify="left")
        self.lbl_meta.pack(anchor="w")
        ttk.Label(right, text=tr("e3d_tex_of", self.lang), font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(6, 2))
        self.lbl_tex = tk.Label(right, bg="#202228")
        self.lbl_tex.pack(anchor="w")
        self.info = ttk.Label(right, text=tr("e3d_note", self.lang), wraplength=260, justify="left", foreground="#8a8f99")
        self.info.pack(anchor="w", pady=12)
        self.bind("<space>", lambda e: self._toggle_play())
        self.reload()
        self.after(150, self._anim)

    def _anim(self):
        """Relógio das texturas animadas/partículas (roda sempre)."""
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        self.anim_t += 2.0
        if not self.playing and not self._drag and self.show_tex.get():
            import previa
            vis = [t for t in self.tracks if self.show_all.get() or t is self.sel]
            if any(previa.sprite_cell(t, 1) is not None or (t.mini.type == 0x05 and previa.shape05_particles(t.mini) > 1)
                   for t in vis):
                self.redraw()
        self.after(66, self._anim)

    # ---- hitbox (cabeçalho do 03_.dat)
    HIT_FIELDS = [(0x08, "e3d_hit_base")] + [(0x08 + 4 * i, "e3d_hit_x%d" % i) for i in range(1, 6)] + \
                 [(0x28 + 4 * i, "e3d_hit_u%d" % (i + 1)) for i in range(6)]

    def _hitbox_tab(self, f):
        ttk.Label(f, text=tr("e3d_hit_title", self.lang), font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(f, text=tr("e3d_hit_hint", self.lang), wraplength=270, justify="left", foreground="#8a8f99").pack(anchor="w", pady=(0, 6))
        ttk.Checkbutton(f, text=tr("e3d_hit_show", self.lang), variable=self.show_hit, command=self.redraw).pack(anchor="w")
        g = ttk.Frame(f)
        g.pack(fill="x", pady=4)
        self.hit_vars = {}
        for r, (o, key) in enumerate(self.HIT_FIELDS):
            ttk.Label(g, text="0x%02X  %s" % (o, tr(key, self.lang))).grid(row=r, column=0, sticky="w")
            v = tk.StringVar()
            e = ttk.Entry(g, textvariable=v, width=9)
            e.grid(row=r, column=1, padx=4, pady=1)
            e.bind("<Return>", lambda ev: self._hit_apply())
            self.hit_vars[o] = v
        c = ttk.Frame(f)
        c.pack(fill="x", pady=4)
        ttk.Label(c, text=tr("e3d_hit_center", self.lang)).pack(side="left")
        self.hit_center = tk.StringVar(value="origin")
        ttk.Radiobutton(c, text=tr("e3d_hit_origin", self.lang), value="origin", variable=self.hit_center, command=self.redraw).pack(side="left")
        ttk.Radiobutton(c, text=tr("e3d_hit_sel", self.lang), value="sel", variable=self.hit_center, command=self.redraw).pack(side="left")
        k = ttk.Frame(f)
        k.pack(fill="x")
        ttk.Label(k, text=tr("e3d_hit_scale", self.lang)).pack(side="left")
        self.hit_scale = tk.StringVar(value="0.25")
        sp = ttk.Spinbox(k, from_=0.05, to=5, increment=0.05, width=6, textvariable=self.hit_scale, command=self.redraw)
        sp.pack(side="left", padx=4)
        sp.bind("<Return>", lambda e: self.redraw())
        b = ttk.Frame(f)
        b.pack(fill="x", pady=6)
        ttk.Button(b, text=tr("apply", self.lang), command=self._hit_apply).pack(side="left", fill="x", expand=True)
        ttk.Button(b, text="×1.25", width=6, command=lambda: self._hit_scale_base(1.25)).pack(side="left", padx=2)
        ttk.Button(b, text="×0.8", width=6, command=lambda: self._hit_scale_base(0.8)).pack(side="left")
        self._hit_fill()

    def _hit_fill(self):
        h = self.app.eff.header if self.app.eff else bytes(64)
        for o, v in self.hit_vars.items():
            v.set("%g" % round(struct.unpack_from("<f", h, o)[0], 4))

    def _hit_apply(self):
        try:
            vals = {o: float(v.get().replace(",", ".")) for o, v in self.hit_vars.items()}
        except ValueError as ex:
            messagebox.showerror(tr("err", self.lang), str(ex), parent=self)
            return
        self.app.snapshot(tr("e3d_tab_hit", self.lang))
        for o, val in vals.items():
            struct.pack_into("<f", self.app.eff.header, o, val)
        self.app.changed()
        self._hit_fill()
        self.redraw()

    def _hit_scale_base(self, k):
        v = self.hit_vars[0x08]
        try:
            v.set("%g" % round(float(v.get().replace(",", ".")) * k, 3))
        except ValueError:
            return
        self._hit_apply()

    def _draw_hitbox(self, cv):
        if not self.show_hit.get() or not self.app.eff:
            return
        try:
            if self._rnb.select() != str(self._hit_tab):      # a hitbox só aparece com a aba Hitbox aberta
                return
        except (AttributeError, tk.TclError):
            return
        h = self.app.eff.header
        try:
            k = float(self.hit_scale.get().replace(",", "."))
        except ValueError:
            k = 0.5
        base = struct.unpack_from("<f", h, 0x08)[0]
        ext = struct.unpack_from("<5f", h, 0x0C)
        c = [0.0, 0.0, 0.0]
        if self.hit_center.get() == "sel" and self.sel is not None:
            d = self.sel.sample(self.time) or self.sel.key(0)
            c = list(d["pos"])
        col = "#ff4d6d"
        r = abs(base) * k
        if r > 0:
            for plane in ((0, 1), (0, 2), (1, 2)):
                pts = []
                for s in range(0, 37):
                    a = 2 * math.pi * s / 36
                    p = list(c)
                    p[plane[0]] += math.cos(a) * r
                    p[plane[1]] += math.sin(a) * r
                    q = self.project(p)
                    if q:
                        pts += [q[0], q[1]]
                if len(pts) >= 4:
                    cv.create_line(*pts, fill=col, width=2 if plane == (0, 1) else 1, dash=() if plane == (0, 1) else (3, 3))
            q = self.project([c[0], c[1] + r, c[2]])
            if q:
                cv.create_text(q[0], q[1] - 10, text="hitbox %g" % base, fill=col, font=("Segoe UI", 8, "bold"))
        # colisões extras (interpretação experimental): caixa com comprimento X, altura Y e largura Z, para frente (-X)
        lx, ly, lz = [abs(v) * k for v in ext[:3]]
        if lx > 0 and (ly > 0 or lz > 0):
            ly = ly or lx * 0.1
            lz = lz or ly
            x0, x1 = c[0], c[0] - lx
            corners = [(x, c[1] + sy * ly / 2, c[2] + sz * lz / 2) for x in (x0, x1) for sy in (-1, 1) for sz in (-1, 1)]
            P = [self.project(list(p)) for p in corners]
            for a, b in ((0, 1), (2, 3), (0, 2), (1, 3), (4, 5), (6, 7), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)):
                if P[a] and P[b]:
                    cv.create_line(P[a][0], P[a][1], P[b][0], P[b][1], fill="#ffa94d", dash=(4, 2))

    # ---- dados
    def reload(self):
        self.cache.clear()
        self.tracks = build_tracks(self.app.eff) if self.app.eff else []
        stages = sorted(set(t.mini.get("invoke") for t in self.tracks))
        for w in self.stage_box.winfo_children():
            w.destroy()
        for st in stages:
            v = self.stage_vars.get(st) or tk.BooleanVar(value=True)
            self.stage_vars[st] = v
            ttk.Checkbutton(self.stage_box, text=stage_label(st, self.lang), variable=v,
                            command=self.redraw).pack(anchor="w")
        self.lst.delete(0, "end")
        for t in self.tracks:
            self.lst.insert("end", t.label(self.lang))
        if self.tracks:
            self.sel = self.tracks[0]
            self.selkey = 0
            self.lst.selection_set(0)
        self.fit()
        self._fill_fields()

    def _pick_list(self):
        s = self.lst.curselection()
        if s:
            self.sel, self.selkey = self.tracks[s[0]], 0
            self._fill_fields()
            if not self.show_all.get():
                self.fit()
            else:
                self.redraw()

    def _commit(self):
        self.app.snapshot(tr("e3d_title", self.lang))

    def _changed(self):
        self.app.changed()
        self._fill_fields()
        self.redraw()

    # ---- câmera e projeção
    def _view(self, yaw, pitch):
        self.yaw, self.pitch = yaw, pitch
        self.redraw()

    def fit(self):
        pts = []
        vis = self.tracks if self.show_all.get() or self.sel is None else [self.sel]
        for t in vis:
            for k in range(t.nkeys()):
                d = t.key(k)
                pts.append((d["pos"], max(abs(x) for x in d["size"])))
        if not pts:
            self.target, self.dist = [0, 0, 0], 60
        else:
            mn = [min(p[0][i] for p in pts) for i in range(3)]
            mx = [max(p[0][i] for p in pts) for i in range(3)]
            self.target = [(a + b) / 2 for a, b in zip(mn, mx)]
            span = max(max(b - a for a, b in zip(mn, mx)), max(p[1] for p in pts) * 2, 0.6)
            self.dist = span * 2.2
        self.redraw()

    def _basis(self):
        cy, sy, cp, sp = math.cos(self.yaw), math.sin(self.yaw), math.cos(self.pitch), math.sin(self.pitch)
        fwd = (-sy * cp, -sp, -cy * cp)
        right = (cy, 0.0, -sy)
        up = (right[1] * fwd[2] - right[2] * fwd[1], right[2] * fwd[0] - right[0] * fwd[2], right[0] * fwd[1] - right[1] * fwd[0])
        up = tuple(-x for x in up)
        eye = tuple(self.target[i] - fwd[i] * self.dist for i in range(3))
        return eye, fwd, right, up

    def project(self, p):
        eye, fwd, right, up = self._basis()
        d = [p[i] - eye[i] for i in range(3)]
        z = sum(d[i] * fwd[i] for i in range(3))
        if z <= 0.1:
            return None
        x = sum(d[i] * right[i] for i in range(3))
        y = sum(d[i] * up[i] for i in range(3))
        w, h = max(1, self.cv.winfo_width()), max(1, self.cv.winfo_height())
        f = 0.9 * min(w, h)
        return (w / 2 + x * f / z, h / 2 - y * f / z, f / z)

    # ---- desenho
    def redraw(self):
        cv = self.cv
        cv.delete("all")
        span = max(10.0, self.dist / 2.2)
        step = 10 ** math.floor(math.log10(span / 4))
        n = int(span / step) + 2
        for i in range(-n, n + 1):
            for a, b in (((i * step, 0, -n * step), (i * step, 0, n * step)), ((-n * step, 0, i * step), (n * step, 0, i * step))):
                pa = self.project([a[0] + self.target[0], 0, a[2] + self.target[2]])
                pb = self.project([b[0] + self.target[0], 0, b[2] + self.target[2]])
                if pa and pb:
                    cv.create_line(pa[0], pa[1], pb[0], pb[1], fill="#2a2e36")
        o = self.project([0, 0, 0])
        for axis, col in (((step * 3, 0, 0), "#d9534f"), ((0, step * 3, 0), "#5cb85c"), ((0, 0, step * 3), "#4a90d9")):
            p = self.project(list(axis))
            if o and p:
                cv.create_line(o[0], o[1], p[0], p[1], fill=col, width=2, arrow="last")
                cv.create_text(p[0] + 8, p[1], text="XYZ"[[axis[0] != 0, axis[1] != 0, axis[2] != 0].index(True)], fill=col)
        items = []
        for t in self.tracks:
            if not self.show_all.get() and t is not self.sel:
                continue
            sv = self.stage_vars.get(t.mini.get("invoke"))
            if sv is not None and not sv.get() and t is not self.sel:
                continue
            d = t.sample(self.time)
            if d is None:
                continue
            pp = self.project(d["pos"])
            if pp:
                items.append((pp[2], t, d, pp))
            if t is self.sel and t.kind == "v00" and t.nkeys() > 1:
                path = [self.project(t.key(k)["pos"]) for k in range(t.nkeys())]
                for a, b in zip(path, path[1:]):
                    if a and b:
                        cv.create_line(a[0], a[1], b[0], b[1], fill="#e8c34a", dash=(4, 3))
                for k, p in enumerate(path):
                    if p:
                        r = 6 if k == self.selkey else 4
                        cv.create_rectangle(p[0] - r, p[1] - r, p[0] + r, p[1] + r,
                                            outline="#e8c34a", fill="#e8c34a" if k == self.selkey else "")
        self._imgs = []
        import previa
        for z, t, d, p in sorted(items, key=lambda it: it[0]):
            r = max(3, min(400, max(abs(x) for x in d["size"]) * p[2] * 0.5))
            col = "#%02x%02x%02x" % tuple(int(min(255, max(0, c))) for c in d["rgba"][:3])
            sel = t is self.sel
            drawn = False
            if self.show_tex.get() and r > 2:
                for dx, dy, dz, sc, cell in previa.expand(t, d, self.time + self.anim_t):
                    q = self.project([d["pos"][0] + dx, d["pos"][1] + dy, d["pos"][2] + dz])
                    if not q:
                        continue
                    rr = max(2, min(400, max(abs(x) for x in d["size"]) * sc * q[2] * 0.5))
                    im = self.cache.get(self.app.eff, t.mini, t.session, d["rgba"], rr * 2, cell)
                    if im is not None:
                        cv.create_image(q[0], q[1], image=im)
                        self._imgs.append(im)
                        drawn = True
            if drawn:
                if sel:
                    cv.create_oval(p[0] - r, p[1] - r, p[0] + r, p[1] + r, outline="#ffffff", width=2, dash=(3, 2))
            else:
                cv.create_oval(p[0] - r, p[1] - r, p[0] + r, p[1] + r, outline="#ffffff" if sel else col,
                               width=3 if sel else 1, fill=col if sel else "", stipple="gray25" if sel else "")
            cv.create_text(p[0], p[1] - r - 8, text="#%d" % t.index, fill="#c8ccd4", font=("Segoe UI", 8))
        if self.sel is not None and self.sel.kind == "mini":
            for k in range(self.sel.nkeys()):
                d = self.sel.key(k)
                p = self.project(d["pos"])
                if p:
                    r = max(2, abs(d["size"][0]) * p[2] * 0.5)
                    cv.create_oval(p[0] - r, p[1] - r, p[0] + r, p[1] + r, outline="#e8c34a", dash=(2, 4))
        self._draw_hitbox(cv)
        self.draw_timeline()

    def draw_timeline(self):
        c = self.tl
        c.delete("all")
        w = max(1, c.winfo_width())
        self.tmax = max([60.0] + [t.frame_of(k) * 1.15 + 5 for t in self.tracks for k in range(t.nkeys())])
        for i in range(0, int(self.tmax) + 1, 10):
            x = 10 + (w - 20) * i / self.tmax
            c.create_line(x, 40, x, 54, fill="#555b66")
            c.create_text(x, 47, text=str(i), fill="#8a8f99", font=("Segoe UI", 7), anchor="w")
        if self.sel:
            for k in range(self.sel.nkeys()):
                x = 10 + (w - 20) * self.sel.frame_of(k) / self.tmax
                col = "#e8c34a" if k == self.selkey else "#c8ccd4"
                c.create_polygon(x, 8, x + 7, 18, x, 28, x - 7, 18, fill=col, outline="#000000")
                c.create_text(x, 34, text=str(k + 1), fill="#c8ccd4", font=("Segoe UI", 7))
        x = 10 + (w - 20) * self.time / self.tmax
        c.create_line(x, 0, x, 54, fill="#d9534f", width=2)
        self.lbl_time.config(text="t = %.0f" % self.time)

    # ---- painel de propriedades
    def _fill_fields(self):
        if not self.sel:
            return
        k = min(self.selkey, self.sel.nkeys() - 1)
        self.selkey = k
        d = self.sel.key(k)
        for key in ("pos", "rot", "size", "rgba"):
            for v, val in zip(self.vars[key], d[key]):
                v.set("%g" % round(val, 4))
        self.vars["t"][0].set("%g" % round(d["t"], 3))
        self.sw.config(bg="#%02x%02x%02x" % tuple(int(min(255, max(0, c))) for c in d["rgba"][:3]))
        txt = self.sel.label(self.lang) + "\n" + tr("e3d_key_n", self.lang, k=k + 1, n=self.sel.nkeys())
        if self.sel.kind == "mini":
            txt += "\n" + tr("e3d_mini_note", self.lang)
        self.lbl_key.config(text=txt)
        m = self.sel.mini
        self.lbl_meta.config(text=tr("e3d_info", self.lang, c=class_label(m.type, self.lang),
                                     s=stage_label(m.get("invoke"), self.lang), d=dis_label(m.param[9], self.lang),
                                     o=ori_label(m.param[10], self.lang)))
        try:
            import base64, texview
            from bt3eff_core import mini_sprite
            spr = mini_sprite(self.app.eff, m, self.sel.session)
            if spr:
                rgba, w, h = spr
                self._tex_img = tk.PhotoImage(master=self, data=base64.b64encode(texview.preview_png(rgba, w, h, 120)).decode())
                self.lbl_tex.config(image=self._tex_img, text="")
            else:
                self.lbl_tex.config(image="", text="—")
        except Exception:
            self.lbl_tex.config(image="", text="—")

    def _read_fields(self):
        d = {}
        for key in ("pos", "rot", "size", "rgba"):
            d[key] = [float(v.get().replace(",", ".")) for v in self.vars[key]]
        d["t"] = float(self.vars["t"][0].get().replace(",", "."))
        return d

    def _apply_fields(self):
        if not self.sel:
            return
        try:
            d = self._read_fields()
        except ValueError as ex:
            messagebox.showerror(tr("err", self.lang), str(ex), parent=self)
            return
        self._commit()
        self.sel.set_key(self.selkey, d)
        self._changed()

    def _copy_prev(self):
        if not self.sel or self.selkey == 0:
            return
        prev = self.sel.key(self.selkey - 1)
        cur = self.sel.key(self.selkey)
        prev["t"] = cur["t"]
        self._commit()
        self.sel.set_key(self.selkey, prev)
        self._changed()

    def _pick_color(self):
        if not self.sel:
            return
        res = self.app.ask_color()
        if res:
            for v, c in zip(self.vars["rgba"], res):
                v.set(str(int(c)))
            self._apply_fields()

    # ---- mouse na vista 3D
    def _hit(self, x, y):
        best = None
        for t in self.tracks:
            if t is self.sel and t.kind == "v00":
                for k in range(t.nkeys()):
                    p = self.project(t.key(k)["pos"])
                    if p and abs(p[0] - x) < 8 and abs(p[1] - y) < 8:
                        return t, k
            d = t.sample(self.time)
            p = self.project(d["pos"]) if d else None
            if p:
                dd = math.hypot(p[0] - x, p[1] - y)
                if dd < 14 and (best is None or dd < best[0]):
                    best = (dd, t)
        return (best[1], None) if best else (None, None)

    def _press(self, e):
        t, k = self._hit(e.x, e.y)
        if t is None:
            self._drag = ("orbit", e.x, e.y)
            return
        if t is not self.sel:
            self.sel = t
            self.lst.selection_clear(0, "end")
            self.lst.selection_set(self.tracks.index(t))
            self.selkey = 0
        if k is not None:
            self.selkey = k
        else:
            # objeto comum: arrasta o quadro-chave mais próximo do tempo atual
            frames = [abs(self.sel.frame_of(i) - self.time) for i in range(self.sel.nkeys())]
            self.selkey = frames.index(min(frames))
        self._fill_fields()
        self._drag = ("move", e.x, e.y, self.sel.key(self.selkey))
        self._moved = False
        self.redraw()

    def _move(self, e):
        if not self._drag:
            return
        if self._drag[0] == "orbit":
            _, x0, y0 = self._drag
            self.yaw += (e.x - x0) * 0.01
            self.pitch = max(-1.5, min(1.5, self.pitch + (e.y - y0) * 0.01))
            self._drag = ("orbit", e.x, e.y)
            self.redraw()
            return
        _, x0, y0, d0 = self._drag
        p = self.project(d0["pos"])
        if not p:
            return
        scale = 1.0 / max(1e-6, p[2])
        dx, dy = (e.x - x0) * scale, -(e.y - y0) * scale
        eye, fwd, right, up = self._basis()
        delta = [right[i] * dx + up[i] * dy for i in range(3)]
        lock = {"xz": 1, "xy": 2, "zy": 0}[self.plane.get()]
        delta[lock] = 0.0
        d = dict(d0)
        d["pos"] = [d0["pos"][i] + delta[i] for i in range(3)]
        if not self._moved:
            self._commit()
            self._moved = True
        self.sel.set_key(self.selkey, d)
        self._fill_fields()
        self.redraw()

    def _release(self, e):
        if self._drag and self._drag[0] == "move" and self._moved:
            self.app.changed()
        self._drag = None

    def _rpress(self, e):
        self._rdrag = (e.x, e.y)

    def _rmove(self, e):
        x0, y0 = self._rdrag
        eye, fwd, right, up = self._basis()
        k = self.dist / 600.0
        for i in range(3):
            self.target[i] -= right[i] * (e.x - x0) * k - up[i] * (e.y - y0) * k
        self._rdrag = (e.x, e.y)
        self.redraw()

    def _wheel(self, e):
        self._zoom(0.9 if e.delta > 0 else 1.1)

    def _zoom(self, f):
        self.dist = max(0.5, self.dist * f)
        self.redraw()

    # ---- linha do tempo
    def _tl_x2t(self, x):
        w = max(1, self.tl.winfo_width())
        return max(0.0, min(self.tmax, (x - 10) * self.tmax / max(1, (w - 20))))

    def _tl_press(self, e):
        self._tl_drag = None
        if self.sel:
            w = max(1, self.tl.winfo_width())
            for k in range(self.sel.nkeys()):
                x = 10 + (w - 20) * self.sel.frame_of(k) / self.tmax
                if abs(x - e.x) < 8 and e.y < 32:
                    self.selkey = k
                    self._fill_fields()
                    if not (self.sel.kind == "mini" and k == 0):
                        self._tl_drag = k
                        self._commit()
                    self.draw_timeline()
                    return
        self.time = self._tl_x2t(e.x)
        self.redraw()

    def _tl_move(self, e):
        if self._tl_drag is None:
            self.time = self._tl_x2t(e.x)
            self.redraw()
            return
        d = self.sel.key(self._tl_drag)
        d["t"] = round(self._tl_x2t(e.x))
        self.sel.set_key(self._tl_drag, d)
        self._fill_fields()
        self.draw_timeline()

    def _tl_release(self, e):
        if self._tl_drag is not None:
            self.app.changed()
            self.redraw()
        self._tl_drag = None

    def _toggle_play(self):
        self.playing = not self.playing
        self.btn_play.config(text="⏸" if self.playing else "▶")
        if self.playing:
            self._tick()

    def _tick(self):
        if not self.playing or not self.winfo_exists():
            return
        self.time += 1
        if self.time > self.tmax:
            self.time = 0
        self.redraw()
        self.after(33, self._tick)
