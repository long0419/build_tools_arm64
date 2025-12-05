#!/usr/bin/env python3
import os
import subprocess
import sys

ROOT = "/home/core"
BUILD_TOOLS = "/home/build_tools_arm64"

def run(cmd, cwd=None):
    print("+", cmd)
    subprocess.check_call(cmd, shell=True, cwd=cwd)

def main():
    print("=== 极简构建 ONLYOFFICE x2t converter (Linux ARM64) ===")

    # 1) 进入 build_tools 的 linux 工具目录
    os.chdir(f"{BUILD_TOOLS}/tools/linux")

    # 2) 只构建必要的 3dParty 库（qt 不需要）
    print("\n=== 构建必要 3dParty ===")
    run("python3 make.py icu")
    run("python3 make.py openssl")
    run("python3 make.py harfbuzz")
    run("python3 make.py brotli")
    run("python3 make.py heif")

    # 3) 构建 core/server（包含 x2t）
    print("\n=== 构建 core/server ===")
    run("python3 make.py core")

    print("\n=== 完成！可执行文件通常在： ===")
    print("/home/core/build/bin/linux_arm64/x2t")
    print("====================================")

if __name__ == "__main__":
    main()
