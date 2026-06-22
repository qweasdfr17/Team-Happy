"""角色管理路由（CRUD 由 _asset_router_factory 统一生成）。"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from fastapi import Body, File, Form, HTTPException, UploadFile

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


# ---- 角色服装参考上传/删除 ----


_COSTUME_IMAGE_EXTS: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".webp"})


@router.post("/projects/{project_name}/characters/{entry_name}/costumes")
async def upload_costume(
    project_name: str,
    entry_name: str,
    _user: CurrentUser,
    _t: Translator,
    file: UploadFile = File(...),
    label: str = Form(""),
    description: str = Form(""),
):
    """为项目角色上传服装参考图。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail=_t("missing_filename"))
    ext = Path(file.filename).suffix.lower()
    if ext not in _COSTUME_IMAGE_EXTS:
        raise HTTPException(
            status_code=400,
            detail=_t("unsupported_image_type", ext=ext, allowed=", ".join(sorted(_COSTUME_IMAGE_EXTS))),
        )
    try:
        content = await file.read()

        def _sync():
            import uuid

            manager = get_project_manager()
            project_dir = manager.get_project_path(project_name)
            project = manager.load_project(project_name)
            chars = project.get("characters") or {}
            if entry_name not in chars:
                raise KeyError(entry_name)

            # 生成唯一 costume id
            costume_id = f"costume_{uuid.uuid4().hex[:8]}"
            costumes_dir = project_dir / "characters" / "costumes"
            costumes_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{entry_name}_{costume_id}{ext}"
            file_path = costumes_dir / filename
            with open(file_path, "wb") as f:
                f.write(content)

            relative_path = f"characters/costumes/{filename}"
            costume_entry = {
                "id": costume_id,
                "label": label.strip() or f"服装 {costume_id[-4:]}",
                "description": description.strip(),
                "image_path": relative_path,
            }

            def _mutate(project_data):
                char_entry = project_data["characters"][entry_name]
                refs = char_entry.setdefault("costume_references", [])
                if not isinstance(refs, list):
                    refs = []
                    char_entry["costume_references"] = refs
                refs.append(costume_entry)

            with project_change_source("webui"):
                manager.update_project(project_name, _mutate)

            return {"success": True, "costume": costume_entry}

        return await asyncio.to_thread(_sync)
    except KeyError:
        raise HTTPException(status_code=404, detail=_t("character_not_found", name=entry_name))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_name))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("上传服装参考失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/projects/{project_name}/characters/{entry_name}/costumes/{costume_id}")
async def update_costume(
    project_name: str,
    entry_name: str,
    costume_id: str,
    _user: CurrentUser,
    _t: Translator,
    label: str | None = None,
    description: str | None = None,
):
    """编辑服装参考的 label / description。"""
    try:

        def _sync():
            manager = get_project_manager()
            project = manager.load_project(project_name)
            chars = project.get("characters") or {}
            if entry_name not in chars:
                raise KeyError(entry_name)
            refs: list = chars[entry_name].get("costume_references") or []
            target = next((r for r in refs if r.get("id") == costume_id), None)
            if target is None:
                raise ValueError(f"costume '{costume_id}' not found")

            def _mutate(project_data):
                entry = project_data["characters"][entry_name]
                for r in (entry.get("costume_references") or []):
                    if r.get("id") == costume_id:
                        if label is not None:
                            r["label"] = label.strip()
                        if description is not None:
                            r["description"] = description.strip()
                        break

            with project_change_source("webui"):
                manager.update_project(project_name, _mutate)
            return {"success": True}

        return await asyncio.to_thread(_sync)
    except KeyError:
        raise HTTPException(status_code=404, detail=_t("character_not_found", name=entry_name))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_name))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("修改服装参考失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/projects/{project_name}/characters/{entry_name}/costumes/{costume_id}/image")
async def replace_costume_image(
    project_name: str,
    entry_name: str,
    costume_id: str,
    _user: CurrentUser,
    _t: Translator,
    file: UploadFile = File(...),
):
    """替换服装参考图片。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail=_t("missing_filename"))
    ext = Path(file.filename).suffix.lower()
    if ext not in _COSTUME_IMAGE_EXTS:
        raise HTTPException(
            status_code=400,
            detail=_t("unsupported_image_type", ext=ext, allowed=", ".join(sorted(_COSTUME_IMAGE_EXTS))),
        )
    try:
        content = await file.read()

        def _sync():
            manager = get_project_manager()
            project_dir = manager.get_project_path(project_name)
            project = manager.load_project(project_name)
            chars = project.get("characters") or {}
            if entry_name not in chars:
                raise KeyError(entry_name)
            refs: list = chars[entry_name].get("costume_references") or []
            target = next((r for r in refs if r.get("id") == costume_id), None)
            if target is None:
                raise ValueError(f"costume '{costume_id}' not found")

            # 删除旧图片
            old_path = target.get("image_path", "")
            if old_path:
                old_file = project_dir / old_path
                try:
                    old_file.resolve().relative_to(project_dir.resolve())
                except ValueError:
                    pass
                else:
                    old_file.unlink(missing_ok=True)

            costumes_dir = project_dir / "characters" / "costumes"
            costumes_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{entry_name}_{costume_id}{ext}"
            file_path = costumes_dir / filename
            with open(file_path, "wb") as f:
                f.write(content)

            relative_path = f"characters/costumes/{filename}"

            def _mutate(project_data):
                entry = project_data["characters"][entry_name]
                for r in (entry.get("costume_references") or []):
                    if r.get("id") == costume_id:
                        r["image_path"] = relative_path
                        break

            with project_change_source("webui"):
                manager.update_project(project_name, _mutate)
            return {"success": True, "path": relative_path, "url": f"/api/v1/files/{project_name}/{relative_path}"}

        return await asyncio.to_thread(_sync)
    except KeyError:
        raise HTTPException(status_code=404, detail=_t("character_not_found", name=entry_name))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_name))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("替换服装图片失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/projects/{project_name}/characters/{entry_name}/costumes/{costume_id}")
async def delete_costume(
    project_name: str,
    entry_name: str,
    costume_id: str,
    _user: CurrentUser,
    _t: Translator,
):
    """删除项目角色的服装参考（清空字段 + 安全删除文件）。"""
    try:

        def _sync():
            manager = get_project_manager()
            project_dir = manager.get_project_path(project_name)
            project = manager.load_project(project_name)
            chars = project.get("characters") or {}
            if entry_name not in chars:
                raise KeyError(entry_name)

            char_entry = chars[entry_name]
            refs: list = char_entry.get("costume_references") or []
            target = next((r for r in refs if r.get("id") == costume_id), None)
            if target is None:
                raise ValueError(f"costume '{costume_id}' not found")

            image_path = target.get("image_path", "")
            if image_path:
                file_path = project_dir / image_path
                try:
                    file_path.resolve().relative_to(project_dir.resolve())
                except ValueError:
                    pass
                else:
                    file_path.unlink(missing_ok=True)

            def _mutate(project_data):
                entry = project_data["characters"][entry_name]
                entry["costume_references"] = [r for r in (entry.get("costume_references") or []) if r.get("id") != costume_id]
                # 从 variants 中也移除对该 costume 的引用
                variants: list = entry.get("variants") or []
                for v in variants:
                    ids: list = v.get("costume_reference_ids") or []
                    if costume_id in ids:
                        ids.remove(costume_id)

            with project_change_source("webui"):
                manager.update_project(project_name, _mutate)

            return {"success": True, "message": _t("costume_deleted", name=entry_name)}

        return await asyncio.to_thread(_sync)
    except KeyError:
        raise HTTPException(status_code=404, detail=_t("character_not_found", name=entry_name))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_name))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("删除服装参考失败")
        raise HTTPException(status_code=500, detail=str(exc))


# ---- 角色变体管理 ----


@router.post("/projects/{project_name}/characters/{entry_name}/variants")
async def add_variant(
    project_name: str,
    entry_name: str,
    _user: CurrentUser,
    _t: Translator,
    variant: dict[str, Any] | None = Body(default=None),
):
    """为项目角色添加变体（少年/成年/战损装等）。"""
    try:
        import uuid

        if not isinstance(variant, dict) or not variant:
            raise HTTPException(status_code=400, detail="variant 必须是非空对象")

        variant_label = str(variant.get("label", "")).strip()
        if not variant_label:
            raise HTTPException(status_code=400, detail="variant.label 不能为空")

        variant_id = str(variant.get("id", "")).strip() or f"variant_{uuid.uuid4().hex[:8]}"
        variant_desc = str(variant.get("description", "")).strip()
        costume_ids = variant.get("costume_reference_ids")
        if costume_ids is not None and not (isinstance(costume_ids, list) and all(isinstance(i, str) for i in costume_ids)):
            raise HTTPException(status_code=422, detail="costume_reference_ids must be a list of strings")

        def _sync():
            manager = get_project_manager()
            project = manager.load_project(project_name)
            chars = project.get("characters") or {}
            if entry_name not in chars:
                raise KeyError(entry_name)

            variant_entry = {
                "id": variant_id,
                "label": variant_label,
                "description": variant_desc,
                "character_sheet": "",
                "costume_reference_ids": list(costume_ids or []),
            }

            def _mutate(project_data):
                char_entry = project_data["characters"][entry_name]
                variants: list = char_entry.setdefault("variants", [])
                if not isinstance(variants, list):
                    variants = []
                    char_entry["variants"] = variants
                # 同 id 覆盖
                existing = next((i for i, v in enumerate(variants) if v.get("id") == variant_id), None)
                if existing is not None:
                    variants[existing] = variant_entry
                else:
                    variants.append(variant_entry)

            with project_change_source("webui"):
                manager.update_project(project_name, _mutate)

            return {"success": True, "variant": variant_entry}

        return await asyncio.to_thread(_sync)
    except KeyError:
        raise HTTPException(status_code=404, detail=_t("character_not_found", name=entry_name))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_name))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("添加角色变体失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/projects/{project_name}/characters/{entry_name}/variants/{variant_id}")
async def update_variant(
    project_name: str,
    entry_name: str,
    variant_id: str,
    _user: CurrentUser,
    _t: Translator,
    body: dict[str, Any] | None = Body(default=None),
):
    """编辑角色变体的 label / description / costume_reference_ids。（JSON body）"""
    try:
        updates = body or {}

        def _sync():
            manager = get_project_manager()
            project = manager.load_project(project_name)
            chars = project.get("characters") or {}
            if entry_name not in chars:
                raise KeyError(entry_name)
            variants: list = chars[entry_name].get("variants") or []
            target = next((v for v in variants if v.get("id") == variant_id), None)
            if target is None:
                raise ValueError(f"variant '{variant_id}' not found")

            def _mutate(project_data):
                entry = project_data["characters"][entry_name]
                for v in (entry.get("variants") or []):
                    if v.get("id") == variant_id:
                        if "label" in updates:
                            v["label"] = str(updates["label"]).strip()
                        if "description" in updates:
                            v["description"] = str(updates["description"]).strip()
                        if "costume_reference_ids" in updates:
                            ids = updates["costume_reference_ids"]
                            if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
                                raise HTTPException(status_code=422, detail="costume_reference_ids must be a list of strings")
                            v["costume_reference_ids"] = list(ids)
                        break

            with project_change_source("webui"):
                manager.update_project(project_name, _mutate)
            return {"success": True}

        return await asyncio.to_thread(_sync)
    except KeyError:
        raise HTTPException(status_code=404, detail=_t("character_not_found", name=entry_name))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_name))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("修改角色变体失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/projects/{project_name}/characters/{entry_name}/variants/{variant_id}/sheet")
async def delete_variant_sheet(
    project_name: str,
    entry_name: str,
    variant_id: str,
    _user: CurrentUser,
    _t: Translator,
):
    """删除角色变体的设计图（清空 sheet 字段 + 安全删除文件），保留变体本身。"""
    try:

        def _sync():
            manager = get_project_manager()
            project_dir = manager.get_project_path(project_name)
            project = manager.load_project(project_name)
            chars = project.get("characters") or {}
            if entry_name not in chars:
                raise KeyError(entry_name)
            variants: list = chars[entry_name].get("variants") or []
            target = next((v for v in variants if v.get("id") == variant_id), None)
            if target is None:
                raise ValueError(f"variant '{variant_id}' not found")

            sheet_path = target.get("character_sheet", "")
            if sheet_path:
                file_path = project_dir / sheet_path
                try:
                    file_path.resolve().relative_to(project_dir.resolve())
                except ValueError:
                    pass
                else:
                    file_path.unlink(missing_ok=True)

            def _mutate(project_data):
                entry = project_data["characters"][entry_name]
                for v in (entry.get("variants") or []):
                    if v.get("id") == variant_id:
                        v["character_sheet"] = ""
                        break

            with project_change_source("webui"):
                manager.update_project(project_name, _mutate)
            return {"success": True}

        return await asyncio.to_thread(_sync)
    except KeyError:
        raise HTTPException(status_code=404, detail=_t("character_not_found", name=entry_name))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_name))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("删除变体设计图失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/projects/{project_name}/characters/{entry_name}/variants/{variant_id}")
async def delete_variant(
    project_name: str,
    entry_name: str,
    variant_id: str,
    _user: CurrentUser,
    _t: Translator,
):
    """删除项目角色变体（清空字段 + 安全删除关联 sheet 文件）。"""
    try:

        def _sync():
            manager = get_project_manager()
            project_dir = manager.get_project_path(project_name)
            project = manager.load_project(project_name)
            chars = project.get("characters") or {}
            if entry_name not in chars:
                raise KeyError(entry_name)

            char_entry = chars[entry_name]
            variants: list = char_entry.get("variants") or []
            target = next((v for v in variants if v.get("id") == variant_id), None)
            if target is None:
                raise ValueError(f"variant '{variant_id}' not found")

            sheet_path = target.get("character_sheet", "")
            if sheet_path:
                file_path = project_dir / sheet_path
                try:
                    file_path.resolve().relative_to(project_dir.resolve())
                except ValueError:
                    pass
                else:
                    file_path.unlink(missing_ok=True)

            def _mutate(project_data):
                entry = project_data["characters"][entry_name]
                entry["variants"] = [v for v in (entry.get("variants") or []) if v.get("id") != variant_id]

            with project_change_source("webui"):
                manager.update_project(project_name, _mutate)

            return {"success": True, "message": _t("variant_deleted", name=entry_name)}

        return await asyncio.to_thread(_sync)
    except KeyError:
        raise HTTPException(status_code=404, detail=_t("character_not_found", name=entry_name))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_name))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("删除角色变体失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/projects/{project_name}/characters/{entry_name}/variants/{variant_id}/sheet")
async def upload_variant_sheet(
    project_name: str,
    entry_name: str,
    variant_id: str,
    _user: CurrentUser,
    _t: Translator,
    file: UploadFile = File(...),
):
    """为角色变体上传设计图。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail=_t("missing_filename"))
    ext = Path(file.filename).suffix.lower()
    if ext not in _COSTUME_IMAGE_EXTS:
        raise HTTPException(
            status_code=400,
            detail=_t("unsupported_image_type", ext=ext, allowed=", ".join(sorted(_COSTUME_IMAGE_EXTS))),
        )
    try:
        content = await file.read()

        def _sync():
            manager = get_project_manager()
            project_dir = manager.get_project_path(project_name)
            project = manager.load_project(project_name)
            chars = project.get("characters") or {}
            if entry_name not in chars:
                raise KeyError(entry_name)

            char_entry = chars[entry_name]
            variants: list = char_entry.get("variants") or []
            target = next((v for v in variants if v.get("id") == variant_id), None)
            if target is None:
                raise ValueError(f"variant '{variant_id}' not found")

            # 保存图片到 characters/variants/
            variants_dir = project_dir / "characters" / "variants"
            variants_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{entry_name}_{variant_id}{ext}"
            file_path = variants_dir / filename

            # 删除旧 sheet 文件
            old_sheet = target.get("character_sheet", "")
            if old_sheet:
                old_file = project_dir / old_sheet
                try:
                    old_file.resolve().relative_to(project_dir.resolve())
                except ValueError:
                    pass
                else:
                    old_file.unlink(missing_ok=True)

            with open(file_path, "wb") as f:
                f.write(content)

            relative_path = f"characters/variants/{filename}"

            def _mutate(project_data):
                entry = project_data["characters"][entry_name]
                for v in (entry.get("variants") or []):
                    if v.get("id") == variant_id:
                        v["character_sheet"] = relative_path
                        break

            with project_change_source("webui"):
                manager.update_project(project_name, _mutate)

            return {"success": True, "path": relative_path, "url": f"/api/v1/files/{project_name}/{relative_path}"}

        return await asyncio.to_thread(_sync)
    except KeyError:
        raise HTTPException(status_code=404, detail=_t("character_not_found", name=entry_name))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_name))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("上传变体设计图失败")
        raise HTTPException(status_code=500, detail=str(exc))
