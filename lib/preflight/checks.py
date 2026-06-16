"""预检检查函数。

对 ad 模式剧本的 shots[] 逐镜头检查资产引用完整性，产出 PreflightReport。
不阻塞生成，不做写操作。
"""

from __future__ import annotations

from lib.asset_types import ASSET_SPECS
from lib.preflight.models import PreflightIssue, PreflightReport, Severity


def _has_sheet(assets: dict, name: str, sheet_field: str) -> bool:
    """检查资产是否存在且有对应 sheet 图路径（非空字符串）。"""
    entry = assets.get(name)
    if not isinstance(entry, dict):
        return False
    sheet = entry.get(sheet_field)
    return isinstance(sheet, str) and bool(sheet.strip())


def _has_any_product_images(products: dict, name: str) -> bool:
    """检查产品是否有任一种可用图（sheet 或 reference_images 原图）。"""
    entry = products.get(name)
    if not isinstance(entry, dict):
        return False
    # sheet
    sheet = entry.get("product_sheet")
    if isinstance(sheet, str) and sheet.strip():
        return True
    # reference_images（原图列表）
    refs = entry.get("reference_images")
    if isinstance(refs, list) and any(isinstance(r, str) and r.strip() for r in refs):
        return True
    return False


# ─── shot 字段 → 类型映射 ──────────────────────────────────────────────
# 按注入优先级排列：产品绝对优先（与 ad_units._REFERENCE_FIELDS 同口径）
_SHOT_REFERENCE_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("products_in_shot", "product", "products"),
    ("characters_in_shot", "character", "characters"),
    ("scenes", "scene", "scenes"),
    ("props", "prop", "props"),
)


def _collect_shot_names(shot: dict, field: str) -> list[str]:
    """从 shot[field] 提取非空字符串名列表。"""
    raw = shot.get(field)
    if not isinstance(raw, list):
        return []
    return [n for n in raw if isinstance(n, str) and n.strip()]


def _asset_label(spec) -> str:
    return spec.label_zh


def run_preflight(project: dict, script: dict) -> PreflightReport:
    """对 ad 模式剧本执行资产引用预检。

    Args:
        project: project.json 内容（dict）
        script: 剧本内容（scripts/episode_1.json），须含 shots[] 字段

    Returns:
        PreflightReport，按 severity 分组的问题列表
    """
    report = PreflightReport()

    shots = script.get("shots")
    if not isinstance(shots, list) or len(shots) == 0:
        report.add(PreflightIssue(
            Severity.warning,
            "NO_SHOTS",
            "剧本没有任何镜头（shots 为空）",
        ))
        return report

    # 预解析资产 bucket
    characters = project.get("characters")
    scenes = project.get("scenes")
    props = project.get("props")
    products = project.get("products")
    if not isinstance(characters, dict):
        characters = {}
    if not isinstance(scenes, dict):
        scenes = {}
    if not isinstance(props, dict):
        props = {}
    if not isinstance(products, dict):
        products = {}

    # ── 逐镜头检查 ──────────────────────────────────────────────────────
    for idx, shot in enumerate(shots):
        if not isinstance(shot, dict):
            continue
        shot_id = shot.get("shot_id", f"shots[{idx}]")
        loc = str(shot_id)

        # 收集本镜头所有引用名（按类型）
        refs_by_type: dict[str, list[str]] = {}
        all_names: list[str] = []
        for field, atype, _bkey in _SHOT_REFERENCE_FIELDS:
            names = _collect_shot_names(shot, field)
            refs_by_type[atype] = names
            all_names.extend(names)

        has_any_ref = any(refs_by_type.values())

        # ── 检查 1：引用不存在的资产（blocking） ────────────────────────
        for field, atype, bkey in _SHOT_REFERENCE_FIELDS:
            spec = ASSET_SPECS.get(atype)
            if spec is None:
                continue
            bucket = project.get(bkey)
            if not isinstance(bucket, dict):
                bucket = {}
            for name in refs_by_type[atype]:
                if name not in bucket:
                    report.add(PreflightIssue(
                        Severity.blocking,
                        "UNREGISTERED_REFERENCE",
                        f"镜头 {loc} 引用了不存在的{spec.label_zh}「{name}」"
                        f"（{spec.label_zh}库中未注册）",
                        location=loc,
                    ))

        # ── 检查 2：产品镜头缺图（blocking） ────────────────────────────
        product_names = refs_by_type.get("product", [])
        if product_names:
            for name in product_names:
                if name not in products:
                    continue  # 已由上面的 UNREGISTERED_REFERENCE 报
                if not _has_any_product_images(products, name):
                    report.add(PreflightIssue(
                        Severity.blocking,
                        "PRODUCT_WITHOUT_REF",
                        f"镜头 {loc} 的产品镜头引用了「{name}」，但该产品既无标准参考图"
                        f"（product_sheet）也无实拍原图（reference_images），"
                        f"保真注入将退化为纯文本",
                        location=loc,
                    ))

        # ── 检查 3：资产存在但缺 sheet（blocking for reference_video） ──
        for atype in ("character", "scene", "prop"):
            spec = ASSET_SPECS.get(atype)
            if spec is None:
                continue
            bucket = project.get(spec.bucket_key)
            if not isinstance(bucket, dict):
                bucket = {}
            for name in refs_by_type.get(atype, []):
                if name not in bucket:
                    continue  # 已由 UNREGISTERED_REFERENCE 报
                if not _has_sheet(bucket, name, spec.sheet_field):
                    report.add(PreflightIssue(
                        Severity.blocking,
                        "ASSET_WITHOUT_SHEET",
                        f"镜头 {loc} 引用的{spec.label_zh}「{name}」已注册但缺少设计图"
                        f"（{spec.sheet_field}），自动注入时将跳过该参考图",
                        location=loc,
                    ))

        # ── 检查 4：镜头无任何引用（warning） ────────────────────────────
        if not has_any_ref:
            report.add(PreflightIssue(
                Severity.warning,
                "NO_REFERENCES",
                f"镜头 {loc} 未引用任何角色/场景/道具/产品资产，"
                f"画面将完全依赖 prompt 文本描述",
                location=loc,
            ))

        # ── 检查 5：image_prompt / video_prompt 为空（warning） ──────────
        ip = shot.get("image_prompt")
        if _is_empty_prompt(ip):
            report.add(PreflightIssue(
                Severity.warning,
                "EMPTY_IMAGE_PROMPT",
                f"镜头 {loc} 的 image_prompt 为空",
                location=loc,
            ))
        vp = shot.get("video_prompt")
        if _is_empty_prompt(vp):
            report.add(PreflightIssue(
                Severity.warning,
                "EMPTY_VIDEO_PROMPT",
                f"镜头 {loc} 的 video_prompt 为空",
                location=loc,
            ))

        # ── 检查 6：prompt 文本里疑似有角色/场景/道具名但引用字段为空（info） ─
        _check_prompt_mentions(report, shot, loc, characters, scenes, props,
                               refs_by_type.get("character", []),
                               refs_by_type.get("scene", []),
                               refs_by_type.get("prop", []))

    # ── 检查 reference_units（ad + reference_video 路径） ────────────────
    ref_units = script.get("reference_units")
    if isinstance(ref_units, list):
        _check_reference_units(report, ref_units, characters, scenes, props, products)

    return report


def _is_empty_prompt(prompt) -> bool:
    """判断 prompt 是否为空：None、空串、空 dict、或结构化字段全空。"""
    if prompt is None:
        return True
    if isinstance(prompt, str):
        return not prompt.strip()
    if isinstance(prompt, dict):
        if not prompt:
            return True
        # 结构化 prompt：检查 scene 或 action 是否有内容
        scene = prompt.get("scene")
        action = prompt.get("action")
        scene_ok = isinstance(scene, str) and scene.strip()
        action_ok = isinstance(action, str) and action.strip()
        return not (scene_ok or action_ok)
    return False


def _check_prompt_mentions(
    report: PreflightReport,
    shot: dict,
    loc: str,
    characters: dict,
    scenes: dict,
    props: dict,
    char_refs: list[str],
    scene_refs: list[str],
    prop_refs: list[str],
) -> None:
    """检查 prompt 文本中是否疑似提到资产名但引用字段未注册（info 级别）。"""
    # 收集所有已注册的资产名
    registered: dict[str, str] = {}
    for name in characters:
        registered[name] = "角色"
    for name in scenes:
        registered[name] = "场景"
    for name in props:
        registered[name] = "道具"

    # 已通过引用字段正确注册的名
    referenced = set(char_refs + scene_refs + prop_refs)

    # 收集 prompt 文本
    text_parts: list[str] = []
    ip = shot.get("image_prompt")
    if isinstance(ip, dict):
        scene_text = ip.get("scene")
        if isinstance(scene_text, str):
            text_parts.append(scene_text)
    elif isinstance(ip, str):
        text_parts.append(ip)
    vp = shot.get("video_prompt")
    if isinstance(vp, dict):
        action = vp.get("action")
        if isinstance(action, str):
            text_parts.append(action)
    elif isinstance(vp, str):
        text_parts.append(vp)
    combined = "".join(text_parts)

    for name, label in registered.items():
        if name in combined and name not in referenced:
            report.add(PreflightIssue(
                Severity.info,
                "PROMPT_MENTIONS_UNREFERENCED",
                f"镜头 {loc} 的 prompt 文本中提到了{label}「{name}」，"
                f"但该镜头的引用字段中未包含此项，画面对应将缺少参考图注入",
                location=loc,
            ))


def _check_reference_units(
    report: PreflightReport,
    ref_units: list,
    characters: dict,
    scenes: dict,
    props: dict,
    products: dict,
) -> None:
    """检查 reference_units 中各 unit 引用的资产是否有可用图。"""
    for unit in ref_units:
        if not isinstance(unit, dict):
            continue
        unit_id = unit.get("unit_id", "?")
        loc = str(unit_id)
        references = unit.get("references")
        if not isinstance(references, list):
            continue

        for ref in references:
            if not isinstance(ref, dict):
                continue
            rtype = ref.get("type")
            rname = ref.get("name")
            if not isinstance(rname, str) or not rname.strip():
                continue

            if rtype == "product":
                bucket = products
                if rname not in bucket:
                    report.add(PreflightIssue(
                        Severity.blocking,
                        "UNIT_UNREGISTERED_REFERENCE",
                        f"Unit {loc} 引用了不存在的产品「{rname}」",
                        location=loc,
                    ))
                elif not _has_any_product_images(products, rname):
                    report.add(PreflightIssue(
                        Severity.warning,
                        "UNIT_PRODUCT_WITHOUT_REF",
                        f"Unit {loc} 引用的产品「{rname}」无可用参考图"
                        f"（product_sheet 与 reference_images 均为空），"
                        f"参考注入将退化为纯文本",
                        location=loc,
                    ))
            elif rtype in ASSET_SPECS:
                spec = ASSET_SPECS[rtype]
                bucket = project_bucket_for_type(characters, scenes, props, rtype)
                if rname not in bucket:
                    report.add(PreflightIssue(
                        Severity.blocking,
                        "UNIT_UNREGISTERED_REFERENCE",
                        f"Unit {loc} 引用了不存在的{spec.label_zh}「{rname}」",
                        location=loc,
                    ))
                elif not _has_sheet(bucket, rname, spec.sheet_field):
                    report.add(PreflightIssue(
                        Severity.blocking,
                        "UNIT_ASSET_WITHOUT_SHEET",
                        f"Unit {loc} 引用的{spec.label_zh}「{rname}」缺少设计图"
                        f"（{spec.sheet_field}），参考直出将跳过该参考图",
                        location=loc,
                    ))


def project_bucket_for_type(characters: dict, scenes: dict, props: dict, atype: str) -> dict:
    """按资产类型返回对应的 project bucket。"""
    if atype == "character":
        return characters
    elif atype == "scene":
        return scenes
    elif atype == "prop":
        return props
    return {}
