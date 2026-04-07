#!/usr/bin/env python3
"""
PDFしおり・リンク移行ツール

しおり（ブックマーク）とリンク注釈を、あるPDFから別のPDFへコピーする。
ページ座標が同じレイアウトのPDF間での移行を想定。

使い方:
    python pdf_bookmark_migration.py source.pdf dest.pdf -o output.pdf
"""

import argparse
import json
import sys

import fitz  # PyMuPDF


def extract_bookmarks(doc: fitz.Document) -> list:
    """PDFからしおり（目次/アウトライン）を抽出する。

    Returns:
        fitz.Document.get_toc() 形式のリスト
        [[level, title, page, dest_dict], ...]
    """
    return doc.get_toc(simple=False)


def extract_links(doc: fitz.Document) -> dict[int, list]:
    """PDFから全ページのリンク注釈を抽出する。

    Returns:
        {page_index: [link_dict, ...], ...}
    """
    links_by_page = {}
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        links = page.get_links()
        if links:
            links_by_page[page_idx] = links
    return links_by_page


def apply_bookmarks(doc: fitz.Document, toc: list, max_page: int) -> int:
    """しおりを対象PDFに設定する。

    ページ番号が対象PDFの範囲外のしおりはスキップする。

    Returns:
        適用されたしおりの数
    """
    if not toc:
        return 0

    filtered_toc = []
    for entry in toc:
        page_num = entry[2]
        if 1 <= page_num <= max_page:
            filtered_toc.append(entry)

    doc.set_toc(filtered_toc)
    return len(filtered_toc)


def apply_links(doc: fitz.Document, links_by_page: dict[int, list]) -> tuple[int, int]:
    """リンク注釈を対象PDFに設定する。

    ページ範囲外のリンクやリンク先はスキップする。

    Returns:
        (適用されたリンク数, スキップされたリンク数)
    """
    max_page = len(doc)
    applied = 0
    skipped = 0

    for page_idx, links in links_by_page.items():
        if page_idx >= max_page:
            skipped += len(links)
            continue

        page = doc[page_idx]
        for link in links:
            # 内部リンクのリンク先ページが範囲外ならスキップ
            if link.get("kind") == fitz.LINK_GOTO:
                dest_page = link.get("page", -1)
                if dest_page < 0 or dest_page >= max_page:
                    skipped += 1
                    continue

            page.insert_link(link)
            applied += 1

    return applied, skipped


COORD_TOLERANCE = 1.0  # 座標の許容誤差 (ポイント)


def _rect_close(r1: fitz.Rect, r2: fitz.Rect, tol: float = COORD_TOLERANCE) -> bool:
    """2つの矩形が許容誤差内で一致するか判定する。"""
    return (
        abs(r1.x0 - r2.x0) <= tol
        and abs(r1.y0 - r2.y0) <= tol
        and abs(r1.x1 - r2.x1) <= tol
        and abs(r1.y1 - r2.y1) <= tol
    )


def verify_migration(
    source_path: str,
    output_path: str,
    copy_bookmarks: bool,
    copy_links: bool,
) -> dict:
    """出力PDFを再度開き、ソースPDFと照合して移行結果を検証する。

    Returns:
        {
            "valid": bool,
            "errors": [str, ...],
            "bookmarks_verified": int,
            "links_verified": int,
        }
    """
    src_doc = fitz.open(source_path)
    out_doc = fitz.open(output_path)
    errors = []
    bookmarks_verified = 0
    links_verified = 0
    max_page = len(out_doc)

    # --- しおり検証 ---
    if copy_bookmarks:
        src_toc = src_doc.get_toc(simple=False)
        out_toc = out_doc.get_toc(simple=False)

        # ソース側で範囲内のしおりだけを期待値とする
        expected_toc = [e for e in src_toc if 1 <= e[2] <= max_page]

        if len(out_toc) != len(expected_toc):
            errors.append(
                f"しおり件数不一致: 期待 {len(expected_toc)} 件, 実際 {len(out_toc)} 件"
            )
        else:
            for i, (exp, act) in enumerate(zip(expected_toc, out_toc)):
                mismatches = []
                if exp[0] != act[0]:
                    mismatches.append(f"階層 {exp[0]}→{act[0]}")
                if exp[1] != act[1]:
                    mismatches.append(f"タイトル '{exp[1]}'→'{act[1]}'")
                if exp[2] != act[2]:
                    mismatches.append(f"ページ {exp[2]}→{act[2]}")
                if mismatches:
                    errors.append(f"しおり[{i+1}] {', '.join(mismatches)}")
                else:
                    bookmarks_verified += 1

    # --- リンク検証 ---
    if copy_links:
        for page_idx in range(min(len(src_doc), max_page)):
            src_links = src_doc[page_idx].get_links()
            out_links = out_doc[page_idx].get_links()

            # ソース側で範囲内の内部リンクだけを期待値とする
            expected_links = []
            for lnk in src_links:
                if lnk.get("kind") == fitz.LINK_GOTO:
                    dest_page = lnk.get("page", -1)
                    if dest_page < 0 or dest_page >= max_page:
                        continue
                expected_links.append(lnk)

            if len(out_links) != len(expected_links):
                errors.append(
                    f"ページ{page_idx+1} リンク件数不一致: "
                    f"期待 {len(expected_links)} 件, 実際 {len(out_links)} 件"
                )
                continue

            for j, (exp, act) in enumerate(zip(expected_links, out_links)):
                mismatches = []

                # 矩形位置
                exp_rect = fitz.Rect(exp.get("from", fitz.Rect()))
                act_rect = fitz.Rect(act.get("from", fitz.Rect()))
                if not _rect_close(exp_rect, act_rect):
                    mismatches.append(
                        f"位置 ({exp_rect.x0:.1f},{exp_rect.y0:.1f})-({exp_rect.x1:.1f},{exp_rect.y1:.1f})"
                        f"→({act_rect.x0:.1f},{act_rect.y0:.1f})-({act_rect.x1:.1f},{act_rect.y1:.1f})"
                    )

                # リンク種別
                if exp.get("kind") != act.get("kind"):
                    mismatches.append(f"種別 {exp.get('kind')}→{act.get('kind')}")

                # 内部リンク: リンク先ページ
                elif exp.get("kind") == fitz.LINK_GOTO:
                    if exp.get("page") != act.get("page"):
                        mismatches.append(f"リンク先ページ {exp.get('page')}→{act.get('page')}")

                # URLリンク: URL文字列
                elif exp.get("kind") == fitz.LINK_URI:
                    if exp.get("uri") != act.get("uri"):
                        mismatches.append(f"URL '{exp.get('uri')}'→'{act.get('uri')}'")

                if mismatches:
                    errors.append(
                        f"ページ{page_idx+1} リンク[{j+1}] {', '.join(mismatches)}"
                    )
                else:
                    links_verified += 1

    src_doc.close()
    out_doc.close()

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "bookmarks_verified": bookmarks_verified,
        "links_verified": links_verified,
    }


def migrate_pdf_bookmarks_and_links(
    source_path: str,
    dest_path: str,
    output_path: str,
    copy_bookmarks: bool = True,
    copy_links: bool = True,
) -> dict:
    """メイン処理: ソースPDFからしおりとリンクを抽出し、対象PDFに適用する。

    Returns:
        処理結果の統計情報
    """
    src_doc = fitz.open(source_path)
    dst_doc = fitz.open(dest_path)

    stats = {
        "source_pages": len(src_doc),
        "dest_pages": len(dst_doc),
        "bookmarks_found": 0,
        "bookmarks_applied": 0,
        "links_found": 0,
        "links_applied": 0,
        "links_skipped": 0,
    }

    # しおりの抽出と適用
    if copy_bookmarks:
        toc = extract_bookmarks(src_doc)
        stats["bookmarks_found"] = len(toc)
        stats["bookmarks_applied"] = apply_bookmarks(dst_doc, toc, len(dst_doc))

    # リンクの抽出と適用
    if copy_links:
        links_by_page = extract_links(src_doc)
        stats["links_found"] = sum(len(v) for v in links_by_page.values())
        applied, skipped = apply_links(dst_doc, links_by_page)
        stats["links_applied"] = applied
        stats["links_skipped"] = skipped

    # 保存
    dst_doc.save(output_path)
    dst_doc.close()
    src_doc.close()

    # 検証: 出力PDFを再度開いてソースと照合
    verification = verify_migration(
        source_path, output_path, copy_bookmarks, copy_links
    )
    stats["verification"] = verification

    return stats


def print_stats(stats: dict) -> None:
    """処理結果を表示する。"""
    print("=== PDF しおり・リンク移行結果 ===")
    print(f"ソースPDF: {stats['source_pages']} ページ")
    print(f"対象PDF:   {stats['dest_pages']} ページ")
    print(f"しおり:    {stats['bookmarks_applied']}/{stats['bookmarks_found']} 件適用")
    print(f"リンク:    {stats['links_applied']}/{stats['links_found']} 件適用", end="")
    if stats["links_skipped"] > 0:
        print(f" ({stats['links_skipped']} 件スキップ)")
    else:
        print()

    v = stats.get("verification", {})
    if v:
        bm_ok = v.get("bookmarks_verified", 0)
        ln_ok = v.get("links_verified", 0)
        if v.get("valid"):
            print(f"検証:      OK (しおり {bm_ok} 件, リンク {ln_ok} 件 一致)")
        else:
            print(f"検証:      NG")
            for err in v.get("errors", []):
                print(f"  - {err}")

    print("================================")


def main():
    parser = argparse.ArgumentParser(
        description="PDFしおり・リンク移行ツール: ソースPDFのしおりとリンクを別のPDFにコピーします。"
    )
    parser.add_argument("source", help="コピー元のPDFファイル")
    parser.add_argument("dest", help="コピー先のPDFファイル")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="出力先のPDFファイル (省略時は dest を上書き)",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--bookmarks-only",
        action="store_true",
        help="しおりのみコピー (リンクはコピーしない)",
    )
    mode_group.add_argument(
        "--links-only",
        action="store_true",
        help="リンクのみコピー (しおりはコピーしない)",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="結果をJSON形式で出力",
    )

    args = parser.parse_args()

    output_path = args.output if args.output else args.dest
    copy_bookmarks = not args.links_only
    copy_links = not args.bookmarks_only

    try:
        stats = migrate_pdf_bookmarks_and_links(
            args.source, args.dest, output_path,
            copy_bookmarks=copy_bookmarks,
            copy_links=copy_links,
        )
    except FileNotFoundError as e:
        print(f"エラー: ファイルが見つかりません: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json_output:
        print(json.dumps(stats))
    else:
        print_stats(stats)
        print(f"出力: {output_path}")


if __name__ == "__main__":
    main()
