"""统一资产工厂单测：覆盖 character 的 extra 字段透传与 409 冲突响应。

scenes/props 的 CRUD 行为由 test_scenes_router / test_props_router 覆盖；本文件聚焦
factory 引入的新能力（character extras + extra='allow' 创建语义）。
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.auth import CurrentUserInfo, get_current_user
from server.routers import characters


class _FakePM:
    def __init__(self):
        self.projects = {"demo": {"characters": {}}}

    def _add_asset(self, asset_type, project_name, name, entry):
        if project_name not in self.projects:
            raise FileNotFoundError(project_name)
        bucket = self.projects[project_name].setdefault("characters", {})
        if name in bucket:
            return False
        bucket[name] = entry
        return True

    def load_project(self, project_name):
        if project_name not in self.projects:
            raise FileNotFoundError(project_name)
        return self.projects[project_name]

    def save_project(self, project_name, project):
        self.projects[project_name] = project

    def update_project(self, project_name, mutate_fn):
        project = self.load_project(project_name)
        mutate_fn(project)
        self.save_project(project_name, project)


def _client(monkeypatch):
    fake_pm = _FakePM()
    monkeypatch.setattr(characters, "get_project_manager", lambda: fake_pm)
    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: CurrentUserInfo(id="default", sub="testuser", role="admin")
    app.include_router(characters.router, prefix="/api/v1")
    return TestClient(app), fake_pm


class TestAssetRouterFactory:
    def test_character_post_passes_extra_voice_style(self, monkeypatch):
        client, fake_pm = _client(monkeypatch)
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters",
                json={"name": "Bob", "description": "hero", "voice_style": "calm"},
            )
            assert resp.status_code == 200
            entry = fake_pm.projects["demo"]["characters"]["Bob"]
            assert entry["voice_style"] == "calm"
            assert entry["character_sheet"] == ""
            # reference_image 是 character 的 extra 字段，create 时未传则默认 ""
            assert entry["reference_image"] == ""

    def test_character_post_400_on_path_unsafe_name(self, monkeypatch):
        """名字含路径分隔符须在 HTTP 边界拒绝：这类名字会让生成（嵌套文件路径）
        与后续单段路由（PATCH/DELETE/{name}）全部失效。"""
        client, fake_pm = _client(monkeypatch)
        with client:
            for bad_name in ("李白/诗人", "a\\b", ".."):
                resp = client.post(
                    "/api/v1/projects/demo/characters",
                    json={"name": bad_name, "description": "x"},
                )
                assert resp.status_code == 400, bad_name
                assert bad_name not in fake_pm.projects["demo"]["characters"]

    def test_character_post_409_on_duplicate(self, monkeypatch):
        client, fake_pm = _client(monkeypatch)
        fake_pm.projects["demo"]["characters"]["Alice"] = {
            "description": "old",
            "character_sheet": "",
            "voice_style": "",
            "reference_image": "",
        }
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters",
                json={"name": "Alice", "description": "dup", "voice_style": ""},
            )
            assert resp.status_code == 409

    def test_character_patch_accepts_extra_fields(self, monkeypatch):
        client, fake_pm = _client(monkeypatch)
        fake_pm.projects["demo"]["characters"]["Alice"] = {
            "description": "old",
            "character_sheet": "",
            "voice_style": "",
            "reference_image": "",
        }
        with client:
            resp = client.patch(
                "/api/v1/projects/demo/characters/Alice",
                json={
                    "description": "new",
                    "voice_style": "strong",
                    "character_sheet": "characters/Alice.png",
                    "reference_image": "characters/refs/Alice.png",
                },
            )
            assert resp.status_code == 200
            entry = fake_pm.projects["demo"]["characters"]["Alice"]
            assert entry["voice_style"] == "strong"
            assert entry["reference_image"] == "characters/refs/Alice.png"

    def test_character_patch_rejects_non_string_value(self, monkeypatch):
        client, fake_pm = _client(monkeypatch)
        fake_pm.projects["demo"]["characters"]["Alice"] = {
            "description": "old",
            "character_sheet": "",
            "voice_style": "",
            "reference_image": "",
        }
        with client:
            resp = client.patch(
                "/api/v1/projects/demo/characters/Alice",
                json={"reference_image": {"foo": "bar"}},
            )
            assert resp.status_code == 422
            # entry 未被污染
            assert fake_pm.projects["demo"]["characters"]["Alice"]["reference_image"] == ""

    def test_unknown_asset_type_raises(self):
        from server.routers._asset_router_factory import build_asset_router

        try:
            build_asset_router(asset_type="unknown", pm_getter=lambda: None)
        except ValueError as e:
            assert "unknown" in str(e)
        else:
            raise AssertionError("should have raised ValueError")


class _FakePMWithFiles:
    """支持 _clear_asset_sheet / voice reference 的 FakePM。"""

    def __init__(self, tmp_path):
        import json

        self.tmp_path = tmp_path
        self.projects: dict[str, dict] = {}
        self.project_dirs: dict[str, str] = {}

    def _add_project(self, name: str):
        import json

        proj_dir = self.tmp_path / name
        proj_dir.mkdir(parents=True, exist_ok=True)
        (proj_dir / "project.json").write_text(json.dumps({"name": name, "characters": {}, "scenes": {}, "props": {}, "products": {}}))
        self.project_dirs[name] = str(proj_dir)
        self.projects[name] = {"name": name, "characters": {}, "scenes": {}, "props": {}, "products": {}}

    def get_project_path(self, project_name: str):
        from pathlib import Path

        if project_name not in self.project_dirs:
            raise FileNotFoundError(project_name)
        return Path(self.project_dirs[project_name])

    def load_project(self, project_name: str):
        if project_name not in self.projects:
            raise FileNotFoundError(project_name)
        return self.projects[project_name]

    def update_project(self, project_name: str, mutate_fn):
        project = self.load_project(project_name)
        mutate_fn(project)

    def _clear_asset_sheet(self, asset_type: str, project_name: str, name: str):
        from pathlib import Path
        from lib.asset_types import ASSET_SPECS

        spec = ASSET_SPECS[asset_type]
        project = self.load_project(project_name)
        proj_dir = Path(self.project_dirs[project_name])
        bucket = project.get(spec.bucket_key, {})
        if name not in bucket:
            raise KeyError(name)
        entry = bucket[name]
        sheet_path = entry.get(spec.sheet_field, "")
        entry[spec.sheet_field] = ""
        if sheet_path:
            file_path = proj_dir / sheet_path
            try:
                file_path.resolve().relative_to(proj_dir.resolve())
            except ValueError:
                return
            file_path.unlink(missing_ok=True)

    def update_character_voice_reference(self, project_name: str, char_name: str, audio_path: str):
        project = self.load_project(project_name)
        if "characters" not in project or char_name not in project["characters"]:
            raise KeyError(char_name)
        project["characters"][char_name]["voice_reference_audio"] = audio_path

    def clear_character_voice_reference(self, project_name: str, char_name: str):
        from pathlib import Path

        project = self.load_project(project_name)
        proj_dir = Path(self.project_dirs[project_name])
        if "characters" not in project or char_name not in project["characters"]:
            raise KeyError(char_name)
        entry = project["characters"][char_name]
        audio_path = entry.get("voice_reference_audio", "")
        entry["voice_reference_audio"] = ""
        if audio_path:
            file_path = proj_dir / audio_path
            try:
                file_path.resolve().relative_to(proj_dir.resolve())
            except ValueError:
                return
            file_path.unlink(missing_ok=True)


def _full_client(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from server.auth import CurrentUserInfo, get_current_user
    from server.routers import characters, products, props, scenes

    fake_pm = _FakePMWithFiles(tmp_path)
    fake_pm._add_project("demo")
    # Add test entries
    fake_pm.projects["demo"]["characters"]["Alice"] = {
        "description": "hero",
        "character_sheet": "characters/Alice.png",
        "voice_style": "calm",
        "reference_image": "",
        "voice_reference_audio": "",
    }
    fake_pm.projects["demo"]["scenes"]["Park"] = {
        "description": "park",
        "scene_sheet": "scenes/Park.png",
    }
    fake_pm.projects["demo"]["props"]["Sword"] = {
        "description": "sword",
        "prop_sheet": "props/Sword.png",
    }
    fake_pm.projects["demo"]["products"]["Widget"] = {
        "description": "widget",
        "product_sheet": "products/Widget.png",
        "brand": "",
        "reference_images": [],
        "selling_points": [],
    }

    # Create dummy sheet files on disk
    for rel_path in ("characters/Alice.png", "scenes/Park.png", "props/Sword.png", "products/Widget.png"):
        abs_path = tmp_path / "demo" / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text("dummy")

    monkeypatch.setattr(characters, "get_project_manager", lambda: fake_pm)
    monkeypatch.setattr(scenes, "get_project_manager", lambda: fake_pm)
    monkeypatch.setattr(props, "get_project_manager", lambda: fake_pm)
    monkeypatch.setattr(products, "get_project_manager", lambda: fake_pm)

    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: CurrentUserInfo(id="default", sub="testuser", role="admin")
    app.include_router(characters.router, prefix="/api/v1")
    app.include_router(scenes.router, prefix="/api/v1")
    app.include_router(props.router, prefix="/api/v1")
    app.include_router(products.router, prefix="/api/v1")
    return TestClient(app), fake_pm


class TestDeleteSheet:
    """测试 DELETE /projects/{name}/{subdir}/{entry}/sheet 端点。"""

    def test_delete_character_sheet_clears_field_and_deletes_file(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        proj_dir = tmp_path / "demo"
        sheet_file = proj_dir / "characters" / "Alice.png"
        assert sheet_file.exists()
        assert pm.projects["demo"]["characters"]["Alice"]["character_sheet"] == "characters/Alice.png"

        with client:
            resp = client.delete("/api/v1/projects/demo/characters/Alice/sheet")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert pm.projects["demo"]["characters"]["Alice"]["character_sheet"] == ""
        assert not sheet_file.exists()
        # description / voice_style not affected
        assert pm.projects["demo"]["characters"]["Alice"]["description"] == "hero"
        assert pm.projects["demo"]["characters"]["Alice"]["voice_style"] == "calm"

    def test_delete_scene_sheet(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        proj_dir = tmp_path / "demo"
        sheet_file = proj_dir / "scenes" / "Park.png"
        assert sheet_file.exists()

        with client:
            resp = client.delete("/api/v1/projects/demo/scenes/Park/sheet")
        assert resp.status_code == 200
        assert pm.projects["demo"]["scenes"]["Park"]["scene_sheet"] == ""
        assert not sheet_file.exists()

    def test_delete_prop_sheet(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.delete("/api/v1/projects/demo/props/Sword/sheet")
        assert resp.status_code == 200
        assert pm.projects["demo"]["props"]["Sword"]["prop_sheet"] == ""

    def test_delete_product_sheet(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.delete("/api/v1/projects/demo/products/Widget/sheet")
        assert resp.status_code == 200
        assert pm.projects["demo"]["products"]["Widget"]["product_sheet"] == ""

    def test_delete_nonexistent_file_not_error(self, monkeypatch, tmp_path):
        """文件已被手动删除时，字段清空不报错。"""
        client, pm = _full_client(monkeypatch, tmp_path)
        # Simulate: sheet field set but file already gone
        pm.projects["demo"]["characters"]["Alice"]["character_sheet"] = "characters/Alice.png"
        sheet_file = tmp_path / "demo" / "characters" / "Alice.png"
        sheet_file.unlink(missing_ok=True)
        assert not sheet_file.exists()

        with client:
            resp = client.delete("/api/v1/projects/demo/characters/Alice/sheet")
        assert resp.status_code == 200
        assert pm.projects["demo"]["characters"]["Alice"]["character_sheet"] == ""

    def test_delete_sheet_404_on_missing_asset(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.delete("/api/v1/projects/demo/characters/NotExist/sheet")
        assert resp.status_code == 404

    def test_delete_sheet_safe_path_no_escape(self, monkeypatch, tmp_path):
        """路径逃逸文件不会被删除。"""
        client, pm = _full_client(monkeypatch, tmp_path)
        # Set sheet to path that tries to escape project dir
        pm.projects["demo"]["characters"]["Alice"]["character_sheet"] = "../outside/file.png"
        # Create a file outside the project
        outside = tmp_path / "outside" / "file.png"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text("outside")

        with client:
            resp = client.delete("/api/v1/projects/demo/characters/Alice/sheet")
        assert resp.status_code == 200
        assert pm.projects["demo"]["characters"]["Alice"]["character_sheet"] == ""
        assert outside.exists()  # 不应该被删除


class TestVoiceReference:
    """测试角色声音参考上传/删除端点。"""

    def test_upload_voice_reference_saves_file_and_updates_field(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/voice-reference",
                files={"file": ("voice.mp3", b"fake-mp3-data", "audio/mpeg")},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["path"] == "characters/voice_refs/Alice.mp3"
        assert pm.projects["demo"]["characters"]["Alice"]["voice_reference_audio"] == "characters/voice_refs/Alice.mp3"
        assert (tmp_path / "demo" / "characters" / "voice_refs" / "Alice.mp3").exists()

    def test_upload_voice_reference_replaces_old(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        # First upload
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/voice-reference",
                files={"file": ("old.wav", b"old-data", "audio/wav")},
            )
        assert resp.status_code == 200
        old_path = tmp_path / "demo" / "characters" / "voice_refs" / "Alice.wav"
        assert old_path.exists()

        # Replace with new format
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/voice-reference",
                files={"file": ("new.mp3", b"new-data", "audio/mpeg")},
            )
        assert resp.status_code == 200
        assert pm.projects["demo"]["characters"]["Alice"]["voice_reference_audio"] == "characters/voice_refs/Alice.mp3"
        assert not old_path.exists()  # old file deleted
        assert (tmp_path / "demo" / "characters" / "voice_refs" / "Alice.mp3").exists()

    def test_delete_voice_reference(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        # Set up voice reference
        pm.projects["demo"]["characters"]["Alice"]["voice_reference_audio"] = "characters/voice_refs/Alice.mp3"
        audio_dir = tmp_path / "demo" / "characters" / "voice_refs"
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_file = audio_dir / "Alice.mp3"
        audio_file.write_text("audio data")
        assert audio_file.exists()

        with client:
            resp = client.delete("/api/v1/projects/demo/characters/Alice/voice-reference")
        assert resp.status_code == 200
        assert pm.projects["demo"]["characters"]["Alice"]["voice_reference_audio"] == ""
        assert not audio_file.exists()

    def test_delete_voice_reference_404_on_missing_character(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.delete("/api/v1/projects/demo/characters/NotExist/voice-reference")
        assert resp.status_code == 404

    def test_upload_voice_reference_rejects_non_audio(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/voice-reference",
                files={"file": ("image.png", b"not-audio", "image/png")},
            )
        assert resp.status_code == 400

    def test_upload_voice_reference_404_missing_character(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/NotExist/voice-reference",
                files={"file": ("voice.mp3", b"data", "audio/mpeg")},
            )
        assert resp.status_code == 404

    def test_delete_voice_reference_no_file_not_error(self, monkeypatch, tmp_path):
        """文件不存在时清空字段不报错。"""
        client, pm = _full_client(monkeypatch, tmp_path)
        pm.projects["demo"]["characters"]["Alice"]["voice_reference_audio"] = "characters/voice_refs/ghost.mp3"
        # File doesn't exist on disk
        with client:
            resp = client.delete("/api/v1/projects/demo/characters/Alice/voice-reference")
        assert resp.status_code == 200
        assert pm.projects["demo"]["characters"]["Alice"]["voice_reference_audio"] == ""

    def test_voice_reference_safe_path_no_escape(self, monkeypatch, tmp_path):
        """路径逃逸文件不会被删除。"""
        client, pm = _full_client(monkeypatch, tmp_path)
        pm.projects["demo"]["characters"]["Alice"]["voice_reference_audio"] = "../outside/evil.mp3"
        outside = tmp_path / "outside" / "evil.mp3"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text("malicious")

        with client:
            resp = client.delete("/api/v1/projects/demo/characters/Alice/voice-reference")
        assert resp.status_code == 200
        assert pm.projects["demo"]["characters"]["Alice"]["voice_reference_audio"] == ""
        assert outside.exists()  # 不应该被删除


class TestCostumeReferences:
    """测试角色服装参考上传/删除端点。"""

    def test_upload_costume_creates_entry_and_file(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/costumes",
                data={"label": "王爷常服", "description": "玄色锦袍"},
                files={"file": ("robe.png", b"fake-png", "image/png")},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        costume = data["costume"]
        assert costume["label"] == "王爷常服"
        assert costume["description"] == "玄色锦袍"
        assert "image_path" in costume
        assert "id" in costume
        # 写入 project.json
        refs = pm.projects["demo"]["characters"]["Alice"].get("costume_references", [])
        assert len(refs) == 1
        assert refs[0]["label"] == "王爷常服"

    def test_delete_costume_removes_entry_and_file(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        # 先上传
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/costumes",
                data={"label": "战甲"},
                files={"file": ("armor.png", b"fake-png", "image/png")},
            )
        costume_id = resp.json()["costume"]["id"]
        image_path = resp.json()["costume"]["image_path"]
        assert (tmp_path / "demo" / image_path).exists()

        # 再删除
        with client:
            resp = client.delete(f"/api/v1/projects/demo/characters/Alice/costumes/{costume_id}")
        assert resp.status_code == 200
        refs = pm.projects["demo"]["characters"]["Alice"].get("costume_references", [])
        assert len(refs) == 0
        assert not (tmp_path / "demo" / image_path).exists()

    def test_delete_costume_404_on_wrong_id(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.delete("/api/v1/projects/demo/characters/Alice/costumes/nonexistent")
        assert resp.status_code == 404

    def test_delete_costume_cleans_variant_refs(self, monkeypatch, tmp_path):
        """删除服装时同时清理 variants 中对该 costume 的引用。"""
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/costumes",
                data={"label": "校服"},
                files={"file": ("school.png", b"png", "image/png")},
            )
        costume_id = resp.json()["costume"]["id"]
        # 手动添加一个引用该 costume 的 variant
        pm.projects["demo"]["characters"]["Alice"]["variants"] = [
            {"id": "v1", "label": "少年", "description": "", "character_sheet": "", "costume_reference_ids": [costume_id]}
        ]
        with client:
            resp = client.delete(f"/api/v1/projects/demo/characters/Alice/costumes/{costume_id}")
        assert resp.status_code == 200
        variants = pm.projects["demo"]["characters"]["Alice"].get("variants", [])
        assert costume_id not in variants[0]["costume_reference_ids"]


class TestCharacterVariants:
    """测试角色变体管理端点。"""

    def test_add_variant(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/variants",
                json={"label": "少年时期", "description": "十五六岁"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        v = data["variant"]
        assert v["label"] == "少年时期"
        assert v["description"] == "十五六岁"
        assert "id" in v
        # 写入 project.json
        variants = pm.projects["demo"]["characters"]["Alice"].get("variants", [])
        assert len(variants) == 1

    def test_add_variant_upserts_on_same_id(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/variants",
                json={"id": "v_young", "label": "少年", "description": "10岁"},
            )
        assert resp.status_code == 200
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/variants",
                json={"id": "v_young", "label": "少年时期", "description": "15岁"},
            )
        assert resp.status_code == 200
        variants = pm.projects["demo"]["characters"]["Alice"].get("variants", [])
        assert len(variants) == 1  # 同 id 覆盖
        assert variants[0]["label"] == "少年时期"

    def test_delete_variant_removes_entry(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/variants",
                json={"label": "战损装"},
            )
        variant_id = resp.json()["variant"]["id"]
        with client:
            resp = client.delete(f"/api/v1/projects/demo/characters/Alice/variants/{variant_id}")
        assert resp.status_code == 200
        variants = pm.projects["demo"]["characters"]["Alice"].get("variants", [])
        assert len(variants) == 0

    def test_delete_variant_cleans_sheet_file(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        # 添加 variant 并上传 sheet
        with client:
            client.post(
                "/api/v1/projects/demo/characters/Alice/variants",
                json={"id": "v_adult", "label": "成年"},
            )
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/variants/v_adult/sheet",
                files={"file": ("adult.png", b"png-data", "image/png")},
            )
        assert resp.status_code == 200
        sheet_path = resp.json()["path"]
        assert (tmp_path / "demo" / sheet_path).exists()

        # 删除 variant
        with client:
            resp = client.delete("/api/v1/projects/demo/characters/Alice/variants/v_adult")
        assert resp.status_code == 200
        assert not (tmp_path / "demo" / sheet_path).exists()

    def test_upload_variant_sheet_404_missing_variant(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/variants/nonexistent/sheet",
                files={"file": ("img.png", b"data", "image/png")},
            )
        assert resp.status_code == 404

    def test_add_variant_rejects_empty_label(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/variants",
                json={"label": ""},
            )
        assert resp.status_code == 400

    def test_variant_costume_ids_default_to_empty(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/variants",
                json={"label": "默认"},
            )
        assert resp.status_code == 200
        v = resp.json()["variant"]
        assert v["costume_reference_ids"] == []


class TestCostumeEdit:
    """测试服装参考编辑/替换端点。"""

    def test_patch_costume_label(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        # 先上传
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/costumes",
                data={"label": "旧标签", "description": "旧描述"},
                files={"file": ("c.png", b"png", "image/png")},
            )
        cid = resp.json()["costume"]["id"]
        # 编辑
        with client:
            resp = client.patch(
                f"/api/v1/projects/demo/characters/Alice/costumes/{cid}?label=新标签&description=新描述",
            )
        assert resp.status_code == 200
        refs = pm.projects["demo"]["characters"]["Alice"]["costume_references"]
        assert refs[0]["label"] == "新标签"
        assert refs[0]["description"] == "新描述"

    def test_replace_costume_image(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/costumes",
                data={"label": "原图"},
                files={"file": ("old.png", b"old", "image/png")},
            )
        cid = resp.json()["costume"]["id"]
        old_path = resp.json()["costume"]["image_path"]
        # 替换图片
        with client:
            resp = client.post(
                f"/api/v1/projects/demo/characters/Alice/costumes/{cid}/image",
                files={"file": ("new.png", b"newdata", "image/png")},
            )
        assert resp.status_code == 200
        refs = pm.projects["demo"]["characters"]["Alice"]["costume_references"]
        # 同扩展名时路径不变，但文件被新内容覆盖
        new_path = resp.json()["path"]
        assert (tmp_path / "demo" / new_path).exists()
        assert (tmp_path / "demo" / new_path).read_text() == "newdata"


class TestVariantEdit:
    """测试变体编辑/删除 sheet 端点。"""

    def test_patch_variant_label_and_costume_ids(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            client.post(
                "/api/v1/projects/demo/characters/Alice/costumes",
                data={"label": "校服"},
                files={"file": ("s.png", b"png", "image/png")},
            )
        cid = pm.projects["demo"]["characters"]["Alice"]["costume_references"][0]["id"]
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/variants",
                json={"id": "vx", "label": "旧变体", "description": "旧描述"},
            )
        assert resp.status_code == 200
        # 编辑
        with client:
            resp = client.patch(
                "/api/v1/projects/demo/characters/Alice/variants/vx",
                json={"label": "新变体", "description": "新描述", "costume_reference_ids": [cid]},
            )
        assert resp.status_code == 200
        variants = pm.projects["demo"]["characters"]["Alice"]["variants"]
        assert variants[0]["label"] == "新变体"
        assert variants[0]["description"] == "新描述"
        assert variants[0]["costume_reference_ids"] == [cid]

    def test_delete_variant_sheet_keeps_variant(self, monkeypatch, tmp_path):
        client, pm = _full_client(monkeypatch, tmp_path)
        with client:
            client.post(
                "/api/v1/projects/demo/characters/Alice/variants",
                json={"id": "v_keep", "label": "保留"},
            )
        with client:
            resp = client.post(
                "/api/v1/projects/demo/characters/Alice/variants/v_keep/sheet",
                files={"file": ("sheet.png", b"png", "image/png")},
            )
        sheet_path = resp.json()["path"]
        assert (tmp_path / "demo" / sheet_path).exists()
        # 删除 sheet
        with client:
            resp = client.delete("/api/v1/projects/demo/characters/Alice/variants/v_keep/sheet")
        assert resp.status_code == 200
        variants = pm.projects["demo"]["characters"]["Alice"]["variants"]
        assert len(variants) == 1  # variant 保留
        assert variants[0]["character_sheet"] == ""  # sheet 清空
        assert not (tmp_path / "demo" / sheet_path).exists()  # 文件删除
