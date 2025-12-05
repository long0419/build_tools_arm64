#!/usr/bin/env python3
import subprocess
from pathlib import Path


# 仓库根目录：/home/build_tools_arm64
ROOT = Path(__file__).resolve().parents[2]


def run(cmd: str, cwd: Path | None = None) -> None:
    if cwd is None:
        cwd = ROOT
    print("+", cmd)
    subprocess.check_call(cmd, shell=True, cwd=str(cwd))


def main() -> None:
    print("=== 极简构建 ONLYOFFICE core / x2t (Linux ARM64) ===")

    # 这里假定 config.py 已经写好：
    #   module = "core"
    #   platform = "linux_arm64"
    #
    # 不再传 core / icu 等位置参数，避免 argparse 报错
    print("\n=== 调用根目录 make.py，按配置构建 core（包含 x2t） ===")
    run("python3 make.py")

    print("\n=== 构建完成（如果 make.py 成功执行）===")
    print("x2t 通常会在：/home/core/build/bin/linux_arm64/x2t")


if __name__ == "__main__":
    main()
