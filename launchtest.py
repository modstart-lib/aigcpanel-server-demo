#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
launchtest.py — AIGCPanel 模型一键「加载 + 功能测试」

全部基于 aigcpanel CLI 实现：

  1. server-install   将当前目录模型加载到 AigcPanel 已安装模型列表
  2. model-list       校验模型已成功加载
  3. model-call       依次调用模型全部功能（soundTts / soundClone / videoGen /
                      asr / textToImage / imageToImage / textToVideo /
                      imageToVideo）并等待结果

用法:
  python3 launchtest.py

行为:
  - AigcPanel 若未运行，自动从默认安装位置启动（macOS 的
    /Applications/AigcPanel.app、Windows 的 %LOCALAPPDATA% 安装目录、
    Linux 的 /opt 等），并等待 HTTP 服务就绪。
  - aigcpanel CLI 在与当前项目同级的 aigcpanel 源码目录（dist-cli）中自动
    定位，缺失时用 go 自动构建当前平台版本。
"""

import json
import os
import platform
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
EXAMPLE_DIR = os.path.join(ROOT, "example-file")
CONFIG_FILE = os.path.join(ROOT, "config.json")
TIMEOUT = 300  # 单次 model-call 轮询超时（秒）
APP_WAIT_SEC = 60  # 自动启动 AigcPanel 后等待 HTTP 服务就绪的超时（秒）

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
CYAN = "\033[0;36m"
NC = "\033[0m"


def ok(msg):
    print(f"  {GREEN}[PASS]{NC} {msg}")


def ko(msg):
    print(f"  {RED}[FAIL]{NC} {msg}")


def info(msg):
    print(f"{CYAN}{msg}{NC}")


def run(cmd, cwd=None, check=False):
    """Run a command, capture stdout/stderr (UTF-8, tolerant decode)."""
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=check,
        )
    except FileNotFoundError as e:
        raise SystemExit(f"错误: 找不到命令 {cmd[0]}，请确认已安装并加入 PATH")


def cli_suffix():
    """当前平台对应的 CLI 二进制后缀（与 aigcpanel 源码的构建约定一致）。"""
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Darwin":
        return "darwin-arm64" if "arm" in machine else "darwin-x64"
    if system == "Linux":
        return "linux-arm64" if "arm" in machine else "linux-x64"
    if system == "Windows":
        return "win-arm64.exe" if "arm" in machine else "win-x64.exe"
    raise SystemExit(f"错误: 不支持的平台 {system}-{machine}")


def _sibling_candidates():
    """返回与当前项目同级的目录列表（跳过自身），用于定位 aigcpanel 源码目录。"""
    parent = os.path.dirname(ROOT)
    self_name = os.path.basename(ROOT)
    try:
        names = sorted(os.listdir(parent))
    except OSError:
        return []
    return [
        os.path.join(parent, name)
        for name in names
        if name != self_name and os.path.isdir(os.path.join(parent, name))
    ]


def ensure_cli():
    """定位 aigcpanel CLI 二进制：
    在与当前项目同级的 aigcpanel 源码目录（dist-cli）中查找，
    找到源码目录但未构建时用 go 自动构建当前平台版本。
    """
    suffix = cli_suffix()
    cli_name = f"aigcpanel-{suffix}"

    # 1) 在同级源码目录中查找现成的 CLI
    for src_dir in _sibling_candidates():
        cli = os.path.join(src_dir, "dist-cli", cli_name)
        if os.access(cli, os.X_OK):
            return cli

    # 2) 找到含 cli 子目录的源码目录，自动构建当前平台版本
    for src_dir in _sibling_candidates():
        if not os.path.isdir(os.path.join(src_dir, "cli")):
            continue
        cli = os.path.join(src_dir, "dist-cli", cli_name)
        print(f"构建 aigcpanel CLI（当前平台 {suffix}）...")
        version = "dev"
        pkg_json = os.path.join(src_dir, "package.json")
        if os.path.isfile(pkg_json):
            try:
                with open(pkg_json, encoding="utf-8") as f:
                    version = json.load(f).get("version", "dev")
            except Exception:
                pass
        os.makedirs(os.path.join(src_dir, "dist-cli"), exist_ok=True)
        proc = run(
            [
                "go", "build",
                f"-ldflags=-X main.Version={version}",
                "-o", os.path.join("..", "dist-cli", cli_name),
                ".",
            ],
            cwd=os.path.join(src_dir, "cli"),
        )
        if proc.returncode != 0 or not os.access(cli, os.X_OK):
            print(proc.stdout, file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            raise SystemExit(f"错误: CLI 构建失败: {cli}")
        return cli

    raise SystemExit(
        "错误: 未找到 aigcpanel CLI。\n"
        "请确认 aigcpanel 源码目录与当前项目位于同一目录，并已执行 make build-cli。"
    )


def find_cli_auth():
    """在 AigcPanel 的 userData 位置查找 cli-auth.json，返回路径或 None。"""
    candidates = []
    if sys.platform == "darwin":
        candidates.append(
            os.path.expanduser("~/Library/Application Support/aigcpanel/cli-auth.json")
        )
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            candidates.append(os.path.join(appdata, "aigcpanel", "cli-auth.json"))
        candidates.append(
            os.path.expanduser("~/AppData/Roaming/aigcpanel/cli-auth.json")
        )
    else:
        config_home = os.environ.get("XDG_CONFIG_HOME", "")
        if config_home:
            candidates.append(os.path.join(config_home, "aigcpanel", "cli-auth.json"))
        candidates.append(os.path.expanduser("~/.config/aigcpanel/cli-auth.json"))
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def find_aigcpanel_app():
    """查找已安装的 AigcPanel 应用路径（跨平台），找不到返回 None。"""
    if sys.platform == "darwin":
        for p in [
            "/Applications/AigcPanel.app",
            os.path.expanduser("~/Applications/AigcPanel.app"),
        ]:
            if os.path.isdir(p):
                return p
    elif sys.platform == "win32":
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\AigcPanel\AigcPanel.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\AigcPanel\AigcPanel.exe"),
        ]
        pf = os.environ.get("ProgramFiles", "")
        if pf:
            candidates.append(os.path.join(pf, "AigcPanel", "AigcPanel.exe"))
        for p in candidates:
            if os.path.isfile(p):
                return p
    else:  # Linux
        candidates = [
            "/opt/AigcPanel/AigcPanel",
            os.path.expanduser("~/Applications/AigcPanel.AppImage"),
            os.path.expanduser("~/.local/bin/AigcPanel"),
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
    return None


def launch_aigcpanel(app_path):
    """启动已安装的 AigcPanel 应用（不阻塞）。"""
    if sys.platform == "darwin":
        subprocess.Popen(["open", app_path])
    else:
        subprocess.Popen([app_path])


def wait_server_alive(timeout=APP_WAIT_SEC):
    """轮询等待 cli-auth.json 出现且 HTTP 端口可连，返回是否就绪。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        cli_auth = find_cli_auth()
        if cli_auth and server_alive(cli_auth):
            return True
        time.sleep(1)
    return False


def server_alive(cli_auth_path):
    """尝试连接 cli-auth.json 中记录的 HTTP 端口，确认 AigcPanel 真的在运行。"""
    try:
        with open(cli_auth_path, encoding="utf-8") as f:
            port = json.load(f).get("port")
        if not port:
            return False
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except Exception:
        return False


def load_cli_json(proc, what):
    """解析 CLI stdout 为 JSON；命令失败或解析失败时输出完整内容并退出。"""
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        print(proc.stdout)
        if proc.returncode != 0 and proc.stderr:
            print(proc.stderr, file=sys.stderr)
        raise SystemExit(f"错误: {what} 执行失败（exit={proc.returncode}），输出不是合法 JSON")


def install_model(cli):
    """server-install: 加载当前目录模型到 AigcPanel。"""
    proc = run([cli, "server-install", "--dir", ROOT])
    result = load_cli_json(proc, "server-install")
    if result.get("code") != 0:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        msg = str(result.get("msg") or "")
        hint = ""
        if "Not found" in msg:
            hint = (
                "\n当前 AigcPanel 版本过旧，不支持 /api/server/install 接口。\n"
                "请升级到包含该接口的版本（或使用 aigcpanel 源码的最新开发版）。"
            )
        raise SystemExit(f"错误: server-install 失败: {msg}{hint}")
    d = result.get("data") or {}
    print(f"  已安装: {d.get('name')} ({d.get('title', '')}) v{d.get('version')}")
    print("  功能: " + ", ".join(d.get("functions") or []))


def verify_installed(cli, name, version):
    """model-list: 校验模型已出现在已安装列表。"""
    proc = run([cli, "model-list"])
    result = load_cli_json(proc, "model-list")
    models = result.get("data") or []
    hit = [
        m for m in models
        if m.get("name") == name and m.get("version") == version
    ]
    if not hit:
        print("  当前已安装:", ", ".join(f"{m.get('name')} v{m.get('version')}" for m in models))
        raise SystemExit("错误: 模型未出现在 model-list")
    funcs = hit[0].get("functions") or []
    print(f"已加载: {name} v{version}")
    print("功能:", ", ".join(f.get("name") for f in funcs))


def run_case(cli, model_key, label, args, skip_on_unknown=False):
    """model-call: 调用单个模型功能。

    Returns:
      True  通过
      False 失败
      None  跳过（平台不支持该 function，见 skip_on_unknown）
    """
    cmd = [cli, "model-call", "--model", model_key, "--timeout", str(TIMEOUT)] + args
    proc = run(cmd)
    if proc.returncode == 0:
        ok(label)
        return True
    output = (proc.stdout or "") + (proc.stderr or "")
    if skip_on_unknown and "Unknown function" in output:
        print(f"  {YELLOW}[SKIP]{NC} {label}（当前 AigcPanel 平台 model-call 不支持，"
              f"已由 tests/queue.py 覆盖）")
        return None
    ko(label)
    for line in output.splitlines():
        print("    " + line)
    return False


def main():
    # ── 0. 读取当前目录模型配置 ──────────────────────────────────────────
    if not os.path.isfile(CONFIG_FILE):
        raise SystemExit(f"错误: 未找到 {CONFIG_FILE}，请在 aigcpanel-server-demo 目录下运行")
    with open(CONFIG_FILE, encoding="utf-8") as f:
        config = json.load(f)
    model_name = config["name"]
    model_version = config["version"]
    model_key = f"{model_name}|{model_version}"

    print("═══════════════════════════════════════════════════════")
    print("  AIGCPanel 模型加载 + 功能测试")
    print(f"  模型: {model_name} v{model_version}  (目录: {ROOT})")
    print("═══════════════════════════════════════════════════════")

    # ── 1. 定位 CLI ─────────────────────────────────────────────────────
    cli = ensure_cli()
    print(f"CLI: {cli}")
    version_proc = run([cli, "version"])
    if version_proc.returncode == 0:
        try:
            print(json.loads(version_proc.stdout).get("version", "unknown"))
        except Exception:
            pass

    # ── 2. 检查 AigcPanel 是否运行，未运行则自动启动打包版 ──────────────
    cli_auth = find_cli_auth()
    if not (cli_auth and server_alive(cli_auth)):
        app_path = find_aigcpanel_app()
        if not app_path:
            raise SystemExit(
                "\n错误: AigcPanel 未运行，且未找到已安装的应用。\n"
                "请先手动启动 AigcPanel（打包版或开发版），再重新运行本命令。"
            )
        print(f"\nAigcPanel 未运行，自动启动: {app_path}")
        launch_aigcpanel(app_path)
        print(f"等待 AigcPanel HTTP 服务就绪（最多 {APP_WAIT_SEC}s）...")
        if not wait_server_alive():
            raise SystemExit(
                f"\n错误: AigcPanel 启动后 {APP_WAIT_SEC}s 内 HTTP 服务未就绪。\n"
                "请检查应用是否正常启动。"
            )

    # ── 3. 加载模型 + 校验 ──────────────────────────────────────────────
    print()
    info(f"==> [1/4] 加载模型 {model_key}")
    install_model(cli)

    print()
    info("==> [2/4] 校验模型已出现在已安装列表")
    verify_installed(cli, model_name, model_version)

    # ── 4. 功能测试 ─────────────────────────────────────────────────────
    print()
    info("==> [3/4] 模型功能测试")

    wav = os.path.join(EXAMPLE_DIR, "nihao.wav")
    mp4 = os.path.join(EXAMPLE_DIR, "short.mp4")
    png = os.path.join(EXAMPLE_DIR, "1.png")

    test_cases = [
        ("语音合成 soundTts", [
            "--function", "soundTts",
            "--text", "你好，欢迎使用 AIGCPanel 模型测试",
        ]),
        ("语音克隆 soundClone", [
            "--function", "soundClone",
            "--text", "你好，这是克隆音色的测试",
            "--promptAudio", wav,
            "--promptText", "参考音频提示文字",
        ]),
        ("视频合成 videoGen", [
            "--function", "videoGen",
            "--video", mp4,
            "--audio", wav,
        ]),
        ("语音识别 asr", [
            "--function", "asr",
            "--audio", wav,
        ]),
        ("文生图 textToImage", [
            "--function", "textToImage",
            "--prompt", "AIGCPanel 文生图测试，山水风景画",
        ]),
        ("图生图 imageToImage", [
            "--function", "imageToImage",
            "--image", png,
            "--prompt", "转换为油画风格",
        ]),
        ("文生视频 textToVideo", [
            "--function", "textToVideo",
            "--prompt", "AIGCPanel 文生视频测试，一只在花园奔跑的猫",
        ]),
        ("图生视频 imageToVideo", [
            "--function", "imageToVideo",
            "--images", json.dumps([png]),
            "--prompt", "让画面动起来，云朵缓缓飘动",
        ]),
        ("通用模型 generalImage", [
            "--function", "generalImage",
            "--prompt", "AIGCPanel 通用模型测试，一张星空下的山脉",
            "--count", "2",
        ]),
    ]
    # general 功能平台 model-call 接口尚未实现，遇到 "Unknown function"
    # 时自动跳过（不视为失败）；已由 tests/queue.py 直接运行 run.py 覆盖。
    skip_on_unknown_labels = {"通用模型 generalImage"}

    passed = 0
    failed = 0
    skipped = 0
    for label, args in test_cases:
        print()
        print(f"{YELLOW}---- {label} ----{NC}")
        result = run_case(
            cli, model_key, label, args,
            skip_on_unknown=label in skip_on_unknown_labels,
        )
        if result is None:
            skipped += 1
        elif result:
            passed += 1
        else:
            failed += 1

    # ── 5. 汇总 ─────────────────────────────────────────────────────────
    print()
    print("═══════════════════════════════════════════════════════")
    info("==> [4/4] 测试汇总")
    print(f"  通过: {passed}   失败: {failed}   跳过: {skipped}")
    print("═══════════════════════════════════════════════════════")
    if failed > 0:
        sys.exit(1)
    print(f"{GREEN}✓ 模型 {model_key} 加载并测试成功{NC}")


if __name__ == "__main__":
    main()

