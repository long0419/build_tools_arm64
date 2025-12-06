#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import sys

# build_tools 根目录：tools/linux/../.. -> /home/build_tools_arm64
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# core 源码根目录（按你现在的路径）
CORE_DIR = os.environ.get("ONLYOFFICE_CORE_DIR", "/home/core")
X2T_PATH = os.path.join(CORE_DIR, "build", "bin", "linux_arm64", "x2t")


def run(cmd, cwd=None):
    print("+", cmd)
    subprocess.check_call(cmd, shell=True, cwd=cwd)


def main():
    print("=== 极简构建 ONLYOFFICE x2t converter (Linux ARM64) ===")

    print("\n=== 1. 调用官方 make.py（按当前 configure 配置构建） ===")
    print("工作目录:", ROOT_DIR)
    # 这里不再传 icu / heif 之类的参数，直接跑官方 make.py
    run("python3 make.py", cwd=ROOT_DIR)

    print("\n=== 2. 检查 x2t 是否生成 ===")
    if os.path.isfile(X2T_PATH):
        print("✅ x2t 已生成：", X2T_PATH)
        sys.exit(0)
    else:
        print("❌ 构建结束，但没有找到 x2t：", X2T_PATH)
        print("大概率是 core/x2t 在编译阶段报错了，日志被淹没了。")
        print("建议在 /home/core 下面 grep 一下编译日志：")
        print("  cd /home/core")
        print("  grep -n \"x2t\" -R build 2>/dev/null | head")
        sys.exit(1)


if __name__ == "__main__":
    main()
