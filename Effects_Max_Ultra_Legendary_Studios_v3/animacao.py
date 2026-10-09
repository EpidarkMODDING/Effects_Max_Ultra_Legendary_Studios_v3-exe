# -*- coding: utf-8 -*-
"""
Leitor de animações do BT3 (.anm e .canm) para cruzar com o efeito aberto.
Estrutura dos eventos e flags conforme o plugin io-sparking-anm (créditos aos autores do plugin):
  • byte 1 = quantidade de eventos; u16 em 2 = quadro final
  • eventos de 16 bytes a partir de 0x94: u64 flags, u16 quadro, u16 índice do hitbox (×4 = offset de 8 floats), u32 ossos
  • Vfx 1 a 6 = bits 1 a 6 do 2º byte das flags (00000010 ... 01000000). Vfx N chama os mini-efeitos do ESTÁGIO N-1.
  • Vfx 7, 8, 9 = bits 5, 6, 7 do 3º byte.
.canm = .anm comprimido com BPE (cabeçalho: u32 tamanho final, u32 tamanho comprimido).
"""
import os, struct
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from lang import tr, class_label, stage_label

BONES = ["waist", "tail", "shank_r", "heel_r", "shank_l", "heel_l", "shoulder_r", "elbow_r", "wrist_r", "shoulder_l",
         "elbow_l", "wrist_l", "neck", "equip1", "equip2", "null", "effect_r", "effect_l", "utility"]
FLAG_NAMES = {
    (0, 0): "Hitbox", (0, 1): "unk 2", (0, 2): "Little kidan (ki blast)", (0, 3): "Linhas de impacto", (0, 4): "Sfx arremesso",
    (0, 5): "Mostrar equip. 1", (0, 6): "Esconder equip. 1", (0, 7): "Hit 2",
    (1, 0): "Hit 1", (1, 1): "Vfx 1", (1, 2): "Vfx 2", (1, 3): "Vfx 3", (1, 4): "Vfx 4", (1, 5): "Vfx 5", (1, 6): "Vfx 6",
    (1, 7): "Adx 1",
    (2, 0): "Sfx 1", (2, 1): "Sfx 2", (2, 2): "Sfx 3", (2, 3): "Sfx 4", (2, 5): "Vfx 7", (2, 6): "Vfx 8", (2, 7): "Vfx 9",
    (3, 0): "Vfx *", (3, 1): "Esconder", (3, 2): "Mostrar", (3, 3): "Esconder hit", (3, 4): "Sfx aceleração",
    (4, 0): "unk 0x100000000", (4, 1): "Dano", (4, 2): "Posição do oponente", (4, 3): "Sfx teleporte", (4, 4): "Sfx espada",
    (4, 5): "Sfx pisão", (4, 6): "Sfx passo", (4, 7): "Adx 2",
    (5, 0): "Sfx descida", (5, 1): "Sfx explosão 1", (5, 2): "Teleporte", (5, 3): "Mostrar equip. 2", (5, 4): "Esconder equip. 2",
    (5, 5): "Vibração", (5, 6): "Tremor de câmera", (5, 7): "Sfx lançamento",
    (6, 0): "Sfx elétrico", (6, 1): "Sfx subida", (6, 2): "Sfx choque", (6, 3): "Sfx giro", (6, 5): "Sfx bloqueio",
    (6, 7): "Sfx explosão 2",
    (7, 0): "Rosto 1", (7, 1): "Rosto 2", (7, 2): "Rosto 3", (7, 3): "Rosto alternativo", (7, 4): "Restaurar rosto"}
VFX_STAGE = {(1, 1): 0, (1, 2): 1, (1, 3): 2, (1, 4): 3, (1, 5): 4, (1, 6): 5, (2, 5): 6, (2, 6): 7, (2, 7): 8}


def bpe_decompress(raw):
    """Descompressor BPE (mesmo algoritmo do plugin io-sparking-anm, reescrito)."""
    outsize, insize = struct.unpack_from("<ii", raw, 0)
    data = raw[8:8 + insize]
    out = bytearray()
    pos = 0
    n = len(data)

    def get():
        nonlocal pos
        if pos >= n:
            return -1
        pos += 1
        return data[pos - 1]
    left, right = bytearray(256), bytearray(256)
    count = get()
    while count >= 0:
        for i in range(256):
            left[i] = i
        c = 0
        while True:
            if count > 127:
                c += count - 127
                count = 0
            if c >= 256:
                break
            for _ in range(count + 1):
                v = get()
                if v < 0 or c >= 256:
                    break
                left[c] = v
                if c != v:
                    v = get()
                    if v < 0:
                        break
                    right[c] = v
                c += 1
            if c >= 256:
                break
            count = get()
            if count < 0:
                break
        hi, lo = get(), get()
        if hi < 0 or lo < 0:
            break
        size = (hi << 8) | lo
        stack = []
        while True:
            if stack:
                c = stack.pop()
            else:
                if size == 0:
                    break
                size -= 1
                c = get()
                if c < 0:
                    break
            if c == left[c]:
                out.append(c)
            else:
                stack.append(right[c])
                stack.append(left[c])
        count = get()
    return bytes(out[:outsize])


def load_anm(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    if path.lower().endswith(".canm"):
        raw = bpe_decompress(raw)
    return parse_anm(raw)


def parse_anm(d):
    """{'frames': quadro final, 'events': [{'frame', 'flags':[(byte,bit)], 'bones':[nomes], 'hitbox':[8 floats]|None}]}"""
    if len(d) < 0x94:
        raise ValueError("animação vazia")
    n = d[1]
    fe = struct.unpack_from("<H", d, 2)[0]
    evs = []
    for e in range(n):
        o = 0x94 + 16 * e
        if o + 16 > len(d):
            break
        flags, frame, hbi, bones = struct.unpack_from("<QHHI", d, o)
        fl = [(b, k) for b in range(8) for k in range(8) if (flags >> (8 * b)) & (1 << k)]
        hb = list(struct.unpack_from("<8f", d, hbi * 4)) if hbi and hbi * 4 + 32 <= len(d) else None
        evs.append({"frame": frame, "flags": fl, "bones": [BONES[i] for i in range(len(BONES)) if bones & (1 << i)],
                    "hitbox": hb})
    evs.sort(key=lambda x: x["frame"])
    return {"frames": fe, "events": evs}


def vfx_calls(anims):
    """Lista de chamadas de efeito ao longo das animações encadeadas (evento 1, 2, 3... continuam o mesmo golpe):
       [(arquivo, quadro_local, quadro_total, estágio, ossos)]"""
    out, base = [], 0
    for name, a in anims:
        for ev in a["events"]:
            for f in ev["flags"]:
                if f in VFX_STAGE:
                    out.append((name, ev["frame"], base + ev["frame"], VFX_STAGE[f], ev["bones"]))
        base += a["frames"]
    return out


class AnimWindow(tk.Toplevel):
    """Abre uma ou mais animações (na ordem do golpe) e mostra quando cada estágio do efeito é chamado."""

    def __init__(self, app, paths=None):
        super().__init__(app)
        self.app, self.lang = app, app.lang
        self.title(tr("anm_title", self.lang))
        self.geometry("1180x720")
        self.anims = []
        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        ttk.Button(top, text=tr("anm_open", self.lang), command=self.open).pack(side="left")
        ttk.Button(top, text=tr("anm_clear", self.lang), command=self.clear).pack(side="left", padx=4)
        self.only_vfx = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text=tr("anm_only_vfx", self.lang), variable=self.only_vfx, command=self.fill).pack(side="left", padx=8)
        ttk.Label(top, text=tr("anm_hint", self.lang), foreground="#8a8f99").pack(side="left", padx=8)
        self.cv = tk.Canvas(self, height=170, bg="#16181d", highlightthickness=0)
        self.cv.pack(fill="x", padx=6)
        self.cv.bind("<Configure>", lambda e: self.draw())
        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True, padx=6, pady=6)
        lf = ttk.Frame(pw)
        self.tv = ttk.Treeview(lf, columns=("file", "frame", "total", "what", "bones", "hit"), show="headings")
        for c, w, t in (("file", 170, "anm_col_file"), ("frame", 60, "anm_col_frame"), ("total", 60, "anm_col_total"),
                        ("what", 300, "anm_col_what"), ("bones", 150, "anm_col_bones"), ("hit", 160, "anm_col_hit")):
            self.tv.column(c, width=w, anchor="w")
            self.tv.heading(c, text=tr(t, self.lang))
        sb = ttk.Scrollbar(lf, command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tv.tag_configure("vfx", foreground="#2ecc71")
        pw.add(lf, weight=3)
        rf = ttk.Frame(pw)
        ttk.Label(rf, text=tr("anm_cross", self.lang), font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.txt = tk.Text(rf, wrap="word", width=52, font=("Segoe UI", 9), padx=8, pady=6)
        self.txt.pack(fill="both", expand=True)
        pw.add(rf, weight=2)
        for p in paths or []:
            self._add(p)
        self.fill()

    def open(self):
        ps = filedialog.askopenfilenames(parent=self, filetypes=[("Animações BT3", "*.anm *.canm"), ("*", "*.*")])
        for p in sorted(ps):
            self._add(p)
        self.fill()

    def _add(self, p):
        try:
            self.anims.append((os.path.basename(p), load_anm(p)))
        except Exception as ex:
            messagebox.showerror(tr("err", self.lang), "%s\n%s" % (os.path.basename(p), ex), parent=self)

    def clear(self):
        self.anims = []
        self.fill()

    def fill(self):
        self.tv.delete(*self.tv.get_children())
        base = 0
        for name, a in self.anims:
            for ev in a["events"]:
                names = [FLAG_NAMES.get(f, "byte%d.bit%d" % f) for f in ev["flags"]]
                is_vfx = any(f in VFX_STAGE for f in ev["flags"])
                if self.only_vfx.get() and not is_vfx and not ev["hitbox"]:
                    continue
                what = ", ".join(n + (" → " + stage_label(VFX_STAGE[f], self.lang) if f in VFX_STAGE else "")
                                 for n, f in zip(names, ev["flags"]))
                hb = " ".join("%g" % round(x, 2) for x in ev["hitbox"]) if ev["hitbox"] else ""
                self.tv.insert("", "end", values=(name, ev["frame"], base + ev["frame"], what, ", ".join(ev["bones"]), hb),
                               tags=("vfx",) if is_vfx else ())
            base += a["frames"]
        self.cross()
        self.draw()

    def cross(self):
        t = self.txt
        t.delete("1.0", "end")
        eff = self.app.eff
        calls = vfx_calls(self.anims)
        if not self.anims:
            t.insert("end", tr("anm_none", self.lang))
            return
        stages = {}
        for name, f, tot, st, bones in calls:
            stages.setdefault(st, []).append((name, f, tot, bones))
        ms = eff.all_minis() if eff else []
        used = set(m.get("invoke") for m in ms)
        for st in sorted(set(stages) | used):
            parts = [(i, m) for i, m in enumerate(ms) if m.get("invoke") == st]
            t.insert("end", stage_label(st, self.lang) + "  (Vfx %d)\n" % (st + 1))
            if st in stages:
                for name, f, tot, bones in stages[st]:
                    t.insert("end", "   " + tr("anm_called", self.lang, f=f, n=name, t=tot,
                                                 b=", ".join(bones) or "—") + "\n")
            else:
                t.insert("end", "   ⚠ " + tr("anm_never", self.lang) + "\n")
            for i, m in parts[:30]:
                d = m.param[4] + m.param[5]
                when = ""
                if st in stages and d:
                    when = "  ≈ " + ", ".join(str(tot + d) for _, _, tot, _ in stages[st][:3])
                t.insert("end", "      #%d %s · %s %d%s\n" % (i, class_label(m.type, self.lang), tr("anm_delay", self.lang), d, when))
            if st in stages and not parts:
                t.insert("end", "      " + tr("anm_empty", self.lang) + "\n")
            t.insert("end", "\n")

    def draw(self):
        c = self.cv
        c.delete("all")
        if not self.anims:
            return
        W = max(200, c.winfo_width())
        total = sum(a["frames"] for _, a in self.anims) or 1
        x0, x1 = 90, W - 10
        sx = lambda f: x0 + (x1 - x0) * f / float(total)
        base = 0
        cols = ("#2b3040", "#24293a")
        for k, (name, a) in enumerate(self.anims):
            c.create_rectangle(sx(base), 0, sx(base + a["frames"]), 170, fill=cols[k % 2], outline="")
            c.create_text(sx(base) + 4, 8, text="%s (%d)" % (name, a["frames"]), anchor="w", fill="#8a8f99", font=("Segoe UI", 8))
            base += a["frames"]
        palette = ("#e8c34a", "#4a90d9", "#5cb85c", "#d9534f", "#b07cd8", "#4ac6c6", "#f08a4b", "#c8ccd4", "#ff6f91")
        for st in range(9):
            y = 26 + st * 15
            c.create_text(4, y, text=stage_label(st, self.lang, num=False)[:12], anchor="w", fill=palette[st], font=("Segoe UI", 8))
        for name, f, tot, st, bones in vfx_calls(self.anims):
            y = 26 + st * 15
            x = sx(tot)
            c.create_polygon(x, y - 6, x + 6, y, x, y + 6, x - 6, y, fill=palette[st], outline="#000000")
        base = 0
        for name, a in self.anims:
            for ev in a["events"]:
                if (4, 1) in ev["flags"] or (1, 0) in ev["flags"]:
                    c.create_line(sx(base + ev["frame"]), 160, sx(base + ev["frame"]), 168, fill="#ff4d6d")
                if ev["hitbox"]:
                    c.create_rectangle(sx(base + ev["frame"]) - 3, 150, sx(base + ev["frame"]) + 3, 156, outline="#ffa94d")
            base += a["frames"]
        c.create_text(4, 164, text=tr("anm_hits", self.lang), anchor="w", fill="#ff4d6d", font=("Segoe UI", 8))
