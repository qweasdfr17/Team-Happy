"""从 TXT 目录批量导入参考生视频成品提示词候选。

用法:
    uv run python scripts/import_prompt_txts.py --input "E:\\提示词海量" --output "projects/.prompt_library/import_candidates.json"
"""

import argparse
import sys
from pathlib import Path

# 确保 lib/ 在 sys.path
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from lib.prompt_library.importer import build_candidates, scan_txt_files, write_import_candidates


def main():
    parser = argparse.ArgumentParser(description="导入 TXT 提示词为 Prompt Library 候选")
    parser.add_argument("--input", required=True, help="TXT 文件根目录路径")
    parser.add_argument("--output", required=True, help="输出 JSON 文件路径")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_path = Path(args.output)

    # 扫描
    print(f"扫描目录: {input_dir}")
    txt_files = scan_txt_files(input_dir)
    print(f"找到 {len(txt_files)} 个 .txt 文件")

    if not txt_files:
        print("未找到任何 .txt 文件，退出。")
        sys.exit(0)

    # 构建候选
    candidates, stats = build_candidates(txt_files, input_dir)

    # 输出
    write_import_candidates(candidates, output_path)

    # 统计
    print(f"\n导入统计:")
    print(f"  扫描 TXT 总数: {stats['total']}")
    print(f"  生成候选数:   {stats['candidates']}")
    print(f"  空文件跳过:   {stats['empty_skipped']}")
    print(f"  输出文件:     {output_path.resolve()}")

    # 标签分布
    tag_counts: dict[str, int] = {}
    for c in candidates:
        for t in c["tags"]:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    print(f"\n标签分布:")
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
        print(f"  {tag}: {count}")


if __name__ == "__main__":
    main()
