#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
极简 x2t 构建脚本（只编译 core/x2t）

使用方式：
    cd /home/build_tools_arm64/tools/linux
    python3 build_x2t.py

根据你本机情况，下面几个路径一定要确认 / 修改：
  CORE_DIR
  ICU_ROOT / OPENSSL_ROOT / HEIF_ROOT 等第三方库路径
  TARGET_NAME 如果工程里目标不是 x2t，要改成实际名字
"""

import os
import sys
import pathlib
import subprocess
import multiprocessing


# ======= 根据自己环境调整这里 =======

# core 仓库的根目录
CORE_DIR = pathlib.Path("/home/core").resolve()

# 构建输出目录（临时）
BUILD_DIR = CORE_DIR / "build" / "linux_arm64_x2t"

# 最终想要放 x2t 的位置（和原来自动脚本一致）
FINAL_BIN_DIR = CORE_DIR / "build" / "bin" / "linux_arm64"

# CMake 目标名，一般就是 x2t；如果你 cmake 里叫别的，请改成对应名字
TARGET_NAME = "x2t"

# 3dParty 库路径（按你前面 build 出来的实际路径改）
ICU_ROOT = CORE_DIR / "Common" / "3dParty" / "icu" / "linux_arm64" / "build"
OPENSSL_ROOT = CORE_DIR / "Common" / "3dParty" / "openssl" / "linux_arm64" / "build"
HEIF_ROOT = CORE_DIR / "Common" / "3dParty" / "heif" / "linux_arm64" / "build"
# 需要别的库同理加几个 -DXXX_ROOT=xxx 即可

# ==================================


def run(cmd, cwd=None):
  """打印并执行命令"""
  print("+", " ".join(cmd))
  subprocess.check_call(cmd, cwd=cwd)


def configure():
  """调用 CMake 生成工程"""
  BUILD_DIR.mkdir(parents=True, exist_ok=True)
  FINAL_BIN_DIR.mkdir(parents=True, exist_ok=True)

  cmake_cmd = [
    "cmake",
    str(CORE_DIR),
    "-DCMAKE_BUILD_TYPE=Release",
    # 根据工程 CMakeLists 的实际选项来关/开模块，这里给一个常见的写法示例
    "-DENABLE_DESKTOP=OFF",
    "-DENABLE_SERVER=ON",
    "-DCMAKE_INSTALL_PREFIX=" + str(CORE_DIR / "build" / "install"),

    # 第三方库路径（如果工程没用这些变量，就删掉对应行）
    f"-DICU_ROOT={ICU_ROOT}",
    f"-DOPENSSL_ROOT_DIR={OPENSSL_ROOT}",
    f"-DHEIF_ROOT={HEIF_ROOT}",
  ]

  run(cmake_cmd, cwd=BUILD_DIR)


def build_x2t():
  """只编译 x2t 这个 target"""
  jobs = str(multiprocessing.cpu_count())
  build_cmd = [
    "cmake", "--build", ".",
    "--target", TARGET_NAME,
    "-j", jobs,
  ]
  run(build_cmd, cwd=BUILD_DIR)


def copy_result():
  """在 build 目录里找 x2t，并复制到最终 bin 目录"""
  candidates = list(BUILD_DIR.rglob(TARGET_NAME))
  if not candidates:
    print("\n[警告] 在构建目录里没有找到可执行文件 '{}'".format(TARGET_NAME))
    print("你可以手动在 {} 里 `find . -name '{}'` 看看实际路径，然后自己 cp 一下。"
          .format(BUILD_DIR, TARGET_NAME))
    return

  src = candidates[0]
  dst = FINAL_BIN_DIR / TARGET_NAME
  print("+ cp {} {}".format(src, dst))
  dst.parent.mkdir(parents=True, exist_ok=True)
  # 覆盖旧的
  try:
    os.remove(dst)
  except FileNotFoundError:
    pass
  os.link(src, dst) if hasattr(os, "link") else subprocess.check_call(["cp", "-f", str(src), str(dst)])
  os.chmod(dst, 0o755)
  print("\n[OK] x2t 已生成：", dst)


def main():
  # 简单检查
  if not CORE_DIR.is_dir():
    print("[错误] CORE_DIR 目录不存在：", CORE_DIR)
    sys.exit(1)

  try:
    configure()
    build_x2t()
    copy_result()
  except subprocess.CalledProcessError as e:
    print("\n[构建失败] 命令退出码：", e.returncode)
    sys.exit(e.returncode)


if __name__ == "__main__":
  main()
