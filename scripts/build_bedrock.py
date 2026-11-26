"""按显式候选版本构建最小 mcpack，只打包入口实际依赖的脚本。"""

import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bedrock-pack"
VERSION = [0, 3, 0]


def script_dependencies(entry: str) -> dict[str, str]:
    """遍历本地静态导入；诊断包不会携带网络和凭据模块。"""
    pending = [entry]
    result = {}
    while pending:
        relative = pending.pop()
        if relative in result:
            continue
        path = (SOURCE / relative).resolve()
        if not path.is_relative_to(SOURCE.resolve()):
            raise ValueError("脚本导入越过行为包目录")
        text = path.read_text(encoding="utf-8")
        result[relative] = text
        imports = re.findall(r'from\s+["\'](\./[^"\']+)["\']', text)
        pending.extend((Path(relative).parent / item).as_posix() for item in imports)
    return result


def manifest(profile_name: str, profile: dict) -> dict:
    """从候选档案生成清晰的 Bedrock 清单，不宣称已通过运行验证。"""
    return {
        "format_version": 2,
        "header": {
            "name": f"English Farm {profile_name}",
            "description": "Development candidate - gameplay compatibility not yet verified",
            "uuid": profile["header_uuid"],
            "version": profile.get("version", VERSION),
            "min_engine_version": profile["min_engine_version"],
        },
        "modules": [
            {
                "type": "script",
                "language": "javascript",
                "version": profile.get("version", VERSION),
                "uuid": profile["script_uuid"],
                "entry": profile["entry"],
            }
        ],
        "dependencies": [
            {"module_name": name, "version": version}
            for name, version in profile["dependencies"].items()
        ],
    }


def build(profile_name: str, output_dir: Path) -> Path:
    """生成自包含 ZIP 行为包，包含根 manifest 和可审阅的版本档案。"""
    profiles = json.loads((SOURCE / "profiles.json").read_text(encoding="utf-8"))
    profile = profiles[profile_name]
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = "english-farm-" if profile_name.startswith("m3-") else "english-farm-m2-"
    destination = output_dir / f"{prefix}{profile_name}.mcpack"
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest(profile_name, profile), indent=2))
        archive.writestr("compatibility.json", json.dumps(profile, indent=2))
        for relative, text in script_dependencies(profile["entry"]).items():
            archive.writestr(relative, text)
    return destination


def main() -> None:
    """构建所有明确登记的入口，并输出供导入和 BDS 安装的产物路径。"""
    for name in json.loads((SOURCE / "profiles.json").read_text(encoding="utf-8")):
        print(build(name, ROOT / "dist"))


if __name__ == "__main__":
    main()
