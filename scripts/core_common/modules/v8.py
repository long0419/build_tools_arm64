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
  注意：这里仍然只识别 win/linux/mac，linux_arm64 会被当成 linux_64 使用。
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
  """
  官方脚本逻辑：在不使用 sysroot，且 gcc >= 6 或手动设置 use-clang=1 的时候启用 clang。
  """
  gcc_version = base.get_gcc_version()
  is_clang = "false"
  if config.option("sysroot") == "" and (
      gcc_version >= 6000 or "1" == config.option("use-clang")):
    is_clang = "true"

  print("gcc version: " + str(gcc_version) + ", use clang:" + is_clang)
  return is_clang


def make_xp():
  """
  非主平台时的占位逻辑（XP 之类老平台）。
  目前我们只关心 Linux/ARM64，这里保持空实现即可。
  """
  print("make_xp() is not implemented in this simplified v8.py")
  return


def make():
  # 如果不是主平台，直接走占位逻辑
  if not is_main_platform():
    make_xp()
    return

  # 记录当前环境，方便恢复
  old_env = dict(os.environ)
  old_cur = os.getcwd()

  # ONLYOFFICE 源码中 v8 根目录位置（父目录）
  base_dir = base.get_script_dir() + "/../../core/Common/3dParty/v8/v8_xp"
  if not base.is_dir(base_dir):
    base_dir = base.get_script_dir() + "/../../core/Common/3dParty/v8/v8"

  os.chdir(base_dir)

  # Windows 环境变量
  if base.host_platform() == "windows":
    base.set_env("DEPOT_TOOLS_WIN_TOOLCHAIN", "0")
    base.set_env("GYP_MSVS_VERSION", "2015")

  # 检查版本号，必要时执行 clean()
  base.common_check_version("v8", "1", clean)

  # ---------------------------------------------------------------------------
  # 准备 depot_tools
  # ---------------------------------------------------------------------------
  if not base.is_dir("depot_tools"):
    base.cmd("git", [
      "clone",
      "https://chromium.googlesource.com/chromium/tools/depot_tools.git"
    ])
    # ONLYOFFICE 自己的 bootstrap hack
    v8_89.change_bootstrap()

    # Windows 下修正 cipd 架构
    if base.host_platform() == "windows":
      if base.is_file("depot_tools/cipd.ps1"):
        base.replaceInFile("depot_tools/cipd.ps1",
                           "windows-386",
                           "windows-amd64")

  # 配置 PATH，优先使用本地 depot_tools 和自带 python2
  path_to_python2 = "/depot_tools/bootstrap-2@3_11_8_chromium_35_bin/python/bin"
  os.environ["PATH"] = os.pathsep.join([
    base_dir + "/depot_tools",
    base_dir + path_to_python2,
    config.option("vs-path") + "/../Common7/IDE",
    os.environ.get("PATH", "")
  ])

  # 统一 GN 调用方式：
  # 优先用 python3 执行 depot_tools/gn.py（不会再走 python3_bin_reldir 检查）
  gn_py = os.path.join(base_dir, "depot_tools", "gn.py")

  def run_gn(args_list):
    """
    - 如果存在 gn.py：使用系统 python3 直接执行它；
    - 否则：退回到 PATH 里的 gn。
    """
    if os.path.isfile(gn_py):
      print("using python3 gn.py:", gn_py)
      base.cmd2("python3", [gn_py] + args_list)
    else:
      print("gn.py not found, fallback to 'gn' in PATH")
      base.cmd2("gn", args_list)

  # ---------------------------------------------------------------------------
  # fetch v8 源码
  # ---------------------------------------------------------------------------
  if not base.is_dir("v8"):
    # ONLYOFFICE 使用的 v8 版本 4.10.253
    base.cmd("./depot_tools/fetch", ["v8"], True)
    base.cmd("./depot_tools/gclient",
             ["sync", "-r", "4.10.253"], True)
    base.delete_dir_with_access_error("v8/buildtools/win")
    base.cmd("git", ["config", "--system", "core.longpaths", "true"], True)
    base.cmd("gclient", ["sync", "--force"], True)

  # ---------------------------------------------------------------------------
  # 找到真正的 V8 源码根目录（包含 .gn 的目录）
  # ---------------------------------------------------------------------------
  v8_root = None
  candidates = [
    os.path.join(base_dir, "v8"),
    os.path.join(base_dir, "v8", "v8"),
    base_dir,
  ]
  for c in candidates:
    if os.path.isfile(os.path.join(c, ".gn")):
      v8_root = c
      break

  if v8_root is None:
    print("ERROR: cannot find .gn under", base_dir)
    # 恢复环境后退出
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
    # 关键：在 ARM64 机器上，即使 platform=linux_64，也强行用 ARM64 配置
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

  # 预留：如果以后你真的把 configure 改出 linux_arm64 平台，也能直接用
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
  # macOS x64
  # ---------------------------------------------------------------------------
  if config.check_option("platform", "mac_64"):
    gn_args = "is_debug=false " + base_args64
    run_gn(["gen", "out.gn/mac_64", "--args='" + gn_args + "'"])
    base.cmd("ninja", ["-C", "out.gn/mac_64"])

  # ---------------------------------------------------------------------------
  # Windows（简化版）
  # ---------------------------------------------------------------------------
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
