"""角色管理路由（CRUD 由 _asset_router_factory 统一生成）。"""

import asyncio
import logging
from pathlib import Path

from fastapi import File, HTTPException, UploadFile

from lib.app_data_dir import app_data_dir
from lib.i18n import Translator
from lib.project_change_hints import project_change_source
from lib.project_manager import ProjectManager
from server.auth import CurrentUser
from server.routers._asset_router_factory import build_asset_router

logger = logging.getLogger(__name__)

pm = ProjectManager(app_data_dir())


def get_project_manager() -> ProjectManager:
    return pm


# late-binding 必需：测试通过 monkeypatch.setattr(characters, "get_project_manager", ...) 替换模块属性
router = build_asset_router(asset_type="character", pm_getter=lambda: get_project_manager())  # noqa: PLW0108

# ---- 角色声音参考上传/删除 ----

_VOICE_AUDIO_EXTS: frozenset[str] = frozenset({".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"})
_VOICE_MAX_BYTES: int = 20 * 1024 * 1024  # 20 MB


@router.post("/projects/{project_name}/characters/{entry_name}/voice-reference")
async def upload_voice_reference(
    project_name: str,
    entry_name: str,
    _user: CurrentUser,
    _t: Translator,
    file: UploadFile = File(...),
):
    """为项目角色上传声音参考音频。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail=_t("missing_filename"))
    ext = Path(file.filename).suffix.lower()
    if ext not in _VOICE_AUDIO_EXTS:
        raise HTTPException(
            status_code=400,
            detail=_t("unsupported_audio_type", ext=ext, allowed=", ".join(sorted(_VOICE_AUDIO_EXTS))),
        )
    try:
        content = await file.read()
        if len(content) > _VOICE_MAX_BYTES:
            raise HTTPException(status_code=413, detail=_t("audio_too_large"))

        def _sync():
            manager = get_project_manager()
            project_dir = manager.get_project_path(project_name)
            # 校验角色存在
            project = manager.load_project(project_name)
            chars = project.get("characters") or {}
            if entry_name not in chars:
                raise KeyError(entry_name)
            # 保存音频到 characters/voice_refs/
            voice_dir = project_dir / "characters" / "voice_refs"
            voice_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{entry_name}{ext}"
            file_path = voice_dir / filename
            # 如果已有旧音频，先删除
            old_path = chars[entry_name].get("voice_reference_audio", "")
            if old_path:
                old_file = project_dir / old_path
                try:
                    old_file.resolve().relative_to(project_dir.resolve())
                except ValueError:
                    pass
                else:
                    old_file.unlink(missing_ok=True)
            with open(file_path, "wb") as f:
                f.write(content)
            relative_path = f"characters/voice_refs/{filename}"
            with project_change_source("webui"):
                manager.update_character_voice_reference(project_name, entry_name, relative_path)
            return {
                "success": True,
                "path": relative_path,
                "url": f"/api/v1/files/{project_name}/{relative_path}",
            }

        return await asyncio.to_thread(_sync)
    except KeyError:
        raise HTTPException(status_code=404, detail=_t("character_not_found", name=entry_name))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_name))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("上传声音参考失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/projects/{project_name}/characters/{entry_name}/voice-reference")
async def delete_voice_reference(
    project_name: str,
    entry_name: str,
    _user: CurrentUser,
    _t: Translator,
):
    """删除项目角色的声音参考音频（清空字段 + 安全删除文件）。"""
    try:

        def _sync():
            manager = get_project_manager()
            with project_change_source("webui"):
                manager.clear_character_voice_reference(project_name, entry_name)
            return {"success": True, "message": _t("voice_reference_deleted", name=entry_name)}

        return await asyncio.to_thread(_sync)
    except KeyError:
        raise HTTPException(status_code=404, detail=_t("character_not_found", name=entry_name))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_name))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("删除声音参考失败")
        raise HTTPException(status_code=500, detail=str(exc))
