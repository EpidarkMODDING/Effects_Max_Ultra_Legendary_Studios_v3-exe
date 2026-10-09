# -*- coding: utf-8 -*-
"""Editor hexadecimal: clique num byte e veja, à direita, tudo o que o programa sabe sobre ele."""
import os
import tkinter as tk
from tkinter import ttk, messagebox
from bt3eff_core import Effect, PakError, pak_pack, dbt_info
import hexdocs
from lang import tr


def describe_files(eff):
    """[(índice, nome, anotador, descrição do arquivo)]"""
    out, i = [], 0
    pre_info = {0: ("00_ — modelos 3D (.pak interno)", hexdocs.unknown(
        "Arquivo 00 do efeito. Quando existe, é um .pak com elementos de modelo 3D (pedras, mãos do Androide 16, fantasmas do Gotenks), "
        "um Model Effect (DBE, como o anel do Gotenks) ou um DBT. Estrutura interna não mapeada pelo programa.")),
        1: ("01_ — vazio", hexdocs.unknown("Arquivo 01: sempre vazio no BT3 (no BT2 era usado para câmeras).")),
        2: ("02_ — cena (X/Y/Z por mapa)", hexdocs.scene)}
    for k, p in enumerate(eff.pre):
        name, an = pre_info.get(k, ("%02d_" % k, hexdocs.unknown("Sem informação.")))
        out.append((i, name, an)); i += 1
    out.append((i, "%02d_ — parâmetros (03_.dat)" % i if eff.pre else "%02d_ — parâmetros da aura" % i, hexdocs.params)); i += 1
    for c in eff.cats:
        for d in c.dbts:
            out.append((i, "%02d_ — DBT da classe %02X" % (i, c.type), hexdocs.dbt)); i += 1
        for m in c.minis:
            for j, f in enumerate(m.files):
                if c.type == 0x02:
                    out.append((i, "%02d_ — classe 02 (saídas de luz)" % i, hexdocs.anim02))
                elif c.type == 0x0E:
                    out.append((i, "%02d_ — V00 (classe 0E)" % i, hexdocs.v00))
                elif j == getattr(m, "shader_idx", 1):
                    out.append((i, "%02d_ — shader da classe %02X" % (i, c.type), hexdocs.shader))
                elif c.type == 0x05:
                    out.append((i, "%02d_ — forma (shape) da classe 05" % i, hexdocs.shape05))
                else:
                    out.append((i, "%02d_ — forma (shape) da classe %02X" % (i, c.type), hexdocs.unknown(
                        "Arquivo de forma da classe %02X. Define o formato/animação do mini efeito; a estrutura ainda não foi documentada." % c.type)))
                i += 1
    return out


def guess_annotator(data, name=""):
    n = os.path.basename(name).lower()
    if data[:4] == b"V000":
        return "V00", hexdocs.v00
    if len(data) == 2816:
        return "02_.dat (cena)", hexdocs.scene
    if len(data) in (192, 320):
        return "shader", hexdocs.shader
    if len(data) % 120 in (16,) and len(data) == 1216:
        return "classe 02", hexdocs.anim02
    if dbt_info(data):
        return "DBT", hexdocs.dbt
    if len(data) >= 64 and data[4] and len(data) >= 64 + 32 * data[4]:
        return "parâmetros (03_.dat)", hexdocs.params
    return "desconhecido", hexdocs.unknown("O programa não reconheceu o tipo deste arquivo.")


class HexWindow(tk.Toplevel):
    def __init__(self, app, external=None, focus=None):
        super().__init__(app)
        self.app, self.lang = app, app.lang
        self.external = external
        self.title(tr("hex_title", self.lang))
        self.geometry("1180x660")
        self.data, self.annot, self.cur, self.fname = b"", [], None, ""
        top = ttk.Frame(self, padding=4)
        top.pack(fill="x")
        self.files = []
        if external:
            ttk.Label(top, text=os.path.basename(external)).pack(side="left")
        else:
            self.files = describe_files(app.eff)
            self.cb = ttk.Combobox(top, state="readonly", width=48, values=[n for _, n, _ in self.files])
            self.cb.pack(side="left")
            self.cb.bind("<<ComboboxSelected>>", lambda e: self._load(self.cb.current()))
        ttk.Button(top, text=tr("apply", self.lang), command=self._apply).pack(side="left", padx=6)
        ttk.Label(top, text=tr("hex_tip", self.lang)).pack(side="left", padx=8)
        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True)
        tf = ttk.Frame(body)
        self.text = tk.Text(tf, font=("Consolas", 10), wrap="none", undo=True, width=78)
        sb = ttk.Scrollbar(tf, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.text.tag_configure("field", background="#f0a020", foreground="#000000")
        body.add(tf, weight=3)
        right = ttk.PanedWindow(body, orient="vertical")
        df = ttk.Frame(right)
        self.detail = tk.Text(df, wrap="word", font=("Segoe UI", 10), padx=10, pady=8, width=52, height=12)
        dsb = ttk.Scrollbar(df, command=self.detail.yview)
        self.detail.configure(yscrollcommand=dsb.set)
        self.detail.pack(side="left", fill="both", expand=True)
        dsb.pack(side="right", fill="y")
        self.detail.tag_configure("h1", font=("Segoe UI", 12, "bold"))
        self.detail.tag_configure("h2", font=("Segoe UI", 10, "bold"))
        self.detail.tag_configure("dim", foreground="#777777")
        self._df = df
        mf = ttk.Frame(right)
        self.info = ttk.Treeview(mf, columns=("off", "len", "txt", "val"), show="headings")
        for c, w in (("off", 64), ("len", 40), ("txt", 330), ("val", 120)):
            self.info.column(c, width=w, anchor="w")
        self.info.heading("off", text="Offset")
        self.info.heading("len", text="Bytes")
        self.info.heading("txt", text=tr("hex_meaning", self.lang))
        self.info.heading("val", text=tr("hex_value", self.lang))
        self.info.tag_configure("cur", background="#f0a020", foreground="#000000")
        msb = ttk.Scrollbar(mf, command=self.info.yview)
        self.info.configure(yscrollcommand=msb.set)
        self.info.pack(side="left", fill="both", expand=True)
        msb.pack(side="right", fill="y")
        self.info.bind("<<TreeviewSelect>>", self._jump)
        right.add(mf, weight=3)
        right.add(df, weight=2)
        self.right = right
        self._syncing = False
        body.add(right, weight=2)
        self.text.bind("<ButtonRelease-1>", self._where)
        self.text.bind("<KeyRelease>", self._where)
        if external:
            with open(external, "rb") as fh:
                self.data = fh.read()
            kind, an = guess_annotator(self.data, external)
            self.fname = "%s (%s)" % (os.path.basename(external), kind)
            self._show(an)
        elif self.files:
            k = len(app.eff.pre)
            if focus:
                k = next((n for n, (fi, _, _) in enumerate(self.files) if fi == focus[0]), k)
            self.cb.current(k)
            self._load(k)
            if focus:
                self.goto(focus[1])

    def goto(self, o):
        o = max(0, min(o, len(self.data) - 1))
        line, col = o // 16 + 1, 8 + (o % 16) * 3
        self.text.mark_set("insert", "%d.%d" % (line, col))
        self.text.see("insert")
        self._where()

    # ---- carregar e mostrar
    def _load(self, k):
        self.cur = k
        self.data = self.app.eff.file_list()[self.files[k][0]]
        self.fname = self.files[k][1]
        self._show(self.files[k][2])

    def _show(self, annotator):
        self.annotator = annotator
        self.annot = sorted(annotator(self.data), key=lambda t: (t[0], t[1])) if annotator else []
        lines = []
        for o in range(0, len(self.data), 16):
            chunk = self.data[o:o + 16]
            asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append("%06X: %-47s  |%s" % (o, " ".join("%02X" % b for b in chunk), asc))
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.info.delete(*self.info.get_children())
        for n, a in enumerate(self.annot):
            self.info.insert("", "end", iid=str(n), values=("0x%04X" % a[0], a[1], a[3], hexdocs.value_short(self.data, a)))
        self._detail_file()

    def _detail_file(self):
        d = self.detail
        d.config(state="normal")
        d.delete("1.0", "end")
        d.insert("end", self.fname + "\n", "h1")
        d.insert("end", "%d bytes\n\n" % len(self.data), "dim")
        d.insert("end", tr("hex_click", self.lang))
        d.config(state="disabled")

    # ---- byte selecionado
    def _offset_at_cursor(self):
        line, col = [int(x) for x in self.text.index("insert").split(".")]
        if col < 8 or col > 8 + 47:
            return None
        return (line - 1) * 16 + (col - 8) // 3

    def _ann_for(self, o):
        best = None
        for a in self.annot:
            if a[0] <= o < a[0] + a[1] and (best is None or a[1] <= best[1]):
                best = a
        return best

    def _highlight(self, start, size):
        self.text.tag_remove("field", "1.0", "end")
        for o in range(start, min(start + size, len(self.data))):
            line, col = o // 16 + 1, 8 + (o % 16) * 3
            self.text.tag_add("field", "%d.%d" % (line, col), "%d.%d" % (line, col + 2))

    def _where(self, _=None):
        o = self._offset_at_cursor()
        if o is None or o >= len(self.data):
            return
        a = self._ann_for(o)
        d = self.detail
        d.config(state="normal")
        d.delete("1.0", "end")
        d.insert("end", self.fname + "\n", "dim")
        d.insert("end", "Offset 0x%04X  ·  byte = %02X (%d)\n\n" % (o, self.data[o], self.data[o]), "dim")
        if a is None:
            d.insert("end", tr("hex_unknown", self.lang) + "\n", "h2")
            self.text.tag_remove("field", "1.0", "end")
        else:
            d.insert("end", a[3] + "\n\n", "h1")
            d.insert("end", a[4] + "\n\n")
            d.insert("end", hexdocs.value_text(self.data, a, o))
            self._highlight(a[0], a[1])
            self._mark_row(a)
        d.config(state="disabled")

    def _mark_row(self, a):
        """Destaca no glossário a linha do campo clicado nos bytes."""
        for iid in self.info.tag_has("cur"):
            self.info.item(iid, tags=())
        try:
            n = self.annot.index(a)
        except ValueError:
            return
        self.info.item(str(n), tags=("cur",))
        self.info.see(str(n))
        if not self._syncing:
            self._syncing = True
            self.info.selection_set(str(n))
            self.after_idle(lambda: setattr(self, "_syncing", False))

    def _jump(self, _=None):
        if self._syncing:
            return
        s = self.info.selection()
        if not s or not s[0].isdigit():
            return
        o = self.annot[int(s[0])][0]
        line, col = o // 16 + 1, 8 + (o % 16) * 3
        self.text.mark_set("insert", "%d.%d" % (line, col))
        self.text.see("insert")
        self._where()

    # ---- aplicar edição
    def _parse(self):
        out = bytearray()
        for ln in self.text.get("1.0", "end").splitlines():
            if ":" not in ln:
                continue
            for tok in ln.split(":", 1)[1].split("|")[0].split():
                out.append(int(tok, 16))
        return bytes(out)

    def _apply(self):
        try:
            new = self._parse()
        except ValueError as ex:
            messagebox.showerror(tr("err", self.lang), str(ex), parent=self)
            return
        if self.external:
            with open(self.external, "wb") as fh:
                fh.write(new)
            self.data = new
            self._show(self.annotator)
            messagebox.showinfo(tr("ok", self.lang), tr("hex_saved", self.lang), parent=self)
            return
        files = self.app.eff.file_list()
        files[self.files[self.cur][0]] = new
        try:
            neweff = Effect.from_bytes(pak_pack(list(files)))
        except PakError as ex:
            messagebox.showerror(tr("err", self.lang), tr("hex_invalid", self.lang) + "\n" + str(ex), parent=self)
            return
        self.app.snapshot(tr("hex_title", self.lang))
        old = self.app.eff
        neweff.kind = old.kind
        if len(neweff.all_minis()) == len(old.all_minis()):
            for x, y in zip(neweff.all_minis(), old.all_minis()):
                x.group = y.group
        self.app.eff = neweff
        self.app.changed()
        self.files = describe_files(neweff)
        self.cb["values"] = [n for _, n, _ in self.files]
        self._load(self.cur)
