# -*- coding: utf-8 -*-
import os, shutil
from datetime import datetime
from proxy import pip_install, setup_network, restore_network, set_log
from utils import extract_zip, dir_name_from_zip, find_req


def run_install(selected, install_dir, python, opt_up, opt_mirror, opt_ed, log_fn):
    q = log_fn
    total = len(selected)
    ok_list = []; fail_list = []
    cn = os.path.join(install_dir, "custom_nodes")
    os.makedirs(cn, exist_ok=True)

    def L(m, t="info"): q((m, t))
    def S(m): q(("__S__" + m, ""))
    def P(v): q(("__P__" + str(v), ""))

    def dump_err(out):
        L(" === pip 输出 ===", "err")
        for _line in (out or "").splitlines():
            if _line.strip():
                L(" " + _line.strip(), "err")
        L(" === 结束 ===", "err")

    # ---- 网络配置 ----
    set_log(lambda m: L(m, "info"))
    mode, net_info = setup_network(use_mirror=opt_mirror)
    L(net_info, "bld")
    if opt_mirror:
        L("pip 镜像: 清华大学源", "info")
    else:
        L("直连模式: 不使用镜像，使用原始 requirements.txt", "info")
    L("-" * 55, "info")
    L("目标: " + cn, "info")
    L("Python: " + python, "info")
    L("共 {} 个扩展".format(total), "bld")

    if opt_up:
        S("升级 pip..."); L("升级 pip...", "info")
        o, out = pip_install(python, ["--upgrade", "pip"])
        if o:
            L("pip 已升级", "ok")
        else:
            L("pip 升级失败 (不影响安装)", "warn")

    failed_reqs = []

    for idx, item in enumerate(selected):
        zp, zn = item["path"], item["name"]
        dn = dir_name_from_zip(zn); tgt = os.path.join(cn, dn)
        S("[{}/{}] {}".format(idx + 1, total, zn))
        P(idx * 100 // total); L("", "")
        L("[{}/{}] {}".format(idx + 1, total, zn), "bld")

        if os.path.exists(tgt):
            L(" 删除旧版", "info")
            shutil.rmtree(tgt, ignore_errors=True)

        L(" 解压...", "info")
        if not extract_zip(zp, tgt):
            fail_list.append(zn); L(" 解压失败", "err"); continue
        L(" 解压完成 -> " + dn, "ok")

        reqs = find_req(tgt)
        if reqs:
            L(" 发现 {} 个 requirements".format(len(reqs)), "info")
            rok = 0; rfl = 0
            for ri, rq in enumerate(reqs):
                rl = os.path.relpath(rq, tgt)
                L(" [依赖 {}/{}] {}".format(ri + 1, len(reqs), rl), "info")
                o2, out = pip_install(python, ["-r", rq, "--no-warn-script-location"])
                if o2:
                    L(" [成功] " + rl, "ok"); rok += 1
                else:
                    L(" [失败] " + rl, "err"); rfl += 1
                    dump_err(out)
                    failed_reqs.append({
                        "type": "req", "req_path": rq, "rel": rl,
                        "target": tgt, "name": dn
                    })
            L(" --- 成功 {}/失败 {} ---".format(rok, rfl), "ok" if rfl == 0 else "warn")
        else:
            L(" 未找到 requirements.txt", "info")

        if opt_ed:
            for sf_name in ("setup.py", "pyproject.toml"):
                sf = os.path.join(tgt, sf_name)
                if os.path.isfile(sf):
                    L(" pip install -e (" + sf_name + ")", "info")
                    o3, out = pip_install(python, ["-e", tgt, "--no-warn-script-location"])
                    if o3:
                        L(" [成功] " + sf_name, "ok"); ok_list.append(zn)
                    else:
                        L(" [失败] " + sf_name, "err"); dump_err(out)
                        failed_reqs.append({
                            "type": "edit", "target": tgt,
                            "sf_name": sf_name, "name": dn
                        })

        P((idx + 1) * 100 // total)

    # ---- 完成 ----
    L("", ""); L("=" * 55, "info")
    frc = len(failed_reqs)
    parts = ["成功: {}".format(len(ok_list)), "失败: {}".format(len(fail_list)), "总计: {}".format(total)]
    if frc > 0:
        parts.append("失败安装: {}".format(frc))
    sm = "完成! " + " | ".join(parts)
    S(sm); L(sm, "bld")
    if fail_list:
        L("解压失败:", "err")
        for fn in fail_list:
            L(" x " + fn, "err")
    if failed_reqs:
        L("", ""); L("失败详情 (可重试):", "warn")
        for i, fr in enumerate(failed_reqs, 1):
            k = fr.get("type", "req")
            if k == "req":
                L(" {}. {} ({})".format(i, fr["rel"], fr["name"]), "warn")
            else:
                L(" {}. {} - {}".format(i, fr.get("sf_name", ""), fr["name"]), "warn")
    L("__HAS_FAILED__", "")
    restore_network()
    L("网络设置已恢复", "info")
    L("请重启 ComfyUI。", "warn")
    L("__DONE__", "")
    return failed_reqs


def run_retry(failed_reqs, python, log_fn):
    q = log_fn
    total = len(failed_reqs); ok_l = []; sf = []

    def L(m, t="info"): q((m, t))
    def S(m): q(("__S__" + m, ""))
    def P(v): q(("__P__" + str(v), ""))

    def dump_err(out):
        L(" === pip 输出 ===", "err")
        for _line in (out or "").splitlines():
            if _line.strip():
                L(" " + _line.strip(), "err")
        L(" === 结束 ===", "err")

    # ---- 网络配置 ----
    set_log(lambda m: L(m, "info"))
    from proxy import _net_mode as cur_mode
    if cur_mode is None:
        mode, net_info = setup_network(use_mirror=True)
        L(net_info, "bld")

    L("-" * 55, "info")
    L("", ""); L("=" * 55, "info")
    L("开始重试 {} 个失败的安装项".format(total), "bld")
    L("Python: " + python, "info")
    L("-" * 55, "info")

    for idx, it in enumerate(failed_reqs):
        k = it.get("type", "req"); nm = it["name"]
        if k == "req":
            rq, rl = it["req_path"], it["rel"]
            S("[{}/{}] {}".format(idx + 1, total, rl))
            P(idx * 100 // total); L("", "")
            L("[{}/{}] 依赖重试: {} ({})".format(idx + 1, total, rl, nm), "bld")
            o2, out = pip_install(python, ["-r", rq, "--no-warn-script-location"])
            if o2:
                L(" [成功] " + rl, "ok"); ok_l.append(rl)
            else:
                L(" [失败] " + rl, "err"); dump_err(out); sf.append(it)
        elif k == "edit":
            tgt, sfn = it["target"], it.get("sf_name", "pip install -e")
            S("[{}/{}] {}".format(idx + 1, total, nm))
            P(idx * 100 // total); L("", "")
            L("[{}/{}] 编译安装重试: {} ({})".format(idx + 1, total, sfn, nm), "bld")
            o2, out = pip_install(python, ["-e", tgt, "--no-warn-script-location"])
            if o2:
                L(" [成功] {} - {}".format(sfn, nm), "ok"); ok_l.append(nm)
            else:
                L(" [失败] {} - {}".format(sfn, nm), "err")
                dump_err(out); sf.append(it)
        P((idx + 1) * 100 // total)

    L("", ""); L("=" * 55, "info")
    sm = "重试完成! 成功: {} | 仍失败: {} | 总计: {}".format(
        len(ok_l), len(sf), total)
    S(sm); L(sm, "bld")
    if sf:
        L("仍然失败:", "err")
        for it2 in sf:
            k2 = it2.get("type", "req")
            if k2 == "req":
                L(" x {} ({})".format(it2["rel"], it2["name"]), "err")
            else:
                L(" x {} - {}".format(it2.get("sf_name", ""), it2["name"]), "err")
        L("您可以再次点击重试按钮。", "warn")
    else:
        L("所有安装均已成功!", "ok")
    L("__UPDATE_FAILED__", sf if sf else [])
    restore_network()
    L("网络设置已恢复", "info")
    L("__DONE_RETRY__", "")
    return sf
