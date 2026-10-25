"""Offline Keep desktop app (Tkinter, standard library only)."""
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import __version__, catalog, rules, settings, updater
from .worldstate import WorldState, game_head, make_fbmod

APP_NAME = "Offline Keep"
ADVANCED = "Advanced: all variables"
SUMMARY_VARS = ["dao_warden_background", "dao_warden_mf", "dao_ruler_state", "dao_loghain_fate", "dao_morrigan_baby",
                "da2_hawke_mf", "da2_hawke_class", "da2_hawke_romance", "da2_hawke_chosen_side"]


def pronouns(text, female):
    swaps = {"S/He": "She" if female else "He", "s/he": "she" if female else "he",
             "him/herself": "herself" if female else "himself", "his/her": "her" if female else "his"}
    return re.sub("|".join(re.escape(k) for k in swaps), lambda m: swaps[m.group(0)], text)


class ScrollFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, padding=(16, 12))
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._wheel, add="+")

    def _wheel(self, event):
        if self.winfo_ismapped():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def clear(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.canvas.yview_moveto(0)


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = settings.load_settings()
        self.ws = None
        self.base_ebx = None
        self.head = None
        self.sections = []
        self.choices, self.overrides, self.values = {}, {}, {}
        self.name = tk.StringVar(value="My World State")
        self.path = None
        self.dirty = False
        self.current = None
        self.widgets = {}

        self.px = root.tk.call("tk", "scaling") / 1.333  # 1.0 at 96 DPI
        px = lambda n: int(n * self.px)
        root.title(APP_NAME)
        root.geometry(f"{px(1180)}x{px(780)}")
        root.minsize(px(900), px(560))
        root.protocol("WM_DELETE_WINDOW", self.quit)
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Treeview", rowheight=px(24))
        style.configure("Q.TLabel", font=("Segoe UI", 10))
        style.configure("H.TLabel", font=("Segoe UI Semibold", 15))
        style.configure("Warn.TLabel", foreground="#9a5b00")
        self._build_menu()
        self._build_layout()
        self.status("Locating Dragon Age: Inquisition…")
        root.after(50, self.locate_game)

    # ---------- layout
    def _build_menu(self):
        m = tk.Menu(self.root)
        f = tk.Menu(m, tearoff=False)
        f.add_command(label="New World State", command=self.new, accelerator="Ctrl+N")
        f.add_command(label="Open…", command=self.open, accelerator="Ctrl+O")
        f.add_command(label="Save", command=self.save, accelerator="Ctrl+S")
        f.add_command(label="Save As…", command=self.save_as)
        f.add_separator()
        f.add_command(label="Generate Mod…", command=self.generate, accelerator="Ctrl+G")
        f.add_separator()
        f.add_command(label="Exit", command=self.quit)
        m.add_cascade(label="File", menu=f)
        t = tk.Menu(m, tearoff=False)
        t.add_command(label="Verify World State…", command=self.open_verify)
        m.add_cascade(label="Tools", menu=t)
        s = tk.Menu(m, tearoff=False)
        s.add_command(label="Game Folder…", command=self.choose_game_dir)
        s.add_command(label="Frosty Mod Manager Folder…", command=self.choose_frosty_dir)
        s.add_separator()
        self.auto_update = tk.BooleanVar(value=bool(self.cfg.get("auto_update", False)))
        s.add_checkbutton(label="Check for Updates at Startup" + ("" if updater.is_packaged() else " (.exe only)"),
                          variable=self.auto_update, command=self.toggle_auto_update,
                          state="normal" if updater.is_packaged() else "disabled")
        m.add_cascade(label="Settings", menu=s)
        h = tk.Menu(m, tearoff=False)
        h.add_command(label="How to Use", command=self.help)
        h.add_command(label="About", command=lambda: messagebox.showinfo(APP_NAME, ABOUT, parent=self.root))
        m.add_cascade(label="Help", menu=h)
        self.root.config(menu=m)
        for key, fn in (("n", self.new), ("o", self.open), ("s", self.save), ("g", self.generate)):
            self.root.bind_all(f"<Control-{key}>", lambda e, fn=fn: fn())

    def _build_layout(self):
        top = ttk.Frame(self.root, padding=(10, 8))
        top.pack(fill="x")
        ttk.Label(top, text="World state:").pack(side="left")
        entry = ttk.Entry(top, textvariable=self.name, width=36)
        entry.pack(side="left", padx=(6, 12))
        self.name.trace_add("write", lambda *_: self.mark_dirty())
        ttk.Button(top, text="New", command=self.new).pack(side="left")
        ttk.Button(top, text="Open…", command=self.open).pack(side="left", padx=4)
        ttk.Button(top, text="Save", command=self.save).pack(side="left")
        self.gen_btn = ttk.Button(top, text="Generate Mod…", command=self.generate, state="disabled")
        self.gen_btn.pack(side="right")
        self.verify_btn = ttk.Button(top, text="Verify…", command=self.open_verify, state="disabled")
        self.verify_btn.pack(side="right", padx=6)

        body = ttk.PanedWindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10)
        self.root.after(1, lambda: body.sashpos(0, int(250 * self.px)))
        left = ttk.Frame(body)
        self.tree = ttk.Treeview(left, show="tree", selectmode="browse")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.show_section())
        body.add(left, weight=1)
        self.right = ttk.Frame(body)
        body.add(self.right, weight=4)
        self.scroll = ScrollFrame(self.right)
        self.scroll.pack(fill="both", expand=True)

        bottom = ttk.Frame(self.root, padding=(10, 6))
        bottom.pack(fill="x")
        self.warn_label = ttk.Label(bottom, style="Warn.TLabel", justify="left", wraplength=1100)
        self.warn_label.pack(fill="x")
        self.status_label = ttk.Label(bottom, foreground="#555")
        self.status_label.pack(fill="x", pady=(4, 0))

    def status(self, text):
        self.status_label.configure(text=text)

    # ---------- game loading
    def locate_game(self):
        game_dir = self.cfg.get("game_dir")
        if not settings.is_game_dir(game_dir):
            game_dir = settings.detect_game_dir()
        if not game_dir:
            messagebox.showinfo(APP_NAME, "Dragon Age: Inquisition wasn't found automatically.\n\n"
                                          "Please choose the game's install folder (the one containing "
                                          "DragonAgeInquisition.exe).", parent=self.root)
            game_dir = filedialog.askdirectory(title="Dragon Age: Inquisition folder", parent=self.root)
            if not settings.is_game_dir(game_dir):
                self.status("No game folder selected. Use Settings → Game Folder… to choose one.")
                return
        self.load_game(game_dir)

    def load_game(self, game_dir):
        self.status(f"Reading world state data from {game_dir} …")
        self.root.configure(cursor="watch")
        result = {}

        def work():
            try:
                ws = WorldState.from_game(game_dir)
                result.update(ws=ws, head=game_head(game_dir))
            except Exception as ex:  # surfaced to the user below
                result["error"] = ex

        t = threading.Thread(target=work, daemon=True)
        t.start()

        def poll():
            if t.is_alive():
                self.root.after(100, poll)
                return
            self.root.configure(cursor="")
            if "error" in result:
                self.status("Could not read the game data.")
                messagebox.showerror(APP_NAME, f"Could not read the world state from the game:\n\n{result['error']}",
                                     parent=self.root)
                return
            self.cfg["game_dir"] = game_dir
            settings.save_settings(self.cfg)
            self.ws, self.head = result["ws"], result["head"]
            self.base_ebx = self.ws.to_bytes()
            self.sections = catalog.build_sections(self.ws)
            self.defaults = {n: v["DefaultValue"] for n, v in self.ws.vars.items()}
            self._fill_tree()
            self.new(confirm=False)
            self.gen_btn.configure(state="normal")
            self.verify_btn.configure(state="normal")
            note = f"  —  updated from {updater.updated_from()} to {__version__}" if updater.updated_from() else ""
            self.status(f"Game: {game_dir}  (build {self.head}){note}")

        poll()

    def _fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        parents = {}
        for i, sec in enumerate(self.sections):
            if sec.game not in parents:
                parents[sec.game] = self.tree.insert("", "end", text=sec.game, open=True)
            self.tree.insert(parents[sec.game], "end", iid=f"s{i}", text=f"{sec.title}  ({len(sec.questions)})")
        self.tree.insert("", "end", iid="adv", text=ADVANCED)
        self.tree.selection_set("s0")

    # ---------- state
    def recompute(self):
        v = dict(self.defaults)
        v.update(self.choices)
        v.update(self.overrides)  # overridden primaries (e.g. experimental values) must drive the derived flags
        rules.derive(v)
        for q in catalog.primary_vars(self.sections) - self.overrides.keys():  # rules may correct impossible answers
            self.choices[q] = v[q]
        v.update(self.overrides)
        self.values = v
        w = rules.warnings(v)
        self.warn_label.configure(text=("⚠ " + "\n⚠ ".join(w)) if w else "")

    def mark_dirty(self):
        self.dirty = True
        self.root.title(f"{APP_NAME} — {self.name.get()} *")

    def new(self, confirm=True):
        if not self.ws or (confirm and not self.confirm_discard()):
            return
        self.choices = {q.var: self.defaults[q.var] for s in self.sections for q in s.questions}
        self.choices.update(dao_played=1, da2_played=1)
        self.overrides = {}
        self.path = None
        self.name.set("My World State")
        self.recompute()
        self.show_section()
        self.dirty = False
        self.root.title(f"{APP_NAME} — {self.name.get()}")

    def confirm_discard(self):
        if not self.dirty:
            return True
        ans = messagebox.askyesnocancel(APP_NAME, "Save changes to the current world state first?", parent=self.root)
        if ans is None:
            return False
        return self.save() if ans else True

    def open(self):
        if not self.ws or not self.confirm_discard():
            return
        path = filedialog.askopenfilename(title="Open world state", parent=self.root,
                                          initialdir=self.cfg.get("worldstate_dir"),
                                          filetypes=[("Offline Keep world state", "*.dakeep.json"), ("JSON", "*.json")])
        if not path:
            return
        try:
            name, choices, overrides = settings.load_worldstate(path)
        except (OSError, ValueError) as ex:
            messagebox.showerror(APP_NAME, f"Couldn't open {path}:\n\n{ex}", parent=self.root)
            return
        unknown = [k for k in list(choices) + list(overrides) if k not in self.defaults]
        self.new(confirm=False)
        self.choices.update({k: v for k, v in choices.items() if k in self.defaults})
        self.overrides = {k: v for k, v in overrides.items() if k in self.defaults}
        self.name.set(name)
        self.path = path
        self.cfg["worldstate_dir"] = str(Path(path).parent)
        settings.save_settings(self.cfg)
        self.recompute()
        self.show_section()
        self.dirty = False
        self.root.title(f"{APP_NAME} — {name}")
        if unknown:
            messagebox.showwarning(APP_NAME, "These entries aren't in this game's data and were ignored:\n"
                                   + ", ".join(unknown), parent=self.root)

    def save(self):
        if not self.path:
            return self.save_as()
        settings.save_worldstate(self.path, self.name.get(), self.choices, self.overrides)
        self.dirty = False
        self.root.title(f"{APP_NAME} — {self.name.get()}")
        self.status(f"Saved {self.path}")
        return True

    def save_as(self):
        if not self.ws:
            return False
        safe = re.sub(r'[<>:"/\\|?*]', "_", self.name.get()).strip() or "World State"
        path = filedialog.asksaveasfilename(title="Save world state", parent=self.root, defaultextension=".dakeep.json",
                                            initialdir=self.cfg.get("worldstate_dir"), initialfile=f"{safe}.dakeep.json",
                                            filetypes=[("Offline Keep world state", "*.dakeep.json")])
        if not path:
            return False
        self.path = path
        self.cfg["worldstate_dir"] = str(Path(path).parent)
        settings.save_settings(self.cfg)
        return self.save()

    # ---------- question pages
    def show_section(self):
        if not self.sections:
            return
        sel = self.tree.selection()
        if not sel or not (sel[0] == "adv" or sel[0].startswith("s")):
            return
        self.current = sel[0]
        self.scroll.clear()
        self.widgets = {}
        if sel[0] == "adv":
            self._show_advanced()
            return
        sec = self.sections[int(sel[0][1:])]
        ttk.Label(self.scroll.inner, text=sec.title, style="H.TLabel").grid(row=0, column=0, columnspan=2,
                                                                            sticky="w", pady=(0, 10))
        self.scroll.inner.columnconfigure(0, weight=1)
        female = self.values.get("dao_warden_mf") == 1
        for row, q in enumerate(sec.questions, start=1):
            ttk.Label(self.scroll.inner, text=pronouns(q.text, female), style="Q.TLabel",
                      wraplength=int(400 * self.px), justify="left").grid(row=row, column=0, sticky="w", pady=5,
                                                                         padx=(0, 16))
            labels = [pronouns(l, female) for l in q.options.values()]
            box = ttk.Combobox(self.scroll.inner, values=labels, state="readonly", width=46)
            box.grid(row=row, column=1, sticky="e", pady=5)
            box.bind("<<ComboboxSelected>>", lambda e, q=q, box=box: self.on_choice(q, box))
            self.widgets[q.var] = (q, box)
        self._sync_boxes()

    def _sync_boxes(self):
        female = self.values.get("dao_warden_mf") == 1
        for var, (q, box) in self.widgets.items():
            value = self.values[var]
            box.configure(values=[pronouns(l, female) for l in q.options.values()])
            label = q.label_for(value)
            box.set(pronouns(label, female) if label is not None else f"{value} (custom value)")

    def on_choice(self, q, box):
        value = list(q.options)[box.current()]
        self.choices[q.var] = value
        self.overrides.pop(q.var, None)
        self.recompute()
        self._sync_boxes()
        self.mark_dirty()

    def _show_advanced(self):
        f = self.scroll.inner
        ttk.Label(f, text=ADVANCED, style="H.TLabel").pack(anchor="w")
        ttk.Label(f, wraplength=760, justify="left", text=(
            "Every Origins and Dragon Age II variable the game reads. Values shown include the ones derived "
            "automatically from your answers. Double-click a row to override it with any number — overrides win "
            "over everything else, including values the original games couldn't produce. Use with care.\n"
            "Kind: question = asked in a section; derived = filled in from your answers; not asked = the game has "
            "no Keep text for it, so it keeps the game's default unless you override it.")
                  ).pack(anchor="w", pady=(4, 8))
        cols = ("value", "default", "max", "kind")
        tree = ttk.Treeview(f, columns=cols, height=26)
        tree.heading("#0", text="Variable")
        for c, w in zip(cols, (70, 70, 60, 190)):
            tree.heading(c, text=c.capitalize())
            tree.column(c, width=int(w * self.px), anchor="center")
        tree.column("#0", width=int(380 * self.px))
        tree.tag_configure("over", foreground="#b00020")
        tree.tag_configure("changed", foreground="#1a5fb4")
        questions = {q.var: q for s in self.sections for q in s.questions}
        derived = rules.derived_names(dict(self.defaults)) - questions.keys()
        for n in sorted(k for k in self.values if k.startswith(("dao_", "da2_"))):
            if n in self.overrides:
                kind = "override"
            else:
                kind = "question" if n in questions else ("derived" if n in derived else "not asked — game default")
            tag = "over" if n in self.overrides else ("changed" if self.values[n] != self.defaults[n] else "")
            # the generated mod raises the game's limit when a value needs it, so show the effective max:
            # the highest answer a question offers, or the current value if an override goes beyond it
            q = questions.get(n)
            effective_max = max(self.ws.vars[n]["MaxValue"], self.values[n], max(q.labels, default=0) if q else 0)
            tree.insert("", "end", iid=n, text=n, tags=(tag,),
                        values=(self.values[n], self.defaults[n], effective_max, kind))
        tree.pack(fill="both", expand=True)
        tree.bind("<Double-1>", lambda e: self._edit_override(tree))
        btns = ttk.Frame(f)
        btns.pack(anchor="w", pady=6)
        ttk.Button(btns, text="Clear override", command=lambda: self._clear_override(tree)).pack(side="left")
        ttk.Button(btns, text="Clear all overrides", command=lambda: self._clear_override(tree, True)).pack(
            side="left", padx=6)

    def _edit_override(self, tree):
        sel = tree.selection()
        if not sel:
            return
        n = sel[0]
        value = simpledialog.askinteger(APP_NAME, f"New value for {n}:", parent=self.root,
                                        initialvalue=self.values[n], minvalue=0, maxvalue=1000)
        if value is None:
            return
        self.overrides[n] = value
        self.recompute()
        self.mark_dirty()
        self.show_section()
        self._reselect(n)

    def _clear_override(self, tree, everything=False):
        if everything:
            self.overrides.clear()
        else:
            for n in tree.selection():
                self.overrides.pop(n, None)
        self.recompute()
        self.mark_dirty()
        self.show_section()

    def _reselect(self, n):
        for child in self.scroll.inner.winfo_children():
            if isinstance(child, ttk.Treeview) and child.exists(n):
                child.selection_set(n)
                child.see(n)

    # ---------- generate
    def generate(self):
        if not self.ws:
            return
        v = self.values
        summary = []
        for n in SUMMARY_VARS:
            q = next((q for s in self.sections for q in s.questions if q.var == n), None)
            if q and q.label_for(v[n]) is not None:
                summary.append(f"{pronouns(q.text, v['dao_warden_mf'] == 1)} {q.label_for(v[n])}")
        description = ("Default world state generated by Offline Keep. Choose \"default world state\" when "
                       "starting a new game.\n\n" + "\n".join(summary))
        safe = re.sub(r'[<>:"/\\|?*]', "_", self.name.get()).strip() or "World State"
        frosty = self.cfg.get("frosty_dir")
        initial = settings.frosty_mods_dir(frosty) if frosty and Path(frosty).exists() else self.cfg.get("mod_dir")
        if initial:
            Path(initial).mkdir(parents=True, exist_ok=True)
        path = filedialog.asksaveasfilename(title="Save Frosty mod", parent=self.root, defaultextension=".fbmod",
                                            initialdir=initial, initialfile=f"OfflineKeep - {safe}.fbmod",
                                            filetypes=[("Frosty mod", "*.fbmod")])
        if not path:
            return
        values = {n: x for n, x in v.items() if n.startswith(("dao_", "da2_"))}
        try:
            data = make_fbmod(self.base_ebx, values, self.head, f"Offline Keep - {self.name.get()}", description)
            Path(path).write_bytes(data)
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Couldn't create the mod:\n\n{ex}", parent=self.root)
            return
        self.cfg["mod_dir"] = str(Path(path).parent)
        settings.save_settings(self.cfg)
        in_frosty = frosty and Path(path).parent.resolve() == settings.frosty_mods_dir(frosty).resolve()
        step1 = ("It's already in Frosty Mod Manager's Mods folder — restart Frosty Mod Manager if it's open."
                 if in_frosty else "In Frosty Mod Manager, click Add Mod(s) and choose this file.")
        messagebox.showinfo(APP_NAME, f"Mod saved:\n{path}\n\nNext steps:\n"
                            f"1. {step1}\n"
                            "2. Select it and click Apply Mod(s); remove any other world state mod from the pack.\n"
                            "3. Click Launch (run Frosty Mod Manager as administrator if the game is in "
                            "Program Files).\n"
                            "4. Start a New Game and choose the DEFAULT world state, not the Keep import.",
                            parent=self.root)
        self.status(f"Generated {path}")

    # ---------- settings
    def choose_game_dir(self):
        d = filedialog.askdirectory(title="Dragon Age: Inquisition folder", parent=self.root,
                                    initialdir=self.cfg.get("game_dir"))
        if not d:
            return
        if not settings.is_game_dir(d):
            messagebox.showerror(APP_NAME, "That folder doesn't contain Dragon Age: Inquisition's Data folder.",
                                 parent=self.root)
            return
        if self.confirm_discard():
            self.load_game(d)

    def choose_frosty_dir(self):
        d = filedialog.askdirectory(title="Folder containing FrostyModManager.exe", parent=self.root,
                                    initialdir=self.cfg.get("frosty_dir"))
        if not d:
            return
        if not (Path(d) / "FrostyModManager.exe").exists():
            messagebox.showerror(APP_NAME, "FrostyModManager.exe isn't in that folder.", parent=self.root)
            return
        self.cfg["frosty_dir"] = d
        settings.save_settings(self.cfg)
        self.status(f"Generated mods will be offered to {settings.frosty_mods_dir(d)}")

    def toggle_auto_update(self):
        self.cfg["auto_update"] = bool(self.auto_update.get())
        settings.save_settings(self.cfg)
        self.status("Offline Keep will check GitHub for a new version each time it starts."
                    if self.cfg["auto_update"] else "Automatic updates are off.")

    def open_verify(self):
        if not self.ws:
            return
        from .verifywindow import VerifyWindow
        VerifyWindow(self)

    def help(self):
        messagebox.showinfo(APP_NAME, HELP, parent=self.root)

    def quit(self):
        if self.confirm_discard():
            self.root.destroy()


HELP = """1. Answer the questions in each section, just like the Dragon Age Keep. Flags that follow from your
answers (e.g. "Is Alistair alive?") are filled in automatically. Warnings at the bottom point out combinations
the original games couldn't produce; they're allowed, but may cause odd dialogue.

2. Save your world state (File → Save) to keep or share it.

3. Click Generate Mod… to create a .fbmod file. Tip: set Settings → Frosty Mod Manager Folder… and the mod
is saved straight into Frosty's Mods folder.

4. In Frosty Mod Manager: Apply the mod, then Launch the game from Frosty.

5. Start a NEW game and pick the DEFAULT world state. World states only apply at character creation.

6. Tools → Verify World State… shows which world state Frosty installed, and which one a save actually uses."""

ABOUT = f"""Offline Keep {__version__} — an offline replacement for the Dragon Age Keep.

Reads the world state definitions directly from your Dragon Age: Inquisition installation; no game data
is included. Mods are written in Frosty Mod Manager's .fbmod format. The only network access is the
optional update check (Settings → Check for Updates at Startup, off by default), which contacts GitHub.

Unofficial fan tool, not affiliated with or endorsed by Electronic Arts or BioWare.
MIT licensed — https://github.com/Fiztba/offline-keep

Thanks to anshela's Custom World States documentation and the Frosty Toolsuite authors."""


def main():
    try:  # crisp text on high-DPI displays instead of Windows bitmap scaling
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (ImportError, AttributeError, OSError):
        pass
    splash = {}

    def show_progress(tag):
        """Small borderless window shown only while a new version downloads."""
        win = tk.Tk()
        win.overrideredirect(True)
        label = ttk.Label(win, text=f"Updating Offline Keep to {tag}…", padding=(24, 16))
        label.pack()
        win.update_idletasks()
        win.geometry(f"+{(win.winfo_screenwidth() - win.winfo_width()) // 2}"
                     f"+{(win.winfo_screenheight() - win.winfo_height()) // 2}")
        win.update()
        splash["win"] = win

        def progress(fraction):
            label.configure(text=f"Updating Offline Keep to {tag}…  {int(fraction * 100)}%")
            win.update()

        return progress

    started_new = updater.run_if_enabled(show_progress)
    if "win" in splash:
        splash["win"].destroy()
    if started_new:
        return
    root = tk.Tk()
    App(root)
    root.mainloop()
