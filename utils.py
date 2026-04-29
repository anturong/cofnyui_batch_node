# -*- coding: utf-8 -*-
import os, shutil, subprocess, sys, zipfile

def extract_zip(zp, dest):
    try:
        with zipfile.ZipFile(zp, "r") as zf:
            ns = zf.namelist(); top = set()
            for n in ns:
                p = n.split("/")[0].split("\\")[0]
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
                p = os.path.join(sroot, v,
                                 "python.exe" if sys.platform == "win32" else "bin/python")
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
