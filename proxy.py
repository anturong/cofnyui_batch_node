# -*- coding: utf-8 -*-
"""网络模块：代理检测 / GitHub依赖直接下载zip安装 / pip国内镜像"""
import subprocess, os, socket, re, tempfile, shutil
import urllib.request, urllib.error, zipfile

# ---- 常量 ----
PROXY_PORTS = [7890, 7891, 7897, 1080, 10808, 10809]
PIP_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"
PIP_HOST = "pypi.tuna.tsinghua.edu.cn"

# 镜像列表: type="replace" 直接替换域名, type="prefix" 在前面加镜像前缀
GITHUB_MIRRORS = [
    {"url": "https://ghfast.top", "type": "replace"},
    {"url": "https://gh-proxy.com", "type": "prefix"},
    {"url": "https://mirror.ghproxy.com", "type": "prefix"},
    {"url": "https://ghproxy.cc", "type": "prefix"},
    {"url": "https://ghps.cc", "type": "prefix"},
    {"url": "https://github.moeyy.xyz", "type": "replace"},
    {"url": "https://gh-proxy.org", "type": "prefix"},
]

# ---- 状态 ----
_net_mode = None
_use_mirror = True
_saved_env = None
_saved_git = None
_log_fn = None
_temp_dirs = []


def set_log(fn):
    global _log_fn; _log_fn = fn


def _log(msg):
    if _log_fn:
        try:
            _log_fn(msg)
        except Exception:
            pass


# ==================== 环境变量 保存/恢复 ====================
def _save_env():
    saved = {}
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
        if k in os.environ:
            saved[k] = os.environ.pop(k)
    return saved


def _restore_env(saved):
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
        os.environ.pop(k, None)
    for k, v in saved.items():
        os.environ[k] = v


# ==================== Git 配置 保存/恢复 ====================
def _save_git():
    saved = {}
    for key in ("http.proxy", "https.proxy"):
        try:
            r = subprocess.run(["git", "config", "--global", "--get", key],
                               capture_output=True, text=True, timeout=5)
            v = r.stdout.strip()
            if v:
                saved[key] = v
                subprocess.run(["git", "config", "--global", "--unset", key],
                               capture_output=True, timeout=5)
        except Exception:
            pass
    try:
        r = subprocess.run(["git", "config", "--global", "--get-regexp", "url"],
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.strip().splitlines():
            if "insteadof" in line.lower():
                parts = line.split(None, 1)
                if len(parts) == 2:
                    saved[parts[0]] = parts[1]
                    subprocess.run(["git", "config", "--global", "--unset", parts[0]],
                                   capture_output=True, timeout=5)
    except Exception:
        pass
    return saved


def _restore_git(saved):
    try:
        r = subprocess.run(["git", "config", "--global", "--get-regexp", "url"],
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.strip().splitlines():
            if "insteadof" in line.lower():
                key = line.split(None, 1)[0]
                subprocess.run(["git", "config", "--global", "--unset", key],
                               capture_output=True, timeout=5)
    except Exception:
        pass
    for key in ("http.proxy", "https.proxy"):
        subprocess.run(["git", "config", "--global", "--unset", key],
                       capture_output=True, timeout=5)
    for k, v in saved.items():
        subprocess.run(["git", "config", "--global", k, v],
                       capture_output=True, timeout=5)


# ==================== 代理检测 ====================
def detect_proxy():
    for port in PROXY_PORTS:
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=2)
            s.close()
            return "127.0.0.1:{}".format(port)
        except Exception:
            continue
    return None


# ==================== GitHub 依赖下载 (zip方式，绕过git clone) ====================
def _parse_github_url(line):
    m = re.match(
        r"^git\+https://github\.com/([^/]+)/([^/@#!]+?)(?:\.git)?"
        r"(?:@([^#\s]+))?(?:\s*#.*)?\s*$", line.strip())
    if m:
        return {
            "user": m.group(1), "repo": m.group(2),
            "branch": m.group(3) or "main",
            "original": line.strip(),
        }
    return None


def _make_zip_url(user, repo, branch, mirror):
    if mirror["type"] == "replace":
        return "{}/{}/{}/archive/refs/heads/{}.zip".format(mirror["url"], user, repo, branch)
    else:
        return "{}/https://github.com/{}/{}/archive/refs/heads/{}.zip".format(
            mirror["url"], user, repo, branch)


def _find_pkg_root(tmp_dir):
    for f in ("setup.py", "pyproject.toml", "setup.cfg"):
        if os.path.isfile(os.path.join(tmp_dir, f)):
            return tmp_dir
    entries = [e for e in os.listdir(tmp_dir) if not e.startswith(".")]
    if len(entries) == 1:
        sub = os.path.join(tmp_dir, entries[0])
        if os.path.isdir(sub):
            for f in ("setup.py", "pyproject.toml", "setup.cfg"):
                if os.path.isfile(os.path.join(sub, f)):
                    return sub
    for entry in entries:
        sub = os.path.join(tmp_dir, entry)
        if os.path.isdir(sub):
            for f in ("setup.py", "pyproject.toml", "setup.cfg"):
                if os.path.isfile(os.path.join(sub, f)):
                    return sub
    return tmp_dir


def _download_github_dep(user, repo, branch):
    global _temp_dirs
    for mirror in GITHUB_MIRRORS:
        dl_url = _make_zip_url(user, repo, branch, mirror)
        _log(" 下载: {} ...".format(dl_url))
        tmp_zip = None
        try:
            tmp_zip = tempfile.mktemp(suffix=".zip")
            req = urllib.request.Request(dl_url)
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status != 200:
                    _log(" HTTP {}".format(resp.status))
                    continue
                with open(tmp_zip, "wb") as f:
                    shutil.copyfileobj(resp, f)
            tmp_dir = tempfile.mkdtemp(prefix="gh_dep_")
            _temp_dirs.append(tmp_dir)
            with zipfile.ZipFile(tmp_zip, "r") as zf:
                zf.extractall(tmp_dir)
            root = _find_pkg_root(tmp_dir)
            _log(" 成功! (镜像: {}) -> {}".format(mirror["url"], os.path.basename(root)))
            return root
        except urllib.error.HTTPError as e:
            _log(" HTTP {} : {}".format(e.code, dl_url))
        except Exception as e:
            _log(" 失败: {}".format(e))
        finally:
            if tmp_zip:
                try:
                    os.remove(tmp_zip)
                except Exception:
                    pass
    return None


def _process_requirements(req_file):
    try:
        with open(req_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        _log("读取 requirements 失败: {}".format(e))
        return req_file, False

    changed = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("git+https://github.com/"):
            info = _parse_github_url(stripped)
            if info:
                _log("发现 GitHub 依赖: {}/{} (分支: {})".format(
                    info["user"], info["repo"], info["branch"]))
                found = None
                for br in (info["branch"], "main", "master"):
                    _log(" 尝试分支: {}".format(br))
                    found = _download_github_dep(info["user"], info["repo"], br)
                    if found:
                        break
                if found:
                    new_lines.append(found + "\n")
                    changed = True
                else:
                    _log(" 所有镜像均失败，保留原始地址")
                    new_lines.append(line)
                continue
        new_lines.append(line)

    if not changed:
        return req_file, False

    tmp_req = req_file + ".mirror_tmp"
    try:
        with open(tmp_req, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        return tmp_req, True
    except Exception as e:
        _log("写入临时文件失败: {}".format(e))
        return req_file, False


# ==================== 主接口 ====================
def setup_network(use_mirror=True):
    global _net_mode, _saved_env, _saved_git, _use_mirror
    _use_mirror = use_mirror
    _saved_env = _save_env()
    _saved_git = _save_git()

    if not use_mirror:
        _net_mode = "direct"
        return "direct", "直连模式，不使用镜像或代理"

    proxy = detect_proxy()
    if proxy:
        _net_mode = "proxy"
        try:
            subprocess.run(["git", "config", "--global", "http.proxy", proxy],
                           capture_output=True, timeout=5)
            subprocess.run(["git", "config", "--global", "https.proxy", proxy],
                           capture_output=True, timeout=5)
        except Exception:
            pass
        for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
            os.environ[k] = proxy
        return "proxy", "检测到代理: {} ，已启用".format(proxy)

    _net_mode = "mirror"
    return "mirror", "无代理，国内镜像模式 (pip:清华源, GitHub:zip下载安装)"


def restore_network():
    global _net_mode, _saved_env, _saved_git, _temp_dirs, _use_mirror
    for d in _temp_dirs:
        try:
            shutil.rmtree(d, ignore_errors=True)
        except Exception:
            pass
    _temp_dirs = []
    if _saved_env is not None:
        _restore_env(_saved_env); _saved_env = None
    if _saved_git is not None:
        _restore_git(_saved_git); _saved_git = None
    _net_mode = None
    _use_mirror = True


def pip_install(py, args):
    global _net_mode, _use_mirror
    new_args = list(args)
    temp_req = None

    # 镜像模式: 预下载 GitHub 依赖为 zip（仅镜像模式且无代理时）
    if _use_mirror and _net_mode == "mirror":
        for i, arg in enumerate(new_args):
            if arg == "-r" and i + 1 < len(new_args):
                req_file = new_args[i + 1]
                if os.path.isfile(req_file):
                    temp_req, modified = _process_requirements(req_file)
                    if modified:
                        new_args[i + 1] = temp_req

    # pip 镜像（仅在启用镜像时添加）
    if _use_mirror:
        new_args.extend(["-i", PIP_INDEX, "--trusted-host", PIP_HOST])

    cmd = [py, "-m", "pip", "install"] + new_args

    def _cleanup():
        if temp_req and temp_req.endswith(".mirror_tmp") and os.path.exists(temp_req):
            try:
                os.remove(temp_req)
            except Exception:
                pass

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        output = r.stdout + r.stderr
        _cleanup()
        return (r.returncode == 0, output)
    except subprocess.TimeoutExpired:
        _cleanup()
        return False, "timeout (安装超时，请检查网络)"
    except Exception as e:
        _cleanup()
        return False, str(e)
