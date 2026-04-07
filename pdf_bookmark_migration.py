#!/usr/bin/env python3
"""
PDFしおり・リンク移行ツール

しおり（ブックマーク）とリンク注釈を、あるPDFから別のPDFへコピーする。
ページ座標が同じレイアウトのPDF間での移行を想定。

使い方:
    python pdf_bookmark_migration.py source.pdf dest.pdf -o output.pdf
"""

import argparse
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


def migrate_pdf_bookmarks_and_links(
    source_path: str,
    dest_path: str,
    output_path: str,
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
    toc = extract_bookmarks(src_doc)
    stats["bookmarks_found"] = len(toc)
    stats["bookmarks_applied"] = apply_bookmarks(dst_doc, toc, len(dst_doc))

    # リンクの抽出と適用
    links_by_page = extract_links(src_doc)
    stats["links_found"] = sum(len(v) for v in links_by_page.values())
    applied, skipped = apply_links(dst_doc, links_by_page)
    stats["links_applied"] = applied
    stats["links_skipped"] = skipped

    # 保存
    dst_doc.save(output_path)
    dst_doc.close()
    src_doc.close()

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

    args = parser.parse_args()

    output_path = args.output if args.output else args.dest

    try:
        stats = migrate_pdf_bookmarks_and_links(args.source, args.dest, output_path)
    except FileNotFoundError as e:
        print(f"エラー: ファイルが見つかりません: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)

    print_stats(stats)
    print(f"出力: {output_path}")


if __name__ == "__main__":
    main()
