"""为用户指定的停机 BDS 安装候选包；不下载游戏、不修改世界实验开关。"""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from zipfile import ZipFile

import httpx
from build_bedrock import ROOT, SOURCE, build

PROFILE = "bds-1.26.66-candidate"


def require_server_stopped() -> None:
    """拒绝在 BDS 运行时写配置，避免运行中的世界覆盖包列表。"""
    check = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "if (Get-Process -Name bedrock_server -ErrorAction SilentlyContinue) { exit 1 }",
        ],
        check=False,
        capture_output=True,
    )
    if check.returncode != 0:
        raise ValueError("请先正常停止 BDS，再安装行为包")


def write_json(path: Path, value: object) -> None:
    """以 UTF-8 写入配置，不将凭据打印到终端。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def inspect_destinations(bds_dir: Path, world_name: str, profile: dict) -> tuple[Path, Path, Path]:
    """解析并约束目标目录，拒绝覆盖已有安装和访问世界目录之外的位置。"""
    bds = bds_dir.resolve(strict=True)
    if not (bds / "bedrock_server.exe").is_file():
        raise ValueError("指定目录没有 bedrock_server.exe")
    worlds = (bds / "worlds").resolve(strict=True)
    world = (worlds / world_name).resolve(strict=True)
    if world.parent != worlds or not (world / "level.dat").is_file():
        raise ValueError("请指定 worlds 内已创建的专用测试世界")
    stage = "m3" if profile["entry"] == "scripts/lesson-entry.js" else "m2"
    pack = (bds / "behavior_packs" / f"english_farm_{stage}").resolve()
    config = (bds / "config" / profile["script_uuid"]).resolve()
    if not pack.is_relative_to(bds) or not config.is_relative_to(bds):
        raise ValueError("安装目录不能通过链接指向 BDS 之外")
    if pack.exists() or config.exists():
        raise ValueError("已有 M2/M3 安装；请保留原配置，在新的测试 BDS 中安装")
    return pack, config, world


def create_binding(base_url: str, bridge_id: str) -> dict:
    """通过本机操作员接口幂等建立匿名课次，不使用 BDS 凭据获取控制权限。"""
    headers = {"X-API-Token": os.getenv("API_TOKEN", "")}
    with httpx.Client(base_url=base_url, headers=headers, timeout=10) as client:
        session = client.post(
            "/v1/sessions",
            json={
                "event_id": f"bds_create_{bridge_id}",
                "player_id": "bds_test_player",
                "lesson_id": "farm_01",
            },
        )
        session.raise_for_status()
        binding = client.post(
            "/v1/bds/bindings",
            json={
                "bridge_id": bridge_id,
                "session_id": session.json()["session_id"],
            },
        )
        binding.raise_for_status()
        return binding.json()


def install_files(
    pack: Path,
    config: Path,
    world: Path,
    profile: dict,
    settings: dict,
    profile_name: str = PROFILE,
) -> None:
    """安装本项目生成的归档，备份世界包列表并仅授予当前脚本所需模块。"""
    packs_file = world / "world_behavior_packs.json"
    if packs_file.resolve().parent != world:
        raise ValueError("世界包列表不能是指向其他目录的链接")
    original = packs_file.read_bytes() if packs_file.exists() else b"[]"
    enabled = json.loads(original)
    if not isinstance(enabled, list):
        raise ValueError("world_behavior_packs.json 必须为列表")
    known = json.loads((SOURCE / "profiles.json").read_text(encoding="utf-8"))
    project_ids = {item["header_uuid"] for item in known.values()}
    if any(item.get("pack_id") in project_ids for item in enabled):
        raise ValueError("测试世界已经启用本项目行为包，不能同时启用另一个版本")
    stage = "m3" if profile_name.startswith("m3-") else "m2"
    backup = world / f"world_behavior_packs.before-{stage}.json"
    if backup.exists():
        raise ValueError("已有 M2 备份，请先检查旧安装")
    with ZipFile(build(profile_name, ROOT / "dist")) as archive:
        archive.extractall(pack)
    write_json(config / "permissions.json", {"allowed_modules": list(profile["dependencies"])})
    write_json(config / "variables.json", settings["variables"])
    write_json(config / "secrets.json", {"farm_bds_token": settings["token"]})
    backup.write_bytes(original)
    enabled.append(
        {"pack_id": profile["header_uuid"], "version": profile.get("version", [0, 3, 0])}
    )
    write_json(packs_file, enabled)


def arguments() -> argparse.Namespace:
    """收集明确的安装路径和版本声明；不会将声明写成已验证版本。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bds-dir", type=Path, required=True)
    parser.add_argument("--world-name", required=True)
    parser.add_argument("--bds-version", required=True)
    parser.add_argument("--bridge-id", default="farm_m2_01")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--profile", choices=[PROFILE, "m3-bds-1.26.66-candidate"], default=PROFILE)
    return parser.parse_args()


def main() -> None:
    """准备可检查的候选安装；真实兼容性需启动 BDS 后运行探针确认。"""
    args = arguments()
    require_server_stopped()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", args.bridge_id):
        raise ValueError("bridge-id 只能包含字母、数字、下划线或连字符，最长 60 字符")
    if not re.fullmatch(r"1\.26\.66(?:\.\d+)?", args.bds_version):
        raise ValueError("目前仅有 1.26.66 候选档案；其他版本需先核对模块，不自动降级")
    if not 1 <= args.port <= 65535:
        raise ValueError("端口超出范围")
    profile = json.loads((SOURCE / "profiles.json").read_text(encoding="utf-8"))[args.profile]
    pack, config, world = inspect_destinations(args.bds_dir, args.world_name, profile)
    token = (ROOT / "data" / "bds-token.txt").read_text(encoding="utf-8").strip()
    base_url = f"http://127.0.0.1:{args.port}"
    binding = create_binding(base_url, args.bridge_id)
    settings = {
        "token": token,
        "variables": {
            "farm_api_url": base_url,
            "farm_bridge_id": args.bridge_id,
        },
    }
    install_files(pack, config, world, profile, settings, args.profile)
    stage = "m3" if args.profile.startswith("m3-") else "m2"
    write_json(ROOT / "data" / f"{stage}-binding.json", binding)
    print(f"候选包已安装：{pack}\n请核对 Beta APIs 和 BDS 日志；尚未通过实机兼容性验收。")


if __name__ == "__main__":
    main()
