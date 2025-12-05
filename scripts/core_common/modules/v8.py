#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
sys.path.append('../..')
import config
import base
import os
import subprocess
import v8_89
import platform


def clean():
  """
  清理 v8 相关目录：depot_tools、v8 源码和 gclient 缓存。
  """
  if base.is_dir("depot_tools"):
    base.delete_dir_with_access_error("depot_tools")
    base.delete_dir("depot_tools")
  if base.is_dir("v8"):
    base.delete_dir_with_access_error("v8")
    base.delete_dir("v8")
  if base.is_exist("./.gclient"):
    base.delete_file("./.gclient")
  if base.is_exist("./.gclient_entries"):
    base.delete_file("./.gclient_entries")
  if base.is_exist("./.cipd"):
    base.delete_dir("./.cipd")
  return


def is_main_platform():
  """
  判断当前 configure 的 platform 是否需要走 v8 主流程。
  """
  if (config.check_option("platform", "win_64") or
      config.check_option("platform", "win_32")):
    return True

  if config.check_option("platform", "win_arm64"):
    return True

  if (config.check_option("platform", "linux_64") or
      config.check_option("platform", "linux_32") or
      config.check_option("platform", "linux_arm64")):
    return True

  if config.check_option("platform", "mac_64"):
    return True

  return False


def is_use_clang():
  gcc_version = base.get_gcc_version()
  is_clang = "false"
  if config.option("sysroot") == "" and (
      gcc_version >= 6000 or "1" == config.option("use-clang")):
    is_clang = "true"

  print("gcc version: " + str(gcc_version) + ", use clang:" + is_clang)
  return is_clang


def make_xp():
  print("make_xp() is not implemented in this simplified v8.py")
  return


def _find_v8_root(v8_parent):
  """
  在 v8_parent（例如 /home/core/Common/3dParty/v8）下找第一个包含 .gn 的目录。
  优先检查：
    v8_xp/v8, v8_xp/v8/v8, v8, v8/v8
  """
  candidates = []

  xp_dir = os.path.join(v8_parent, "v8_xp")
  if os.path.isdir(xp_dir):
    candidates.append(os.path.join(xp_dir, "v8"))
    candidates.append(os.path.join(xp_dir, "v8", "v8"))

  v8_dir = os.path.join(v8_parent, "v8")
  if os.path.isdir(v8_dir):
    candidates.append(v8_dir)
    candidates.append(os.path.join(v8_dir, "v8"))

  # 兜底：从顶层往下扫一层
  candidates.append(v8_parent)

  for c in candidates:
    if c and os.path.isfile(os.path.join(c, ".gn")):
      return c

  return None


def make():
  if not is_main_platform():
    make_xp()
    return

  old_env = dict(os.environ)
  old_cur = os.getcwd()

  # === 关键：以 core/Common/3dParty/v8 为根，而不是死写 v8_xp ===
  script_dir = base.get_script_dir()  # 比如 /home/build_tools_arm64/scripts
  v8_parent = os.path.abspath(os.path.join(
      script_dir, "../../core/Common/3dParty/v8"))

  # 这个目录下应该有 v8_xp/ 或 v8/
  if not os.path.isdir(v8_parent):
    print("ERROR: v8 parent dir not found:", v8_parent)
    os.chdir(old_cur)
    os.environ.clear()
    os.environ.update(old_env)
    return

  os.chdir(v8_parent)

  # Windows 环境
  if base.host_platform() == "windows":
    base.set_env("DEPOT_TOOLS_WIN_TOOLCHAIN", "0")
    base.set_env("GYP_MSVS_VERSION", "2015")

  # 检查版本号，必要时 clean（针对当前 v8_parent）
  base.common_check_version("v8", "1", clean)

  # ---------------------------------------------------------------------------
  # 准备 depot_tools（放在 v8_parent/depot_tools）
  # ---------------------------------------------------------------------------
  depot_dir = os.path.join(v8_parent, "depot_tools")
  if not base.is_dir(depot_dir):
    base.cmd("git", [
      "clone",
      "https://chromium.googlesource.com/chromium/tools/depot_tools.git",
      "depot_tools"
    ])
    v8_89.change_bootstrap()

    if base.host_platform() == "windows":
      ps1 = os.path.join(depot_dir, "cipd.ps1")
      if base.is_file(ps1):
        base.replaceInFile(ps1, "windows-386", "windows-amd64")

  path_to_python2 = "/depot_tools/bootstrap-2@3_11_8_chromium_35_bin/python/bin"
  os.environ["PATH"] = os.pathsep.join([
    depot_dir,
    v8_parent + path_to_python2,
    config.option("vs-path") + "/../Common7/IDE",
    os.environ.get("PATH", "")
  ])

  # GN 封装：优先用 python3 执行 depot_tools/gn.py
  gn_py = os.path.join(depot_dir, "gn.py")

  def run_gn(args_list):
    if os.path.isfile(gn_py):
      print("using python3 gn.py:", gn_py)
      base.cmd2("python3", [gn_py] + args_list)
    else:
      print("gn.py not found, fallback to 'gn' in PATH")
      base.cmd2("gn", args_list)

  # ---------------------------------------------------------------------------
  # fetch v8 源码（放在 v8_parent/v8）
  # ---------------------------------------------------------------------------
  v8_dir = os.path.join(v8_parent, "v8")
  if not base.is_dir(v8_dir):
    base.cmd(os.path.join(depot_dir, "fetch"), ["v8"], True)
    base.cmd(os.path.join(depot_dir, "gclient"),
             ["sync", "-r", "4.10.253"], True)
    base.delete_dir_with_access_error(os.path.join(v8_dir, "buildtools", "win"))
    base.cmd("git", ["config", "--system", "core.longpaths", "true"], True)
    base.cmd("gclient", ["sync", "--force"], True)

  # ---------------------------------------------------------------------------
  # 找到真正的 V8 源码根目录（包含 .gn 的目录）
  # ---------------------------------------------------------------------------
  v8_root = _find_v8_root(v8_parent)
  if v8_root is None:
    print("ERROR: cannot find .gn under", v8_parent)
    os.chdir(old_cur)
    os.environ.clear()
    os.environ.update(old_env)
    return

  print("V8 root dir:", v8_root)
  os.chdir(v8_root)

  # ---------------------------------------------------------------------------
  # 不同架构的 GN 参数
  # ---------------------------------------------------------------------------
  base_args64 = (
    'target_cpu="x64" '
    'v8_target_cpu="x64" '
    'v8_static_library=true '
    'is_component_build=false '
    'v8_use_snapshot=false'
  )

  base_args32 = (
    'target_cpu="x86" '
    'v8_target_cpu="x86" '
    'v8_static_library=true '
    'is_component_build=false '
    'v8_use_snapshot=false'
  )

  base_args_arm64 = (
    'target_cpu="arm64" '
    'v8_target_cpu="arm64" '
    'v8_static_library=true '
    'is_component_build=false '
    'v8_use_snapshot=false'
  )

  host_arch = platform.machine().lower()
  print("host arch:", host_arch)

  # ---------------------------------------------------------------------------
  # Linux 平台
  # ---------------------------------------------------------------------------
  if config.check_option("platform", "linux_64"):
    if host_arch in ("aarch64", "arm64"):
      print("Detected ARM64 host, building V8 as arm64 (out.gn/linux_arm64)")
      gn_args = (
        "is_debug=false "
        + base_args_arm64
        + " is_clang=" + is_use_clang()
        + " use_sysroot=false treat_warnings_as_errors=false"
      )
      run_gn(["gen", "out.gn/linux_arm64", "--args='" + gn_args + "'"])
      base.cmd("ninja", ["-C", "out.gn/linux_arm64"])
    else:
      print("Detected x86_64 host, building V8 as x64 (out.gn/linux_64)")
      gn_args = (
        "is_debug=false "
        + base_args64
        + " is_clang=" + is_use_clang()
        + " use_sysroot=false treat_warnings_as_errors=false"
      )
      run_gn(["gen", "out.gn/linux_64", "--args='" + gn_args + "'"])
      base.cmd("ninja", ["-C", "out.gn/linux_64"])

  if config.check_option("platform", "linux_32"):
    gn_args = (
      "is_debug=false "
      + base_args32
      + " is_clang=" + is_use_clang()
      + " use_sysroot=false treat_warnings_as_errors=false"
    )
    run_gn(["gen", "out.gn/linux_32", "--args='" + gn_args + "'"])
    base.cmd("ninja", ["-C", "out.gn/linux_32"])

  if config.check_option("platform", "linux_arm64"):
    gn_args = (
      "is_debug=false "
      + base_args_arm64
      + " is_clang=" + is_use_clang()
      + " use_sysroot=false treat_warnings_as_errors=false"
    )
    run_gn(["gen", "out.gn/linux_arm64", "--args='" + gn_args + "'"])
    base.cmd("ninja", ["-C", "out.gn/linux_arm64"])

  # ---------------------------------------------------------------------------
  # macOS / Windows（基本保持原逻辑，顺手也改成 run_gn）
  # ---------------------------------------------------------------------------
  if config.check_option("platform", "mac_64"):
    gn_args = "is_debug=false " + base_args64
    run_gn(["gen", "out.gn/mac_64", "--args='" + gn_args + "'"])
    base.cmd("ninja", ["-C", "out.gn/mac_64"])

  if config.check_option("platform", "win_64"):
    if -1 != config.option("config").lower().find("debug"):
      gn_args = "is_debug=true " + base_args64 + " is_clang=false"
      run_gn(["gen", "out.gn/win_64/debug", "--args='" + gn_args + "'"])
      base.cmd("ninja", ["-C", "out.gn/win_64/debug"])

    gn_args = "is_debug=false " + base_args64 + " is_clang=false"
    run_gn(["gen", "out.gn/win_64/release", "--args='" + gn_args + "'"])
    base.cmd("ninja", ["-C", "out.gn/win_64/release"])

  if config.check_option("platform", "win_32"):
    if -1 != config.option("config").lower().find("debug"):
      gn_args = "is_debug=true " + base_args32 + " is_clang=false"
      run_gn(["gen", "out.gn/win_32/debug", "--args='" + gn_args + "'"])
      base.cmd("ninja", ["-C", "out.gn/win_32/debug"])

    gn_args = "is_debug=false " + base_args32 + " is_clang=false"
    run_gn(["gen", "out.gn/win_32/release", "--args='" + gn_args + "'"])
    base.cmd("ninja", ["-C", "out.gn/win_32/release"])

  # 恢复环境
  os.chdir(old_cur)
  os.environ.clear()
  os.environ.update(old_env)
  return
