#!/usr/bin/env python

import sys
sys.path.append('../..')
import config
import base
import os
import subprocess
import v8_89


def clean():
  # 清理 depot_tools 和 v8 目录
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
  # 这里根据 ONLYOFFICE 的平台选项判断是否走主平台逻辑
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
  # 官方脚本的逻辑：gcc >= 6 或者 use-clang=1 时启用 clang
  if config.option("sysroot") == "" and (
      gcc_version >= 6000 or "1" == config.option("use-clang")):
    is_clang = "true"

  print("gcc version: " + str(gcc_version) + ", use clang:" + is_clang)
  return is_clang


def make_xp():
  """
  旧的 Windows XP 路径。为了兼容原有结构，保留空壳，
  如果你只在 Linux/ARM64 下构建，这个函数不会被用到。
  """
  print("make_xp() is not implemented in this simplified v8.py")
  return


def make():
  # 非主平台的话，走 XP 的老逻辑（这里只是占位，不做实际工作）
  if not is_main_platform():
    make_xp()
    return

  # 记录当前路径和环境变量，方便结束时恢复
  old_env = dict(os.environ)
  old_cur = os.getcwd()

  # ONLYOFFICE 源码里 V8 所在目录
  base_dir = base.get_script_dir() + "/../../core/Common/3dParty/v8/v8_xp"
  if not base.is_dir(base_dir):
    # 如果你实际的 v8 路径不一样，可以改这里
    base_dir = base.get_script_dir() + "/../../core/Common/3dParty/v8/v8"

  os.chdir(base_dir)

  # Windows 下的一些环境
  if base.host_platform() == "windows":
    base.set_env("DEPOT_TOOLS_WIN_TOOLCHAIN", "0")
    base.set_env("GYP_MSVS_VERSION", "2015")

  # 用 common_check_version 决定是否需要 clean
  base.common_check_version("v8", "1", clean)

  # 如果还没有 depot_tools，则 clone 一份
  if not base.is_dir("depot_tools"):
    base.cmd("git", [
      "clone",
      "https://chromium.googlesource.com/chromium/tools/depot_tools.git"
    ])
    # ONLYOFFICE 用的一个 bootstrap hack
    v8_89.change_bootstrap()

    # Windows 上的一个 32/64 bit hack
    if base.host_platform() == "windows":
      if base.is_file("depot_tools/cipd.ps1"):
        base.replaceInFile("depot_tools/cipd.ps1",
                           "windows-386",
                           "windows-amd64")

  # 配置 PATH，加入 depot_tools 和自带 python2
  path_to_python2 = "/depot_tools/bootstrap-2@3_11_8_chromium_35_bin/python/bin"
  os.environ["PATH"] = os.pathsep.join([
    base_dir + "/depot_tools",
    base_dir + path_to_python2,
    config.option("vs-path") + "/../Common7/IDE",
    os.environ.get("PATH", "")
  ])

  # --------------------------------------------------------------------------
  # fetch v8 源码
  if not base.is_dir("v8"):
    # 版本号 4.10.253 是 ONLYOFFICE 这套脚本里常用的
    base.cmd("./depot_tools/fetch", ["v8"], True)
    base.cmd("./depot_tools/gclient",
             ["sync", "-r", "4.10.253"], True)
    base.delete_dir_with_access_error("v8/buildtools/win")
    base.cmd("git", ["config", "--system", "core.longpaths", "true"], True)
    base.cmd("gclient", ["sync", "--force"], True)

  # --------------------------------------------------------------------------
  # build
  os.chdir("v8")

  # 不同架构的 GN 参数
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

  # ----------------- Linux x64 -----------------
  if config.check_option("platform", "linux_64"):
    gn_args = (
      "is_debug=false "
      + base_args64
      + " is_clang=" + is_use_clang()
      + " use_sysroot=false treat_warnings_as_errors=false"
    )
    base.cmd2("gn", ["gen", "out.gn/linux_64", "--args=" + gn_args])
    base.cmd("ninja", ["-C", "out.gn/linux_64"])

  # ----------------- Linux x86 -----------------
  if config.check_option("platform", "linux_32"):
    gn_args = (
      "is_debug=false "
      + base_args32
      + " is_clang=" + is_use_clang()
      + " use_sysroot=false treat_warnings_as_errors=false"
    )
    base.cmd2("gn", ["gen", "out.gn/linux_32", "--args=" + gn_args])
    base.cmd("ninja", ["-C", "out.gn/linux_32"])

  # ----------------- Linux ARM64（重点） -----------------
  if config.check_option("platform", "linux_arm64"):
    gn_args = (
      "is_debug=false "
      + base_args_arm64
      + " is_clang=" + is_use_clang()
      + " use_sysroot=false treat_warnings_as_errors=false"
    )
    # 单独的输出目录，避免和 linux_64 混在一起
    base.cmd2("gn", ["gen", "out.gn/linux_arm64", "--args=" + gn_args])
    base.cmd("ninja", ["-C", "out.gn/linux_arm64"])

  # ----------------- macOS x64 -----------------
  if config.check_option("platform", "mac_64"):
    gn_args = "is_debug=false " + base_args64
    base.cmd2("gn", ["gen", "out.gn/mac_64", "--args=" + gn_args])
    base.cmd("ninja", ["-C", "out.gn/mac_64"])

  # ----------------- Windows（保留简化版） -----------------
  # 这里只保留最基础的 win_64 / win_32 逻辑，如果你需要在 Windows 下
  # 真正用 XP 之类的老模式，需要再按官方脚本补全。
  if config.check_option("platform", "win_64"):
    if -1 != config.option("config").lower().find("debug"):
      gn_args = "is_debug=true " + base_args64 + " is_clang=false"
      base.cmd2("gn", [
        "gen",
        "out.gn/win_64/debug",
        "--args=" + gn_args
      ])
      base.cmd("ninja", ["-C", "out.gn/win_64/debug"])

    gn_args = "is_debug=false " + base_args64 + " is_clang=false"
    base.cmd2("gn", [
      "gen",
      "out.gn/win_64/release",
      "--args=" + gn_args
    ])
    base.cmd("ninja", ["-C", "out.gn/win_64/release"])

  if config.check_option("platform", "win_32"):
    if -1 != config.option("config").lower().find("debug"):
      gn_args = "is_debug=true " + base_args32 + " is_clang=false"
      base.cmd2("gn", [
        "gen",
        "out.gn/win_32/debug",
        "--args=" + gn_args
      ])
      base.cmd("ninja", ["-C", "out.gn/win_32/debug"])

    gn_args = "is_debug=false " + base_args32 + " is_clang=false"
    base.cmd2("gn", [
      "gen",
      "out.gn/win_32/release",
      "--args=" + gn_args
    ])
    base.cmd("ninja", ["-C", "out.gn/win_32/release"])

  # 恢复环境
  os.chdir(old_cur)
  os.environ.clear()
  os.environ.update(old_env)
  return