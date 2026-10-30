import ipaddress
import queue
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .bridge import LinuxAirDrop, StableInbox, diagnose
from .errors import ShareError
from .settings import Translator, load_settings, save_settings
from .transfer import APPROVAL_SECONDS, Receiver, local_ipv4_addresses, send_file


@dataclass
class Decision:
    offer: object
    receiver: object
    finished: threading.Event = field(default_factory=threading.Event)
    accepted: bool = False
    expires: float = field(default_factory=lambda: time.monotonic() + APPROVAL_SECONDS - 1)


def human_size(value):
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{value} B"
        value /= 1024


class App:
    def __init__(self):
        self.settings = load_settings()
        self.t = Translator(self.settings["language"])
        self.root = tk.Tk()
        self.root.title(f"ChimpiShare {__version__}")
        self.root.geometry("960x760")
        self.root.minsize(800, 680)
        self.root.configure(bg="#10121b")
        self.events = queue.Queue()
        self.receiver = None
        self.airdrop = LinuxAirDrop()
        self.decisions = []
        self.closing = False
        self.sending = False
        self.bridge_files = {}
        self.scanning = False
        self.selected_file = tk.StringVar()
        self.target = tk.StringVar()
        self.receive_folder = tk.StringVar(value=self.settings["receive_folder"] or str(Path.home() / "Downloads" / "ChimpiShare"))
        self.bridge_folder = tk.StringVar(value=self.settings["bridge_folder"] or str(Path.home() / "ChimpiShare-Bridge"))
        addresses = local_ipv4_addresses()
        self.host = tk.StringVar(value=self.settings["host"] or addresses[0])
        self.port = tk.StringVar(value=str(self.settings["port"]))
        self.status = tk.StringVar(value=self.t("idle"))
        self.inbox = StableInbox(self.bridge_folder.get())
        self._style()
        self._layout(addresses)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(60, self._drain)
        self.root.after(1000, self._scan)

    def _style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background="#171b28", foreground="#f1f3ff")
        style.configure("TFrame", background="#171b28")
        style.configure("TLabel", background="#171b28", foreground="#f1f3ff")
        style.configure("Muted.TLabel", foreground="#aab3ca")
        style.configure("Title.TLabel", font=("Segoe UI", 25, "bold"))
        style.configure("TNotebook", background="#10121b", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(20, 10), background="#202638")
        style.map("TNotebook.Tab", background=[("selected", "#493b82")])
        style.configure("TButton", padding=(12, 8), background="#30394f")
        style.configure("Accent.TButton", background="#7155cf")
        style.map("TButton", background=[("active", "#4b5874"), ("disabled", "#252b3c")],
                  foreground=[("disabled", "#747e95")])
        style.configure("TEntry", fieldbackground="#101521", foreground="#ffffff", insertcolor="#ffffff", padding=8)
        style.configure("TCombobox", fieldbackground="#101521", foreground="#ffffff", padding=6)
        style.configure("Treeview", fieldbackground="#101521", background="#101521", rowheight=29)
        style.configure("Treeview.Heading", background="#30394f")
        style.configure("TProgressbar", background="#a38aff", troughcolor="#242c40")

    def _layout(self, addresses):
        outer = ttk.Frame(self.root, padding=22)
        outer.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(outer, text="ChimpiShare", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text=self.t("tagline"), style="Muted.TLabel").pack(anchor="w", pady=(3, 13))
        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill="both", expand=True)
        self.receive_tab, self.send_tab, self.bridge_tab = [ttk.Frame(self.tabs, padding=18) for _ in range(3)]
        for frame, key in [(self.receive_tab, "receive"), (self.send_tab, "send"), (self.bridge_tab, "bridge")]:
            self.tabs.add(frame, text=self.t(key))
        self._receive_layout(addresses)
        self._send_layout()
        self._bridge_layout()
        ttk.Label(outer, textvariable=self.status, style="Muted.TLabel", wraplength=830).pack(anchor="w", pady=(12, 6))
        self.log = tk.Text(outer, height=3, bg="#101521", fg="#bcc5de", relief="flat", wrap="word",
                           font=("Segoe UI", 9), state="disabled", padx=10, pady=6)
        self.log.pack(fill="x")
        menu = tk.Menu(self.root)
        language = tk.Menu(menu, tearoff=False)
        for value, label in [("system", self.t("system_language")), ("pt-BR", "Português (Brasil)"), ("en", "English")]:
            language.add_command(label=label, command=lambda v=value: self._language(v))
        menu.add_cascade(label=self.t("language"), menu=language)
        menu.add_command(label=self.t("diagnostics"), command=self._diagnostics)
        self.root.config(menu=menu)

    def _entry_row(self, parent, label, variable, choose=None):
        ttk.Label(parent, text=self.t(label)).pack(anchor="w", pady=(7, 5))
        row = ttk.Frame(parent)
        row.pack(fill="x")
        entry = ttk.Entry(row, textvariable=variable)
        entry.pack(side="left", fill="x", expand=True)
        if choose:
            ttk.Button(row, text=self.t("browse"), command=choose).pack(side="right", padx=(8, 0))
        return entry

    def _receive_layout(self, addresses):
        tab = self.receive_tab
        ttk.Label(tab, text=self.t("receive_help"), wraplength=790).pack(anchor="w", pady=(0, 6))
        self.folder_entry = self._entry_row(tab, "destination_folder", self.receive_folder,
                                            lambda: self._choose_folder(self.receive_folder))
        ttk.Label(tab, text=self.t("network_help"), style="Muted.TLabel", wraplength=790).pack(anchor="w", pady=(12, 6))
        row = ttk.Frame(tab)
        row.pack(fill="x")
        ttk.Label(row, text=self.t("address")).pack(side="left")
        self.host_entry = ttk.Combobox(row, textvariable=self.host, values=addresses, width=20)
        self.host_entry.pack(side="left", padx=9)
        ttk.Label(row, text=self.t("port")).pack(side="left", padx=(14, 4))
        self.port_entry = ttk.Entry(row, textvariable=self.port, width=8)
        self.port_entry.pack(side="left")
        buttons = ttk.Frame(tab)
        buttons.pack(fill="x", pady=13)
        self.start_button = ttk.Button(buttons, text=self.t("start_receiver"), command=self._start_receiver, style="Accent.TButton")
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(buttons, text=self.t("stop"), command=self._stop_receiver, state="disabled")
        self.stop_button.pack(side="left", padx=8)
        self.copy_button = ttk.Button(buttons, text=self.t("copy_invitation"), command=self._copy_invitation, state="disabled")
        self.copy_button.pack(side="left")
        ttk.Label(tab, text=self.t("invitation_help"), style="Muted.TLabel", wraplength=790).pack(anchor="w", pady=(0, 7))
        self.invitation_text = tk.Text(tab, height=3, bg="#101521", fg="#d0c6ff", wrap="char", relief="flat",
                                       font=("Consolas", 10), state="disabled", padx=10, pady=8)
        self.invitation_text.pack(fill="x")

    def _send_layout(self):
        tab = self.send_tab
        ttk.Label(tab, text=self.t("send_help"), wraplength=790).pack(anchor="w", pady=(0, 8))
        self._entry_row(tab, "receiver_invitation", self.target)
        self._entry_row(tab, "selected_file", self.selected_file, self._choose_file)
        self.send_button = ttk.Button(tab, text=self.t("send_file"), command=self._send, style="Accent.TButton")
        self.send_button.pack(anchor="w", pady=18)
        self.progress = ttk.Progressbar(tab, maximum=100, mode="determinate")
        self.progress.pack(fill="x")
        ttk.Label(tab, text=self.t("transfer_help"), style="Muted.TLabel", wraplength=790).pack(anchor="w", pady=14)

    def _bridge_layout(self):
        tab = self.bridge_tab
        ttk.Label(tab, text=self.t("bridge_help"), wraplength=790).pack(anchor="w", pady=(0, 5))
        row = ttk.Frame(tab)
        row.pack(fill="x", pady=6)
        ttk.Button(row, text=self.t("select_airdrop_file"), command=self._choose_file).pack(side="left")
        ttk.Button(row, text=self.t("linux_airdrop"), command=self._start_airdrop).pack(side="left", padx=8)
        ttk.Button(row, text=self.t("stop_airdrop"), command=self._stop_airdrop).pack(side="left")
        self._entry_row(tab, "bridge_inbox", self.bridge_folder, self._choose_inbox).configure(state="readonly")
        ttk.Label(tab, text=self.t("inbox_help"), style="Muted.TLabel", wraplength=790).pack(anchor="w", pady=(8, 7))
        self.file_tree = ttk.Treeview(tab, columns=("name", "size"), show="headings", height=4, selectmode="browse")
        self.file_tree.heading("name", text=self.t("file"))
        self.file_tree.heading("size", text=self.t("size"))
        self.file_tree.column("name", width=610, stretch=True)
        self.file_tree.column("size", width=105, stretch=False)
        self.file_tree.pack(fill="both", expand=True)
        ttk.Button(tab, text=self.t("review_selected"), command=self._review_selected).pack(anchor="w", pady=(9, 0))

    def _choose_folder(self, variable):
        if self.receiver and variable is self.receive_folder:
            messagebox.showinfo("ChimpiShare", self.t("stop_to_change"))
            return
        folder = filedialog.askdirectory(parent=self.root)
        if folder:
            variable.set(folder)

    def _choose_inbox(self):
        if self.airdrop.process is not None and self.airdrop.process.poll() is None:
            messagebox.showinfo("ChimpiShare", self.t("stop_to_change"))
            return
        self._choose_folder(self.bridge_folder)
        self.inbox = StableInbox(self.bridge_folder.get())

    def _choose_file(self):
        path = filedialog.askopenfilename(parent=self.root, title=self.t("select_airdrop_file"))
        if path:
            self.selected_file.set(path)
            self.tabs.select(self.send_tab)

    def _start_receiver(self):
        try:
            host = str(ipaddress.IPv4Address(self.host.get().strip()))
            port = int(self.port.get())
            if not 1 <= port <= 65535 or not 1 <= self.settings["max_file_mib"] <= 1024 * 1024:
                raise ShareError("invalid_request")
            if not self.receive_folder.get().strip():
                raise ShareError("choose_folder")
            # Bind only to the interface selected by the user.
            receiver = Receiver(self.receive_folder.get(), lambda offer: self._approve(offer, receiver),
                                self._notify, host=host, port=port,
                                max_bytes=self.settings["max_file_mib"] * 1024 * 1024)
            self.receiver = receiver
            invitation = receiver.invitation(host)
            receiver.start()
            self.active_invitation = invitation
            self.invitation_text.configure(state="normal")
            self.invitation_text.delete("1.0", "end")
            self.invitation_text.insert("1.0", invitation)
            self.invitation_text.configure(state="disabled")
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            self.copy_button.configure(state="normal")
            self.folder_entry.configure(state="readonly")
            self.host_entry.configure(state="disabled")
            self.port_entry.configure(state="disabled")
            self.status.set(self.t("listening", host=host, port=port))
            self._remember()
        except Exception as exc:
            if self.receiver is not None:
                self.receiver.close()
                self.receiver = None
            self._show_error(exc)

    def _stop_receiver(self):
        for decision in self.decisions:
            decision.finished.set()
        if self.receiver:
            self.receiver.close()
            self.receiver = None
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.copy_button.configure(state="disabled")
        self.folder_entry.configure(state="normal")
        self.host_entry.configure(state="normal")
        self.port_entry.configure(state="normal")
        self.invitation_text.configure(state="normal")
        self.invitation_text.delete("1.0", "end")
        self.invitation_text.configure(state="disabled")
        self.status.set(self.t("stopped"))

    def _copy_invitation(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.active_invitation)
        self.status.set(self.t("invitation_copied"))

    def _approve(self, offer, receiver):
        decision = Decision(offer, receiver)
        self.events.put(("approve", decision))
        while not decision.finished.wait(0.15):
            if self.closing or receiver.closed.is_set() or time.monotonic() >= decision.expires:
                decision.finished.set()
                return False
        return decision.accepted and not self.closing

    def _notify(self, kind, **values):
        self.events.put((kind, values))

    def _send(self):
        if self.sending:
            return
        path, invitation = self.selected_file.get().strip(), self.target.get().strip()
        if not path:
            messagebox.showinfo("ChimpiShare", self.t("choose_file"))
            return
        self.sending = True
        self.send_button.configure(state="disabled")
        self.progress["value"] = 0
        self.status.set(self.t("waiting_approval"))

        def work():
            last = 0

            def progress(done, total):
                nonlocal last
                now = time.monotonic()
                if now - last > 0.1 or done == total:
                    self.events.put(("progress", (done, total)))
                    last = now

            try:
                result = send_file(invitation, path, progress)
                self.events.put(("sent", result))
            except Exception as exc:
                self.events.put(("send_error", exc))

        threading.Thread(target=work, daemon=True).start()

    def _start_airdrop(self):
        try:
            report = diagnose()
            if report["system"] != "Linux" or report["wsl"]:
                raise ShareError("linux_only")
            if not report["awdl_interface"] or not report["opendrop"]:
                raise ShareError("awdl_missing")
            if not messagebox.askyesno("ChimpiShare", self.t("airdrop_confirm"), parent=self.root):
                return
            folder = self.airdrop.start(self.bridge_folder.get())
            self._log(self.t("airdrop_started", folder=folder))
        except Exception as exc:
            self._show_error(exc)

    def _stop_airdrop(self):
        self.airdrop.stop()
        self._log(self.t("airdrop_stopped"))

    def _scan(self):
        if self.closing:
            return
        if not self.scanning:
            self.scanning = True
            folder = self.bridge_folder.get()
            if Path(folder).expanduser().resolve() != self.inbox.folder:
                self.inbox = StableInbox(folder)
            inbox = self.inbox

            def work():
                try:
                    self.events.put(("inbox", (inbox, inbox.scan())))
                except OSError as exc:
                    self.events.put(("inbox_error", exc))

            threading.Thread(target=work, daemon=True).start()
        if self.airdrop.process is not None and self.airdrop.process.poll() is not None:
            self._log(self.t("airdrop_exited", code=self.airdrop.process.returncode))
            self.airdrop.process = None
        self.root.after(2000, self._scan)

    def _review_selected(self):
        selection = self.file_tree.selection()
        if selection and selection[0] in self.bridge_files:
            self.selected_file.set(str(self.bridge_files[selection[0]]))
            self.tabs.select(self.send_tab)

    def _diagnostics(self):
        data = diagnose()
        yes, no = self.t("yes"), self.t("no")
        messagebox.showinfo(self.t("diagnostics"), self.t("diagnostic_report",
            system=data["system"], wsl=yes if data["wsl"] else no,
            awdl=yes if data["awdl_interface"] else no,
            opendrop=yes if data["opendrop"] else no, owl=yes if data["owl"] else no), parent=self.root)

    def _language(self, value):
        self.settings["language"] = value
        self._remember()
        messagebox.showinfo("ChimpiShare", self.t("restart_language"), parent=self.root)

    def _remember(self):
        self.settings.update(receive_folder=self.receive_folder.get(), bridge_folder=self.bridge_folder.get(),
                             host=self.host.get())
        try:
            self.settings["port"] = int(self.port.get())
            save_settings(self.settings)
        except (ValueError, OSError) as exc:
            self._log(self.t("settings_error", error=str(exc)))

    def _show_error(self, exc):
        text = self.t(exc.code, **exc.values) if isinstance(exc, ShareError) else self.t("system_error", error=str(exc))
        self.status.set(text)
        self._log(text)
        messagebox.showerror("ChimpiShare", text, parent=self.root)

    def _log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        if int(self.log.index("end-1c").split(".")[0]) > 100:
            self.log.delete("1.0", "20.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _drain(self):
        if self.closing:
            return
        for _ in range(150):
            try:
                kind, data = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "approve":
                if (data.finished.is_set() or data.receiver is not self.receiver
                        or time.monotonic() >= data.expires):
                    data.finished.set()
                    continue
                self.decisions.append(data)
                offer = data.offer
                accepted = messagebox.askyesno(self.t("incoming_file"), self.t("accept_file", name=offer.name,
                                               size=human_size(offer.size), peer=offer.peer), parent=self.root)
                data.accepted = accepted and not data.finished.is_set() and time.monotonic() < data.expires
                data.finished.set()
                self.decisions.remove(data)
            elif kind == "progress":
                done, total = data
                self.progress["value"] = 100 * done / total if total else 100
                self.status.set(self.t("sending", amount=human_size(done), total=human_size(total)))
            elif kind in {"sent", "send_error"}:
                self.sending = False
                self.send_button.configure(state="normal")
                if kind == "send_error":
                    self._show_error(data)
                else:
                    self.progress["value"] = 100
                    text = self.t("sent_ok", name=data["name"])
                    self.status.set(text)
                    self._log(text)
            elif kind == "received":
                text = self.t("received_ok", path=data["path"])
                self.status.set(text)
                self._log(text)
            elif kind == "inbox":
                self.scanning = False
                inbox, files = data
                if inbox is not self.inbox:
                    continue
                old = self.file_tree.selection()
                prior = self.bridge_files.get(old[0]) if old else None
                self.file_tree.delete(*self.file_tree.get_children())
                self.bridge_files = {}
                for index, (path, size) in enumerate(files):
                    iid = str(index)
                    self.file_tree.insert("", "end", iid=iid, values=(str(path.relative_to(inbox.folder)), human_size(size)))
                    self.bridge_files[iid] = path
                    if path == prior:
                        self.file_tree.selection_set(iid)
            elif kind == "inbox_error":
                self.scanning = False
                self.status.set(self.t("system_error", error=str(data)))
        self.root.after(60, self._drain)

    def _close(self):
        self.closing = True
        for decision in self.decisions:
            decision.finished.set()
        self.airdrop.stop()
        if self.receiver:
            self.receiver.close()
        self._remember()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
