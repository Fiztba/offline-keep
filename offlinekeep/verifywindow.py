"""The Verify World State window: what Frosty installed, and what a save actually imported."""
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from . import savegame, verify


def _when(ts):
    return time.strftime("%d %b %Y, %H:%M", time.localtime(ts))


class VerifyWindow:
    def __init__(self, app):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.title("Verify World State")
        px = app.px
        self.win.geometry(f"{int(980 * px)}x{int(640 * px)}")
        self.win.transient(app.root)
        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=10, pady=10)
        self.inst = self._tab(nb, "Installed mod (Frosty)", (
            "Shows the world state Frosty Mod Manager actually installed into the game. Frosty rebuilds these files "
            "when you click Launch, so changes applied since your last Launch won't show yet."))
        self.save = self._tab(nb, "Saved game", (
            "Shows the world state stored in a save. The game copies the world state into your save when you create "
            "a character, so this is what that playthrough uses."))
        row = ttk.Frame(self.save["frame"])
        row.pack(fill="x", pady=(0, 6), before=self.save["result"])
        ttk.Label(row, text="Save:").pack(side="left")
        self.save_box = ttk.Combobox(row, state="readonly", width=60)
        self.save_box.pack(side="left", padx=6)
        self.save_box.bind("<<ComboboxSelected>>", lambda e: self.check_save())
        ttk.Button(row, text="Browse…", command=self.browse_save).pack(side="left")
        self.apply_btn = ttk.Button(row, text="Apply my world state to this save…", command=self.apply_to_save,
                                    state="disabled")
        self.apply_btn.pack(side="right")
        self.save_values = None
        ttk.Button(self.inst["frame"], text="Check again", command=self.check_installed).pack(
            anchor="w", pady=(0, 6), before=self.inst["result"])
        self.saves = []
        self.fill_saves()
        self.check_installed()

    def _tab(self, nb, title, intro):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text=title)
        ttk.Label(f, text=intro, wraplength=int(900 * self.app.px), justify="left").pack(anchor="w", pady=(0, 8))
        result = ttk.Label(f, text="", justify="left", wraplength=int(900 * self.app.px), font=("Segoe UI", 10))
        result.pack(anchor="w", pady=(0, 8), fill="x")
        cols = ("section", "yours", "found")
        tree = ttk.Treeview(f, columns=cols, height=14)
        tree.heading("#0", text="Question")
        tree.heading("section", text="Section")
        tree.heading("yours", text="Your current world state")
        tree.heading("found", text="Found")
        tree.column("#0", width=int(330 * self.app.px))
        tree.column("section", width=int(140 * self.app.px))
        tree.column("yours", width=int(220 * self.app.px))
        tree.column("found", width=int(220 * self.app.px))
        tree.pack(fill="both", expand=True)
        return {"frame": f, "result": result, "tree": tree}

    # ---------- shared
    def _run(self, tab, work, done):
        tab["result"].configure(text="Checking…")
        tab["tree"].delete(*tab["tree"].get_children())
        box = {}

        def target():
            try:
                box["value"] = work()
            except Exception as ex:  # shown in the window
                box["error"] = ex

        t = threading.Thread(target=target, daemon=True)
        t.start()

        def poll():
            if t.is_alive():
                self.win.after(100, poll)
            elif "error" in box:
                tab["result"].configure(text=f"Couldn't check: {box['error']}")
            else:
                done(box["value"])

        poll()

    def _candidates(self):
        app = self.app
        cands = {"your current world state": verify.world_vars(app.values)}
        cands.update(verify.saved_worldstates(app.cfg.get("worldstate_dir"), app.defaults))
        cands["the game's own default world state (no world state mod)"] = verify.world_vars(app.defaults)
        return cands

    def _describe(self, tab, values, heading):
        app = self.app
        current = verify.world_vars(app.values)
        match = verify.identify(values, self._candidates())
        rows, other = verify.differences(values, current, app.sections)
        if match == "your current world state":
            verdict = "✔ Matches your current world state."
        elif match:
            verdict = f"This is {match}." if match.startswith("the game") else f"Matches your saved world state {match}."
        else:
            verdict = "This doesn't match your current world state or any saved world state file."
        lines = [heading, verdict]
        if rows or other:
            lines.append(f"{len(rows)} answer(s) differ from your current world state"
                         + (f", plus {other} other variable(s)." if other else "."))
        lines.append(self._summary(values))
        tab["result"].configure(text="\n".join(lines))
        from .app import pronouns
        for sec, q, yours, found in rows:
            f_yours = q.label_for(yours) or str(yours)
            f_found = q.label_for(found) or str(found)
            tab["tree"].insert("", "end", text=pronouns(q.text, current.get("dao_warden_mf") == 1),
                               values=(sec.title, pronouns(f_yours, current.get("dao_warden_mf") == 1),
                                       pronouns(f_found, values.get("dao_warden_mf") == 1)))

    def _summary(self, values):
        from .app import SUMMARY_VARS, pronouns
        female = values.get("dao_warden_mf") == 1
        parts = []
        for n in SUMMARY_VARS[:6]:
            q = next((q for s in self.app.sections for q in s.questions if q.var == n), None)
            if q and n in values and q.label_for(values[n]):
                parts.append(f"{pronouns(q.text, female)} {pronouns(q.label_for(values[n]), female)}")
        return "\n".join("• " + p for p in parts)

    # ---------- installed mod
    def check_installed(self):
        game_dir = self.app.cfg.get("game_dir")

        def done(packs):
            tab = self.inst
            if not packs:
                tab["result"].configure(text=(
                    "Frosty Mod Manager hasn't installed any mods into this game yet (no ModData folder).\n"
                    "Apply your world state mod in Frosty and click Launch once, then check again."))
                return
            pack = max(packs, key=lambda p: p["modified"])  # the pack Frosty launched most recently
            others = [p["pack"] for p in packs if p is not pack]
            heading = f"Frosty pack \"{pack['pack']}\", installed {_when(pack['modified'])}."
            if others:
                heading += f" (Other packs found: {', '.join(others)}.)"
            if pack["error"]:
                tab["result"].configure(text=f"{heading}\nCouldn't read its world state: {pack['error']}")
                return
            self._describe(tab, pack["values"], heading)

        self._run(self.inst, lambda: verify.installed_packs(game_dir), done)

    # ---------- saves
    def fill_saves(self):
        self.saves = savegame.list_saves()
        self.save_box.configure(values=[f"{p.name}   ({_when(t)})" for p, t in self.saves])
        if self.saves:
            self.save_box.current(0)
            self.check_save()
        else:
            self.save["result"].configure(text=f"No saves found in {savegame.default_save_dir()}. Use Browse… "
                                               "to pick one.")

    def browse_save(self):
        path = filedialog.askopenfilename(title="Choose a save", parent=self.win,
                                          initialdir=str(savegame.default_save_dir()),
                                          filetypes=[("Inquisition save", "*.DAS")])
        if path:
            p = Path(path)
            self.saves.insert(0, (p, p.stat().st_mtime))
            self.save_box.configure(values=[f"{q.name}   ({_when(t)})" for q, t in self.saves])
            self.save_box.current(0)
            self.check_save()

    def check_save(self):
        i = self.save_box.current()
        if i < 0:
            return
        path, mtime = self.saves[i]
        heading = f"Save {path.name}, saved {_when(mtime)}."
        self.apply_btn.configure(state="disabled")
        self.save_values = None

        def done(values):
            self.save_values = values
            self._describe(self.save, values, heading)
            differs = any(values.get(n) != v for n, v in verify.world_vars(self.app.values).items() if n in values)
            self.apply_btn.configure(state="normal" if differs else "disabled")

        self._run(self.save, lambda: verify.saved_game(path, self.app.ws), done)

    def apply_to_save(self):
        from tkinter import messagebox
        from .app import pronouns
        i = self.save_box.current()
        if i < 0 or self.save_values is None:
            return
        path, _ = self.saves[i]
        target = verify.world_vars(self.app.values)
        rows, other = verify.differences(target, self.save_values, self.app.sections)
        female = target.get("dao_warden_mf") == 1
        lines = [f"• {pronouns(q.text, female)} {pronouns(q.label_for(new) or str(new), female)}"
                 for _, q, _, new in rows[:12]]
        if len(rows) > 12:
            lines.append(f"• …and {len(rows) - 12} more")
        if other:
            lines.append(f"• plus {other} other variable(s) that follow from your answers")
        if not messagebox.askokcancel(
                "Apply world state to save",
                f"Change the world state stored in {path.name} to your current world state?\n\n"
                + "\n".join(lines) +
                "\n\nClose Dragon Age: Inquisition first. The original save is backed up to the "
                "\"OfflineKeep backups\" folder next to your saves.\n\n"
                "This changes what the game checks from now on (dialogue, companions, endings). Scenes you've "
                "already played won't change.", parent=self.win):
            return
        try:
            changed, backup = savegame.apply_world_state(path, target, self.app.ws)
        except Exception as ex:
            messagebox.showerror("Apply world state to save", f"The save was not changed:\n\n{ex}", parent=self.win)
            return
        messagebox.showinfo("Apply world state to save",
                            f"Updated {len(changed)} world-state flag(s) in {path.name}.\n\nBackup: {backup}"
                            if changed else "The save already matches your world state.", parent=self.win)
        self.saves[i] = (path, path.stat().st_mtime)
        self.check_save()
