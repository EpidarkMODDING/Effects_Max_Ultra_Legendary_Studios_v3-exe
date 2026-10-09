# -*- coding: utf-8 -*-
"""
Effects Max Ultra Legendary Studios v1.6 — interface gráfica (antigo BT3 Effect Studio)
Requer Python 3.8+ (tkinter já vem junto no Windows).
Uso: python Effects_Max_Ultra_Legendary_Studios.py
"""
import os, sys, json, shutil, struct
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox, colorchooser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bt3eff_core import recolor_dbt_imgs
from bt3eff_core import (Effect, PakError, SUPPORT_NAME, CLASS_NAMES, container_entries, container_get,
                         container_put, scene_table, scene_set, SCENE_MAPS, SCENE_EVENTS, MAP_NAMES,
                         scene_row, scene_set3)
from lang import LANGS, PRESET_GROUPS, tr, group_label, class_label, stage_label, dis_label, ori_label, short
from recursos import Resources

# no .exe (PyInstaller) os arquivos do usuário (recursos.dat, config.json, pastas) ficam ao lado do executável
HERE = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")
TEMPLATES = os.path.join(HERE, "modelos")
SCENES = os.path.join(HERE, "cenas")
EXPLOSION = "explosao_vfx5.pak"
RES = Resources(HERE)
EXTRAS = os.path.join(HERE, "extras")
SIZE_WARN_KB = 200
PARAM_FIELDS = ["dbt", "tex", "delay_a", "delay_b", "dur_a", "dur_b", "invoke",
                "pos_x", "pos_y", "pos_z", "size1", "size2", "size3", "time1", "time2", "unk30"]
INT_FIELDS = {"dbt", "tex", "delay_a", "delay_b", "dur_a", "dur_b", "invoke", "unk9", "unkA", "unkB"}


def rgb_hex(rgba):
    r, g, b = [max(0, min(255, int(round(v)))) for v in rgba[:3]]
    return "#%02x%02x%02x" % (r, g, b)


class MiniList(ttk.Frame):
    """Lista de mini-efeitos com caixas de marcar (ordem de colunas da documentação Madeirada parte 3)."""
    COLS = ("chk", "idx", "tex", "cls", "stage", "dis", "ori")
    TIPS = {"#1": "tip_chk", "#2": "tip_idx", "#3": "tip_tex", "#4": "tip_cls", "#5": "tip_stage", "#6": "tip_dis", "#7": "tip_ori"}

    def __init__(self, master, app, on_select=None, context=True):
        super().__init__(master)
        self.app, self.on_select = app, on_select
        self.on_check = None
        self.minis, self.checked = [], set()
        self.tree = ttk.Treeview(self, columns=self.COLS, show="headings", selectmode="browse", height=12)
        widths = (30, 34, 84, 168, 136, 176, 176)
        for c, w in zip(self.COLS, widths):
            self.tree.column(c, width=w, minwidth=30, anchor="center", stretch=(c in ("cls", "ori")))
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb.set, xscrollcommand=hb.set)
        hb.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Button-1>", self._click)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.on_select and self.on_select(self.selected()))
        self.tree.bind("<Motion>", self._motion)
        self.tree.bind("<Leave>", lambda e: self._tip_hide())
        if context:
            for ev in ("<Button-3>", "<Button-2>"):
                self.tree.bind(ev, self._context)
        self._tip, self._tip_col = None, None

    # ---- dica ao passar o mouse no cabeçalho
    def _motion(self, ev):
        col = self.tree.identify_column(ev.x) if self.tree.identify_region(ev.x, ev.y) == "heading" else None
        if col == self._tip_col:
            if self._tip is not None:
                self._tip.geometry("+%d+%d" % (ev.x_root + 14, ev.y_root + 18))
            return
        self._tip_hide()
        self._tip_col = col
        key = self.TIPS.get(col)
        if not key:
            return
        tw = tk.Toplevel(self)
        tw.wm_overrideredirect(True)
        tk.Label(tw, text=tr(key, self.app.lang), bg="#ffffe0", fg="#000000", relief="solid", bd=1,
                 padx=6, pady=2).pack()
        tw.geometry("+%d+%d" % (ev.x_root + 14, ev.y_root + 18))
        self._tip = tw

    def _tip_hide(self):
        if self._tip is not None:
            self._tip.destroy()
        self._tip, self._tip_col = None, None

    # ---- botão direito
    def _context(self, ev):
        iid = self.tree.identify_row(ev.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        m = self.minis[int(iid)]
        L = self.app.lang
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=tr("ctx_textures", L), command=lambda: self.app.open_textures(mini=m),
                         state="normal" if m.type != 0x00 else "disabled")
        menu.add_command(label=tr("ctx_hex", L), command=lambda: self.app.open_hex(mini=m),
                         state="normal" if m.files else "disabled")
        menu.add_command(label=tr("ctx_hex_params", L), command=lambda: self.app.open_hex(mini=m, params=True))
        menu.add_command(label=tr("ctx_3d", L), command=lambda: self.app.open_3d(mini=m),
                         state="normal" if m.type != 0x00 else "disabled")
        menu.add_separator()
        menu.add_command(label=tr("ctx_mark", L), command=lambda: self._toggle(iid))
        try:
            menu.tk_popup(ev.x_root, ev.y_root)
        finally:
            menu.grab_release()

    def headings(self):
        L = self.app.lang
        for c in self.COLS:
            self.tree.heading(c, text=tr("col_" + c, L))

    def fill(self, effect):
        self.tree.delete(*self.tree.get_children())
        self.minis = effect.all_minis() if effect else []
        self.checked &= set(id(m) for m in self.minis)
        L = self.app.lang
        for i, m in enumerate(self.minis):
            has_dbt = m.type != 0x00
            vals = ("☑" if id(m) in self.checked else "☐", i,
                    "%d/%d" % (m.get("dbt"), m.get("tex")) if has_dbt else "—",
                    class_label(m.type, L), short(stage_label(m.get("invoke"), L)),
                    dis_label(m.param[9], L) if has_dbt else "—", short(ori_label(m.param[10], L)) if has_dbt else "—")
            self.tree.insert("", "end", iid=str(i), values=vals)

    def _toggle(self, iid):
        m = self.minis[int(iid)]
        if id(m) in self.checked:
            self.checked.discard(id(m))
        else:
            self.checked.add(id(m))
        self.tree.set(iid, "chk", "☑" if id(m) in self.checked else "☐")
        if self.on_check:
            self.on_check()

    def _click(self, ev):
        if self.tree.identify_region(ev.x, ev.y) != "cell" or self.tree.identify_column(ev.x) != "#1":
            return
        iid = self.tree.identify_row(ev.y)
        if not iid:
            return
        self._toggle(iid)
        return "break"

    def set_all(self, on, pred=None):
        for m in self.minis:
            if pred and not pred(m):
                continue
            (self.checked.add if on else self.checked.discard)(id(m))
        for i, m in enumerate(self.minis):
            self.tree.set(str(i), "chk", "☑" if id(m) in self.checked else "☐")
        if self.on_check:
            self.on_check()

    def marked(self):
        return [m for m in self.minis if id(m) in self.checked]

    def selected(self):
        s = self.tree.selection()
        return self.minis[int(s[0])] if s else None

    def groups(self):
        """Estágios de invocação presentes (em ordem)."""
        return sorted(set(m.get("invoke") for m in self.minis))


class ScrollFrame(ttk.Frame):
    """Área com barra de rolagem vertical: nada fica escondido em telas pequenas."""

    def __init__(self, master, padding=10):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, padding=padding)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        for w in (self.canvas, self.inner):
            w.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
            w.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, ev):
        if self.inner.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-ev.delta / 120) or (-1 if ev.delta > 0 else 1), "units")


class GroupChips(ttk.Frame):
    """Caixas de marcar por estágio de invocação: marcar/desmarcar vários de uma vez."""

    def __init__(self, master, app, lst, per_row=4):
        super().__init__(master)
        self.app, self.lst, self.per_row = app, lst, per_row
        self.vars = {}
        old = lst.on_check
        lst.on_check = self.sync

    def rebuild(self):
        for w in self.winfo_children():
            w.destroy()
        self.vars = {}
        stages = self.lst.groups()
        if not stages:
            return
        ttk.Label(self, text=self.app.t("mark_groups")).grid(row=0, column=0, sticky="w", padx=(0, 6))
        for i, g in enumerate(stages):
            n = sum(1 for m in self.lst.minis if m.get("invoke") == g)
            v = tk.BooleanVar(value=False)
            ttk.Checkbutton(self, text="%s (%d)" % (stage_label(g, self.app.lang, num=False), n), variable=v,
                            command=lambda g=g, v=v: self.lst.set_all(v.get(), lambda m: m.get("invoke") == g)
                            ).grid(row=i // self.per_row, column=1 + i % self.per_row, sticky="w", padx=3)
            self.vars[g] = v
        self.sync()

    def sync(self):
        for g, v in self.vars.items():
            ms = [m for m in self.lst.minis if m.get("invoke") == g]
            v.set(bool(ms) and all(id(m) in self.lst.checked for m in ms))
        cb = getattr(self.app, "on_marks_changed", None)
        if cb and self.lst is getattr(self.app, "list", None):
            cb()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = self._load_cfg()
        self.lang = self.cfg.get("lang", "pt")
        self.eff, self.path, self.dirty, self.history = None, None, False, []
        self.src, self.src_path = None, None
        self.keep_sat = tk.BooleanVar(value=False)
        self.imp_alpha = tk.BooleanVar(value=True)
        self.imp_depth = tk.BooleanVar(value=True)
        self.tex_color = tk.BooleanVar(value=True)
        self.beh_tpl, self.beh_tpl_path = None, None
        self.scale = float(self.cfg.get("scale", 1.0))
        self._set_icon()
        self.apply_theme()
        self.splash()
        if "lang" not in self.cfg:
            self.first_run()
        self.apply_display(first=True)
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.bind("<Control-z>", lambda e: self.undo())
        self.bind("<Control-y>", lambda e: self.redo())
        self.bind("<Control-Z>", lambda e: self.redo())
        self.redo_stack = []
        self.bind("<Control-s>", lambda e: self.save())
        self.build_ui()

    # ------------------------------------------------------------ config
    def _load_cfg(self):
        try:
            with open(CONFIG, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_cfg(self):
        try:
            with open(CONFIG, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f)
        except Exception:
            pass

    def t(self, key, **kw):
        return tr(key, self.lang, **kw)

    # ------------------------------------------------------------ ícone, capa e modo noturno
    def _photo(self, data):
        import base64
        try:
            return tk.PhotoImage(data=base64.b64encode(data).decode())
        except tk.TclError:
            return None

    def _set_icon(self):
        data = RES.get("arte", "icone64.png")
        if data:
            img = self._photo(data)
            if img is not None:
                self._icon_img = img
                try:
                    self.iconphoto(True, img)
                except tk.TclError:
                    pass
        ico = os.path.join(HERE, "icone.ico")
        if os.name == "nt" and os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except tk.TclError:
                pass

    def splash(self):
        """Capa ao abrir: fica na tela até apertar Enter (ou clicar)."""
        data = RES.get("arte", "capa.png")
        img = self._photo(data) if data else None
        if img is None:
            return
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        k = 1
        while img.width() // k > sw * 0.85 or img.height() // k > sh * 0.85:
            k += 1
        if k > 1:
            img = img.subsample(k, k)
        self._splash_img = img
        self.withdraw()
        w = tk.Toplevel(self)
        w.overrideredirect(True)
        x, y = (sw - img.width()) // 2, (sh - img.height()) // 2
        w.geometry("%dx%d+%d+%d" % (img.width(), img.height(), x, y))
        tk.Label(w, image=img, bd=0).pack()
        done = tk.BooleanVar(value=False)
        for ev in ("<Return>", "<KP_Enter>", "<Button-1>", "<Escape>"):
            w.bind(ev, lambda e: done.set(True))
        w.focus_force()
        w.grab_set()
        self.wait_variable(done)
        w.destroy()
        self.deiconify()

    DARK = {"bg": "#1f2126", "fg": "#e6e6e6", "field": "#2b2e35", "sel": "#3d6fb5", "btn": "#30343c", "border": "#3a3d44"}

    def apply_theme(self):
        dark = bool(self.cfg.get("dark"))
        st = ttk.Style(self)
        if not hasattr(self, "_theme0"):
            self._theme0 = st.theme_use()
        if dark:
            c = self.DARK
            try:
                st.theme_use("clam")
            except tk.TclError:
                pass
            for w in ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton", "TLabelframe", "TLabelframe.Label", "TPanedwindow"):
                st.configure(w, background=c["bg"], foreground=c["fg"])
            st.configure("TButton", background=c["btn"], foreground=c["fg"], bordercolor=c["border"])
            st.map("TButton", background=[("active", c["sel"])])
            st.configure("TMenubutton", background=c["btn"], foreground=c["fg"])
            st.configure("TNotebook", background=c["bg"], bordercolor=c["border"])
            st.configure("TNotebook.Tab", background=c["btn"], foreground=c["fg"], padding=(6, 3))
            st.map("TNotebook.Tab", background=[("selected", c["sel"])])
            for w in ("TEntry", "TCombobox", "TSpinbox"):
                st.configure(w, fieldbackground=c["field"], foreground=c["fg"], background=c["btn"])
            st.map("TCombobox", fieldbackground=[("readonly", c["field"])], foreground=[("readonly", c["fg"])])
            st.configure("Treeview", background=c["field"], fieldbackground=c["field"], foreground=c["fg"])
            st.configure("Treeview.Heading", background=c["btn"], foreground=c["fg"])
            st.map("Treeview", background=[("selected", c["sel"])])
            st.map("TCheckbutton", background=[("active", c["bg"])])
            st.map("TRadiobutton", background=[("active", c["bg"])])
            self.configure(bg=c["bg"])
            for k, v in (("*Background", c["bg"]), ("*Foreground", c["fg"]), ("*Text.Background", c["field"]),
                         ("*Canvas.Background", c["bg"]), ("*Menu.Background", c["btn"]), ("*Menu.Foreground", c["fg"]),
                         ("*TCombobox*Listbox.Background", c["field"]), ("*TCombobox*Listbox.Foreground", c["fg"]),
                         ("*insertBackground", c["fg"])):
                self.option_add(k, v)
        else:
            try:
                st.theme_use(self._theme0)
            except tk.TclError:
                pass

    def toggle_dark(self):
        self.cfg["dark"] = not self.cfg.get("dark")
        self._save_cfg()
        if not self.cfg["dark"]:
            messagebox.showinfo(self.t("app_title"), self.t("dark_restart"))
        self.apply_theme()
        self.build_ui()

    def show_image(self, key, title=""):
        """Imagem ilustrativa de um formato/extra/aura (resources: imagens/mapa.json)."""
        import json as _json
        try:
            mp = _json.loads(RES.get("imagens", "mapa.json").decode("utf-8"))
        except Exception:
            mp = {}
        fn = self._img_file(key, mp)
        data = RES.get("imagens", fn) if fn else None
        img = self._photo(data) if data else None
        if img is None:
            messagebox.showinfo(self.t("app_title"), self.t("no_image"))
            return
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        k = 1
        while img.width() // k > sw * 0.9 or img.height() // k > sh * 0.82:
            k += 1
        if k > 1:
            img = img.subsample(k, k)
        w = tk.Toplevel(self)
        w.title(title or key.split("/")[-1].replace(".pak", ""))
        w.transient(self)
        lb = tk.Label(w, image=img, bd=0)
        lb.image = img
        lb.pack()
        ttk.Button(w, text=self.t("close"), command=w.destroy).pack(pady=6)
        w.bind("<Escape>", lambda e: w.destroy())
        w.update_idletasks()
        ww, wh = w.winfo_reqwidth(), w.winfo_reqheight()
        w.geometry("+%d+%d" % (max(0, (sw - ww) // 2), max(0, (sh - wh) // 2)))

    # ---- imagem ao passar o mouse (formatos, pré-disparos, complementares, auras)
    def _image_for(self, key, max_w=440, max_h=330):
        import json as _json
        cache = self.__dict__.setdefault("_hover_cache", {})
        if key in cache:
            return cache[key]
        try:
            mp = _json.loads(RES.get("imagens", "mapa.json").decode("utf-8"))
        except Exception:
            mp = {}
        fn = self._img_file(key, mp)
        data = RES.get("imagens", fn) if fn else None
        img = self._photo(data) if data else None
        if img is not None:
            k = 1
            while img.width() // k > max_w or img.height() // k > max_h:
                k += 1
            if k > 1:
                img = img.subsample(k, k)
        cache[key] = img
        return img

    def show_hover(self, key, x, y):
        img = self._image_for(key) if key else None
        if img is None:
            self.hide_hover()
            return
        w = getattr(self, "_hover", None)
        if w is None or not w.winfo_exists():
            w = tk.Toplevel(self)
            w.overrideredirect(True)
            try:
                w.attributes("-topmost", True)
            except tk.TclError:
                pass
            w.lbl = tk.Label(w, bd=2, relief="solid", bg="#000000")
            w.lbl.pack()
            self._hover = w
        w.lbl.config(image=img)
        w.lbl.image = img
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        if x + img.width() + 10 > sw:
            x = max(0, x - img.width() - 40)
        y = max(0, min(y, sh - img.height() - 10))
        w.geometry("+%d+%d" % (x, y))
        w.deiconify()
        w.lift()

    def hide_hover(self):
        w = getattr(self, "_hover", None)
        if w is not None and w.winfo_exists():
            w.withdraw()

    def _menu_hover(self, e):
        path = str(e.widget)
        try:
            i = self.tk.call(path, "index", "active")
            if i in ("none", "", None):
                self.hide_hover()
                return
            cmd = str(self.tk.call(path, "entrycget", i, "-command"))
        except tk.TclError:
            self.hide_hover()
            return
        key = getattr(self, "_hover_cmds", {}).get(cmd)
        if not key:
            self.hide_hover()
            return
        try:
            x = int(self.tk.call("winfo", "rootx", path)) + int(self.tk.call("winfo", "width", path)) + 8
        except tk.TclError:
            x = self.winfo_pointerx() + 30
        self.show_hover(key, x, self.winfo_pointery() - 40)

    def hover_bind(self, widget, key):
        """Mostra a imagem ilustrativa ao lado do item enquanto o mouse estiver em cima dele."""
        if not self.has_image(key):
            return
        widget.bind("<Enter>", lambda e: self.show_hover(key, widget.winfo_rootx() + widget.winfo_width() + 12,
                                                         widget.winfo_rooty() - 20), add="+")
        widget.bind("<Leave>", lambda e: self.hide_hover(), add="+")

    def has_image(self, key):
        import json as _json
        try:
            return bool(self._img_file(key, _json.loads(RES.get("imagens", "mapa.json").decode("utf-8"))))
        except Exception:
            return False

    @staticmethod
    def _img_file(key, mp):
        """Imagem de um item. Sem imagem própria, usa a do mesmo ataque na outra lista
        (pré-disparo ↔ disparo)."""
        if not key:
            return None
        if key in mp:
            return mp[key]
        head, _, rest = key.partition("/")
        swap = {"pre_disparo": "modelos", "modelos": "pre_disparo"}.get(head)
        if swap and swap + "/" + rest in mp:
            return mp[swap + "/" + rest]
        return None

    # ------------------------------------------------------------ menus em árvore (grupos de formatos)
    def fill_tree_menu(self, menu, names, callback, img_prefix=None):
        """names: caminhos 'Grupo/Subgrupo/Nome.pak' → submenus aninhados.
           img_prefix: com ele, passar o mouse num item mostra a imagem ilustrativa ao lado do menu."""
        tree = {}
        for n in names:
            node = tree
            parts = n.split("/")
            for p in parts[:-1]:
                node = node.setdefault(p + "/", {})
            node[parts[-1]] = n
        def build(m, node):
            keys = {}
            for k in sorted([k for k in node if k.endswith("/")], key=str.lower):
                sub = tk.Menu(m, tearoff=0)
                build(sub, node[k])
                m.add_cascade(label=k[:-1], menu=sub)
            for k in sorted([k for k in node if not k.endswith("/")], key=str.lower):
                m.add_command(label=os.path.splitext(k)[0], command=lambda n=node[k]: (self.hide_hover(), callback(n)))
                keys[m.index("end")] = node[k]
            if img_prefix:
                # o Tk usa CÓPIAS dos submenus ao abrir; por isso a imagem é achada pelo comando do item
                # (igual na cópia) numa ligação global, e não por uma ligação no menu original
                hm = self.__dict__.setdefault("_hover_cmds", {})
                for i, n in keys.items():
                    try:
                        hm[str(m.entrycget(i, "command"))] = img_prefix + "/" + n
                    except tk.TclError:
                        pass
                if not getattr(self, "_hover_bound", False):
                    self.bind_all("<<MenuSelect>>", self._menu_hover, add="+")
                    self.bind_class("Menu", "<Unmap>", lambda e: self.hide_hover(), add="+")
                    self._hover_bound = True
        build(menu, tree)

    def tree_button(self, parent, sub, callback, width=34):
        """Botão que abre o menu em árvore de uma pasta de recursos e mostra a escolha."""
        var = tk.StringVar(value=self.t("choose"))
        box = ttk.Frame(parent)
        mb = ttk.Menubutton(box, textvariable=var, width=width)
        mb.pack(side="left")
        chosen = {"key": None}
        ib = ttk.Button(box, text="🖼", width=3, state="disabled",
                        command=lambda: chosen["key"] and self.show_image(chosen["key"], var.get()))
        ib.pack(side="left", padx=2)
        menu = tk.Menu(mb, tearoff=0)
        def pick(name):
            var.set(os.path.splitext(name)[0].replace("/", " › "))
            chosen["key"] = sub + "/" + name
            ib.config(state="normal" if self.has_image(chosen["key"]) else "disabled")
            callback(name)
        self.fill_tree_menu(menu, RES.list(sub), pick, img_prefix=sub)
        mb["menu"] = menu
        return box

    def first_run(self):
        """Primeira execução: pergunta idioma, tamanho da janela e escala."""
        self.withdraw()
        w = tk.Toplevel(self)
        w.title("BT3 Effect Studio")
        w.resizable(False, False)
        lang = tk.StringVar(value="pt")
        win = tk.StringVar(value="auto")
        sc = tk.StringVar(value="1.0")
        box = ttk.Frame(w, padding=16)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text="Idioma / Idioma / Language", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        for code, name in LANGS.items():
            ttk.Radiobutton(box, text=name, value=code, variable=lang).pack(anchor="w", padx=10)
        ttk.Separator(box).pack(fill="x", pady=10)
        ttk.Label(box, text="Resolução / Resolución / Resolution", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        ttk.Label(box, text="Monitor: %d × %d" % (sw, sh)).pack(anchor="w", padx=10)
        opts = ["auto"] + self.WINDOW_SIZES
        cb = ttk.Combobox(box, state="readonly", width=28,
                          values=["Automático / Automatic"] + [x.replace("x", " × ") if x != "max" else "Maximizada / Maximized" for x in self.WINDOW_SIZES])
        cb.current(0)
        cb.pack(anchor="w", padx=10, pady=2)
        ttk.Label(box, text="Escala / Escala / Scale").pack(anchor="w", pady=(8, 0))
        cs = ttk.Combobox(box, state="readonly", width=10, values=["%d%%" % round(x * 100) for x in self.SCALES])
        cs.current(self.SCALES.index(1.0))
        cs.pack(anchor="w", padx=10, pady=2)
        dark = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="Modo noturno / Modo nocturno / Dark mode", variable=dark).pack(anchor="w", pady=(10, 0))

        def ok():
            self.cfg["dark"] = bool(dark.get())
            self.cfg["lang"] = lang.get()
            self.cfg["window"] = opts[max(0, cb.current())]
            self.cfg["scale"] = self.SCALES[max(0, cs.current())]
            self._save_cfg()
            w.destroy()
        ttk.Button(box, text="OK", command=ok).pack(fill="x", pady=(14, 0))
        w.protocol("WM_DELETE_WINDOW", ok)
        w.grab_set()
        self.wait_window(w)
        self.lang = self.cfg.get("lang", "pt")
        self.scale = float(self.cfg.get("scale", 1.0))
        self.apply_theme()
        self.deiconify()

    # ------------------------------------------------------------ exibição
    WINDOW_SIZES = ["1024x600", "1280x720", "1366x768", "1600x900", "1920x1080", "max"]
    SCALES = [0.8, 0.9, 1.0, 1.15, 1.3]

    def fs(self, n):
        return max(6, int(round(n * self.scale)))

    def wrap(self):
        return int(380 * self.scale)

    def apply_display(self, first=False):
        for name in ("TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont", "TkCaptionFont"):
            try:
                tkfont.nametofont(name).configure(size=self.fs(9))
            except tk.TclError:
                pass
        try:
            ttk.Style(self).configure("Treeview", rowheight=int(20 * self.scale))
        except tk.TclError:
            pass
        size = self.cfg.get("window", "auto")
        if size == "auto":
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            size = "max" if sw < 1400 or sh < 800 else "1280x760"
        self.minsize(760, 480)
        if size == "max":
            try:
                self.state("zoomed")
            except tk.TclError:
                self.attributes("-zoomed", True)
        else:
            try:
                self.state("normal")
            except tk.TclError:
                pass
            self.geometry(size)

    def set_display(self, window=None, scale=None, layout=None):
        if window is not None:
            self.cfg["window"] = window
        if scale is not None:
            self.cfg["scale"] = scale
            self.scale = scale
        if layout is not None:
            self.cfg["layout"] = layout
        self._save_cfg()
        self.apply_display()
        self.build_ui()

    def _tab(self, nb, key):
        sf = ScrollFrame(nb)
        nb.add(sf, text=self.t(key))
        self._tabs[key] = sf
        return sf.inner

    def info(self, key):
        w = tk.Toplevel(self)
        w.title(self.t("info_title"))
        w.transient(self)
        txt = tk.Text(w, wrap="word", width=70, height=24, font=("Segoe UI", self.fs(10)), padx=10, pady=10)
        txt.insert("1.0", self.t(key))
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True)
        ttk.Button(w, text=self.t("close"), command=w.destroy).pack(pady=6)

    def info_btn(self, parent, key, text=None):
        return ttk.Button(parent, text=text or "?", width=(3 if text is None else 0),
                          command=lambda: self.info(key))

    # ------------------------------------------------------------ UI
    def cur_kind(self):
        return getattr(self.eff, "kind", "skill") if self.eff else "skill"

    def build_ui(self):
        self._ui_kind = self.cur_kind()
        self._tabs = {}
        for w in self.winfo_children():
            w.destroy()
        self.title(self.t("app_title") + (" — " + os.path.basename(self.path) if self.path else ""))
        self._menu()
        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        self.lbl_file = ttk.Label(top, font=("Segoe UI", self.fs(11), "bold"))
        self.lbl_file.pack(side="left")
        self.lbl_sum = ttk.Label(top)
        self.lbl_sum.pack(side="left", padx=16)
        self.lbl_size = tk.Label(top, font=("Segoe UI", self.fs(10), "bold"))
        self.lbl_size.pack(side="left")
        ttk.Button(top, text=self.t("w_btn"), command=self.show_weight).pack(side="left", padx=6)
        ttk.Button(top, text=self.t("btn_textures"), command=self.open_textures).pack(side="left")
        ttk.Button(top, text=self.t("btn_hex"), command=self.open_hex).pack(side="left", padx=6)
        ttk.Button(top, text=self.t("btn_3d"), command=self.open_3d).pack(side="left")
        self.info_btn(top, "info_classes", self.t("btn_classes")).pack(side="right")

        body = ttk.PanedWindow(self, orient="vertical" if self.cfg.get("layout") == "bottom" else "horizontal")
        body.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        left = ttk.Frame(body)
        body.add(left, weight=1)
        bar = ttk.Frame(left)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Button(bar, text=self.t("mark_all"), command=lambda: self.list.set_all(True)).pack(side="left")
        ttk.Button(bar, text=self.t("unmark_all"), command=lambda: self.list.set_all(False)).pack(side="left", padx=4)
        ttk.Button(bar, text=self.t("remove_marked"), command=self.remove_marked).pack(side="right")
        ttk.Button(bar, text=self.t("hide_marked"), command=lambda: self.hide_minis(self.list.marked())).pack(side="right", padx=4)
        chips_holder = ttk.Frame(left)
        chips_holder.pack(fill="x", pady=(0, 4))
        self.list = MiniList(left, self, on_select=self.on_select)
        self.list.pack(fill="both", expand=True)
        self.chips = GroupChips(chips_holder, self, self.list)
        self.chips.pack(fill="x")
        self.list.headings()

        nb = ttk.Notebook(body)
        body.add(nb, weight=1)
        self._body = body
        self.after(60, self._sash)
        self.tab_colors(nb)
        self.tab_params(nb)
        self.tab_combine(nb)
        self.tab_behavior(nb)
        self.tab_extras(nb)
        self.tab_scene(nb)
        self.tab_aura(nb)
        self.tab_support(nb)
        self.tab_support_params(nb)
        self.tab_flags(nb)
        self.tab_history(nb)
        visible = {"aura": ("tab_colors", "tab_params", "tab_extras", "tab_aura", "tab_flags", "tab_history"),
                   "support": ("tab_colors", "tab_params", "tab_extras", "tab_support", "tab_sparams", "tab_aura", "tab_flags", "tab_history")}
        show_adv = bool(self.cfg.get("show_advanced"))
        for key, sf in self._tabs.items():
            if self._ui_kind in visible:
                hide = key not in visible[self._ui_kind]
            else:
                hide = key in ("tab_aura", "tab_support", "tab_sparams")
            if key == "tab_flags" and not show_adv:
                hide = True
            if hide:
                nb.hide(sf)
        self.refresh()

    def _menu(self):
        mb = tk.Menu(self)
        mf = tk.Menu(mb, tearoff=0)
        mf.add_command(label=self.t("open"), command=self.open, accelerator="Ctrl+O")
        mf.add_command(label=self.t("save"), command=self.save, accelerator="Ctrl+S")
        mf.add_command(label=self.t("save_as"), command=lambda: self.save(as_new=True))
        mf.add_separator()
        mf.add_command(label=self.t("undo"), command=self.undo, accelerator="Ctrl+Z")
        mf.add_command(label=self.t("redo"), command=self.redo, accelerator="Ctrl+Y")
        mf.add_separator()
        mf.add_command(label=self.t("quit"), command=self.quit_app)
        mtools = tk.Menu(mb, tearoff=0)
        mtools.add_command(label=self.t("btn_3d"), command=self.open_3d)
        mtools.add_command(label=self.t("btn_textures"), command=self.open_textures)
        mtools.add_command(label=self.t("btn_hex"), command=self.open_hex)
        mtools.add_command(label=self.t("hex_external"), command=self.open_hex_external)
        mtools.add_separator()
        mtools.add_command(label=self.t("tools_anm"), command=self.open_anm)
        mb.add_cascade(label=self.t("file"), menu=mf)
        mb.add_cascade(label=self.t("tools"), menu=mtools)
        mt = tk.Menu(mb, tearoff=0)
        tpls = RES.list("modelos")
        if tpls:
            self.fill_tree_menu(mt, tpls, lambda f: self.open_template(f), img_prefix="modelos")
        else:
            mt.add_command(label=self.t("no_templates"), state="disabled")
        for sub, key in (("auras", "tab_aura"), ("suportes", "tab_support"), ("pre_disparo", "pre_title")):
            names = RES.list(sub)
            if names:
                sm = tk.Menu(mt, tearoff=0)
                self.fill_tree_menu(sm, names, lambda f, sub=sub: self.open_template(f, sub), img_prefix=sub)
                mt.add_separator()
                mt.add_cascade(label=self.t(key), menu=sm)
        mb.add_cascade(label=self.t("templates"), menu=mt)
        ml = tk.Menu(mb, tearoff=0)
        self.lang_var = tk.StringVar(value=self.lang)
        for code, name in LANGS.items():
            ml.add_radiobutton(label=name, value=code, variable=self.lang_var,
                               command=lambda c=code: self.set_lang(c))
        mb.add_cascade(label=self.t("language"), menu=ml)
        md = tk.Menu(mb, tearoff=0)
        mw = tk.Menu(md, tearoff=0)
        self.win_var = tk.StringVar(value=self.cfg.get("window", "auto"))
        mw.add_radiobutton(label=self.t("win_auto"), value="auto", variable=self.win_var, command=lambda: self.set_display(window="auto"))
        for ws in self.WINDOW_SIZES:
            mw.add_radiobutton(label=self.t("win_max") if ws == "max" else ws.replace("x", " × "), value=ws,
                               variable=self.win_var, command=lambda ws=ws: self.set_display(window=ws))
        md.add_cascade(label=self.t("win_size"), menu=mw)
        msc = tk.Menu(md, tearoff=0)
        self.scale_menu_var = tk.StringVar(value=str(self.scale))
        for sc in self.SCALES:
            msc.add_radiobutton(label="%d%%" % round(sc * 100), value=str(sc), variable=self.scale_menu_var,
                                command=lambda sc=sc: self.set_display(scale=sc))
        md.add_cascade(label=self.t("ui_scale"), menu=msc)
        mlay = tk.Menu(md, tearoff=0)
        self.layout_var = tk.StringVar(value=self.cfg.get("layout", "right"))
        mlay.add_radiobutton(label=self.t("layout_right"), value="right", variable=self.layout_var, command=lambda: self.set_display(layout="right"))
        mlay.add_radiobutton(label=self.t("layout_bottom"), value="bottom", variable=self.layout_var, command=lambda: self.set_display(layout="bottom"))
        md.add_cascade(label=self.t("panel_pos"), menu=mlay)
        self.dark_var = tk.BooleanVar(value=bool(self.cfg.get("dark")))
        md.add_checkbutton(label=self.t("dark_mode"), variable=self.dark_var, command=self.toggle_dark)
        self.adv_var = tk.BooleanVar(value=bool(self.cfg.get("show_advanced")))
        md.add_checkbutton(label=self.t("show_advanced"), variable=self.adv_var, command=self._toggle_adv)
        mb.add_cascade(label=self.t("display"), menu=md)
        mh = tk.Menu(mb, tearoff=0)
        mh.add_command(label=self.t("tutorials"), command=self.open_tutorials)
        mh.add_command(label=self.t("btn_classes"), command=lambda: self.info("info_classes"))
        mh.add_command(label=self.t("about"), command=lambda: messagebox.showinfo(self.t("about"), self.t("about_text")))
        mb.add_cascade(label=self.t("help"), menu=mh)
        self.config(menu=mb)
        self.bind("<Control-o>", lambda e: self.open())

    def _sash(self, tries=0):
        """Divide a janela meio a meio (a lista precisa de espaço para as colunas novas)."""
        try:
            w = self._body.winfo_width()
            if w < 400:
                if tries < 40:
                    self.after(100, lambda: self._sash(tries + 1))
                return
            if self.cfg.get("layout") != "bottom":
                self._body.sashpos(0, int(w * 0.52))
        except tk.TclError:
            pass

    def _toggle_adv(self):
        self.cfg["show_advanced"] = bool(self.adv_var.get())
        self._save_cfg()
        self.build_ui()

    # ---- aba backup e histórico
    def tab_history(self, nb):
        f = self._tab(nb, "tab_history")
        hdr = ttk.Frame(f)
        hdr.pack(fill="x")
        ttk.Label(hdr, text=self.t("hist_title"), font=("Segoe UI", self.fs(10), "bold")).pack(side="left")
        self.info_btn(hdr, "info_history", self.t("more_info")).pack(side="right")
        lf = ttk.Frame(f)
        lf.pack(fill="both", expand=True, pady=4)
        self.hist_list = tk.Listbox(lf, height=14, activestyle="none", exportselection=False, font=("Consolas", self.fs(9)))
        hsb = ttk.Scrollbar(lf, command=self.hist_list.yview)
        self.hist_list.configure(yscrollcommand=hsb.set)
        self.hist_list.pack(side="left", fill="both", expand=True)
        hsb.pack(side="right", fill="y")
        b = ttk.Frame(f)
        b.pack(fill="x")
        ttk.Button(b, text="⟲ " + self.t("undo"), command=self.undo).pack(side="left", fill="x", expand=True)
        ttk.Button(b, text="⟳ " + self.t("redo"), command=self.redo).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(f, text=self.t("hist_back_to"), command=self._hist_back).pack(fill="x", pady=4)
        ttk.Separator(f).pack(fill="x", pady=8)
        hdr = ttk.Frame(f)
        hdr.pack(fill="x")
        ttk.Label(hdr, text=self.t("bk_title"), font=("Segoe UI", self.fs(10), "bold")).pack(side="left")
        self.lbl_bkdir = ttk.Label(f, text="", wraplength=self.wrap(), justify="left", foreground="#8a8f99")
        self.lbl_bkdir.pack(anchor="w")
        bf = ttk.Frame(f)
        bf.pack(fill="both", expand=True, pady=4)
        self.bk_list = tk.Listbox(bf, height=8, activestyle="none", exportselection=False, font=("Consolas", self.fs(9)))
        bsb = ttk.Scrollbar(bf, command=self.bk_list.yview)
        self.bk_list.configure(yscrollcommand=bsb.set)
        self.bk_list.pack(side="left", fill="both", expand=True)
        bsb.pack(side="right", fill="y")
        bb = ttk.Frame(f)
        bb.pack(fill="x")
        ttk.Button(bb, text=self.t("bk_restore"), command=self._bk_restore).pack(side="left", fill="x", expand=True)
        ttk.Button(bb, text=self.t("bk_now"), command=self._bk_now).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(bb, text=self.t("bk_open"), command=self._bk_open).pack(side="left", fill="x", expand=True)
        self._hist_fill()

    def _cur_file(self):
        cont = getattr(self, "container", None)
        return cont[0] if cont else self.path

    def _hist_fill(self):
        if not hasattr(self, "hist_list"):
            return
        try:
            if not self.hist_list.winfo_exists():
                return
        except tk.TclError:
            return
        L = self.hist_list
        L.delete(0, "end")
        hist = self.history
        for i, st in enumerate(hist):
            L.insert("end", "%2d  %s  %s" % (i + 1, st["time"], st["label"]))
        L.insert("end", "▶  " + self.t("hist_now"))
        L.itemconfig("end", foreground="#2ecc71")
        for st in reversed(getattr(self, "redo_stack", [])):
            L.insert("end", "    %s  %s  (%s)" % (st["time"], st["label"], self.t("redo").lower()))
            L.itemconfig("end", foreground="#7a7f89")
        L.see(len(hist))
        self.bk_list.delete(0, "end")
        p = self._cur_file()
        self._bk_files = self.list_backups(p) if p else []
        self.lbl_bkdir.config(text=(self.t("bk_where", d=self.backup_dir(p)) if p else self.t("bk_none")))
        for fp in self._bk_files:
            st = os.stat(fp)
            import time as _time
            self.bk_list.insert("end", "%s   %6.1f KB" % (_time.strftime("%d/%m %H:%M:%S", _time.localtime(st.st_mtime)), st.st_size / 1024.0))

    def _hist_back(self):
        s = self.hist_list.curselection()
        if not s or s[0] >= len(self.history):
            return
        self.undo_to(len(self.history) - s[0])

    def _bk_restore(self):
        s = self.bk_list.curselection()
        if not s:
            return
        fp = self._bk_files[s[0]]
        try:
            with open(fp, "rb") as fh:
                raw = fh.read()
            cont = getattr(self, "container", None)
            data = container_get(raw, cont[1]) if cont else raw
            eff = Effect.from_bytes(data)
        except (PakError, OSError, IndexError) as ex:
            messagebox.showerror(self.t("err"), str(ex))
            return
        if self.eff:
            self.snapshot(self.t("bk_restore"))
            eff.kind = self.eff.kind
        self.eff = eff
        self.changed()
        messagebox.showinfo(self.t("ok"), self.t("bk_restored"))

    def _bk_now(self):
        p = self._cur_file()
        if p and self.make_backup(p):
            self._hist_fill()

    def _bk_open(self):
        p = self._cur_file()
        d = self.backup_dir(p) if p else os.path.join(HERE, "backups")
        os.makedirs(d, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(d)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", d])
        except Exception:
            messagebox.showinfo(self.t("app_title"), d)

    def set_lang(self, code):
        self.lang = code
        self.cfg["lang"] = code
        self._save_cfg()
        self.build_ui()

    # ---- aba cores
    def tab_colors(self, nb):
        f = self._tab(nb, "tab_colors")
        self.info_btn(f, "info_colors", self.t("more_info")).pack(anchor="e")
        ttk.Checkbutton(f, text=self.t("keep_sat"), variable=self.keep_sat).pack(anchor="w")
        ttk.Checkbutton(f, text=self.t("tex_color"), variable=self.tex_color).pack(anchor="w")
        fr = ttk.Frame(f)
        fr.pack(fill="x", pady=(2, 8))
        ttk.Label(fr, text=self.t("force_color")).pack(side="left")
        self.force_var = tk.DoubleVar(value=float(self.cfg.get("force", 0)))
        self.lbl_force = ttk.Label(fr, text="%d%%" % round(self.force_var.get() * 100), width=5)
        ttk.Scale(fr, from_=0.0, to=1.0, variable=self.force_var, orient="horizontal",
                  command=lambda v: self.lbl_force.config(text="%d%%" % round(float(v) * 100))).pack(side="left", fill="x", expand=True, padx=4)
        self.lbl_force.pack(side="left")
        ttk.Button(f, text=self.t("color_all"), command=lambda: self.recolor(self.list.minis, whole=True)).pack(fill="x")
        ttk.Button(f, text=self.t("color_marked"), command=lambda: self.recolor(self.list.marked())).pack(fill="x", pady=4)
        cr = ttk.Frame(f)
        cr.pack(fill="x", pady=(0, 4))
        ttk.Button(cr, text=self.t("color_contrast"), command=self._recolor_contrast).pack(side="left", fill="x", expand=True)
        ttk.Label(cr, text=self.t("contrast_shift")).pack(side="left", padx=(6, 2))
        self.contrast_var = tk.StringVar(value="-35")
        ttk.Spinbox(cr, from_=-90, to=90, increment=5, width=5, textvariable=self.contrast_var).pack(side="left")
        self.info_btn(cr, "info_contrast").pack(side="left", padx=4)
        gr = ttk.Frame(f)
        gr.pack(fill="x", pady=(0, 4))
        ttk.Button(gr, text="◐ " + self.t("grad_btn"), command=self._gradient_dialog).pack(side="left", fill="x", expand=True)
        self.info_btn(gr, "info_grad").pack(side="left", padx=4)
        g = ttk.Frame(f)
        g.pack(fill="x", pady=4)
        ttk.Label(g, text=self.t("color_group")).pack(side="left")
        self.cb_colorgroup = ttk.Combobox(g, state="readonly", width=16)
        self.cb_colorgroup.pack(side="left", padx=4)
        ttk.Button(g, text=self.t("pick"), command=self._color_group).pack(side="left")
        ttk.Separator(f).pack(fill="x", pady=10)
        self._dark_section(f)
        ttk.Separator(f).pack(fill="x", pady=10)
        self._opacity_section(f)
        ttk.Separator(f).pack(fill="x", pady=10)
        hdr = ttk.Frame(f)
        hdr.pack(fill="x")
        ttk.Label(hdr, text=self.t("nerf_title"), font=("Segoe UI", self.fs(10), "bold")).pack(side="left")
        self.info_btn(hdr, "info_nerf", self.t("more_info")).pack(side="right")
        self.lbl_depth = ttk.Label(f, text="")
        self.lbl_depth.pack(anchor="w", pady=2)
        nr = ttk.Frame(f)
        nr.pack(fill="x", pady=(2, 0))
        ttk.Button(nr, text=self.t("nerf_all"), command=lambda: self._nerf(None)).pack(side="left", fill="x", expand=True)
        ttk.Button(nr, text=self.t("nerf_marked"), command=lambda: self._nerf(self.list.marked())).pack(side="left", fill="x", expand=True, padx=(4, 0))
        ttk.Separator(f).pack(fill="x", pady=10)
        ttk.Label(f, text=self.t("manual_rgb"), font=("Segoe UI", self.fs(10), "bold")).pack(anchor="w")
        self.rgb_box = ttk.Frame(f)
        self.rgb_box.pack(fill="both", expand=True, pady=6)

    def _fill_rgb(self, m):
        for w in self.rgb_box.winfo_children():
            w.destroy()
        if m is None:
            ttk.Label(self.rgb_box, text=self.t("select_one")).pack(anchor="w")
            return
        rows = m.color_rows()
        if not rows:
            ttk.Label(self.rgb_box, text=self.t("no_colors")).pack(anchor="w")
            return
        canvas = tk.Canvas(self.rgb_box, highlightthickness=0, height=300)
        sb = ttk.Scrollbar(self.rgb_box, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        tools = ttk.Frame(self.rgb_box)
        tools.pack(side="top", fill="x", pady=(0, 4))
        chans = [self.t("ch_red"), self.t("ch_green"), self.t("ch_blue"), self.t("ch_int")]
        ttk.Label(tools, text=self.t("ch_color1")).pack(side="left")
        self.ch_a = ttk.Combobox(tools, state="readonly", width=9, values=chans)
        self.ch_a.current(0)
        self.ch_a.pack(side="left", padx=2)
        ttk.Label(tools, text=self.t("ch_color2")).pack(side="left", padx=(6, 0))
        self.ch_b = ttk.Combobox(tools, state="readonly", width=9, values=chans)
        self.ch_b.current(2)
        self.ch_b.pack(side="left", padx=2)
        ttk.Button(tools, text=self.t("ch_swap"), command=lambda: self._rgb_entries("swap")).pack(side="left", padx=2)
        ttk.Button(tools, text=self.t("ch_copy"), command=lambda: self._rgb_entries("copy")).pack(side="left")
        self.info_btn(tools, "info_channels").pack(side="left", padx=4)
        canvas.pack_forget()
        sb.pack_forget()
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for c, h in enumerate(("", "R", "G", "B", "A", "")):
            ttk.Label(inner, text=h).grid(row=0, column=c)
        self.rgb_vars = []
        for i, row in enumerate(rows):
            vals = m.read_rgba(row)
            lbl = self.t("session_row", s=i // 3 + 1, r=i % 3 + 1) if row[2] == 'f' else "%s %d" % (self.t("row"), i + 1)
            ttk.Label(inner, text=lbl).grid(row=i + 1, column=0, padx=2, sticky="w")
            vs = []
            for k in range(4):
                v = tk.StringVar(value=("%g" % vals[k]))
                ttk.Spinbox(inner, from_=0, to=255, width=6, textvariable=v).grid(row=i + 1, column=k + 1, padx=1, pady=1)
                vs.append(v)
            sw = tk.Label(inner, width=3, bg=rgb_hex(vals), relief="solid", bd=1)
            for v in vs[:3]:
                v.trace_add("write", lambda *_a, vs=vs, sw=sw: self._swatch(sw, vs))
            sw.grid(row=i + 1, column=5, padx=4)
            sw.bind("<Button-1>", lambda e, vs=vs: self._pick_into(vs))
            self.rgb_vars.append((row, vs))
        ttk.Button(inner, text=self.t("apply"), command=lambda: self._apply_rgb(m)).grid(row=len(rows) + 1, column=1, columnspan=4, pady=6, sticky="ew")

    def _swatch(self, sw, vs):
        try:
            sw.config(bg=rgb_hex([float(v.get() or 0) for v in vs[:3]]))
        except (ValueError, tk.TclError):
            pass

    def _rgb_entries(self, mode):
        """Como no Skill Shader Editor: 'Inverter' troca os valores de duas colunas em todas as linhas;
           'Copiar' copia a Cor 1 para a Cor 2. Depois é só clicar em Aplicar."""
        a, b = self.ch_a.current(), self.ch_b.current()
        if a == b or not getattr(self, "rgb_vars", None):
            return
        for row, vs in self.rgb_vars:
            va, vb = vs[a].get(), vs[b].get()
            if mode == "swap":
                vs[a].set(vb)
                vs[b].set(va)
            else:
                vs[b].set(va)

    def ask_color(self, initial=None, title=None):
        import seletor_cor
        return seletor_cor.ask_color(self, initial, title)

    def _pick_into(self, vs):
        cur = [min(255, max(0, float(v.get() or 0))) for v in vs[:3]]
        res = self.ask_color(cur)
        if res:
            for k in range(3):
                vs[k].set(str(int(res[k])))

    def _apply_rgb(self, m):
        # primeiro lê e valida TODAS as linhas; só depois grava. Antes, um campo inválido
        # deixava o efeito meio alterado e criava um ponto de desfazer falso.
        try:
            new = [(row, [float(v.get().replace(",", ".")) for v in vs]) for row, vs in self.rgb_vars]
        except ValueError as ex:
            messagebox.showerror(self.t("err"), str(ex))
            return
        n_hist = len(self.history)
        self.snapshot()
        try:
            for row, vals in new:
                m.write_rgba(row, vals)
        except (OverflowError, struct.error) as ex:
            messagebox.showerror(self.t("err"), str(ex))
            if len(self.history) > n_hist:
                self._restore(self.history.pop())       # desfaz o que chegou a ser escrito
            return
        self.changed()

    def recolor(self, minis, whole=False):
        if not self.eff:
            return
        if not minis:
            messagebox.showinfo(self.t("app_title"), self.t("nothing_marked"))
            return
        minis = self.ask_gray(minis)
        if not minis:
            return
        res = self.ask_color()
        if not res:
            return
        self.snapshot()
        rgb = [int(c) for c in res]
        for m in minis:
            m.recolor(rgb, self.keep_sat.get(), self._force())
        n = None
        if whole and self.tex_color.get():
            ks, fo = self.keep_sat.get(), self._force()
            n = self.eff.recolor_dbts_of(minis, lambda d, im: recolor_dbt_imgs(d, im, rgb, ks, fo))
        self.changed()
        if n is not None:
            messagebox.showinfo(self.t("ok"), self.t("tex_done", n=n))

    def ask_gray(self, minis, what=None):
        """Partes 100% preto e branco (principalmente V00): pergunta se troca a cor delas também.
           Devolve a lista a usar, ou None se o usuário cancelar."""
        if not self.eff:
            return minis
        gray = self.eff.gray_minis(minis)
        if not gray:
            return minis
        n_v00 = sum(1 for m in gray if m.type == 0x0E)
        allm = self.eff.all_minis()
        ids = ", ".join("#%d" % allm.index(m) for m in gray[:14]) + (" …" if len(gray) > 14 else "")
        r = messagebox.askyesnocancel(self.t("app_title"), self.t("gray_q", n=len(gray), v=n_v00, ids=ids))
        if r is None:
            return None
        if r:
            return minis
        gid = set(id(m) for m in gray)
        return [m for m in minis if id(m) not in gid]

    def _force(self):
        try:
            v = float(self.force_var.get())
        except (AttributeError, ValueError, TypeError):
            v = 0.0
        self.cfg["force"] = v
        return max(0.0, min(1.0, v))

    def _recolor_contrast(self):
        if not self.eff:
            return
        ms = self.ask_gray([m for m in self.eff.all_minis() if m.type != 0x00])
        if ms is None:
            return
        res = self.ask_color()
        if not res:
            return
        try:
            shift = float(self.contrast_var.get())
        except ValueError:
            shift = -35
        self.snapshot()
        alt = self.eff.recolor_contrast2([int(c) for c in res], shift, self._force(), self.tex_color.get(), ms)
        self.changed()
        messagebox.showinfo(self.t("ok"), self.t("contrast_done", c="#%02x%02x%02x" % alt))

    # ---- degradê de acordo com a textura
    GRAD_PRESETS = (("Final Flash", ((40, 70, 255), (120, 200, 255), (255, 255, 230))),
                    ("Big Bang", ((255, 90, 0), (255, 190, 40), (255, 255, 200))),
                    ("Hakai", ((70, 0, 110), (200, 40, 200), (255, 220, 255))),
                    ("Ki verde", ((0, 90, 30), (60, 230, 90), (230, 255, 220))),
                    ("Fogo", ((150, 0, 0), (255, 80, 0), (255, 240, 120))))

    def _gradient_dialog(self):
        if not self.eff:
            return
        import seletor_cor, base64, texview
        from bt3eff_core import dbt_info, dbt_image_rgba, recolor_dbt_gradient, contrast_stops
        w = tk.Toplevel(self)
        w.title(self.t("grad_title"))
        w.transient(self)
        box = ttk.Frame(w, padding=10)
        box.pack(fill="both", expand=True)
        st = self.cfg.get("grad_stops") or [[40, 70, 255], [120, 200, 255], [255, 255, 230]]
        cols = [tuple(c) for c in st]
        use_mid = tk.BooleanVar(value=bool(self.cfg.get("grad_mid", True)))
        keep = tk.BooleanVar(value=True)
        tex = tk.BooleanVar(value=True)
        iso = tk.BooleanVar(value=False)
        con = tk.BooleanVar(value=False)
        scope = tk.StringVar(value="all")
        sws = []
        r = ttk.Frame(box)
        r.pack(fill="x")
        for i, key in enumerate(("grad_dark", "grad_mid", "grad_light")):
            fr = ttk.Frame(r)
            fr.pack(side="left", padx=6)
            ttk.Label(fr, text=self.t(key)).pack()
            b = tk.Label(fr, width=10, height=2, relief="solid", bd=1, bg=seletor_cor.hexrgb(cols[i]), cursor="hand2")
            b.pack()
            sws.append(b)
            def pick(_e=None, i=i):
                res = self.ask_color(cols[i])
                if res:
                    cols[i] = tuple(res)
                    sws[i].config(bg=seletor_cor.hexrgb(res))
                    redraw()
            b.bind("<Button-1>", pick)
        bar = tk.Canvas(box, height=22, highlightthickness=0)
        bar.pack(fill="x", pady=6)
        pr = ttk.Frame(box)
        pr.pack(fill="x")
        ttk.Label(pr, text=self.t("grad_presets")).pack(side="left")
        for name, cc in self.GRAD_PRESETS:
            def setp(cc=cc):
                for i in range(3):
                    cols[i] = cc[i]
                    sws[i].config(bg=seletor_cor.hexrgb(cc[i]))
                redraw()
            ttk.Button(pr, text=name, command=setp).pack(side="left", padx=2)
        for var, key in ((use_mid, "grad_use_mid"), (keep, "grad_keep_light"), (tex, "grad_textures"),
                         (iso, "grad_isolate"), (con, "grad_contrast")):
            ttk.Checkbutton(box, text=self.t(key), variable=var, command=lambda: redraw()).pack(anchor="w")
        sr = ttk.Frame(box)
        sr.pack(fill="x", pady=4)
        ttk.Label(sr, text=self.t("grad_scope")).pack(side="left")
        ttk.Radiobutton(sr, text=self.t("grad_all"), value="all", variable=scope).pack(side="left", padx=4)
        ttk.Radiobutton(sr, text=self.t("grad_marked"), value="marked", variable=scope).pack(side="left")
        # prévia numa textura
        items = []
        for c in self.eff.cats:
            for di, d in enumerate(c.dbts):
                for ii, im in enumerate(dbt_info(d)):
                    items.append((c, di, ii, "%s · DBT %d · img %d" % (class_label(c.type, self.lang), di, ii)))
        ttk.Label(box, text=self.t("grad_preview")).pack(anchor="w", pady=(6, 0))
        cb = ttk.Combobox(box, state="readonly", width=46, values=[x[3] for x in items])
        cb.pack(anchor="w")
        pv = ttk.Frame(box)
        pv.pack(fill="x", pady=4)
        lb_a = tk.Label(pv, bg="#202228"); lb_a.pack(side="left")
        ttk.Label(pv, text="  →  ").pack(side="left")
        lb_b = tk.Label(pv, bg="#202228"); lb_b.pack(side="left")
        if items:
            cb.current(0)

        def stops():
            if use_mid.get():
                return [(0.0, cols[0]), (0.5, cols[1]), (1.0, cols[2])]
            return [(0.0, cols[0]), (1.0, cols[2])]

        def redraw(_=None):
            bar.update_idletasks()
            W = max(200, bar.winfo_width())
            bar.delete("all")
            from bt3eff_core import gradient_at
            for x in range(0, W, 3):
                c = gradient_at(stops(), x / float(W))
                bar.create_rectangle(x, 0, x + 3, 22, fill=seletor_cor.hexrgb(c), outline="")
            i = cb.current()
            if i < 0:
                return
            c, di, ii, _ = items[i]
            d = c.dbts[di]
            try:
                a, ww, hh = dbt_image_rgba(d, ii)
                st_ = stops() if not (con.get() and c.type in (0x10, 0x12)) else contrast_stops(stops(), self._shift())
                b, _, _ = dbt_image_rgba(recolor_dbt_gradient(d, st_, {ii}, keep.get()), ii)
                w._pa = tk.PhotoImage(master=w, data=base64.b64encode(texview.preview_png(a, ww, hh, 150)).decode())
                w._pb = tk.PhotoImage(master=w, data=base64.b64encode(texview.preview_png(b, ww, hh, 150)).decode())
                lb_a.config(image=w._pa)
                lb_b.config(image=w._pb)
            except Exception:
                pass
        cb.bind("<<ComboboxSelected>>", redraw)

        def apply():
            ms = self.eff.all_minis() if scope.get() == "all" else self.list.marked()
            ms = [m for m in ms if m.type != 0x00]
            if not ms:
                messagebox.showinfo(self.t("app_title"), self.t("nothing_marked"), parent=w)
                return
            ms = self.ask_gray(ms)
            if not ms:
                return
            self.cfg["grad_stops"] = [list(map(int, c)) for c in cols]
            self.cfg["grad_mid"] = use_mid.get()
            self._save_cfg()
            self.snapshot(self.t("act_gradient"))
            per = {}
            if con.get():
                alt = contrast_stops(stops(), self._shift())
                per = {0x10: alt, 0x12: alt}
            n = self.eff.recolor_gradient(ms, stops(), textures=tex.get(), keep_light=keep.get(),
                                          isolate=iso.get() and scope.get() != "all", per_class=per)
            self.changed()
            w.destroy()
            messagebox.showinfo(self.t("ok"), self.t("grad_done", n=len(ms), t=n))
        bb = ttk.Frame(box)
        bb.pack(fill="x", pady=(8, 0))
        ttk.Button(bb, text=self.t("apply"), command=apply).pack(side="right")
        ttk.Button(bb, text=self.t("close"), command=w.destroy).pack(side="right", padx=6)
        w.after(80, redraw)

    def _shift(self):
        try:
            return float(self.contrast_var.get())
        except (ValueError, AttributeError):
            return -35.0

    # ---- efeitos negros (cor inversa)
    def _dark_section(self, f):
        hdr = ttk.Frame(f)
        hdr.pack(fill="x")
        ttk.Label(hdr, text="⬛ " + self.t("dark_title"), font=("Segoe UI", self.fs(10), "bold")).pack(side="left")
        self.info_btn(hdr, "info_dark", self.t("more_info")).pack(side="right")
        m = self.cfg.get("dark_method", "real")
        self.dark_method = tk.StringVar(value=m if m in ("real", "texture") else "real")
        ttk.Radiobutton(f, text=self.t("dark_m_real"), value="real", variable=self.dark_method).pack(anchor="w")
        ttk.Radiobutton(f, text=self.t("dark_m_texture"), value="texture", variable=self.dark_method).pack(anchor="w")
        r = ttk.Frame(f)
        r.pack(fill="x", pady=2)
        ttk.Label(r, text=self.t("dark_strength")).pack(side="left")
        self.dark_str = tk.StringVar(value="100")
        ttk.Spinbox(r, from_=20, to=100, increment=10, width=5, textvariable=self.dark_str).pack(side="left", padx=2)
        ttk.Label(r, text="%").pack(side="left")
        self.dark_layer = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text=self.t("dark_layer"), variable=self.dark_layer).pack(anchor="w")
        b = ttk.Frame(f)
        b.pack(fill="x", pady=4)
        ttk.Button(b, text=self.t("dark_btn") + " (" + self.t("grad_marked").lower() + ")",
                   command=lambda: self._dark_apply(self.list.marked())).pack(side="left", fill="x", expand=True)
        ttk.Button(b, text=self.t("grad_all"), command=lambda: self._dark_apply(self.eff.all_minis() if self.eff else [])
                   ).pack(side="left", padx=(4, 0))
        ttk.Label(f, text=self.t("dark_table"), foreground="#8a8f99").pack(anchor="w", pady=(6, 2))
        self.dark_box = ttk.Frame(f)
        self.dark_box.pack(fill="x")

    def _dark_apply(self, minis):
        if not self.eff:
            return
        ms = [m for m in minis if m.type != 0x00]
        if not ms:
            messagebox.showinfo(self.t("app_title"), self.t("nothing_marked"))
            return
        ms = self.ask_gray(ms)
        if not ms:
            return
        try:
            k = max(0.2, min(1.0, float(self.dark_str.get().replace(",", ".")) / 100.0))
        except ValueError:
            k = 1.0
        self.cfg["dark_method"] = self.dark_method.get()
        self._save_cfg()
        self.snapshot()
        if self.dark_method.get() == "texture":
            from bt3eff_core import dbt_dark_chroma
            copied = self.eff.isolate_dbt(ms)
            n = self.eff.recolor_dbts_of(ms, lambda d, im: dbt_dark_chroma(d, im, k))
            self.changed()
            messagebox.showinfo(self.t("ok"), self.t("dark_tex_done", n=n, c=copied))
            return
        normal, layered, other, copied = self.eff.make_dark3(ms, k, keep_color=self.dark_layer.get())
        self.changed()
        allm = self.eff.all_minis()
        msg = self.t("dark3_done", a=len(normal), b=len(layered), c=len(other))
        if other:
            msg += "\n" + self.t("dark3_other", l=", ".join("#%d %s" % (allm.index(m), class_label(m.type, self.lang))
                                                            for m in other[:10]))
        messagebox.showinfo(self.t("ok"), msg)

    def _dark_table(self):
        if not hasattr(self, "dark_box"):
            return
        for w in self.dark_box.winfo_children():
            w.destroy()
        if not self.eff:
            return
        ms = self.list.marked() or ([self.list.selected()] if self.list.selected() else [])
        rows = []
        allm = self.eff.all_minis()
        for m in ms:
            for fi, o, lbl in m.blend_points():
                rows.append((m, fi, o, lbl, allm.index(m)))
        if not rows:
            ttk.Label(self.dark_box, text=self.t("dark_none"), foreground="#8a8f99", wraplength=self.wrap()).pack(anchor="w")
            return
        for r, (m, fi, o, lbl, idx) in enumerate(rows[:40]):
            cur = m.files[fi][o]
            orig = (getattr(m, "orig_blend", None) or {}).get(o, cur if cur != 0 else 1)
            ttk.Label(self.dark_box, text="#%d %s · %s" % (idx, class_label(m.type, self.lang), lbl)).grid(row=r, column=0, sticky="w")
            tk.Label(self.dark_box, text="= %02X" % cur, fg="#2ecc71" if cur else "#c39bff",
                     font=("Consolas", self.fs(9), "bold")).grid(row=r, column=1, padx=6)

            def set0(m=m, fi=fi, o=o):
                self.snapshot(self.t("act_blend"))
                m.orig_blend = getattr(m, "orig_blend", None) or {}
                m.orig_blend.setdefault(o, m.files[fi][o])
                m.files[fi][o] = 0
                self.changed()

            def back(m=m, fi=fi, o=o, v=orig):
                self.snapshot(self.t("act_blend"))
                m.files[fi][o] = v
                self.changed()
            ttk.Button(self.dark_box, text=self.t("dark_set0"), command=set0).grid(row=r, column=2, padx=2, pady=1)
            ttk.Button(self.dark_box, text=self.t("dark_restore", v="%02X" % orig), command=back).grid(row=r, column=3)

    def on_marks_changed(self):
        self._dark_table()
        self._preview_update()
        self._adv_marked_load()

    def _channels(self, mode):
        if not self.eff:
            return
        a, b = self.ch_a.current(), self.ch_b.current()
        if a == b:
            return
        sc = self.ch_scope.get()
        if sc == "sel":
            m = self.list.selected()
            ms = [m] if m else []
        elif sc == "marked":
            ms = self.list.marked()
        else:
            ms = self.eff.all_minis()
        ms = [m for m in ms if m.color_rows()]
        if not ms:
            messagebox.showinfo(self.t("app_title"), self.t("nothing_marked"))
            return
        ms = self.ask_gray(ms)
        if not ms:
            return
        self.snapshot()
        for m in ms:
            m.channels(a, b, mode)
        self.changed()

    def _nerf(self, minis):
        if not self.eff:
            return
        if minis is not None and not minis:
            messagebox.showinfo(self.t("app_title"), self.t("nothing_marked"))
            return
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            broken = self.eff.reduce16_check(minis)
        finally:
            self.config(cursor="")
        skip = []
        if broken:
            from bt3eff_core import dbt_info as _di
            names = ", ".join("%s DBT %d img %d" % (class_label(c.type, self.lang), di, i) for c, di, i in broken[:8])
            r = messagebox.askyesnocancel(self.t("app_title"), self.t("nerf_broken_q", n=len(broken), l=names))
            if r is None:
                return
            if not r:
                skip = broken
        self.snapshot()
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            n, before, after = self.eff.reduce16(minis, skip)
        finally:
            self.config(cursor="")
        self.changed()
        messagebox.showinfo(self.t("ok"), self.t("nerf_done", n=n, b=before / 1024.0, a=after / 1024.0))

    def _depth_status(self):
        if hasattr(self, "lbl_depth"):
            if self.eff:
                a, b = self.eff.color_depth()
                self.lbl_depth.config(text=self.t("depth", a=a, b=b))
            else:
                self.lbl_depth.config(text="")

    def _color_group(self):
        g = self._combo_group(self.cb_colorgroup)
        if g is not None:
            self.recolor([m for m in self.list.minis if m.get("invoke") == g])

    # ---- aba parâmetros
    def tab_params(self, nb):
        f = self._tab(nb, "tab_params")
        import previa
        hdr = ttk.Frame(f)
        hdr.pack(fill="x")
        ttk.Label(hdr, text=self.t("prev_title"), font=("Segoe UI", self.fs(10), "bold")).pack(side="left")
        self.info_btn(hdr, "h_size", self.t("more_info")).pack(side="right")
        ttk.Label(f, text=self.t("prev_hint"), wraplength=self.wrap(), justify="left", foreground="#8a8f99").pack(anchor="w")
        self.preview = previa.GrowthPreview(f, self)
        self.preview.pack(fill="x", pady=(4, 8))
        ttk.Separator(f).pack(fill="x", pady=(0, 8))
        s = ttk.Frame(f)
        s.pack(fill="x")
        ttk.Label(s, text=self.t("scale_marked")).pack(side="left")
        self.scale_var = tk.StringVar(value="1.5")
        ttk.Spinbox(s, from_=0.1, to=10, increment=0.1, width=6, textvariable=self.scale_var).pack(side="left", padx=4)
        ttk.Button(s, text=self.t("apply"), command=self._scale).pack(side="left")
        s2 = ttk.Frame(f)
        s2.pack(fill="x", pady=(8, 0))
        ttk.Label(s2, text=self.t("scale_group")).pack(side="left")
        self.cb_scalegroup = ttk.Combobox(s2, state="readonly", width=16)
        self.cb_scalegroup.pack(side="left", padx=4)
        ttk.Label(s2, text="×").pack(side="left")
        self.scale_var2 = tk.StringVar(value="1.5")
        ttk.Spinbox(s2, from_=0.1, to=10, increment=0.1, width=6, textvariable=self.scale_var2).pack(side="left", padx=4)
        ttk.Button(s2, text=self.t("apply"), command=self._scale_group).pack(side="left")
        # padrões de crescimento
        ttk.Separator(f).pack(fill="x", pady=10)
        hdr = ttk.Frame(f)
        hdr.pack(fill="x")
        ttk.Label(hdr, text=self.t("grow_title"), font=("Segoe UI", self.fs(10), "bold")).pack(side="left")
        self.info_btn(hdr, "info_grow", self.t("more_info")).pack(side="right")
        g1 = ttk.Frame(f)
        g1.pack(fill="x", pady=2)
        self.grow_keys = ["turles", "bills"]
        self.cb_grow = ttk.Combobox(g1, state="readonly", width=26, values=[self.t("grow_" + k) for k in self.grow_keys])
        self.cb_grow.current(0)
        self.cb_grow.pack(side="left")
        self.grow_rev = tk.BooleanVar(value=False)
        ttk.Checkbutton(g1, text=self.t("grow_reverse"), variable=self.grow_rev).pack(side="left", padx=6)
        g2 = ttk.Frame(f)
        g2.pack(fill="x", pady=2)
        ttk.Button(g2, text=self.t("grow_marked"), command=lambda: self._grow(None)).pack(side="left", fill="x", expand=True)
        self.cb_growgroup = ttk.Combobox(g2, state="readonly", width=14)
        self.cb_growgroup.pack(side="left", padx=4)
        ttk.Button(g2, text=self.t("grow_group"), command=lambda: self._grow(self._combo_group(self.cb_growgroup))).pack(side="left")
        ttk.Separator(f).pack(fill="x", pady=10)
        ttk.Label(f, text=self.t("params_of"), font=("Segoe UI", self.fs(10), "bold")).pack(anchor="w")
        self.param_box = ttk.Frame(f)
        self.param_box.pack(fill="both", expand=True, pady=6)

    SECTIONS = [("sec_when", ["invoke", "delay_a", "delay_b"], ["h_invoke", "h_delay", "h_delay"]),
                ("sec_behave", ["unk9", "unkA", "unkB"], ["h_b9", "h_bA", "h_bB"]),
                ("sec_dur", ["dur_a", "dur_b"], ["h_dur", "h_dur"]),
                ("sec_size", ["size1", "size2", "size3", "time1", "time2"], ["h_size"] * 5),
                ("sec_where", ["pos_x", "pos_y", "pos_z"], ["h_pos"] * 3),
                ("sec_tex", ["dbt", "tex"], ["h_dbt", "h_tex"]),
                ("sec_unk", ["unk30"], ["h_unk"])]

    def _fill_params(self, m):
        for w in self.param_box.winfo_children():
            w.destroy()
        if m is None:
            ttk.Label(self.param_box, text=self.t("select_one")).pack(anchor="w")
            return
        self.param_vars = {}
        g = ttk.Frame(self.param_box)
        g.pack(fill="x")
        row = 0
        if m.type == 0x00:
            ttk.Label(g, text=self.t("type00_note"), wraplength=self.wrap() - 20, justify="left",
                      foreground="#7a4b00").grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 6))
            row += 1
        for sec, fields, helps in self.SECTIONS:
            if m.type == 0x00:
                fields_h = [(f, h) for f, h in zip(fields, helps) if f in ("invoke", "delay_a", "delay_b", "dur_a", "dur_b")]
            else:
                fields_h = list(zip(fields, helps))
            if not fields_h:
                continue
            ttk.Label(g, text=self.t(sec), font=("Segoe UI", self.fs(9), "bold")).grid(row=row, column=0, columnspan=3, sticky="w", pady=(6, 1))
            row += 1
            for k, h in fields_h:
                ttk.Label(g, text=self.t("p_" + k)).grid(row=row, column=0, sticky="w", padx=(10, 0))
                v = m.get(k)
                var = tk.StringVar(value=str(v) if k in INT_FIELDS else "%g" % v)
                ttk.Entry(g, textvariable=var, width=12).grid(row=row, column=1, padx=6, pady=1)
                self.info_btn(g, h).grid(row=row, column=2)
                self.param_vars[k] = var
                row += 1
        fh = ttk.Frame(g)
        fh.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(8, 1))
        ttk.Label(fh, text=self.t("sec_flags"), font=("Segoe UI", self.fs(9), "bold")).pack(side="left")
        self.info_btn(fh, "h_flags").pack(side="right")
        row += 1
        self.flag_vars = {}
        b0 = m.param[0]
        for bit in (1, 2, 4, 8, 16, 32, 64, 128):
            v = tk.BooleanVar(value=bool(b0 & bit))
            ttk.Checkbutton(g, text="%d — %s" % (bit, self.t("flag_%d" % bit)), variable=v).grid(row=row, column=0, columnspan=3, sticky="w", padx=(10, 0))
            self.flag_vars[bit] = v
            row += 1
        ttk.Button(g, text=self.t("apply"), command=lambda: self._apply_params(m)).grid(row=row, column=0, columnspan=3, pady=8, sticky="ew")

    def _apply_params(self, m):
        # valida tudo antes de gravar (sem alterações pela metade nem desfazer falso)
        new = {}
        try:
            for k, var in self.param_vars.items():
                v = var.get().replace(",", ".")
                if k in INT_FIELDS:
                    n = int(float(v))
                    if not 0 <= n <= 255:
                        raise ValueError("%s: %d (0-255)" % (self.t("p_" + k), n))
                    new[k] = n
                else:
                    f = float(v)
                    if abs(f) > 3.0e38 or f != f:
                        raise ValueError("%s: %s" % (self.t("p_" + k), v))
                    new[k] = f
        except (ValueError, OverflowError) as ex:
            messagebox.showerror(self.t("err"), str(ex))
            return
        self.snapshot()
        for k, v in new.items():
            m.set(k, v)
        if getattr(self, "flag_vars", None):
            m.param[0] = sum(bit for bit, var in self.flag_vars.items() if var.get())
        self.changed()

    def _scale(self):
        ms = [m for m in self.list.marked() if m.type != 0x00]
        if not ms:
            messagebox.showinfo(self.t("app_title"), self.t("nothing_marked"))
            return
        try:
            fac = float(self.scale_var.get().replace(",", "."))
        except ValueError:
            return
        self.snapshot()
        for m in ms:
            m.scale_size(fac)
        self.changed()

    def _preview_update(self):
        if not hasattr(self, "preview") or not self.preview.winfo_exists():
            return
        ms = self.list.marked()
        if not ms and self.list.selected() is not None:
            ms = [self.list.selected()]
        self.preview.set_minis([m for m in ms if m.type != 0x00][:40])

    def _grow(self, group):
        if not self.eff:
            return
        ms = self.list.marked() if group is None else [m for m in self.list.minis if m.get("invoke") == group]
        ms = [m for m in ms if m.type != 0x00]
        if not ms:
            messagebox.showinfo(self.t("app_title"), self.t("nothing_marked"))
            return
        key = self.grow_keys[max(0, self.cb_grow.current())]
        self.snapshot()
        n = sum(1 for m in ms if m.apply_growth(key, self.grow_rev.get()))
        self.changed()
        messagebox.showinfo(self.t("ok"), self.t("scaled", n=n))

    def _stripes(self, hide):
        if not self.eff:
            return
        self.snapshot()
        ok = self.eff.hide_stripes(hide)
        self.changed()
        if not ok:
            messagebox.showinfo(self.t("app_title"), self.t("stripes_none"))

    def _scale_group(self):
        g = self._combo_group(self.cb_scalegroup)
        if g is None or not self.eff:
            return
        try:
            fac = float(self.scale_var2.get().replace(",", "."))
        except ValueError:
            return
        ms = [m for m in self.list.minis if m.get("invoke") == g and m.type != 0x00]
        self.snapshot()
        for m in ms:
            m.scale_size(fac)
        self.changed()
        messagebox.showinfo(self.t("ok"), self.t("scaled", n=len(ms)))

    # ---- aba grupos
    def tab_groups(self, nb):
        f = self._tab(nb, "tab_groups")
        self._groups_extra(f)

    def _groups_extra(self, f):
        hdr = ttk.Frame(f)
        hdr.pack(fill="x")
        ttk.Label(hdr, text=self.t("phase_tools"), font=("Segoe UI", self.fs(10), "bold")).pack(side="left")
        self.info_btn(hdr, "info_hide", self.t("more_info")).pack(side="right")
        r = ttk.Frame(f)
        r.pack(fill="x", pady=6)
        ttk.Label(r, text=self.t("group_or_phase")).pack(side="left")
        self.cb_hidegroup = ttk.Combobox(r, state="readonly", width=18)
        self.cb_hidegroup.pack(side="left", padx=4)
        self.hide_method = tk.StringVar(value="alpha")
        ttk.Radiobutton(f, text=self.t("hide_alpha"), value="alpha", variable=self.hide_method).pack(anchor="w")
        ttk.Radiobutton(f, text=self.t("hide_size"), value="size", variable=self.hide_method).pack(anchor="w")
        b = ttk.Frame(f)
        b.pack(fill="x", pady=6)
        ttk.Button(b, text=self.t("hide_group"), command=lambda: self._group_action("hide")).pack(side="left", fill="x", expand=True)
        ttk.Button(b, text=self.t("remove_group"), command=lambda: self._group_action("remove")).pack(side="left", fill="x", expand=True, padx=(4, 0))

    def _group_action(self, action):
        g = self._combo_group(self.cb_hidegroup)
        if g is None or not self.eff:
            return
        ms = [m for m in self.list.minis if m.group == g]
        if action == "hide":
            self.hide_minis(ms)
        else:
            self._remove(ms)

    def hide_minis(self, ms):
        ms = [m for m in ms if m.type != 0x00]
        if not ms:
            messagebox.showinfo(self.t("app_title"), self.t("nothing_marked"))
            return
        method = self.hide_method.get() if hasattr(self, "hide_method") else "alpha"
        self.snapshot()
        skipped = sum(1 for m in ms if not m.hide(method))
        self.changed()
        msg = self.t("hidden", n=len(ms) - skipped)
        if skipped:
            msg += "\n" + self.t("hidden_skip", n=skipped)
        messagebox.showinfo(self.t("ok"), msg)

    def _set_group(self):
        txt = self.cb_setgroup.get().strip()
        if not txt:
            return
        key = next((g for g in PRESET_GROUPS if group_label(g, self.lang) == txt), txt)
        ms = self.list.marked()
        if not ms:
            messagebox.showinfo(self.t("app_title"), self.t("nothing_marked"))
            return
        self.snapshot()
        for m in ms:
            m.group = key
        self.changed()

    # ---- aba combinar
    def tab_combine(self, nb):
        f = self._tab(nb, "tab_combine")
        ttk.Label(f, text=self.t("combine_hint"), wraplength=self.wrap(), justify="left").pack(anchor="w")
        self.info_btn(f, "info_phases", self.t("what_phases")).pack(anchor="e", pady=(2, 8))
        ttk.Button(f, text=self.t("src_open"), command=self.open_source).pack(fill="x")
        self.lbl_src = ttk.Label(f, text="")
        self.lbl_src.pack(anchor="w", pady=4)
        # controles de aplicar ficam embaixo e sempre visíveis
        bottom = ttk.Frame(f)
        bottom.pack(side="bottom", fill="x")
        self.rep_mode = tk.StringVar(value=self.cfg.get("rep_mode", "phase"))
        ttk.Radiobutton(bottom, text=self.t("rep_phase"), value="phase", variable=self.rep_mode).pack(anchor="w")
        r2 = ttk.Frame(bottom)
        r2.pack(fill="x")
        ttk.Radiobutton(r2, text=self.t("rep_group"), value="group", variable=self.rep_mode).pack(side="left")
        self.cb_replace = ttk.Combobox(r2, state="readonly", width=16)
        self.cb_replace.pack(side="left", padx=4)
        ttk.Radiobutton(bottom, text=self.t("rep_add"), value="add", variable=self.rep_mode).pack(anchor="w")
        r3 = ttk.Frame(bottom)
        r3.pack(fill="x", pady=(4, 0))
        ttk.Label(r3, text=self.t("import_phase")).pack(side="left")
        self.cb_phase = ttk.Combobox(r3, state="readonly", width=30,
                                     values=[self.t("keep")] + [stage_label(i, self.lang) for i in range(6)])
        self.cb_phase.current(0)
        self.cb_phase.pack(side="left", padx=4)
        r4 = ttk.Frame(bottom)
        r4.pack(fill="x", pady=(4, 0))
        ttk.Label(r4, text=self.t("import_ori")).pack(side="left")
        self.ori_vals = [None, 0, 1, 2, 4, 5]
        self.cb_ori = ttk.Combobox(r4, state="readonly", width=38,
                                   values=[self.t("keep")] + [ori_label(v, self.lang) for v in self.ori_vals[1:]])
        self.cb_ori.current(0)
        self.cb_ori.pack(side="left", padx=4)
        self.imp_hide_scene = tk.BooleanVar(value=False)
        self.imp_recolor = tk.BooleanVar(value=False)
        ttk.Checkbutton(bottom, text=self.t("import_hide_scene"), variable=self.imp_hide_scene).pack(anchor="w")
        ttk.Checkbutton(bottom, text=self.t("import_recolor"), variable=self.imp_recolor).pack(anchor="w")
        self.import_options(bottom).pack(anchor="w")
        ttk.Button(bottom, text=self.t("import_marked"), command=self.import_marked).pack(fill="x", pady=(8, 0), ipady=4)
        r = ttk.Frame(f)
        r.pack(fill="x")
        ttk.Button(r, text=self.t("mark_all"), command=lambda: self.srclist.set_all(True)).pack(side="left")
        ttk.Button(r, text=self.t("unmark_all"), command=lambda: self.srclist.set_all(False)).pack(side="left", padx=4)
        chips_holder = ttk.Frame(f)
        chips_holder.pack(fill="x", pady=4)
        self.srclist = MiniList(f, self, context=False)
        self.srclist.tree.configure(height=10)
        self.srclist.pack(fill="both", expand=True, pady=4)
        self.srclist.headings()
        self.src_chips = GroupChips(chips_holder, self, self.srclist, per_row=3)
        self.src_chips.pack(fill="x")
        if self.src:
            self.srclist.fill(self.src)
            self.src_chips.rebuild()
            self.lbl_src.config(text=self.t("source") + ": " + os.path.basename(self.src_path or ""))

    def open_source(self):
        p = filedialog.askopenfilename(filetypes=[("PAK", "*.pak"), ("*", "*.*")], parent=self)
        if not p:
            return
        try:
            self.src = Effect.load(p)
            self._load_groups(self.src, p)
        except (PakError, OSError) as ex:
            messagebox.showerror(self.t("err"), str(ex))
            return
        self.src_path = p
        self.lbl_src.config(text=self.t("source") + ": " + os.path.basename(p))
        self.srclist.fill(self.src)
        self.src_chips.rebuild()
        self._refresh_combos()

    def import_marked(self):
        if not self.eff or not self.src:
            return
        ms = [m for m in self.srclist.marked() if m.type != 0x00]
        if not ms:
            messagebox.showinfo(self.t("app_title"), self.t("nothing_marked"))
            return
        self.snapshot()
        ph = self.cb_phase.current()
        mode = self.rep_mode.get()
        self.cfg["rep_mode"] = mode
        self._save_cfg()
        removed = []
        if mode == "phase":
            phases = {ph - 1} if ph > 0 else set(m.get("invoke") for m in ms)
            removed = [m for m in self.eff.all_minis() if m.type != 0x00 and m.get("invoke") in phases]
        elif mode == "group":
            rg = self._combo_group(self.cb_replace)
            if rg is not None:
                removed = [m for m in self.eff.all_minis() if m.get("invoke") == rg and m.type != 0x00]
        color = self.eff.dominant_color() if self.imp_recolor.get() else None
        if removed:
            self.eff.remove_minis(removed)
        sig = self.eff.phase_signature(ph - 1) if ph > 0 else None
        added = self.eff.import_minis(self.src, ms)
        ori = self.ori_vals[max(0, self.cb_ori.current())]
        for m in added:
            if ph > 0:
                m.move_to_phase(ph - 1, sig)
                m.group = "phase%d" % (ph - 1)
            if ori is not None:
                m.param[10] = ori
            if self.imp_hide_scene.get():
                m.param[9] = 5
        if color and added:
            self.eff.recolor_parts(added, color)
        self._match_new()
        self.changed()
        messagebox.showinfo(self.t("ok"), self.t("imported2", n=len(added), r=len(removed)))
        return
        messagebox.showinfo(self.t("ok"), self.t("imported", n=len(added)))

    # ---- aba pré-disparo e disparo (antiga Comportamento)
    def _sec(self, f, key, info=None):
        hdr = ttk.Frame(f)
        hdr.pack(fill="x", pady=(4, 2))
        ttk.Label(hdr, text=self.t(key), font=("Segoe UI", self.fs(11), "bold")).pack(side="left")
        if info:
            self.info_btn(hdr, info, self.t("more_info")).pack(side="right")

    def tab_behavior(self, nb):
        f = self._tab(nb, "tab_behavior")
        self.lbl_beh_now = ttk.Label(f, text="", font=("Segoe UI", self.fs(9), "bold"), wraplength=self.wrap(), justify="left")
        self.lbl_beh_now.pack(anchor="w", pady=(0, 6))
        # 1) pré-disparo
        self._sec(f, "beh_sec_pre", "info_pre")
        pr = ttk.Frame(f)
        pr.pack(fill="x", pady=4)
        ttk.Label(pr, text=self.t("beh_model")).pack(side="left")
        self.pre_choice = None
        self.pre_file = None
        self.tree_button(pr, "pre_disparo", self._pick_pre).pack(side="left", padx=4)
        ttk.Button(f, text=self.t("pre_from_file"), command=self._pre_from_file).pack(anchor="w")
        self.lbl_pre = ttk.Label(f, text="", wraplength=self.wrap(), justify="left")
        self.lbl_pre.pack(anchor="w", pady=4)
        self.pre_recolor = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text=self.t("beh_opt_color"), variable=self.pre_recolor).pack(anchor="w")
        ttk.Button(f, text="✔ " + self.t("pre_apply"), command=self._apply_pre).pack(fill="x", pady=6, ipady=3)
        # 2) disparo
        ttk.Separator(f).pack(fill="x", pady=12)
        self._sec(f, "beh_sec_launch", "info_behavior")
        r = ttk.Frame(f)
        r.pack(fill="x", pady=4)
        ttk.Label(r, text=self.t("beh_model")).pack(side="left")
        self.tree_button(r, "modelos", self._load_beh_name).pack(side="left", padx=4)
        ttk.Button(f, text=self.t("beh_browse"), command=self._browse_beh).pack(anchor="w")
        self.lbl_beh = ttk.Label(f, text="", wraplength=self.wrap(), justify="left")
        self.lbl_beh.pack(anchor="w", pady=8)
        self.beh_launch = tk.BooleanVar(value=True)
        self.beh_recolor = tk.BooleanVar(value=True)
        self.beh_header = tk.BooleanVar(value=True)
        self.beh_scene = tk.BooleanVar(value=True)
        self.beh_mode = tk.StringVar(value="shape")
        ttk.Radiobutton(f, text=self.t("beh_mode_shape"), value="shape", variable=self.beh_mode).pack(anchor="w")
        ttk.Radiobutton(f, text=self.t("beh_mode_only"), value="only", variable=self.beh_mode).pack(anchor="w", pady=(0, 6))
        ttk.Checkbutton(f, text=self.t("beh_opt_hits"), state="disabled", variable=tk.BooleanVar(value=True)).pack(anchor="w")
        ttk.Checkbutton(f, text=self.t("beh_opt_launch"), variable=self.beh_launch).pack(anchor="w")
        ttk.Checkbutton(f, text=self.t("beh_opt_header"), variable=self.beh_header).pack(anchor="w")
        ttk.Checkbutton(f, text=self.t("beh_opt_color"), variable=self.beh_recolor).pack(anchor="w")
        ttk.Checkbutton(f, text=self.t("beh_opt_scene"), variable=self.beh_scene).pack(anchor="w", pady=(0, 6))
        self.import_options(f).pack(anchor="w", pady=(0, 6))
        ttk.Label(f, text=self.t("beh_steps"), wraplength=self.wrap(), justify="left", foreground="#8a8f99").pack(anchor="w")
        ttk.Button(f, text="✔ " + self.t("beh_apply"), command=self._apply_beh).pack(fill="x", pady=6, ipady=3)
        bb = ttk.Frame(f)
        bb.pack(fill="x", pady=(4, 4))
        self.lbl_barrage = ttk.Label(bb, text="")
        self.lbl_barrage.pack(side="left")
        ttk.Button(bb, text=self.t("barrage_on"), command=lambda: self._barrage(True)).pack(side="left", padx=4)
        ttk.Button(bb, text=self.t("barrage_off"), command=lambda: self._barrage(False)).pack(side="left")
        self.info_btn(bb, "info_barrage").pack(side="left", padx=4)
        st = ttk.Frame(f)
        st.pack(fill="x", pady=(2, 6))
        bst = ttk.Button(st, text=self.t("stripes_hide"), command=lambda: self._stripes(True))
        bst.pack(side="left", fill="x", expand=True)
        self.hover_bind(bst, "info:stripes")
        ttk.Button(st, text=self.t("stripes_show"), command=lambda: self._stripes(False)).pack(side="left", fill="x", expand=True, padx=4)
        self.info_btn(st, "info_stripes").pack(side="left")
        ttk.Button(st, text="🖼", width=3, command=lambda: self.show_image("info:stripes", self.t("stripes_hide"))).pack(side="left", padx=2)
        self._beh_summary()

    def _counts(self, eff):
        ms = [m for m in eff.all_minis() if m.type != 0x00]
        return (sum(1 for m in ms if m.get("invoke") == 0), sum(1 for m in ms if m.get("invoke") == 1),
                sum(1 for m in eff.all_minis() if m.hits))

    def _pre_from_file(self):
        p = filedialog.askopenfilename(filetypes=[("PAK", "*.pak"), ("*", "*.*")], parent=self)
        if not p:
            return
        try:
            eff = Effect.load(p)
        except (PakError, OSError) as ex:
            messagebox.showerror(self.t("err"), str(ex))
            return
        k = sum(1 for m in eff.all_minis() if m.type != 0x00 and m.get("invoke") == 0)
        if not k:
            messagebox.showinfo(self.t("app_title"), self.t("pre_none_in_file"))
            return
        self.pre_file, self.pre_choice = (eff, os.path.basename(p)), None
        self.lbl_pre.config(text=self.t("pre_src", n=os.path.basename(p), k=k))

    def _browse_beh(self):
        p = filedialog.askopenfilename(filetypes=[("PAK", "*.pak"), ("*", "*.*")], parent=self)
        if p:
            self._load_beh(p)

    def _barrage(self, on):
        if not self.eff:
            return
        self.snapshot()
        self.eff.set_barrage(on, in_scene=self.eff.header[0x27] == 3 and on)
        self.changed()

    def _apply_pre(self):
        if not self.eff or not (self.pre_choice or self.pre_file):
            return
        if self.pre_file:
            pre, only0 = self.pre_file[0], True
        else:
            try:
                pre, only0 = Effect.from_bytes(RES.get("pre_disparo", self.pre_choice)), False
            except (PakError, TypeError) as ex:
                messagebox.showerror(self.t("err"), str(ex))
                return
        self.snapshot()
        added, color = self.eff.apply_prelaunch(pre, recolor=self.pre_recolor.get(), stage0_only=only0)
        self._match_new()
        self.changed()
        messagebox.showinfo(self.t("ok"), self.t("pre_done", n=len(added)))

    WARNINGS = (("Cortes de Espada", "warn_magic344"), ("Cortes Trunks", "warn_magic344"),
                ("Espada de Ki", "warn_params"), ("Paralisia General Blue", "warn_scene_only"))

    def _warn_for(self, name):
        for key, msg in self.WARNINGS:
            if key in name:
                messagebox.showwarning(self.t("app_title"), self.t(msg))
                return

    def _pick_pre(self, name):
        self.pre_choice, self.pre_file = name, None
        if hasattr(self, "lbl_pre"):
            self.lbl_pre.config(text="")
        self._warn_for(name)

    def _load_beh_name(self, name):
        self._warn_for(name)
        try:
            self.beh_tpl, self.beh_tpl_path = Effect.from_bytes(RES.get("modelos", name)), name
        except (PakError, TypeError) as ex:
            messagebox.showerror(self.t("err"), str(ex))
            return
        self._beh_summary()

    def _load_beh(self, p):
        try:
            self.beh_tpl, self.beh_tpl_path = Effect.load(p), p
        except (PakError, OSError) as ex:
            messagebox.showerror(self.t("err"), str(ex))
            return
        self._beh_summary()

    def _describe_hits(self, eff):
        hs = eff.behavior_summary() if eff else []
        if not hs:
            return self.t("beh_none"), ""
        desc = ", ".join("%02X/inv %d" % (m.type, m.get("invoke")) for m in hs)
        bits = sorted(set(m.get("invoke") for m in hs))
        b = ", ".join({4: "00100000", 5: "01000000"}[i] for i in bits)
        return desc, b

    def _beh_summary(self):
        if not hasattr(self, "lbl_beh"):
            return
        if self.eff and hasattr(self, "lbl_beh_now"):
            p, d, h = self._counts(self.eff)
            self.lbl_beh_now.config(text=self.t("beh_now", p=p, d=d, h=h))
        if self.beh_tpl:
            p, d, h = self._counts(self.beh_tpl)
            self.lbl_beh.config(text=self.t("beh_tpl_now", n=os.path.splitext(os.path.basename(self.beh_tpl_path))[0], p=p, d=d, h=h))
        else:
            self.lbl_beh.config(text="")

    def _apply_beh(self):
        if not self.eff or not self.beh_tpl:
            return
        if not self.beh_tpl.all_minis():
            self.snapshot()
            ok = self.eff.copy_scene(self.beh_tpl)
            self.changed()
            messagebox.showinfo(self.t("ok"), self.t("scene_copied") if ok else self.t("scene_empty"))
            return
        self.snapshot()
        scene_copied = self.beh_scene.get() and self.beh_mode.get() != "only" and self.eff.copy_scene(self.beh_tpl)
        added, color = self.eff.apply_behavior(self.beh_tpl, launch=self.beh_launch.get(), recolor=self.beh_recolor.get(),
                                                 header=self.beh_header.get(),
                                                 keep_shape=self.beh_mode.get() == "only")
        self._match_new()
        self.changed()
        msg = self.t("beh_done_only", n=len(added), p=self.eff.launch_phase()) if self.beh_mode.get() == "only" \
            else self.t("beh_done2", n=len(added))
        if color:
            msg += "\n" + self.t("painted", c="#%02x%02x%02x" % color)
        if scene_copied:
            msg += "\n" + self.t("scene_copied")
        messagebox.showinfo(self.t("ok"), msg)

    # ---- aba cena ao acertar
    SCENE_PRESETS = [("none", None), ("ground", "chao.bin"), ("air", "ar.bin")]

    def _scene_data(self, fname):
        return RES.get("cenas", fname)

    def tab_scene(self, nb):
        f = self._tab(nb, "tab_scene")
        self.info_btn(f, "info_scene", self.t("more_info")).pack(anchor="e")
        self.lbl_scene = ttk.Label(f, text="", font=("Segoe UI", self.fs(10), "bold"))
        self.lbl_scene.pack(anchor="w", pady=(0, 8))
        self.scene_var = tk.StringVar(value="")
        for key, fname in self.SCENE_PRESETS:
            ok = fname is None or self._scene_data(fname) is not None
            rb = ttk.Radiobutton(f, text=self.t("scene_" + key) + ("" if ok else "  " + self.t("scene_missing")),
                                 value=key, variable=self.scene_var, state="normal" if ok else "disabled")
            rb.pack(anchor="w", pady=2)
        ttk.Button(f, text=self.t("apply"), command=self._apply_scene).pack(fill="x", pady=8)
        ttk.Separator(f).pack(fill="x", pady=6)
        ttk.Button(f, text=self.t("scene_copy"), command=self._copy_scene).pack(fill="x")
        r = ttk.Frame(f)
        r.pack(fill="x", pady=(8, 0))
        ttk.Label(r, text=self.t("scene_save_as")).pack(side="left")
        ttk.Button(r, text=self.t("scene_ground"), command=lambda: self._save_scene("chao.bin")).pack(side="left", padx=4)
        ttk.Button(r, text=self.t("scene_air"), command=lambda: self._save_scene("ar.bin")).pack(side="left")
        ttk.Button(f, text=self.t("scene_table_btn"), command=self._scene_table).pack(fill="x", pady=(8, 0))
        # como o golpe aparece na ceninha (bytes 0x21-0x27 do 03.dat)
        ttk.Separator(f).pack(fill="x", pady=12)
        hdr = ttk.Frame(f)
        hdr.pack(fill="x")
        ttk.Label(hdr, text=self.t("appear_title"), font=("Segoe UI", self.fs(10), "bold")).pack(side="left")
        self.info_btn(hdr, "info_appear", self.t("more_info")).pack(side="right")
        self.appear_var = tk.StringVar(value="none")
        for k in ("none", "beam", "projectile", "vertical"):
            ttk.Radiobutton(f, text=self.t("appear_" + k), value=k, variable=self.appear_var).pack(anchor="w")
        self.appear_barrage = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text=self.t("appear_barrage"), variable=self.appear_barrage).pack(anchor="w", pady=(4, 0))
        ttk.Button(f, text=self.t("apply"), command=self._apply_appear).pack(fill="x", pady=6)
        # grupo 01 durante a ceninha
        ttk.Separator(f).pack(fill="x", pady=8)
        hdr = ttk.Frame(f)
        hdr.pack(fill="x")
        ttk.Label(hdr, text=self.t("persist_scene_title"), font=("Segoe UI", self.fs(10), "bold")).pack(side="left")
        self.info_btn(hdr, "info_persist_scene", self.t("more_info")).pack(side="right")
        tk.Label(f, text="⚠ " + self.t("persist_scene_warn"), fg="#e0a030", wraplength=self.wrap(), justify="left").pack(anchor="w", pady=(2, 4))
        sc = ttk.Frame(f)
        sc.pack(fill="x")
        self.persist_scope = tk.StringVar(value="all")
        ttk.Radiobutton(sc, text=self.t("persist_scope_all"), value="all", variable=self.persist_scope).pack(side="left")
        ttk.Radiobutton(sc, text=self.t("persist_scope_marked"), value="marked", variable=self.persist_scope).pack(side="left", padx=6)
        ttk.Button(sc, text=self.t("persist_before_after"), command=self._scene_before_after).pack(side="right")
        pr = ttk.Frame(f)
        pr.pack(fill="x", pady=4)
        ttk.Button(pr, text=self.t("persist_scene_off"), command=lambda: self._scene_persist(False)).pack(side="left", fill="x", expand=True)
        ttk.Button(pr, text=self.t("persist_scene_on"), command=lambda: self._scene_persist(True)).pack(side="left", fill="x", expand=True, padx=(4, 0))
        # explosão (Vfx 5)
        ttk.Separator(f).pack(fill="x", pady=12)
        hdr = ttk.Frame(f)
        hdr.pack(fill="x")
        ttk.Label(hdr, text=self.t("expl_title"), font=("Segoe UI", self.fs(10), "bold")).pack(side="left")
        self.info_btn(hdr, "info_expl", self.t("more_info")).pack(side="right")
        cr = ttk.Frame(f)
        cr.pack(fill="x", pady=6)
        ttk.Label(cr, text=self.t("dominant")).pack(side="left")
        self.sw_dom = tk.Label(cr, width=4, relief="solid", bd=1)
        self.sw_dom.pack(side="left", padx=6)
        self.lbl_dom = ttk.Label(cr, text="")
        self.lbl_dom.pack(side="left")
        self.expl_recolor = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text=self.t("expl_color"), variable=self.expl_recolor).pack(anchor="w")
        ttk.Button(f, text=self.t("expl_add"), command=self._add_explosion,
                   state="normal" if RES.get("extras", EXPLOSION) else "disabled").pack(fill="x", pady=6)
        self._scene_status()

    def _scene_status(self):
        if not hasattr(self, "lbl_scene"):
            return
        if not self.eff:
            self.lbl_scene.config(text="")
            return
        cur = self.eff.pre[2] if len(self.eff.pre) > 2 else b""
        state = "custom"
        if not cur:
            state = "none"
        else:
            for key, fname in self.SCENE_PRESETS:
                if fname and self._scene_data(fname) == cur:
                    state = key
        self.lbl_scene.config(text=self.t("scene_current") + " " + self.t("scene_" + state))
        ap = self.eff.scene_appear()
        self.appear_var.set(ap if ap != "custom" else "")
        self.appear_barrage.set(self.eff.header[0x27] == 3)
        dom = self.eff.dominant_color()
        if dom:
            hx = "#%02x%02x%02x" % dom
            self.sw_dom.config(bg=hx)
            self.lbl_dom.config(text=hx)
        else:
            self.lbl_dom.config(text="—")
        self.scene_var.set(state if state != "custom" else "")

    def _apply_scene(self):
        if not self.eff:
            return
        key = self.scene_var.get()
        data = b""
        for k, fname in self.SCENE_PRESETS:
            if k == key and fname:
                data = self._scene_data(fname)
                if data is None:
                    return
        if key not in dict(self.SCENE_PRESETS):
            return
        self.snapshot()
        self.eff.pre[2] = data
        self.changed()

    def _apply_appear(self):
        if not self.eff:
            return
        want_barrage = self.appear_barrage.get()
        if want_barrage and not self.eff.is_barrage():
            if not messagebox.askyesno(self.t("app_title"), self.t("appear_need_barrage")):
                return
        self.snapshot()
        self.eff.set_scene_appear(self.appear_var.get())
        if want_barrage:
            self.eff.set_barrage(True, in_scene=True)
        elif self.eff.header[0x27] == 3:
            self.eff.header[0x27] = 2
        self.changed()

    def _scene_before_after(self):
        self.show_gallery([("info:scene_before", self.t("ba_before")), ("info:scene_after", self.t("ba_after"))],
                          self.t("persist_scene_title"))

    def show_gallery(self, items, title):
        """Imagens com setas ◀ ▶ (e as setas do teclado) para alternar, sem fechar sozinho."""
        imgs = [(self._image_for(k, 1000, 700), cap) for k, cap in items]
        imgs = [x for x in imgs if x[0] is not None]
        if not imgs:
            messagebox.showinfo(self.t("app_title"), self.t("no_image"))
            return
        w = tk.Toplevel(self)
        w.title(title)
        w.transient(self)
        cap = ttk.Label(w, font=("Segoe UI", self.fs(12), "bold"))
        cap.pack(pady=(8, 4))
        lb = tk.Label(w, bd=0)
        lb.pack()
        bar = ttk.Frame(w, padding=8)
        bar.pack(fill="x")
        pos = {"i": 0}

        def show(i):
            pos["i"] = i % len(imgs)
            img, c = imgs[pos["i"]]
            lb.config(image=img)
            lb.image = img
            cap.config(text="%s   (%d/%d)" % (c, pos["i"] + 1, len(imgs)))
        ttk.Button(bar, text="◀", width=6, command=lambda: show(pos["i"] - 1)).pack(side="left")
        ttk.Label(bar, text=self.t("ba_keys"), foreground="#8a8f99").pack(side="left", expand=True)
        ttk.Button(bar, text="▶", width=6, command=lambda: show(pos["i"] + 1)).pack(side="right")
        for ev, d in (("<Left>", -1), ("<Right>", 1), ("<Up>", -1), ("<Down>", 1), ("<space>", 1)):
            w.bind(ev, lambda e, d=d: show(pos["i"] + d))
        w.bind("<Escape>", lambda e: w.destroy())
        show(0)
        w.focus_force()

    def _scene_persist(self, on):
        if not self.eff:
            return
        minis = None
        if getattr(self, "persist_scope", None) is not None and self.persist_scope.get() == "marked":
            minis = self.list.marked()
            if not minis:
                messagebox.showinfo(self.t("app_title"), self.t("nothing_marked"))
                return
        self.snapshot()
        n = self.eff.scene_persist(on, minis)
        self.changed()
        messagebox.showinfo(self.t("ok"), self.t("persist_scene_done", n=n))

    def _scene_table(self):
        if not self.eff or len(self.eff.pre) < 3:
            return
        w = tk.Toplevel(self)
        w.title(self.t("scene_table_btn"))
        w.transient(self)
        box = ttk.Frame(w, padding=10)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text=self.t("scene_table_hint"), wraplength=460, justify="left").grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(box, text=self.t("scene_map")).grid(row=1, column=0, sticky="w", pady=6)
        cb = ttk.Combobox(box, state="readonly", values=["%02d - %s" % (i, MAP_NAMES[i]) for i in range(SCENE_MAPS)], width=28)
        cb.current(0)
        cb.grid(row=1, column=1, sticky="w")
        vars_ = []
        ttk.Label(box, text=self.t("scene_event")).grid(row=2, column=0)
        ttk.Label(box, text=self.t("scene_x")).grid(row=2, column=1)
        ttk.Label(box, text=self.t("scene_y")).grid(row=2, column=2)
        ttk.Label(box, text=self.t("scene_z")).grid(row=2, column=3)
        for ev in range(SCENE_EVENTS):
            vx, vy, vz = tk.StringVar(), tk.StringVar(), tk.StringVar()
            ttk.Label(box, text=str(ev + 1)).grid(row=3 + ev, column=0)
            for j, v in enumerate((vx, vy, vz)):
                ttk.Entry(box, textvariable=v, width=10).grid(row=3 + ev, column=1 + j, padx=2, pady=1)
            vars_.append((vx, vy, vz))

        def load(_=None):
            data = self.eff.pre[2] or bytes(2816)
            mp = cb.current()
            for ev, vs in enumerate(vars_):
                for v, val in zip(vs, scene_row(data, mp, ev)):
                    v.set("%g" % val)
        cb.bind("<<ComboboxSelected>>", load)

        def apply(all_maps=False):
            try:
                vals = [tuple(float(v.get().replace(",", ".")) for v in vs) for vs in vars_]
            except ValueError as ex:
                messagebox.showerror(self.t("err"), str(ex), parent=w)
                return
            self.snapshot(self.t("act_scene_table"))
            data = self.eff.pre[2] or bytes(2816)
            for mp in (range(SCENE_MAPS) if all_maps else [cb.current()]):
                for ev, (x, y, z) in enumerate(vals):
                    data = scene_set3(data, mp, ev, x, y, z)
            self.eff.pre[2] = data
            self.changed()
        br = ttk.Frame(box)
        br.grid(row=9, column=0, columnspan=4, sticky="ew", pady=8)
        ttk.Button(br, text=self.t("scene_apply_map"), command=apply).pack(side="left", fill="x", expand=True)
        ttk.Button(br, text=self.t("scene_apply_all"), command=lambda: apply(True)).pack(side="left", fill="x", expand=True, padx=4)
        load()

    def _add_explosion(self):
        if not self.eff:
            return
        try:
            ex = Effect.from_bytes(RES.get("extras", EXPLOSION))
        except (PakError, OSError, TypeError) as e:
            messagebox.showerror(self.t("err"), str(e))
            return
        if not self.eff.pre[2] and not messagebox.askyesno(self.t("app_title"), self.t("expl_noscene")):
            return
        self.snapshot()
        added, color = self.eff.add_explosion(ex, recolor=self.expl_recolor.get())
        self._match_new()
        self.changed()
        msg = self.t("expl_done", n=len(added))
        if color:
            msg += "\n" + self.t("painted", c="#%02x%02x%02x" % color)
        messagebox.showinfo(self.t("ok"), msg)

    def _copy_scene(self):
        if not self.eff:
            return
        p = filedialog.askopenfilename(filetypes=[("PAK", "*.pak"), ("*", "*.*")], parent=self)
        if not p:
            return
        try:
            data = Effect.load(p).pre[2]
        except (PakError, OSError) as ex:
            messagebox.showerror(self.t("err"), str(ex))
            return
        self.snapshot()
        self.eff.pre[2] = data
        self.changed()

    def _save_scene(self, fname):
        if not self.eff or not self.eff.pre[2]:
            messagebox.showinfo(self.t("app_title"), self.t("scene_empty"))
            return
        os.makedirs(SCENES, exist_ok=True)
        with open(os.path.join(SCENES, fname), "wb") as fh:
            fh.write(self.eff.pre[2])
        self.build_ui()

    # ---- peso
    def show_weight(self):
        if not self.eff:
            return
        lines = [self.t("w_total", kb=len(self.eff.to_bytes()) / 1024.0), ""]
        rows = []
        for c in self.eff.cats:
            for i, d in enumerate(c.dbts):
                users = [m for m in c.minis if m.get("dbt") == i]
                gs = sorted(set(stage_label(m.get("invoke"), self.lang, num=False) for m in users))
                rows.append((len(d), "  %s / DBT %d — %.1f KB — %d mini — %s" % (class_label(c.type, self.lang), i, len(d) / 1024.0, len(users), ", ".join(gs))))
        dbt_total = sum(r[0] for r in rows)
        other = sum(len(f) for m in self.eff.all_minis() for f in m.files)
        lines.append(self.t("w_dbt", kb=dbt_total / 1024.0))
        lines += [r[1] for r in sorted(rows, reverse=True)]
        lines += ["", self.t("w_other", kb=other / 1024.0), self.t("w_pre", kb=sum(len(x) for x in self.eff.pre) / 1024.0),
                  "", self.t("w_tip"), "", self.t("w_scene_tip") if len(self.eff.pre) > 2 and self.eff.pre[2] else ""]
        w = tk.Toplevel(self)
        w.title(self.t("w_title"))
        txt = tk.Text(w, wrap="word", width=80, height=26, font=("Consolas", self.fs(9)), padx=10, pady=10)
        txt.insert("1.0", "\n".join(lines))
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True)
        ttk.Button(w, text=self.t("close"), command=w.destroy).pack(pady=6)

    # ---- aba extras
    def _extras_list(self):
        return RES.extras_manifest()

    def _extra_tag(self, x):
        kind = x.get("kind", "x")
        if kind.startswith("custom"):
            return "extra:%s:%s:%s" % (kind, x.get("slot", "launch"), x.get("name", "").replace(":", " "))
        return "extra:%s:%s" % (kind, x.get("slot", "launch"))

    def _extra_label(self, x):
        if x.get("kind", "").startswith("custom"):
            return x.get("name") or self.t("ext_custom")
        return self.t("kind_" + x.get("kind", "x"))

    def tab_extras(self, nb):
        f = self._tab(nb, "tab_extras")
        self.info_btn(f, "info_extras", self.t("more_info")).pack(anchor="e")
        ttk.Label(f, text=self.t("extras_hint"), wraplength=self.wrap(), justify="left").pack(anchor="w", pady=(0, 8))
        self.extra_vars = {}
        self.extra_widgets = {}
        items = self._extras_list()
        for slot in (("aura", "charge", "pair") if self._ui_kind == "aura" else ("aura", "charge", "pair", "launch")):
            ttk.Label(f, text=self.t("slot_" + slot), font=("Segoe UI", self.fs(10), "bold")).pack(anchor="w", pady=(6, 2))
            if slot == "aura":
                ar = ttk.Frame(f)
                ar.pack(anchor="w", padx=12)
                ttk.Label(ar, text=self.t("aura_stage")).pack(side="left")
                self.aura_stage = tk.StringVar(value=self.cfg.get("aura_stage", "0"))
                ttk.Radiobutton(ar, text=self.t("aura_stage0"), value="0", variable=self.aura_stage).pack(side="left", padx=4)
                ttk.Radiobutton(ar, text=self.t("aura_stage3"), value="3", variable=self.aura_stage).pack(side="left")
            found = False
            for x in items:
                if x.get("slot") != slot:
                    continue
                found = True
                v = tk.BooleanVar(value=False)
                tag = self._extra_tag(x)
                row = ttk.Frame(f)
                row.pack(anchor="w", padx=12, fill="x")
                label = self._extra_label(x)
                if x.get("requires") == "beam":
                    label += "  " + self.t("needs_beam")
                cbw = ttk.Checkbutton(row, text=label, variable=v)
                cbw.pack(side="left")
                self.hover_bind(cbw, "extras:" + tag[6:])
                if self.has_image("extras:" + tag[6:]):
                    ttk.Button(row, text="🖼", width=3,
                               command=lambda t=tag, l=label: self.show_image("extras:" + t[6:], l)).pack(side="left", padx=4)
                self.extra_vars[tag] = (v, x)
                self.extra_widgets[tag] = cbw
            # complementares importados nesta sessão (não guardados na lista)
            if self.eff:
                for g in sorted(set(m.group for m in self.eff.all_minis())):
                    if g.startswith("extra:custom") and g.split(":")[2] == slot and g not in self.extra_vars:
                        v = tk.BooleanVar(value=True)
                        ttk.Checkbutton(f, text=group_label(g, self.lang), variable=v).pack(anchor="w", padx=12)
                        self.extra_vars[g] = (v, {"slot": slot, "kind": g.split(":")[1], "_session": True})
                        found = True
            if not found:
                ttk.Label(f, text="—").pack(anchor="w", padx=12)
        self.extra_recolor = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text=self.t("expl_color"), variable=self.extra_recolor).pack(anchor="w", pady=(10, 0))
        self.import_options(f).pack(anchor="w")
        ttk.Button(f, text=self.t("extras_apply"), command=self._apply_extras).pack(fill="x", pady=8)
        ttk.Separator(f).pack(fill="x", pady=6)
        ttk.Button(f, text="⤓ " + self.t("ext_import"), command=self._extra_import).pack(fill="x")
        self._extras_status()

    def _extras_status(self):
        if not hasattr(self, "extra_vars"):
            return
        present = set(m.group for m in self.eff.all_minis()) if self.eff else set()
        has_beam = bool(self.eff) and any(m.type == 0x11 for m in self.eff.all_minis())
        for tag, (v, x) in self.extra_vars.items():
            v.set(tag in present)
            wdg = self.extra_widgets.get(tag)
            if wdg is not None and x.get("requires") == "beam":
                wdg.config(state="normal" if has_beam or tag in present else "disabled")

    def _add_extra_eff(self, ex, x, tag):
        slot = x.get("slot", "launch")
        if slot == "aura":
            if self.aura_stage.get() == "3":
                return self.eff.add_extra(ex, slot, tag, recolor=self.extra_recolor.get(), src_lp=-1, to_charge=False)
            return self.eff.add_extra(ex, slot, tag, recolor=self.extra_recolor.get(), src_lp=-1, to_charge=True)
        return self.eff.add_extra(ex, slot, tag, recolor=self.extra_recolor.get(),
                                  src_lp=int(x.get("src_lp", 1)), to_charge=bool(x.get("to_charge")))

    def _apply_extras(self):
        if not self.eff:
            return
        self.cfg["aura_stage"] = self.aura_stage.get() if hasattr(self, "aura_stage") else "0"
        want = {tag: v.get() for tag, (v, x) in self.extra_vars.items()}
        for tag, (v, x) in self.extra_vars.items():      # um extra que já inclui outro desliga o outro
            if want.get(tag):
                for cov in x.get("covers", []):
                    if cov in want:
                        want[cov] = False
                        self.extra_vars[cov][0].set(False)
        present = set(m.group for m in self.eff.all_minis())
        todo = [(tag, on, self.extra_vars[tag][1]) for tag, on in want.items() if on != (tag in present)]
        if not todo:
            return
        self.snapshot()
        added = removed = 0
        for tag, on, x in sorted(todo, key=lambda t: t[1]):   # remove antes de adicionar
            if on:
                if x.get("_session"):
                    continue
                try:
                    ex = Effect.from_bytes(RES.get("extras", x["file"]))
                except (PakError, OSError, TypeError, KeyError) as e:
                    messagebox.showerror(self.t("err"), str(e))
                    continue
                added += len(self._add_extra_eff(ex, x, tag))
            else:
                removed += self.eff.remove_extra(tag)
        self._match_new()
        self.changed()
        messagebox.showinfo(self.t("ok"), self.t("extras_done", a=added, r=removed, p=self.eff.launch_phase()))

    def _extra_import(self):
        """Importa mini-efeitos de qualquer .pak como complementar (aura, pré-disparo, os dois ou pós-disparo)."""
        if not self.eff:
            return
        p = filedialog.askopenfilename(filetypes=[("PAK", "*.pak"), ("*", "*.*")], parent=self)
        if not p:
            return
        try:
            src = Effect.load(p)
        except (PakError, OSError) as ex:
            messagebox.showerror(self.t("err"), str(ex))
            return
        w = tk.Toplevel(self)
        w.title(self.t("ext_imp_title") + " — " + os.path.basename(p))
        w.transient(self)
        w.geometry("900x560")
        box = ttk.Frame(w, padding=8)
        box.pack(fill="both", expand=True)
        lst = MiniList(box, self, context=False)
        lst.headings()
        lst.fill(src)
        lst.set_all(True, lambda m: m.type != 0x00)
        opts = ttk.Frame(box)
        opts.pack(side="bottom", fill="x", pady=(6, 0))
        lst.pack(fill="both", expand=True)
        r = ttk.Frame(opts)
        r.pack(fill="x")
        ttk.Label(r, text=self.t("ext_imp_slot")).pack(side="left")
        slots = ["aura", "charge", "pair", "launch"]
        cb = ttk.Combobox(r, state="readonly", width=30, values=[self.t("slot_" + k) for k in slots])
        cb.current(2)
        cb.pack(side="left", padx=4)
        ttk.Label(r, text=self.t("ext_imp_name")).pack(side="left", padx=(12, 2))
        name = tk.StringVar(value=os.path.splitext(os.path.basename(p))[0])
        ttk.Entry(r, textvariable=name, width=24).pack(side="left")
        save = tk.BooleanVar(value=False)
        recolor = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text=self.t("expl_color"), variable=recolor).pack(anchor="w")
        ttk.Checkbutton(opts, text=self.t("ext_imp_save"), variable=save).pack(anchor="w")

        def ok():
            marked = [m for m in lst.marked() if m.type != 0x00]
            if not marked:
                messagebox.showinfo(self.t("app_title"), self.t("nothing_marked"), parent=w)
                return
            sub = Effect.from_bytes(src.to_bytes())
            keep_idx = set(lst.minis.index(m) for m in marked)
            subm = sub.all_minis()
            sub.remove_minis([m for i, m in enumerate(subm) if i not in keep_idx and m.type != 0x00])
            slot = slots[max(0, cb.current())]
            nm = (name.get().strip() or self.t("ext_custom")).replace(":", " ")
            safe = "".join(ch if ch.isalnum() else "_" for ch in nm).strip("_")[:40] or "importado"
            if slot == "launch":                      # tudo vai para o pós-disparo
                sig = sub.phase_signature(1)
                for m in sub.all_minis():
                    if m.type != 0x00 and m.get("invoke") != 1:
                        m.move_to_phase(1, sig)
            x = {"slot": slot, "kind": "custom_" + safe, "name": nm, "src_lp": 1, "to_charge": slot == "charge"}
            tag = self._extra_tag(x)
            self.snapshot(self.t("act_extra_import"))
            self.extra_recolor.set(recolor.get())
            added = self._add_extra_eff(sub, x, tag)
            if save.get():
                try:
                    os.makedirs(EXTRAS, exist_ok=True)
                    x["file"] = safe + ".pak"
                    with open(os.path.join(EXTRAS, x["file"]), "wb") as fh:
                        fh.write(sub.to_bytes())
                    mpath = os.path.join(EXTRAS, "extras.json")
                    man = []
                    if os.path.exists(mpath):
                        with open(mpath, encoding="utf-8") as fh:
                            man = json.load(fh)
                    man = [y for y in man if y.get("file") != x["file"]] + [x]
                    with open(mpath, "w", encoding="utf-8") as fh:
                        json.dump(man, fh, ensure_ascii=False, indent=1)
                except (OSError, ValueError) as ex:
                    messagebox.showerror(self.t("err"), str(ex), parent=w)
            self._match_new()
            w.destroy()
            self.changed()
            self.build_ui()
            messagebox.showinfo(self.t("ok"), self.t("ext_imp_done", n=len(added)))
        ttk.Button(opts, text="✔ " + self.t("ext_imp_ok"), command=ok).pack(fill="x", pady=6, ipady=3)

    # ---- aba formato da aura (arquivos 01_charge_aura.pak)
    def tab_aura(self, nb):
        f = self._tab(nb, "tab_aura")
        self.info_btn(f, "info_aura", self.t("more_info")).pack(anchor="e")
        if self._ui_kind == "support":
            tk.Label(f, text=self.t("aura_on_support_warn"), fg="#b00020", wraplength=self.wrap(), justify="left").pack(anchor="w", pady=(0, 6))
        ttk.Label(f, text=self.t("aura_hint"), wraplength=self.wrap(), justify="left").pack(anchor="w", pady=(0, 8))
        self.aura_files = RES.list("auras")
        r = ttk.Frame(f)
        r.pack(fill="x", pady=4)
        ttk.Label(r, text=self.t("aura_model")).pack(side="left")
        self.cb_aura = ttk.Combobox(r, state="readonly", width=28, values=[os.path.splitext(x)[0] for x in self.aura_files])
        ttk.Button(r, text="🖼", width=3, command=lambda: self.cb_aura.current() >= 0 and self.show_image(
            "auras/" + self.aura_files[self.cb_aura.current()], self.cb_aura.get())).pack(side="right")
        self.cb_aura.pack(side="left", padx=4)
        self.aura_recolor = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text=self.t("aura_keep_color"), variable=self.aura_recolor).pack(anchor="w")
        ttk.Button(f, text=self.t("aura_apply"), command=self._apply_aura).pack(fill="x", pady=8)

    def _apply_aura(self):
        if not self.eff or self.cb_aura.current() < 0:
            return
        try:
            tpl = Effect.from_bytes(RES.get("auras", self.aura_files[self.cb_aura.current()]))
        except (PakError, TypeError) as ex:
            messagebox.showerror(self.t("err"), str(ex))
            return
        self.snapshot()
        new, color = self.eff.swap_aura(tpl, recolor=self.aura_recolor.get(), force=self._force())
        self.eff = new
        self.changed()
        msg = self.t("aura_done")
        if color:
            msg += "\n" + self.t("painted", c="#%02x%02x%02x" % color)
        messagebox.showinfo(self.t("ok"), msg)

    # ---- aba suporte / skills (00_skill_001, 01_skill_002, 00_effect_skill_1, 01_effect_skill_2)
    MOVING_REF = "Paralisia Hitto (móvel).pak"

    def tab_support(self, nb):
        f = self._tab(nb, "tab_support")
        self.info_btn(f, "info_support", self.t("more_info")).pack(anchor="e")
        ttk.Label(f, text=self.t("support_hint"), wraplength=self.wrap(), justify="left").pack(anchor="w", pady=(0, 8))
        r = ttk.Frame(f)
        r.pack(fill="x", pady=4)
        ttk.Label(r, text=self.t("aura_model")).pack(side="left")
        self.sup_choice = None
        self.tree_button(r, "suportes", lambda n: setattr(self, "sup_choice", n), width=30).pack(side="left", padx=4)
        self.sup_recolor = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text=self.t("aura_keep_color"), variable=self.sup_recolor).pack(anchor="w")
        ttk.Button(f, text=self.t("support_apply"), command=self._apply_support).pack(fill="x", pady=8)

    def _apply_support(self):
        if not self.eff or not self.sup_choice:
            return
        try:
            tpl = Effect.from_bytes(RES.get("suportes", self.sup_choice))
        except (PakError, TypeError) as ex:
            messagebox.showerror(self.t("err"), str(ex))
            return
        self.snapshot()
        new, color = self.eff.swap_content(tpl, recolor=self.sup_recolor.get(), force=self._force())
        self.eff = new
        self.changed()
        msg = self.t("support_done")
        if color:
            msg += "\n" + self.t("painted", c="#%02x%02x%02x" % color)
        messagebox.showinfo(self.t("ok"), msg)

    # ---- aba parâmetros de suporte
    MOVING_REF = "Paralisias/Paralisia Hitto (móvel).pak"

    def tab_support_params(self, nb):
        f = self._tab(nb, "tab_sparams")
        ttk.Label(f, text=self.t("sparams_hint"), wraplength=self.wrap(), justify="left").pack(anchor="w", pady=(0, 6))
        # 1) disparar até o adversário
        hdr = ttk.Frame(f)
        hdr.pack(fill="x")
        ttk.Label(hdr, text=self.t("goto_title"), font=("Segoe UI", self.fs(10), "bold")).pack(side="left")
        self.info_btn(hdr, "info_goto", self.t("more_info")).pack(side="right")
        self.goto_attach = tk.BooleanVar(value=True)
        self.goto_zero = tk.BooleanVar(value=True)
        self.goto_impact = tk.BooleanVar(value=False)
        self.goto_hits = tk.BooleanVar(value=False)
        for var, key in ((self.goto_attach, "goto_attach"), (self.goto_zero, "goto_zero"),
                         (self.goto_impact, "goto_impact"), (self.goto_hits, "goto_hits")):
            ttk.Checkbutton(f, text=self.t(key), variable=var).pack(anchor="w")
        ttk.Button(f, text=self.t("goto_apply"), command=self._go_to_opponent,
                   state="normal" if RES.get("suportes", self.MOVING_REF) else "disabled").pack(fill="x", pady=6)
        # 2) ficar até usar especial
        ttk.Separator(f).pack(fill="x", pady=8)
        hdr = ttk.Frame(f)
        hdr.pack(fill="x")
        ttk.Label(hdr, text=self.t("persist_title"), font=("Segoe UI", self.fs(10), "bold")).pack(side="left")
        self.info_btn(hdr, "info_persist", self.t("more_info")).pack(side="right")
        pr = ttk.Frame(f)
        pr.pack(fill="x")
        self.persist_all = tk.BooleanVar(value=True)
        ttk.Checkbutton(pr, text=self.t("opa_all"), variable=self.persist_all).pack(side="left")
        self.persist_ph = {}
        for p in range(6):
            v = tk.BooleanVar(value=False)
            ttk.Checkbutton(pr, text=str(p), variable=v).pack(side="left")
            self.persist_ph[p] = v
        br = ttk.Frame(f)
        br.pack(fill="x", pady=4)
        ttk.Button(br, text=self.t("persist_on"), command=lambda: self._persist(True)).pack(side="left", fill="x", expand=True)
        ttk.Button(br, text=self.t("persist_off"), command=lambda: self._persist(False)).pack(side="left", fill="x", expand=True, padx=(4, 0))
        # 3) parâmetros de cada suporte (cabeçalho)
        ttk.Separator(f).pack(fill="x", pady=8)
        hdr = ttk.Frame(f)
        hdr.pack(fill="x")
        ttk.Label(hdr, text=self.t("hdr_title"), font=("Segoe UI", self.fs(10), "bold")).pack(side="left")
        self.info_btn(hdr, "info_hdr", self.t("more_info")).pack(side="right")
        r = ttk.Frame(f)
        r.pack(fill="x", pady=4)
        ttk.Label(r, text=self.t("hdr_from")).pack(side="left")
        self.tree_button(r, "suportes", self._hdr_from, width=28).pack(side="left", padx=4)
        self.hdr_box = ttk.Frame(f)
        self.hdr_box.pack(fill="x")
        self._fill_hdr()

    def _fill_hdr(self):
        if not hasattr(self, "hdr_box"):
            return
        for w in self.hdr_box.winfo_children():
            w.destroy()
        if not self.eff:
            return
        import struct as _st
        self.hdr_vars = []
        v6 = tk.StringVar(value=str(self.eff.header[6]))
        ttk.Label(self.hdr_box, text="Byte 0x06").grid(row=0, column=0, sticky="w")
        ttk.Entry(self.hdr_box, textvariable=v6, width=10).grid(row=0, column=1, padx=4, pady=1)
        self.hdr_vars.append(("b6", v6))
        for i in range(14):
            val = _st.unpack_from("<f", self.eff.header, 8 + 4 * i)[0]
            v = tk.StringVar(value="%g" % val)
            r, c = 1 + i // 2, (i % 2) * 2
            ttk.Label(self.hdr_box, text="%s %d (0x%02X)" % (self.t("hdr_param"), i + 1, 8 + 4 * i)).grid(row=r, column=c, sticky="w")
            ttk.Entry(self.hdr_box, textvariable=v, width=10).grid(row=r, column=c + 1, padx=4, pady=1)
            self.hdr_vars.append((8 + 4 * i, v))
        ttk.Button(self.hdr_box, text=self.t("apply"), command=self._apply_hdr).grid(row=9, column=0, columnspan=4, sticky="ew", pady=6)

    def _apply_hdr(self):
        import struct as _st
        try:
            new = []
            for key, v in self.hdr_vars:
                txt = v.get().replace(",", ".")
                if key == "b6":
                    new.append((key, int(float(txt)) & 0xFF))
                else:
                    f = float(txt)
                    _st.pack("<f", f)        # valida (valores gigantes dão OverflowError)
                    new.append((key, f))
        except (ValueError, OverflowError, _st.error) as ex:
            messagebox.showerror(self.t("err"), str(ex))
            return
        self.snapshot()
        for key, val in new:
            if key == "b6":
                self.eff.header[6] = val
            else:
                _st.pack_into("<f", self.eff.header, key, val)
        self.changed()

    def _hdr_from(self, name):
        if not self.eff:
            return
        try:
            ref = Effect.from_bytes(RES.get("suportes", name))
        except (PakError, TypeError):
            return
        self.snapshot()
        self.eff.header[6:] = ref.header[6:]
        self.changed()
        messagebox.showinfo(self.t("ok"), self.t("hdr_done", n=os.path.splitext(name)[0].split("/")[-1]))

    def _persist(self, on):
        if not self.eff:
            return
        phases = None if self.persist_all.get() else set(p for p, v in self.persist_ph.items() if v.get())
        self.snapshot()
        n = self.eff.persist(phases, on)
        self.changed()
        messagebox.showinfo(self.t("ok"), self.t("persist_done" if on else "persist_undone", n=n))

    def _go_to_opponent(self):
        if not self.eff:
            return
        ref = Effect.from_bytes(RES.get("suportes", self.MOVING_REF))
        self.snapshot()
        moved, hits = self.eff.go_to_opponent(ref, attach=self.goto_attach.get(), zero_delay=self.goto_zero.get(),
                                              hits=self.goto_hits.get(), to_impact=self.goto_impact.get())
        self.changed()
        messagebox.showinfo(self.t("ok"), self.t("goto_done", m=moved, h=hits))

    # ---- opacidade / intensidade
    def _opacity_section(self, f):
        hdr = ttk.Frame(f)
        hdr.pack(fill="x")
        ttk.Label(hdr, text=self.t("opa_title"), font=("Segoe UI", self.fs(10), "bold")).pack(side="left")
        self.info_btn(hdr, "info_opa", self.t("more_info")).pack(side="right")
        r = ttk.Frame(f)
        r.pack(fill="x", pady=2)
        ttk.Label(r, text=self.t("opa_reduce")).pack(side="left")
        self.opa_var = tk.StringVar(value="30")
        ttk.Spinbox(r, from_=5, to=95, increment=5, width=5, textvariable=self.opa_var).pack(side="left", padx=4)
        ttk.Label(r, text="%").pack(side="left")
        self.opa_alpha = tk.BooleanVar(value=True)
        self.opa_bright = tk.BooleanVar(value=False)
        self.opa_tex = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text=self.t("opa_alpha"), variable=self.opa_alpha).pack(anchor="w")
        ttk.Checkbutton(f, text=self.t("opa_bright"), variable=self.opa_bright).pack(anchor="w")
        ttk.Checkbutton(f, text=self.t("opa_tex"), variable=self.opa_tex).pack(anchor="w")
        pr = ttk.Frame(f)
        pr.pack(fill="x", pady=(4, 0))
        ttk.Label(pr, text=self.t("opa_phases")).pack(side="left")
        self.opa_all = tk.BooleanVar(value=True)
        ttk.Checkbutton(pr, text=self.t("opa_all"), variable=self.opa_all).pack(side="left", padx=4)
        pr2 = ttk.Frame(f)
        pr2.pack(fill="x")
        self.opa_ph = {}
        for p in range(6):
            v = tk.BooleanVar(value=False)
            ttk.Checkbutton(pr2, text=str(p), variable=v).pack(side="left")
            self.opa_ph[p] = v
        ttk.Button(f, text=self.t("opa_apply"), command=self._apply_opacity).pack(fill="x", pady=6)

    def _apply_opacity(self):
        if not self.eff:
            return
        try:
            pct = float(self.opa_var.get().replace(",", "."))
        except ValueError:
            return
        if self.opa_all.get():
            ms = [m for m in self.eff.all_minis() if m.type != 0x00]
        else:
            ph = set(p for p, v in self.opa_ph.items() if v.get())
            ms = [m for m in self.eff.all_minis() if m.type != 0x00 and m.get("invoke") in ph]
        if not ms:
            messagebox.showinfo(self.t("app_title"), self.t("nothing_marked"))
            return
        self.snapshot()
        self.eff.reduce_opacity(ms, pct, alpha=self.opa_alpha.get(), brightness=self.opa_bright.get(),
                                textures=self.opa_tex.get())
        self.changed()
        messagebox.showinfo(self.t("ok"), self.t("opa_done", n=len(ms), p=pct))

    # ---- aba Avançado (antiga Flags)
    def tab_flags(self, nb):
        f = self._tab(nb, "tab_flags")
        # 1) flags do primeiro bloco (Linhas de Foco)
        hdr = ttk.Frame(f)
        hdr.pack(fill="x")
        ttk.Label(hdr, text=self.t("adv_global"), font=("Segoe UI", self.fs(10), "bold")).pack(side="left")
        self.info_btn(hdr, "h_flags", self.t("more_info")).pack(side="right")
        ttk.Label(f, text=self.t("adv_check", a=130, b=151), wraplength=self.wrap(), justify="left",
                  foreground="#8a8f99").pack(anchor="w", pady=(0, 4))
        self.lbl_flags_cur = ttk.Label(f, text="", font=("Segoe UI", self.fs(10), "bold"))
        self.lbl_flags_cur.pack(anchor="w", pady=(0, 6))
        self.fl_vars = {}
        for bit in (1, 2, 4, 8, 16, 32, 64, 128):
            v = tk.BooleanVar(value=False)
            ttk.Checkbutton(f, text="%d — %s" % (bit, self.t("flag_%d" % bit)), variable=v,
                            command=self._flags_preview).pack(anchor="w")
            self.fl_vars[bit] = v
        ttk.Button(f, text=self.t("apply"), command=self._flags_apply).pack(fill="x", pady=8)
        # 2) flags dos marcados
        ttk.Separator(f).pack(fill="x", pady=8)
        ttk.Label(f, text=self.t("adv_marked"), font=("Segoe UI", self.fs(10), "bold")).pack(anchor="w")
        ttk.Label(f, text=self.t("adv_marked_hint"), wraplength=self.wrap(), justify="left", foreground="#8a8f99").pack(anchor="w")
        self.adv_box = ttk.Frame(f)
        self.adv_box.pack(fill="x", pady=4)
        self.adv_rows = {}
        for r, bit in enumerate((1, 2, 4, 8, 16, 32, 64, 128)):
            ttk.Label(self.adv_box, text="%d — %s" % (bit, self.t("flag_%d" % bit)), wraplength=int(self.wrap() * 0.6),
                      justify="left").grid(row=r, column=0, sticky="w")
            lb = ttk.Label(self.adv_box, text="", width=8)
            lb.grid(row=r, column=1)
            ttk.Button(self.adv_box, text=self.t("adv_on"), width=8, command=lambda b=bit: self._adv_flag(b, True)).grid(row=r, column=2, padx=2, pady=1)
            ttk.Button(self.adv_box, text=self.t("adv_off"), width=8, command=lambda b=bit: self._adv_flag(b, False)).grid(row=r, column=3)
            self.adv_rows[bit] = lb
        # 3) cabeçalho do 03_.dat
        ttk.Separator(f).pack(fill="x", pady=8)
        hdr = ttk.Frame(f)
        hdr.pack(fill="x")
        ttk.Label(hdr, text=self.t("adv_header"), font=("Segoe UI", self.fs(10), "bold")).pack(side="left")
        self.info_btn(hdr, "info_adv_header", self.t("more_info")).pack(side="right")
        self.adv_hdr = ttk.Frame(f)
        self.adv_hdr.pack(fill="x", pady=4)
        self._flags_load()
        self._adv_marked_load()
        self._adv_hdr_fill()
        if hasattr(self, "lbl_barrage"):
            self.lbl_barrage.config(text=self.t("barrage_state_on") if self.eff and self.eff.is_barrage() else self.t("barrage_state_off"))

    def _adv_marked_load(self):
        if not hasattr(self, "adv_rows"):
            return
        ms = [m for m in self.list.marked()] if self.eff else []
        for bit, lb in self.adv_rows.items():
            k = sum(1 for m in ms if m.param[0] & bit)
            lb.config(text=self.t("adv_count", k=k, n=len(ms)) if ms else "—")

    def _adv_flag(self, bit, on):
        ms = self.list.marked()
        if not ms:
            messagebox.showinfo(self.t("app_title"), self.t("nothing_marked"))
            return
        self.snapshot()
        for m in ms:
            m.param[0] = (m.param[0] | bit) if on else (m.param[0] & ~bit & 0xFF)
        self.changed()

    def _adv_hdr_fill(self):
        if not hasattr(self, "adv_hdr"):
            return
        import struct as _st
        for w in self.adv_hdr.winfo_children():
            w.destroy()
        if not self.eff:
            return
        self.adv_hdr_vars = []
        v6 = tk.StringVar(value=str(self.eff.header[6]))
        ttk.Label(self.adv_hdr, text=self.t("hdr_lbl_6")).grid(row=0, column=0, sticky="w")
        ttk.Entry(self.adv_hdr, textvariable=v6, width=10).grid(row=0, column=1, padx=4, pady=1)
        self.adv_hdr_vars.append(("b6", v6))
        row = 1
        for i in range(6):
            o = 8 + 4 * i
            lbl = self.t("hdr_lbl_8") if i == 0 else self.t("hdr_lbl_c", o=o, n=i)
            self._adv_hdr_field(lbl, o, row)
            row += 1
        for i in range(6):
            o = 0x28 + 4 * i
            self._adv_hdr_field(self.t("hdr_lbl_x", o=o, n=i + 1), o, row)
            row += 1
        ttk.Button(self.adv_hdr, text=self.t("apply"), command=self._adv_hdr_apply).grid(row=row, column=0, columnspan=2, sticky="ew", pady=6)

    def _adv_hdr_field(self, lbl, o, row):
        import struct as _st
        v = tk.StringVar(value="%g" % _st.unpack_from("<f", self.eff.header, o)[0])
        ttk.Label(self.adv_hdr, text=lbl).grid(row=row, column=0, sticky="w")
        ttk.Entry(self.adv_hdr, textvariable=v, width=10).grid(row=row, column=1, padx=4, pady=1)
        self.adv_hdr_vars.append((o, v))

    def _adv_hdr_apply(self):
        import struct as _st
        try:
            new = []
            for key, v in self.adv_hdr_vars:
                txt = v.get().replace(",", ".")
                if key == "b6":
                    new.append((key, int(float(txt)) & 0xFF))
                else:
                    f = float(txt)
                    _st.pack("<f", f)        # valida (valores gigantes dão OverflowError)
                    new.append((key, f))
        except (ValueError, OverflowError, _st.error) as ex:
            messagebox.showerror(self.t("err"), str(ex))
            return
        self.snapshot()
        for key, val in new:
            if key == "b6":
                self.eff.header[6] = val
            else:
                _st.pack_into("<f", self.eff.header, key, val)
        self.changed()

    def _flags_block(self):
        ms = self.eff.all_minis() if self.eff else []
        return ms[0] if ms else None

    def _flags_load(self):
        if not hasattr(self, "fl_vars"):
            return
        m = self._flags_block()
        val = m.param[0] if m is not None else 0
        for bit, v in self.fl_vars.items():
            v.set(bool(val & bit))
        self._flags_preview()

    def _flags_preview(self):
        m = self._flags_block()
        if m is None:
            self.lbl_flags_cur.config(text=self.t("flags_none"))
            return
        new = sum(bit for bit, v in self.fl_vars.items() if v.get())
        self.lbl_flags_cur.config(text="%s — %s" % (class_label(m.type, self.lang), self.t("flags_cur", v=m.param[0], n=new)))

    def _flags_apply(self):
        m = self._flags_block()
        if m is None:
            return
        self.snapshot()
        m.param[0] = sum(bit for bit, v in self.fl_vars.items() if v.get())
        self.changed()

    # ------------------------------------------------------------ ações
    def _combo_group(self, cb, lst=None):
        lst = lst or self.list
        i = cb.current()
        gs = lst.groups()
        return gs[i] if 0 <= i < len(gs) else None

    def _refresh_combos(self):
        gl = [stage_label(g, self.lang) for g in self.list.groups()]
        self.cb_colorgroup["values"] = gl
        self.cb_scalegroup["values"] = gl
        if hasattr(self, "cb_growgroup"):
            self.cb_growgroup["values"] = gl
        if hasattr(self, "cb_hidegroup"):
            self.cb_hidegroup["values"] = gl
        self.cb_replace["values"] = gl
        if self.cb_replace.current() < 0 and gl:
            self.cb_replace.current(0)
        self.chips.rebuild()

    def on_select(self, m):
        self._fill_rgb(m)
        self._fill_params(m)
        if not self.list.marked():
            self._dark_table()
            self._preview_update()


    def refresh(self):
        if self.cur_kind() != getattr(self, "_ui_kind", "skill"):
            self.build_ui()
            return
        sel = self.list.selected()
        self.list.fill(self.eff)
        if self.eff:
            name = os.path.basename(self.path) if self.path else getattr(self, "tpl_name", "?")
            self.lbl_file.config(text=name + (" *" if self.dirty else ""))
            self.lbl_sum.config(text=self.t("summary", n=len(self.eff.all_minis()), c=len(self.eff.cats),
                                            f=len(self.eff.file_list())))
            try:
                kb = len(self.eff.to_bytes()) / 1024.0
            except PakError:
                kb = 0.0          # (ex.: mais de 255 mini-efeitos): o erro aparece ao validar/salvar
            self.lbl_size.config(text="%.0f KB" % kb + ("  ⚠ " + self.t("w_warn") if kb > SIZE_WARN_KB else ""),
                                 fg="#b00020" if kb > SIZE_WARN_KB else "#1b6e20")
        else:
            self.lbl_file.config(text=self.t("no_file"))
            self.lbl_sum.config(text="")
            self.lbl_size.config(text="")
        if sel in self.list.minis:
            i = str(self.list.minis.index(sel))
            self.list.tree.selection_set(i)
            self.list.tree.see(i)
        else:
            self.on_select(None)
        self._refresh_combos()
        self._beh_summary()
        self._scene_status()
        self._extras_status()
        self._depth_status()
        self._flags_load()
        self._fill_hdr()
        self._adv_hdr_fill()
        self._hist_fill()
        self._dark_table()
        self._preview_update()
        self._adv_marked_load()

    # ------------------------------------------------------------ histórico (desfazer / refazer)
    HISTORY_MAX = 60
    ACTION_NAMES = {}          # nome da função que chamou → chave do texto (lang: "act_<função>")

    def _state(self, label):
        import time as _time
        return {"data": self.eff.to_bytes(), "groups": [m.group for m in self.eff.all_minis()], "kind": self.eff.kind,
                "label": label, "time": _time.strftime("%H:%M:%S")}

    def _action_label(self, depth=2):
        try:
            fn = sys._getframe(depth).f_code.co_name
        except ValueError:
            return "?"
        key = "act_" + fn.lstrip("_")
        txt = self.t(key)
        if txt != key:
            return txt
        return fn.strip("_").replace("_", " ").capitalize()

    def snapshot(self, label=None):
        """Guarda o estado ANTES de uma ação (para desfazer). O nome da ação vem de quem chamou."""
        if self.eff:
            self._pre_ids = set(id(m) for m in self.eff.all_minis())
            self._pre_dark = self.eff.is_dark()
            self._pre_prof = self.eff.alpha_profile()
            self._pre_d16 = self.eff.prefers_16()
            try:
                st = self._state(label or self._action_label())
            except PakError:
                return            # estado que nem dá para serializar: não há o que guardar
            self.history.append(st)
            self.history = self.history[-self.HISTORY_MAX:]
            self.redo_stack = []

    def _match_new(self):
        """Depois de importar: opacidade e quantidade de cores das partes novas iguais às do efeito original."""
        if not self.eff or not hasattr(self, "_pre_ids"):
            return
        added = [m for m in self.eff.all_minis() if id(m) not in self._pre_ids and m.type != 0x00]
        if not added:
            return
        self.eff.match_import(added, self._pre_prof, self._pre_d16,
                              opacity=self.imp_alpha.get(), colors=self.imp_depth.get())
        if getattr(self, "_pre_dark", False) and messagebox.askyesno(self.t("app_title"), self.t("dark_ask_new", n=len(added))):
            self.eff.make_dark3(added, 1.0, keep_color=True)

    def import_options(self, parent):
        """Caixas 'igualar ao original' (as mesmas em todas as abas de importar)."""
        box = ttk.Frame(parent)
        ttk.Checkbutton(box, text=self.t("imp_alpha"), variable=self.imp_alpha).pack(anchor="w")
        ttk.Checkbutton(box, text=self.t("imp_depth"), variable=self.imp_depth).pack(anchor="w")
        return box

    def _restore(self, st):
        self.eff = Effect.from_bytes(st["data"])
        self.eff.kind = st["kind"]
        for m, g in zip(self.eff.all_minis(), st["groups"]):
            m.group = g
        self.dirty = True
        self.refresh()

    def undo(self):
        if not self.history:
            return
        st = self.history.pop()
        cur = self._state(st["label"])
        self.redo_stack = getattr(self, "redo_stack", []) + [cur]
        self._restore(st)

    def redo(self):
        rs = getattr(self, "redo_stack", [])
        if not rs:
            return
        st = rs.pop()
        cur = self._state(st["label"])
        self.history.append(cur)
        self._restore(st)

    def undo_to(self, n):
        """Desfaz as últimas n ações de uma vez (botão 'Voltar para antes desta ação')."""
        last = None
        for _ in range(max(0, n)):
            if not self.history:
                break
            st = self.history.pop()
            self.redo_stack = getattr(self, "redo_stack", []) + [self._state(st["label"])]
            if last is not None:
                self.eff = Effect.from_bytes(st["data"])
            last = st
            self.eff = Effect.from_bytes(st["data"])
            self.eff.kind = st["kind"]
            for m, g in zip(self.eff.all_minis(), st["groups"]):
                m.group = g
        if last is not None:
            self._restore(last)

    def changed(self):
        self.dirty = True
        self.refresh()

    def _groups_path(self, p):
        """Os grupos ficam na pasta do programa (fora da pasta do EFF, para o Sparking Studio exportar sem sujeira)."""
        import hashlib as _h
        d = os.path.join(HERE, "dados", "grupos")
        os.makedirs(d, exist_ok=True)
        key = _h.sha1(os.path.abspath(p).lower().encode("utf-8")).hexdigest()[:16]
        return os.path.join(d, "%s_%s.json" % (os.path.splitext(os.path.basename(p))[0], key))

    def backup_dir(self, p):
        """Pasta gerada para os backups de um arquivo: <programa>/backups/<pasta do arquivo>/<arquivo>/"""
        parent = os.path.basename(os.path.dirname(os.path.abspath(p))) or "raiz"
        d = os.path.join(HERE, "backups", parent, os.path.splitext(os.path.basename(p))[0])
        os.makedirs(d, exist_ok=True)
        return d

    def make_backup(self, p, reason="save"):
        """Copia o arquivo atual (antes de sobrescrever) para a pasta de backups, com data e hora."""
        import time as _time
        if not os.path.exists(p):
            return None
        d = self.backup_dir(p)
        stem, ext = os.path.splitext(os.path.basename(p))
        dst = os.path.join(d, "%s_%s%s" % (stem, _time.strftime("%Y%m%d_%H%M%S"), ext))
        shutil.copy2(p, dst)
        olds = sorted(f for f in os.listdir(d) if f.startswith(stem + "_"))
        for f in olds[:-40]:                     # guarda os 40 mais recentes
            try:
                os.remove(os.path.join(d, f))
            except OSError:
                pass
        return dst

    def list_backups(self, p):
        if not p:
            return []
        d = self.backup_dir(p)
        stem = os.path.splitext(os.path.basename(p))[0]
        return sorted((os.path.join(d, f) for f in os.listdir(d) if f.startswith(stem + "_")), reverse=True)

    def _load_groups(self, eff, p):
        try:
            gp = self._groups_path(p)
            if not os.path.exists(gp) and os.path.exists(p + ".grupos.json"):
                gp = p + ".grupos.json"          # arquivos antigos (v1.5 ou antes)
            with open(gp, encoding="utf-8") as f:
                gs = json.load(f)
            ms = eff.all_minis()
            if len(gs) == len(ms):
                for m, g in zip(ms, gs):
                    m.group = g
        except Exception:
            pass

    def open(self, path=None, template=False):
        if self.dirty and not messagebox.askyesno(self.t("app_title"), self.t("unsaved")):
            return
        p = path or filedialog.askopenfilename(filetypes=[("PAK", "*.pak"), ("*", "*.*")], parent=self)
        if not p:
            return
        try:
            with open(p, "rb") as fh:
                raw = fh.read()
            ents = container_entries(raw)
            if ents:
                self._choose_from_container(p, raw, ents)
                return
            self.container = None
            self.eff = Effect.load(p)
            if self.eff.kind == "skill" and SUPPORT_NAME.search(os.path.basename(p)):
                self.eff.kind = "support"
            self._load_groups(self.eff, p)
        except (PakError, OSError) as ex:
            messagebox.showerror(self.t("err"), str(ex))
            return
        self.path = None if template else p
        self.dirty, self.history = bool(template), []
        self.list.checked.clear()
        self.title(self.t("app_title") + (" — " + os.path.basename(p)))
        self.refresh()

    def _choose_from_container(self, p, raw, ents):
        w = tk.Toplevel(self)
        w.title(self.t("cont_title", n=os.path.basename(p)))
        w.transient(self)
        ttk.Label(w, text=self.t("cont_hint"), padding=8, wraplength=460).pack(anchor="w")
        tv = ttk.Treeview(w, columns=("kind", "n"), show="tree headings", height=min(14, len(ents)))
        tv.heading("#0", text=".pak")
        tv.heading("kind", text=self.t("cont_kind"))
        tv.heading("n", text=self.t("summary_minis"))
        tv.column("#0", width=300)
        tv.column("kind", width=90)
        tv.column("n", width=80, anchor="center")
        kinds = {"skill": self.t("kind_skill"), "aura": self.t("kind_aura"), "support": self.t("kind_support")}
        for k, (path, name, kind, n) in enumerate(ents):
            if kind == "skill" and SUPPORT_NAME.search(name):
                kind = "support"
            tv.insert("", "end", iid=str(k), text=name, values=(kinds.get(kind, kind), n))
        tv.pack(fill="both", expand=True, padx=8)

        def go(_=None):
            sel = tv.selection()
            if not sel:
                return
            path, name, kind, n = ents[int(sel[0])]
            try:
                eff = Effect.from_bytes(container_get(raw, path))
            except PakError as ex:
                messagebox.showerror(self.t("err"), str(ex), parent=w)
                return
            if eff.kind == "skill" and SUPPORT_NAME.search(name):
                eff.kind = "support"
            w.destroy()
            self.eff = eff
            self.container = (p, path, name)
            self.path = p
            self.dirty, self.history = False, []
            self.list.checked.clear()
            self.title(self.t("app_title") + " — " + os.path.basename(p) + " › " + name)
            self.refresh()
        tv.bind("<Double-1>", go)
        ttk.Button(w, text=self.t("cont_open"), command=go).pack(fill="x", padx=8, pady=8)

    def open_anm(self):
        import animacao
        animacao.AnimWindow(self)

    def open_tutorials(self):
        import tutoriais
        w = tk.Toplevel(self)
        w.title(self.t("tutorials"))
        w.geometry("980x640")
        w.transient(self)
        pw = ttk.PanedWindow(w, orient="horizontal")
        pw.pack(fill="both", expand=True)
        lb = tk.Listbox(pw, font=("Segoe UI", self.fs(10)), activestyle="none", exportselection=False)
        pw.add(lb, weight=1)
        tf = ttk.Frame(pw)
        txt = tk.Text(tf, wrap="word", font=("Segoe UI", self.fs(11)), padx=14, pady=12)
        sb = ttk.Scrollbar(tf, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        txt.tag_configure("h", font=("Segoe UI", self.fs(14), "bold"))
        pw.add(tf, weight=3)
        topics = tutoriais.TOPICS
        for title, _ in topics:
            lb.insert("end", title)

        def show(_=None):
            sel = lb.curselection()
            if not sel:
                return
            title, body = topics[sel[0]]
            txt.config(state="normal")
            txt.delete("1.0", "end")
            txt.insert("end", title + "\n\n", "h")
            txt.insert("end", body)
            txt.config(state="disabled")
        lb.bind("<<ListboxSelect>>", show)
        lb.selection_set(0)
        show()

    def open_3d(self, mini=None):
        if not self.eff:
            return
        import editor3d
        w = editor3d.Editor3D(self)
        if mini is not None:
            for k, t in enumerate(w.tracks):
                if t.mini is mini:
                    w.lst.selection_clear(0, "end")
                    w.lst.selection_set(k)
                    w.lst.see(k)
                    w._pick_list()
                    break

    def open_textures(self, mini=None):
        if not self.eff:
            return
        import texview
        focus = None
        if mini is not None:
            c = self.eff.cat_of(mini)
            if c is not None and mini.get("dbt") < len(c.dbts):
                imgs = sorted(mini.textures(c)) or [0]
                focus = (c, mini.get("dbt"), imgs[0])
        texview.TextureWindow(self, focus=focus)

    def file_index_of(self, mini):
        """Índice, no .pak, do 1º arquivo do mini-efeito; e offset do bloco dele no arquivo de parâmetros."""
        i = len(self.eff.pre) + 1
        k = 0
        for c in self.eff.cats:
            i += len(c.dbts)
            for m in c.minis:
                if m is mini:
                    return i, k
                i += len(m.files)
                k += 1
        return None, None

    def open_hex(self, mini=None, params=False):
        if not self.eff:
            return
        import hexview
        focus = None
        if mini is not None:
            fi, k = self.file_index_of(mini)
            if params or not mini.files:
                focus = (len(self.eff.pre), 64 + 32 * len(self.eff.cats) + 64 * k)
            elif fi is not None:
                sh = getattr(mini, "shader_idx", 1)
                focus = (fi + (sh if mini.type in (0x05, 0x09, 0x0A, 0x0F, 0x10, 0x11, 0x12) and params == "shader" else 0), 0)
        hexview.HexWindow(self, focus=focus)

    def open_hex_external(self):
        p = filedialog.askopenfilename(filetypes=[("DAT", "*.dat *_"), ("*", "*.*")], parent=self)
        if p:
            import hexview
            hexview.HexWindow(self, external=p)

    def open_template(self, name, sub="modelos"):
        if self.dirty and not messagebox.askyesno(self.t("app_title"), self.t("unsaved")):
            return
        try:
            self.eff = Effect.from_bytes(RES.get(sub, name))
            if sub == "suportes":
                self.eff.kind = "support"
        except (PakError, TypeError) as ex:
            messagebox.showerror(self.t("err"), str(ex))
            return
        self.path, self.dirty, self.history = None, True, []
        self.tpl_name = os.path.splitext(name)[0].split("/")[-1]
        self.container = None
        self.list.checked.clear()
        self.title(self.t("app_title") + " — " + os.path.splitext(name)[0])
        self.refresh()

    def save(self, as_new=False):
        if not self.eff:
            return
        if RES.is_protected(self.eff.to_bytes()):
            messagebox.showerror(self.t("err"), self.t("protected_save"))
            return
        probs = self.eff.validate()
        if probs:
            messagebox.showerror(self.t("err"), self.t("invalid") + "\n".join(probs))
            return
        cont = getattr(self, "container", None)
        if cont and not as_new:
            cp, path, name = cont
            try:
                with open(cp, "rb") as fh:
                    raw = fh.read()
                self.make_backup(cp)
                with open(cp, "wb") as fh:
                    fh.write(container_put(raw, path, self.eff.to_bytes()))
            except (OSError, PakError) as ex:
                messagebox.showerror(self.t("err"), str(ex))
                return
            self.dirty = False
            self.refresh()
            messagebox.showinfo(self.t("ok"), self.t("cont_saved", n=name, c=os.path.basename(cp)))
            return
        p = self.path if not cont else None
        if as_new or not p:
            p = filedialog.asksaveasfilename(defaultextension=".pak", filetypes=[("PAK", "*.pak")], parent=self)
            if not p:
                return
        backup = self.make_backup(p)
        try:
            self.eff.save(p)
            with open(self._groups_path(p), "w", encoding="utf-8") as f:
                json.dump([m.group for m in self.eff.all_minis()], f, ensure_ascii=False)
        except OSError as ex:
            messagebox.showerror(self.t("err"), str(ex))
            return
        self.path, self.dirty = p, False
        self.container = None
        self.refresh()
        messagebox.showinfo(self.t("ok"), self.t("saved", b=backup) if backup else self.t("saved_nb"))

    def remove_marked(self):
        self._remove(self.list.marked())

    def _remove(self, ms):
        if not ms:
            messagebox.showinfo(self.t("app_title"), self.t("nothing_marked"))
            return
        prot = [m for m in ms if m.type == 0x00]
        ms = [m for m in ms if m.type != 0x00]
        if ms:
            q = self.t("confirm_remove", n=len(ms))
            if any(m.hits for m in ms):
                q += "\n\n" + self.t("warn_hits")
            if messagebox.askyesno(self.t("app_title"), q):
                self.snapshot()
                self.eff.remove_minis(ms)
                self.changed()
        if prot:
            messagebox.showinfo(self.t("app_title"), self.t("protected"))

    def quit_app(self):
        if self.dirty and not messagebox.askyesno(self.t("app_title"), self.t("unsaved")):
            return
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
