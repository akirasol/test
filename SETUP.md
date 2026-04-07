# PDF しおり・リンク移行ツール - サーバー構築手順

## 1. 前提条件の確認

共有機で以下のコマンドを実行し、必要なソフトがインストールされていることを確認してください。

```bash
git --version      # Git
node --version     # Node.js (v18以上)
python3 --version  # Python (3.8以上)
pip --version      # pip
```

いずれかが `command not found` になる場合は、先にインストールが必要です。

---

## 2. コードの取得

```bash
git clone https://github.com/akirasol/test.git
cd test
git checkout claude/pdf-bookmark-migration-aKLOD
```

---

## 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt   # Python (PyMuPDF)
npm install                       # Node.js (Express, multer 等)
```

---

## 4. 動作確認

### 4.1 サーバー起動

```bash
npm start
```

`PDF Migration Server running on http://localhost:3008` と表示されれば起動成功です。

### 4.2 ヘルスチェック

別のターミナルを開いて:

```bash
curl http://localhost:3008/api/health
```

`{"status":"ok"}` と返ればOKです。

### 4.3 テスト用PDFで動作検証

```bash
# テスト用PDF作成
python3 -c "
import fitz
src = fitz.open()
for i in range(3):
    p = src.new_page()
    tw = fitz.TextWriter(p.rect)
    tw.append((72,100), f'Page {i+1}', fontsize=20)
    tw.write_text(p)
src.set_toc([[1,'Chapter 1',1],[1,'Chapter 2',2],[1,'Chapter 3',3]])
src.save('/tmp/test_source.pdf')
src.close()
dst = fitz.open()
for i in range(3):
    dst.new_page()
dst.save('/tmp/test_dest.pdf')
dst.close()
print('テスト用PDF作成完了')
"

# API でコピー実行
curl -o /tmp/test_output.pdf \
  -F "source=@/tmp/test_source.pdf" \
  -F "dest=@/tmp/test_dest.pdf" \
  -F "mode=both" \
  http://localhost:3008/api/migrate

# 結果確認
python3 -c "
import fitz
doc = fitz.open('/tmp/test_output.pdf')
toc = doc.get_toc()
print(f'しおり: {len(toc)} 件')
for e in toc:
    print(f'  [{e[0]}] {e[1]} -> p.{e[2]}')
doc.close()
"
```

以下のように表示されれば成功です:

```
しおり: 3 件
  [1] Chapter 1 -> p.1
  [1] Chapter 2 -> p.2
  [1] Chapter 3 -> p.3
```

確認後、`npm start` を Ctrl+C で停止してください。

---

## 5. PM2 で本番起動 (常時稼働)

```bash
npm install -g pm2          # 初回のみ
pm2 start ecosystem.config.js
```

ターミナルを閉じてもサーバーが動き続けます。

### PM2 基本操作

```bash
pm2 status                        # 状態確認
pm2 logs                          # ログ表示
pm2 restart pdf-migration-web     # 再起動
pm2 stop pdf-migration-web        # 停止
```

### サーバー再起動時に自動起動する設定 (任意)

```bash
pm2 startup       # 表示されたコマンドをコピーして実行
pm2 save          # 現在の状態を保存
```

---

## 6. ブラウザからアクセス

- 共有機自体: `http://localhost:3008`
- 他のPC: `http://共有機のIPアドレス:3008`

---

## 7. 使い方

1. 「コピー元 PDF」を選択 (しおり・リンクが入っているPDF)
2. 「コピー先 PDF」を選択 (コピーしたいPDF)
3. コピー対象を選ぶ (両方 / しおりのみ / リンクのみ)
4. 「移行を実行」をクリック
5. 結果PDFが自動ダウンロードされる

---

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| `git clone` で認証エラー | リポジトリが private の場合、GitHub アカウントでの認証が必要。`gh auth login` またはパーソナルアクセストークンを使用 |
| ポート 3008 が使えない | `PORT=別の番号 npm start` で変更可能。PM2の場合は `ecosystem.config.js` の `PORT` を変更 |
| 他のPCからアクセスできない | 共有機のファイアウォールでポート 3008 を許可する |
| `python3: command not found` | Python がインストールされていない。管理者に依頼 |
| `npm start` でエラー | `node --version` が v18 未満なら Node.js をアップデート |

---

## コードの更新方法

新しい変更が push されたら、共有機で以下を実行:

```bash
cd test
git pull origin claude/pdf-bookmark-migration-aKLOD
npm install                       # 依存が変わった場合
pip install -r requirements.txt   # 依存が変わった場合
pm2 restart pdf-migration-web     # サーバー再起動
```
