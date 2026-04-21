# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading, queue, zipfile, subprocess, sys, os, shutil
import glob as globmod
from datetime import datetime

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

NL = chr(10)
IS_WIN = sys.platform == "win32"
BG="#1a1b26"; BG2="#24283b"; BG3="#2f3349"; BG4="#3b4f57"
TEXT="#a9b1d6"; TEXT2="#c0caf5"; DIM="#565f89"
BLUE="#7aa2f7"; BLUE2="#89b4fa"; GREEN="#9ece6a"; RED="#f7768e"; YELLOW="#e0af68"; SEL_BG="#3d4166"

def pip_install(py, args):
    try:
        r = subprocess.run([py, "-m", "pip", "install"] + list(args), capture_output=True, text=True, timeout=300)
        return r.returncode == 0, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)

def extract_zip(zp, dest):
    try:
        with zipfile.ZipFile(zp, "r") as zf:
            ns = zf.namelist(); top = set()
            for n in ns:
                p = n.split("/")[0].split(chr(92))[0]
                if p: top.add(p)
            if len(top) == 1:
                t = dest + ".tmp_ext"; os.makedirs(t, exist_ok=True); zf.extractall(t)
                inner = os.path.join(t, list(top)[0])
                if os.path.isdir(inner):
                    os.makedirs(dest, exist_ok=True)
                    for i in os.listdir(inner):
                        shutil.move(os.path.join(inner, i), os.path.join(dest, i))
                    shutil.rmtree(t, ignore_errors=True)
                else:
                    shutil.move(t, dest)
            else:
                os.makedirs(dest, exist_ok=True); zf.extractall(dest)
        return True
    except:
        return False

def dir_name_from_zip(z):
    n = os.path.splitext(z)[0]
    for s in ("main", "Main", "MASTER", "master"):
        if n.endswith("-" + s) or n.endswith("_" + s):
            n = n[:-(len(s) + 1)]; break
    return n

def find_req(t):
    r = []
    for root, dirs, files in os.walk(t):
        dirs[:] = [d for d in dirs if d not in {"venv", ".venv", ".git", "__pycache__"}]
        for f in files:
            if f.lower().startswith("requirements") and f.lower().endswith(".txt"):
                r.append(os.path.join(root, f))
    return r

def detect_python(ir):
    cs = []
    if ir:
        sr = [ir]; c = ir
        for _ in range(2):
            pp = os.path.dirname(c)
            if pp and pp != c: sr.append(pp); c = pp
        for sroot in sr:
            for v in ("venv", ".venv", "python_embeded"):
                p = os.path.join(sroot, v, "python.exe" if IS_WIN else "bin/python")
                if os.path.isfile(p): cs.append(p)
    for c in ("python3", "python"):
        f = shutil.which(c)
        if f: cs.append(f)
    for c in cs:
        try:
            r = subprocess.run([c, "--version"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0: return c, r.stdout.strip()
        except: continue
    return "", ""

def fmt_size(s):
    return "{:.1f} MB".format(s / 1048576) if s > 1048576 else "{:.1f} KB".format(s / 1024)

class App:
    def __init__(self):
        self.root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
        self.root.title("ComfyUI 扩展安装器")
        self.root.geometry("920x720"); self.root.minsize(800, 600); self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.zip_items = []; self.lq = queue.Queue()
        self.installing = False; self._aid = None; self.failed_reqs = []
        self.install_dir = tk.StringVar(); self.python_path = tk.StringVar()
        self._opt_up = tk.BooleanVar(value=True)
        self._opt_bk = tk.BooleanVar(value=True)
        self._opt_ed = tk.BooleanVar(value=False)
        self._styles(); self._build()
        self.root.after(200, self._do_scan)
        if not HAS_DND:
            self.root.after(500, lambda: self._alog("\u672a\u5b89\u88c5 tkinterdnd2\uff0c\u62d6\u653e\u4e0d\u53ef\u7528\u3002\u8bf7\u6267\u884c pip install tkinterdnd2", "warn"))

    def _styles(self):
        s = ttk.Style(); s.theme_use("clam")
        s.configure(".", background=BG, foreground=TEXT, borderwidth=0, focusthickness=0)
        s.map(".", background=[("active", BG3)])
        s.configure("TFrame", background=BG); s.configure("P.TFrame", background=BG2)
        s.configure("TLabel", background=BG, foreground=TEXT, font=("Arial", 10))
        s.configure("Title.TLabel", background=BG, foreground=BLUE, font=("Arial", 18, "bold"))
        s.configure("Dim.TLabel", background=BG, foreground=DIM, font=("Arial", 9))
        s.configure("H.TLabel", background=BG2, foreground=GREEN, font=("Arial", 11, "bold"))
        s.configure("ST.TLabel", background=BG2, foreground=TEXT, font=("Arial", 9))
        s.configure("TButton", background=BG3, foreground=TEXT2, font=("Arial", 10), padding=(12, 6))
        s.map("TButton", background=[("active", BG4), ("pressed", BLUE)])
        s.configure("Go.TButton", background=BLUE, foreground=BG, font=("Arial", 13, "bold"), padding=(20, 10))
        s.map("Go.TButton", background=[("active", BLUE2)])
        s.configure("Sm.TButton", background=BG3, foreground=DIM, font=("Arial", 9), padding=(8, 3))
        s.map("Sm.TButton", background=[("active", BG4)])
        s.configure("Retry.TButton", background=RED, foreground=BG, font=("Arial", 12, "bold"), padding=(16, 8))
        s.map("Retry.TButton", background=[("active", "#ff9aa2")])
        s.configure("Treeview", background=BG2, foreground=TEXT, fieldbackground=BG2, borderwidth=0, font=("Arial", 10), rowheight=30)
        s.configure("Treeview.Heading", background=BG3, foreground=BLUE, font=("Arial", 10, "bold"), borderwidth=0, relief="flat")
        s.map("Treeview", background=[("selected", SEL_BG)], foreground=[("selected", TEXT2)])
        s.map("Treeview.Heading", background=[("active", BG4)])
        s.configure("TScrollbar", background=BG3, troughcolor=BG, borderwidth=0, arrowcolor=DIM)
        s.map("TScrollbar", background=[("active", BG4)])
        s.configure("Bar.Horizontal.TProgressbar", background=BLUE, troughcolor=BG3, borderwidth=0, thickness=10)
        s.configure("TCheckbutton", background=BG2, foreground=TEXT, font=("Arial", 10))
        s.map("TCheckbutton", background=[("active", BG2)])

    def _build(self):
        top = ttk.Frame(self.root); top.pack(fill="x", padx=24, pady=(18, 2))
        ttk.Label(top, text="ComfyUI 扩展安装器", style="Title.TLabel").pack(side="left")
        self.lbl_dir = ttk.Label(top, text="", style="Dim.TLabel"); self.lbl_dir.pack(side="right")
        body = ttk.Frame(self.root); body.pack(fill="both", expand=True, padx=24, pady=8)
        body.columnconfigure(0, weight=3); body.columnconfigure(1, weight=2); body.rowconfigure(0, weight=1)
        self._left(body); self._right(body); self._log_panel(); self._bar()

    def _left(self, parent):
        w = ttk.Frame(parent, style="P.TFrame"); w.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        hdr = ttk.Frame(w, style="P.TFrame"); hdr.pack(fill="x", padx=14, pady=(12, 4))
        dnd = " (支持拖放 ZIP 加入)" if HAS_DND else " (拖放需 pip install tkinterdnd2)"
        ttk.Label(hdr, text=" 扩展列表" + dnd, style="H.TLabel").pack(side="left")
        br = ttk.Frame(hdr, style="P.TFrame"); br.pack(side="right")
        self.btn_add = ttk.Button(br, text="+ 添加", style="Sm.TButton", command=self._add_zips, width=6); self.btn_add.pack(side="left", padx=2)
        self.btn_all = ttk.Button(br, text="全选", style="Sm.TButton", command=self._sel_all, width=5); self.btn_all.pack(side="left", padx=2)
        self.btn_none = ttk.Button(br, text="取消", style="Sm.TButton", command=self._sel_none, width=5); self.btn_none.pack(side="left", padx=2)
        self.btn_scan = ttk.Button(br, text="扫描", style="Sm.TButton", command=self._do_scan, width=5); self.btn_scan.pack(side="left", padx=2)
        self.btn_rm = ttk.Button(br, text="- 删除", style="Sm.TButton", command=self._remove_sel, width=5); self.btn_rm.pack(side="left", padx=2)
        tf = ttk.Frame(w, style="P.TFrame"); tf.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        self.tree = ttk.Treeview(tf, columns=("chk", "name", "size"), show="headings", style="Treeview", selectmode="none")
        self.tree.heading("chk", text="", anchor="center"); self.tree.heading("name", text="文件", anchor="w"); self.tree.heading("size", text="大小", anchor="e")
        self.tree.column("chk", width=44, minwidth=44, stretch=False, anchor="center")
        self.tree.column("name", minwidth=200); self.tree.column("size", width=90, minwidth=70, stretch=False, anchor="e")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview); self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True); vsb.pack(side="right", fill="y")
        self.tree.bind("<ButtonRelease-1>", self._on_click)
        if HAS_DND:
            self.tree.drop_target_register(DND_FILES)
            self.tree.dnd_bind("<<Drop>>", self._on_drop)
        self.lbl_cnt = ttk.Label(w, text="已选择: 0 / 0", style="Dim.TLabel"); self.lbl_cnt.pack(padx=14, pady=(0, 10))

    def _right(self, parent):
        w = ttk.Frame(parent, style="P.TFrame"); w.grid(row=0, column=1, sticky="nsew")
        inner = ttk.Frame(w, style="P.TFrame"); inner.pack(fill="both", expand=True, padx=18, pady=18)
        ttk.Label(inner, text=" 安装路径（ComfyUI 根目录）", style="H.TLabel").pack(anchor="w", pady=(0, 8))
        dr = ttk.Frame(inner, style="P.TFrame"); dr.pack(fill="x")
        self.ent_dir = ttk.Entry(dr, textvariable=self.install_dir, font=("Consolas", 10)); self.ent_dir.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(dr, text="浏览...", style="Sm.TButton", command=self._browse, width=8).pack(side="left")
        ttk.Label(inner, text="扩展将安装至 <路径>/custom_nodes/<名称>/", style="Dim.TLabel").pack(anchor="w", pady=(2, 14))
        ttk.Separator(inner, orient="horizontal").pack(fill="x", pady=4)
        ttk.Label(inner, text=" Python 解释器", style="H.TLabel").pack(anchor="w", pady=(12, 8))
        pr = ttk.Frame(inner, style="P.TFrame"); pr.pack(fill="x")
        self.ent_py = ttk.Entry(pr, textvariable=self.python_path, font=("Consolas", 10)); self.ent_py.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(pr, text="检测", style="Sm.TButton", command=self._detect_py, width=7).pack(side="left")
        self.lbl_py = ttk.Label(inner, text="自动检测虚拟环境或系统 Python", style="Dim.TLabel"); self.lbl_py.pack(anchor="w", pady=(2, 14))
        ttk.Separator(inner, orient="horizontal").pack(fill="x", pady=4)
        ttk.Label(inner, text=" 选项", style="H.TLabel").pack(anchor="w", pady=(12, 8))
        for txt, var in [("安装前升级 pip", self._opt_up), ("备份已存在的扩展", self._opt_bk), ("通过 setup.py / pyproject.toml 安装 (pip install -e)", self._opt_ed)]:
            ttk.Checkbutton(inner, text=txt, variable=var).pack(anchor="w", pady=1)
        ttk.Label(inner, text="  提示: 大多数扩展无需此选项，仅在扩展要求时勾选", style="Dim.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Separator(inner, orient="horizontal").pack(fill="x", pady=(14, 4))
        self.btn_go = ttk.Button(inner, text=" 开始安装 ", style="Go.TButton", command=self._start); self.btn_go.pack(fill="x", pady=(14, 6))
        self.btn_retry = ttk.Button(inner, text=" 重试失败的安装 ", style="Retry.TButton", command=self._retry)
        self.btn_open = ttk.Button(inner, text=" 打开安装文件夹 ", style="TButton", command=self._open_dir); self.btn_open.pack(fill="x")

    def _log_panel(self):
        f = ttk.Frame(self.root); f.pack(fill="both", padx=24, pady=(4, 2))
        ttk.Label(f, text=" 安装日志", style="Dim.TLabel").pack(anchor="w", pady=(0, 3))
        box = ttk.Frame(f, style="P.TFrame"); box.pack(fill="both", expand=True)
        self.log = tk.Text(box, height=9, wrap="word", bg=BG2, fg=TEXT, insertbackground=BLUE, selectbackground=SEL_BG, selectforeground=TEXT2, font=("Consolas", 9), borderwidth=0, highlightthickness=0, padx=10, pady=8, state="disabled", cursor="arrow")
        sb = ttk.Scrollbar(box, orient="vertical", command=self.log.yview); self.log.configure(yscrollcommand=sb.set)
        self.log.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        for tag, fg in [("ts", DIM), ("ok", GREEN), ("err", RED), ("warn", YELLOW), ("info", BLUE)]:
            self.log.tag_configure(tag, foreground=fg)
        self.log.tag_configure("bld", foreground=TEXT2, font=("Consolas", 9, "bold"))

    def _bar(self):
        bar = ttk.Frame(self.root, style="P.TFrame"); bar.pack(fill="x", padx=24, pady=(2, 18))
        self.prog = ttk.Progressbar(bar, mode="determinate", style="Bar.Horizontal.TProgressbar"); self.prog.pack(fill="x", padx=10, pady=(8, 4))
        self.lbl_st = ttk.Label(bar, text="就绪", style="ST.TLabel"); self.lbl_st.pack(padx=10, pady=(0, 6))

    def _on_drop(self, event):
        files = self.root.tk.splitlist(event.data)
        zips = [f for f in files if f.lower().endswith(".zip")]
        a = self._add_paths(zips)
        if a > 0:
            self._alog("拖放添加了 {} 个 ZIP".format(a), "info")

    def _add_paths(self, paths):
        if self.installing: return 0
        ex = {it["path"] for it in self.zip_items}; added = 0
        for fp in paths:
            if not isinstance(fp, str) or not os.path.isfile(fp) or not fp.lower().endswith(".zip"): continue
            if fp not in ex:
                ex.add(fp); var = tk.BooleanVar(value=True); sz = os.path.getsize(fp)
                item = dict(path=fp, name=os.path.basename(fp), size=sz, var=var, iid=None)
                item["iid"] = self.tree.insert("", "end", values=("[+]", item["name"], fmt_size(sz)))
                self.zip_items.append(item); added += 1
        self._rcnt(); return added

    def _sbs(self, st):
        for b in (self.btn_add, self.btn_all, self.btn_none, self.btn_scan, self.btn_rm): b.configure(state=st)

    def _log_err(self, out, lf):
        for ln in (out or "").splitlines():
            s = ln.strip()
            if not s: continue
            lo = s.lower()
            if any(k in lo for k in ("error", "failed", "could not", "exception")): lf("    > " + s, "err")
            elif "warning" in lo: lf("    > " + s, "warn")

    def _retry(self):
        if self.installing: return
        fl = list(self.failed_reqs)
        if not fl: messagebox.showinfo("提示", "没有需要重试的失败安装。"); return
        py = self.python_path.get().strip()
        if not py: messagebox.showwarning("警告", "请先检测 Python!"); return
        self.btn_retry.pack_forget(); self.installing = True
        self.btn_go.configure(state="disabled", text=" 重试中... "); self._sbs("disabled"); self.prog["value"] = 0
        threading.Thread(target=self._w_retry, args=(fl, py), daemon=True).start(); self._poll()

    def _w_retry(self, fl, py):
        q = self.lq; total = len(fl); ok_l = []; sf = []
        def L(m, t="info"): q.put((m, t))
        def S(m): q.put(("__S__" + m, ""))
        def P(v): q.put(("__P__" + str(v), ""))
        L("", ""); L("=" * 55, "info")
        L("开始重试 {} 个失败的安装项".format(total), "bld"); L("Python: " + py, "info"); L("-" * 55, "info")
        for idx, it in enumerate(fl):
            k = it.get("type", "req"); nm = it["name"]
            if k == "req":
                rq, rl = it["req_path"], it["rel"]
                S("[{}/{}] {}".format(idx + 1, total, rl)); P(idx * 100 // total); L("", "")
                L("[{}/{}] 依赖重试: {} ({})".format(idx + 1, total, rl, nm), "bld")
                o2, out = pip_install(py, ["-r", rq, "--no-warn-script-location"])
                if o2: L("  [成功] " + rl, "ok"); ok_l.append(rl)
                else: L("  [失败] " + rl, "err"); self._log_err(out, L); sf.append(it)
            elif k == "edit":
                tgt, sfn = it["target"], it.get("sf_name", "pip install -e")
                S("[{}/{}] {}".format(idx + 1, total, nm)); P(idx * 100 // total); L("", "")
                L("[{}/{}] 编译安装重试: {} ({})".format(idx + 1, total, sfn, nm), "bld")
                o2, out = pip_install(py, ["-e", tgt, "--no-warn-script-location"])
                if o2: L("  [成功] {} - {}".format(sfn, nm), "ok"); ok_l.append(nm)
                else: L("  [失败] {} - {}".format(sfn, nm), "err"); self._log_err(out, L); sf.append(it)
            P((idx + 1) * 100 // total)
        L("", ""); L("=" * 55, "info")
        sm = "重试完成! 成功: {} | 仍失败: {} | 总计: {}".format(len(ok_l), len(sf), total)
        S(sm); L(sm, "bld")
        if sf:
            L("仍然失败:", "err")
            for it2 in sf:
                k2 = it2.get("type", "req")
                if k2 == "req": L("  x {} ({})".format(it2["rel"], it2["name"]), "err")
                else: L("  x {} - {}".format(it2.get("sf_name", "pip install -e"), it2["name"]), "err")
            L("您可以再次点击重试按钮。", "warn")
            q.put(("__UPDATE_FAILED__", sf))
        else:
            L("所有安装均已成功!", "ok"); q.put(("__UPDATE_FAILED__", []))
        q.put(("__DONE_RETRY__", ""))

    def _do_scan(self):
        if self.installing: return
        cwd = os.getcwd(); found = []
        for ext in ("*.zip", "*.ZIP"): found.extend(globmod.glob(os.path.join(cwd, ext)))
        found.sort(key=lambda x: x.lower()); a = self._add_paths(found)
        self.lbl_dir.configure(text="扫描目录: " + cwd)
        if a > 0: self._alog("扫描发现 {} 个新 ZIP".format(a), "info")
        else: self._alog("扫描: 未发现新文件", "info")

    def _add_zips(self):
        if self.installing: return
        ps = filedialog.askopenfilenames(title="选择 ZIP", filetypes=[("ZIP", "*.zip *.ZIP"), ("所有", "*.*")])
        if ps:
            a = self._add_paths(list(ps))
            if a > 0: self._alog("添加了 {} 个 ZIP".format(a), "info")

    def _remove_sel(self):
        if self.installing: return
        tr = [it for it in self.zip_items if it["var"].get()]
        if tr:
            for it in tr:
                if it.get("iid"): self.tree.delete(it["iid"])
                self.zip_items.remove(it)
            self._rcnt()

    def _on_click(self, event):
        row = self.tree.identify_row(event.y); col = self.tree.identify_column(event.x)
        if not row or not col: return
        for it in self.zip_items:
            if it["iid"] == row:
                it["var"].set(not it["var"].get()); v = list(self.tree.item(row, "values"))
                v[0] = "[+]" if it["var"].get() else "[ ]"; self.tree.item(row, values=v); break
        self._rcnt()

    def _sel_all(self):
        for it in self.zip_items: it["var"].set(True); self.tree.item(it["iid"], values=("[+]", it["name"], fmt_size(it["size"])))
        self._rcnt()

    def _sel_none(self):
        for it in self.zip_items: it["var"].set(False); self.tree.item(it["iid"], values=("[ ]", it["name"], fmt_size(it["size"])))
        self._rcnt()

    def _rcnt(self):
        n = sum(1 for i in self.zip_items if i["var"].get())
        self.lbl_cnt.configure(text="已选择: {} / {}".format(n, len(self.zip_items)))

    def _browse(self):
        d = filedialog.askdirectory(title="选择 ComfyUI 根目径", initialdir=self.install_dir.get() or os.path.expanduser("~"))
        if d: self.install_dir.set(d); self._detect_py()

    def _detect_py(self):
        root = self.install_dir.get().strip(); py, ver = detect_python(root)
        if py: self.python_path.set(py); self.lbl_py.configure(text=ver or py, foreground=GREEN)
        else: self.lbl_py.configure(text="未找到 Python!", foreground=RED)

    def _start(self):
        if self.installing: return
        sel = [i for i in self.zip_items if i["var"].get()]
        if not sel: messagebox.showwarning("警告", "请至少选择一个扩展!"); return
        d = self.install_dir.get().strip()
        if not d: messagebox.showwarning("警告", "请设置安装路径!"); return
        py = self.python_path.get().strip()
        if not py: messagebox.showwarning("警告", "请先检测 Python!"); return
        self.installing = True; self.failed_reqs = []; self.btn_retry.pack_forget()
        self.btn_go.configure(state="disabled", text=" 安装中... "); self._sbs("disabled"); self.prog["value"] = 0
        self.log.configure(state="normal"); self.log.delete("1.0", "end"); self.log.configure(state="disabled")
        threading.Thread(target=self._worker, args=(sel, d, py), daemon=True).start(); self._poll()

    def _worker(self, selected, install_dir, python):
        q = self.lq; total = len(selected); ok_list = []; fail_list = []
        cn = os.path.join(install_dir, "custom_nodes"); os.makedirs(cn, exist_ok=True)
        def L(m, t="info"): q.put((m, t))
        def S(m): q.put(("__S__" + m, ""))
        def P(v): q.put(("__P__" + str(v), ""))
        L("目标: " + cn, "info"); L("Python: " + python, "info"); L("共 {} 个扩展".format(total), "bld"); L("-" * 55, "info")
        if self._opt_up.get():
            S("升级 pip..."); L("升级 pip...", "info")
            o, _ = pip_install(python, ["--upgrade", "pip", "-q"])
            L("pip 已升级" if o else "pip 升级失败", "ok" if o else "warn")
        for idx, item in enumerate(selected):
            zp, zn = item["path"], item["name"]; dn = dir_name_from_zip(zn); tgt = os.path.join(cn, dn)
            S("[{}/{}] {}".format(idx + 1, total, zn)); P(idx * 100 // total); L("", ""); L("[{}/{}] {}".format(idx + 1, total, zn), "bld")
            if os.path.exists(tgt):
                if self._opt_bk.get():
                    bak = tgt + "_bak_" + datetime.now().strftime("%Y%m%d_%H%M%S")
                    L(" 备份 -> " + os.path.basename(bak), "info")
                    try: shutil.move(tgt, bak)
                    except Exception as e: L(" 备份失败: " + str(e), "warn")
                else: L(" 删除旧版", "info"); shutil.rmtree(tgt, ignore_errors=True)
            L(" 解压...", "info")
            if not extract_zip(zp, tgt): fail_list.append(zn); L(" 解压失败", "err"); continue
            L(" 解压完成 -> " + dn, "ok")
            reqs = find_req(tgt)
            if reqs:
                L(" 发现 {} 个 requirements".format(len(reqs)), "info"); rok = 0; rfl = 0
                for ri, rq in enumerate(reqs):
                    rl = os.path.relpath(rq, tgt)
                    L("  [依赖 {}/{}] {}".format(ri + 1, len(reqs), rl), "info")
                    o2, out = pip_install(python, ["-r", rq, "--no-warn-script-location"])
                    if o2: L("  [成功] " + rl, "ok"); rok += 1
                    else: L("  [失败] " + rl, "err"); rfl += 1; self._log_err(out, L); self.failed_reqs.append({"type": "req", "req_path": rq, "rel": rl, "target": tgt, "name": dn})
                L("  --- 成功 {}/失败 {} ---".format(rok, rfl), "ok" if rfl == 0 else "warn")
            else: L(" 未找到 requirements.txt", "info")
            if self._opt_ed.get():
                for sf_name in ("setup.py", "pyproject.toml"):
                    sf = os.path.join(tgt, sf_name)
                    if os.path.isfile(sf):
                        L("  pip install -e (" + sf_name + ")", "info")
                        o3, out = pip_install(python, ["-e", tgt, "--no-warn-script-location"])
                        if o3: L("  [成功] " + sf_name, "ok"); ok_list.append(zn)
                        else: L("  [失败] " + sf_name, "err"); self._log_err(out, L); self.failed_reqs.append({"type": "edit", "target": tgt, "sf_name": sf_name, "name": dn})
            P((idx + 1) * 100 // total)
        L("", ""); L("=" * 55, "info"); frc = len(self.failed_reqs)
        parts = ["成功: {}".format(len(ok_list)), "失败: {}".format(len(fail_list)), "总计: {}".format(total)]
        if frc > 0: parts.append("失败安装: {}".format(frc))
        sm = "完成! " + " | ".join(parts); S(sm); L(sm, "bld")
        if fail_list:
            L("解压失败:", "err")
            for fn in fail_list: L("  x " + fn, "err")
        if self.failed_reqs:
            L("", ""); L("失败详情 (可重试):", "warn")
            for i, fr in enumerate(self.failed_reqs, 1):
                k = fr.get("type", "req")
                if k == "req": L("  {}. {} ({})".format(i, fr["rel"], fr["name"]), "warn")
                else: L("  {}. {} - {}".format(i, fr.get("sf_name", "pip install -e"), fr["name"]), "warn")
            q.put(("__HAS_FAILED__", ""))
        L("请重启 ComfyUI。", "warn"); q.put(("__DONE__", ""))

    def _poll(self):
        try:
            while True:
                msg, tag = self.lq.get_nowait()
                if msg.startswith("__DONE__"): self._done(len(self.failed_reqs) > 0); return
                if msg.startswith("__DONE_RETRY__"): self._done_r(); return
                if msg.startswith("__HAS_FAILED__") or msg.startswith("__UPDATE_FAILED__"):
                    if msg.startswith("__UPDATE_FAILED__"): self.failed_reqs = tag if isinstance(tag, list) else []
                    continue
                if msg.startswith("__S__"): self.lbl_st.configure(text=msg[5:]); continue
                if msg.startswith("__P__"): self.prog["value"] = float(msg[5:]); continue
                ts = datetime.now().strftime("%H:%M:%S")
                self.log.configure(state="normal"); self.log.insert("end", "[{}] ".format(ts), "ts"); self.log.insert("end", msg + NL, tag); self.log.see("end"); self.log.configure(state="disabled")
        except queue.Empty: pass
        if self.installing: self._aid = self.root.after(80, self._poll)

    def _done(self, has_f=False):
        self.installing = False; self.btn_go.configure(state="normal", text=" 开始安装 "); self._sbs("normal")
        if has_f:
            self.btn_retry.pack(fill="x", pady=(6, 0), before=self.btn_open)
            messagebox.showwarning("部分失败", "安装完成但部分失败。可点击重试按钮。请重启 ComfyUI。")
        else:
            self.btn_retry.pack_forget(); messagebox.showinfo("完成", "所有扩展已安装完成!请重启 ComfyUI。")

    def _done_r(self):
        self.installing = False; self.btn_go.configure(state="normal", text=" 开始安装 "); self._sbs("normal")
        if self.failed_reqs:
            self.btn_retry.pack(fill="x", pady=(6, 0), before=self.btn_open)
            messagebox.showwarning("部分失败", "重试后仍然失败。请检查网络/Python环境。")
        else:
            self.btn_retry.pack_forget(); messagebox.showinfo("完成", "所有安装已成功!")

    def _alog(self, msg, tag):
        ts = datetime.now().strftime("%H:%M:%S"); self.log.configure(state="normal"); self.log.insert("end", "[{}] ".format(ts), "ts"); self.log.insert("end", msg + NL, tag); self.log.see("end"); self.log.configure(state="disabled")

    def _open_dir(self):
        d = self.install_dir.get().strip()
        if not d or not os.path.isdir(d): messagebox.showinfo("提示", "请先设置安装路径。"); return
        p = os.path.join(d, "custom_nodes"); os.makedirs(p, exist_ok=True)
        if IS_WIN: os.startfile(p)
        else: subprocess.Popen(["xdg-open", p])

    def _on_close(self):
        if self.installing:
            if not messagebox.askyesno("退出", "安装中，确定退出?"): return
            self.installing = False
            if self._aid: self.root.after_cancel(self._aid)
        self.root.destroy()

    def run(self): self.root.mainloop()

if __name__ == "__main__":
    try: App().run()
    except Exception as e:
        try:
            r = tk.Tk(); r.withdraw()
            messagebox.showerror("错误", str(e) + NL + NL + "Python " + sys.version)
        except: print(str(e)); input()
        sys.exit(1)
