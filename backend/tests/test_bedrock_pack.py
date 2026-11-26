"""检查行为包闭包和安装文件边界；这些检查不替代 Minecraft 实机加载。"""

import json
from zipfile import ZipFile

import pytest
from build_bedrock import SOURCE, build
from configure_bds import PROFILE, inspect_destinations, install_files


def profile():
    """读取与生成产物共用的候选档案。"""
    return json.loads((SOURCE / "profiles.json").read_text(encoding="utf-8"))[PROFILE]


def fake_bds(tmp_path):
    """只构造安装脚本需要的文件结构，不假装是可运行的游戏。"""
    bds = tmp_path / "bds"
    world = bds / "worlds" / "TestFarm"
    world.mkdir(parents=True)
    (bds / "bedrock_server.exe").write_bytes(b"test placeholder")
    (world / "level.dat").write_bytes(b"test placeholder")
    return bds, world


def test_diagnostic_pack_excludes_network_and_secrets(tmp_path):
    """本地诊断包没有网络依赖，ZIP 根目录可直接被导入。"""
    with ZipFile(build("diagnostic", tmp_path)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["modules"][0]["entry"] in archive.namelist()
        assert manifest["dependencies"] == [
            {"module_name": "@minecraft/server", "version": "2.0.0"}
        ]
        assert "scripts/transport.js" not in archive.namelist()
        assert all("secret" not in path for path in archive.namelist())
        text = "\n".join(archive.read(path).decode() for path in archive.namelist())
        assert "@minecraft/server-net" not in text.replace(
            "// 诊断包不导入 server-net / server-admin", ""
        )


def test_network_pack_contains_all_relative_imports_and_candidate_label(tmp_path):
    """网络包清单与入口一致，必须明确保留未实机验证标志。"""
    with ZipFile(build(PROFILE, tmp_path)) as archive:
        config = json.loads(archive.read("compatibility.json"))
        assert config["verification"] == "candidate_only_not_bds_tested"
        assert "scripts/bds.js" in archive.namelist()
        assert "scripts/outbox.js" in archive.namelist()
        assert "scripts/transport.js" in archive.namelist()
        assert "scripts/diagnostic.js" not in archive.namelist()


def test_install_preserves_other_packs_and_keeps_secret_out_of_archive(tmp_path):
    """只增加当前包，备份原列表；模块凭据留在 BDS 配置目录。"""
    bds, world = fake_bds(tmp_path)
    original = b'[{"pack_id":"other-pack","version":[1,0,0]}]'
    (world / "world_behavior_packs.json").write_bytes(original)
    pack, config, target = inspect_destinations(bds, "TestFarm", profile())
    settings = {"token": "test-secret-only", "variables": {"farm_bridge_id": "world_1"}}
    install_files(pack, config, target, profile(), settings)
    assert (world / "world_behavior_packs.before-m2.json").read_bytes() == original
    enabled = json.loads((world / "world_behavior_packs.json").read_text())
    assert enabled[0]["pack_id"] == "other-pack"
    assert enabled[1]["pack_id"] == profile()["header_uuid"]
    assert json.loads((config / "secrets.json").read_text())["farm_bds_token"] == settings["token"]
    assert all(
        "test-secret-only" not in path.read_text() for path in pack.rglob("*") if path.is_file()
    )
    with pytest.raises(ValueError, match="已有 M2/M3 安装"):
        inspect_destinations(bds, "TestFarm", profile())


def test_install_rejects_world_outside_worlds_directory(tmp_path):
    """用户参数不能把安装写到 worlds 以外的目录。"""
    bds, _ = fake_bds(tmp_path)
    outside = bds / "outside"
    outside.mkdir()
    (outside / "level.dat").write_bytes(b"test")
    with pytest.raises(ValueError, match="专用测试世界"):
        inspect_destinations(bds, "../outside", profile())


def test_m3_package_installs_its_own_profile_and_complete_script_graph(tmp_path):
    """M3 使用独立 UUID、版本和入口，不覆写 M2 包。"""
    name = "m3-bds-1.26.66-candidate"
    selected = json.loads((SOURCE / "profiles.json").read_text(encoding="utf-8"))[name]
    bds, world = fake_bds(tmp_path)
    pack, config, target = inspect_destinations(bds, "TestFarm", selected)
    install_files(pack, config, target, selected, {"token": "test", "variables": {}}, name)
    assert pack.name == "english_farm_m3"
    manifest = json.loads((pack / "manifest.json").read_text())
    assert manifest["header"]["version"] == [0, 4, 0]
    assert manifest["modules"][0]["entry"] == "scripts/lesson-entry.js"
    assert (pack / "scripts/action-worker.js").is_file()
    assert (pack / "scripts/farm-scene.js").is_file()
    assert (world / "world_behavior_packs.before-m3.json").is_file()
