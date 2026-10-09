# -*- coding: utf-8 -*-
"""Seletor de cor do programa: roda de cor, imagem de referência (conta-gotas) e paleta das texturas do efeito."""
import base64, colorsys
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
from lang import tr, class_label
from bt3eff_core import dbt_info, dbt_image_rgba


def hexrgb(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb[:3])


class ColorPicker(tk.Toplevel):
    SQ, BAR = 200, 22

    def __init__(self, app, initial=None, title=None):
        super().__init__(app)
        self.app, self.lang = app, app.lang
        self.title(title or tr("cp_title", self.lang))
        self.transient(app)
        self.resizable(False, False)
        self.result = None
        self.rgb = tuple(initial) if initial else (255, 140, 0)
        h, s, v = colorsys.rgb_to_hsv(*[c / 255.0 for c in self.rgb])
        self.h, self.s, self.v = h, s, v
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        self.sw = tk.Label(top, width=8, height=2, relief="solid", bd=1, bg=hexrgb(self.rgb))
        self.sw.pack(side="left")
        self.hexvar = tk.StringVar(value=hexrgb(self.rgb).upper())
        e = ttk.Entry(top, textvariable=self.hexvar, width=10, font=("Consolas", 11))
        e.pack(side="left", padx=8)
        e.bind("<Return>", lambda ev: self._from_hex())
        e.bind("<FocusOut>", lambda ev: self._from_hex())
        ttk.Button(top, text=tr("cp_system", self.lang), command=self._system).pack(side="right")
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8)
        self._tab_wheel(nb)
        self._tab_ref(nb)
        self._tab_pal(nb)
        rec = ttk.Frame(self, padding=(8, 6))
        rec.pack(fill="x")
        ttk.Label(rec, text=tr("cp_recent", self.lang)).pack(side="left")
        for c in (app.cfg.get("recent_colors") or [])[:12]:
            b = tk.Label(rec, width=2, bg=c, relief="solid", bd=1, cursor="hand2")
            b.pack(side="left", padx=1)
            b.bind("<Button-1>", lambda ev, c=c: self.set_rgb(tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))))
        bb = ttk.Frame(self, padding=8)
        bb.pack(fill="x")
        ttk.Button(bb, text="OK", command=self._ok).pack(side="right")
        ttk.Button(bb, text=tr("close", self.lang), command=self.destroy).pack(side="right", padx=6)
        self.bind("<Escape>", lambda e: self.destroy())
        self._draw_wheel()
        self.grab_set()

    # ---------------------------------------------------------------- roda (quadrado S/V + barra de tom)
    def _tab_wheel(self, nb):
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text=tr("cp_wheel", self.lang))
        self.cv_sq = tk.Canvas(f, width=self.SQ, height=self.SQ, highlightthickness=0, cursor="crosshair")
        self.cv_sq.pack(side="left")
        self.cv_bar = tk.Canvas(f, width=self.BAR, height=self.SQ, highlightthickness=0, cursor="sb_v_double_arrow")
        self.cv_bar.pack(side="left", padx=8)
        self._img_bar = tk.PhotoImage(width=self.BAR, height=self.SQ)
        rows = []
        for y in range(self.SQ):
            r, g, b = colorsys.hsv_to_rgb(y / float(self.SQ), 1, 1)
            rows.append("{" + " ".join([hexrgb((r * 255, g * 255, b * 255))] * self.BAR) + "}")
        self._img_bar.put(" ".join(rows))
        self.cv_bar.create_image(0, 0, image=self._img_bar, anchor="nw")
        self._img_sq = tk.PhotoImage(width=self.SQ, height=self.SQ)
        self.cv_sq.create_image(0, 0, image=self._img_sq, anchor="nw")
        for ev in ("<Button-1>", "<B1-Motion>"):
            self.cv_sq.bind(ev, self._sq_click)
            self.cv_bar.bind(ev, self._bar_click)

    def _draw_wheel(self):
        n = self.SQ
        rows = []
        for y in range(0, n):
            v = 1 - y / float(n - 1)
            row = []
            for x in range(0, n):
                r, g, b = colorsys.hsv_to_rgb(self.h, x / float(n - 1), v)
                row.append("#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255)))
            rows.append("{" + " ".join(row) + "}")
        self._img_sq.put(" ".join(rows))
        self.cv_sq.delete("mk")
        x, y = self.s * (n - 1), (1 - self.v) * (n - 1)
        self.cv_sq.create_oval(x - 6, y - 6, x + 6, y + 6, outline="#ffffff", width=2, tags="mk")
        self.cv_sq.create_oval(x - 7, y - 7, x + 7, y + 7, outline="#000000", tags="mk")
        self.cv_bar.delete("mk")
        yb = self.h * self.SQ
        self.cv_bar.create_rectangle(0, yb - 2, self.BAR, yb + 2, outline="#ffffff", width=2, tags="mk")

    def _sq_click(self, e):
        n = self.SQ - 1
        self.s = max(0.0, min(1.0, e.x / float(n)))
        self.v = max(0.0, min(1.0, 1 - e.y / float(n)))
        self._from_hsv()

    def _bar_click(self, e):
        self.h = max(0.0, min(0.999, e.y / float(self.SQ)))
        self._from_hsv()
        self._draw_wheel()

    def _from_hsv(self):
        r, g, b = colorsys.hsv_to_rgb(self.h, self.s, self.v)
        self._show((round(r * 255), round(g * 255), round(b * 255)))
        self._draw_wheel()

    # ---------------------------------------------------------------- imagem de referência (conta-gotas)
    def _tab_ref(self, nb):
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text=tr("cp_ref", self.lang))
        r = ttk.Frame(f)
        r.pack(fill="x")
        ttk.Button(r, text=tr("cp_load", self.lang), command=self._load_ref).pack(side="left")
        ttk.Label(r, text=tr("cp_ref_hint", self.lang), foreground="#8a8f99").pack(side="left", padx=8)
        self.cv_ref = tk.Canvas(f, width=420, height=300, bg="#202228", highlightthickness=0, cursor="tcross")
        self.cv_ref.pack(pady=6)
        self.cv_ref.bind("<Button-1>", self._ref_pick)
        self.cv_ref.bind("<B1-Motion>", self._ref_pick)
        self._ref = None
        last = self.app.cfg.get("ref_image")
        if last:
            self._open_ref(last, quiet=True)

    def _load_ref(self):
        p = filedialog.askopenfilename(parent=self, filetypes=[("Imagem", "*.png *.gif *.ppm *.jpg *.jpeg"), ("*", "*.*")])
        if p:
            self._open_ref(p)

    def _open_ref(self, p, quiet=False):
        img = None
        try:
            img = tk.PhotoImage(file=p)
        except tk.TclError:
            try:
                from PIL import Image
                import io
                im = Image.open(p).convert("RGB")
                buf = io.BytesIO()
                im.save(buf, "PNG")
                img = tk.PhotoImage(data=base64.b64encode(buf.getvalue()).decode())
            except Exception:
                img = None
        if img is None:
            if not quiet:
                messagebox.showerror(tr("err", self.lang), tr("cp_noimg", self.lang), parent=self)
            return
        k = 1
        while img.width() // k > 420 or img.height() // k > 300:
            k += 1
        self._ref_full, self._ref_k = img, k
        self._ref = img.subsample(k, k) if k > 1 else img
        self.cv_ref.delete("all")
        self.cv_ref.config(width=self._ref.width(), height=self._ref.height())
        self.cv_ref.create_image(0, 0, image=self._ref, anchor="nw")
        self.app.cfg["ref_image"] = p

    def _ref_pick(self, e):
        if self._ref is None:
            return
        x, y = e.x * self._ref_k, e.y * self._ref_k
        if 0 <= x < self._ref_full.width() and 0 <= y < self._ref_full.height():
            c = self._ref_full.get(x, y)
            if isinstance(c, str):
                c = tuple(int(v) for v in c.split())
            self.set_rgb(tuple(c[:3]))
            self.cv_ref.delete("mk")
            self.cv_ref.create_oval(e.x - 6, e.y - 6, e.x + 6, e.y + 6, outline="#ffffff", width=2, tags="mk")

    # ---------------------------------------------------------------- paleta da textura
    def _tab_pal(self, nb):
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text=tr("cp_pal", self.lang))
        self.pal_items = []
        eff = self.app.eff
        if eff:
            for c in eff.cats:
                for di, d in enumerate(c.dbts):
                    for ii, im in enumerate(dbt_info(d)):
                        self.pal_items.append((c, di, ii, "%s · DBT %d · img %d (%d×%d)" % (
                            class_label(c.type, self.lang), di, ii, im["w"], im["h"])))
        self.cb_pal = ttk.Combobox(f, state="readonly", width=52, values=[x[3] for x in self.pal_items])
        self.cb_pal.pack(anchor="w")
        self.cb_pal.bind("<<ComboboxSelected>>", lambda e: self._show_pal())
        ttk.Label(f, text=tr("cp_pal_hint", self.lang), foreground="#8a8f99").pack(anchor="w", pady=4)
        row = ttk.Frame(f)
        row.pack(fill="both")
        self.lbl_tex = tk.Label(row, bg="#202228")
        self.lbl_tex.pack(side="left", anchor="n")
        self.cv_pal = tk.Canvas(row, width=272, height=272, bg="#202228", highlightthickness=0, cursor="hand2")
        self.cv_pal.pack(side="left", padx=8)
        self.cv_pal.bind("<Button-1>", self._pal_click)
        self._pal = []
        if self.pal_items:
            self.cb_pal.current(0)
            self._show_pal()

    def _show_pal(self):
        i = self.cb_pal.current()
        if i < 0:
            return
        c, di, ii, _ = self.pal_items[i]
        try:
            rgba, w, h = dbt_image_rgba(c.dbts[di], ii)
        except Exception:
            return
        import texview
        self._tex_img = tk.PhotoImage(data=base64.b64encode(texview.preview_png(rgba, w, h, 140)).decode())
        self.lbl_tex.config(image=self._tex_img)
        uniq = []
        seen = set()
        for p in rgba:
            if p[3] < 8:
                continue
            k = p[:3]
            if k not in seen:
                seen.add(k)
                uniq.append(k)
        uniq.sort(key=lambda c: colorsys.rgb_to_hsv(*[x / 255.0 for x in c])[2])
        if len(uniq) > 256:
            step = len(uniq) / 256.0
            uniq = [uniq[int(j * step)] for j in range(256)]
        self._pal = uniq
        self.cv_pal.delete("all")
        for j, col in enumerate(uniq):
            x, y = (j % 16) * 17, (j // 16) * 17
            self.cv_pal.create_rectangle(x, y, x + 16, y + 16, fill=hexrgb(col), outline="#000000")

    def _pal_click(self, e):
        j = (e.y // 17) * 16 + e.x // 17
        if 0 <= j < len(self._pal):
            self.set_rgb(self._pal[j])

    # ---------------------------------------------------------------- comum
    def _show(self, rgb):
        self.rgb = tuple(int(c) for c in rgb)
        self.sw.config(bg=hexrgb(self.rgb))
        self.hexvar.set(hexrgb(self.rgb).upper())

    def set_rgb(self, rgb):
        self._show(rgb)
        self.h, self.s, self.v = colorsys.rgb_to_hsv(*[c / 255.0 for c in self.rgb])
        self._draw_wheel()

    def _from_hex(self):
        t = self.hexvar.get().strip().lstrip("#")
        if len(t) == 6:
            try:
                self.set_rgb(tuple(int(t[i:i + 2], 16) for i in (0, 2, 4)))
            except ValueError:
                pass

    def _system(self):
        res = colorchooser.askcolor(color=hexrgb(self.rgb), parent=self)
        if res and res[0]:
            self.set_rgb(tuple(int(c) for c in res[0]))

    def _ok(self):
        self._from_hex()
        self.result = self.rgb
        rec = [hexrgb(self.rgb)] + [c for c in (self.app.cfg.get("recent_colors") or []) if c != hexrgb(self.rgb)]
        self.app.cfg["recent_colors"] = rec[:12]
        try:
            self.app._save_cfg()
        except Exception:
            pass
        self.destroy()


def ask_color(app, initial=None, title=None):
    w = ColorPicker(app, initial, title)
    app.wait_window(w)
    return w.result
