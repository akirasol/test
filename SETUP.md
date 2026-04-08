# PDF しおり・リンク移行ツール - サーバー構築手順 (Windows)

## 1. 必要なソフトのインストール

以下の3つを順番にインストールしてください。すべて無料です。

### 1.1 Git

1. https://gitforwindows.org を開く
2. 「Download」ボタンをクリックしてインストーラーをダウンロード
3. インストーラーを実行し、すべてデフォルト設定のまま「Next」→「Install」

### 1.2 Node.js

1. https://nodejs.org を開く
2. **LTS** (推奨版) をダウンロード
3. インストーラーを実行し、すべてデフォルト設定のまま進める

### 1.3 Python

1. https://www.python.org/downloads/ を開く
2. 「Download Python 3.x.x」をクリック
3. インストーラーを実行
4. **重要: 最初の画面で「Add Python to PATH」に必ずチェックを入れる**
5. 「Install Now」をクリック

### 1.4 インストール確認

**インストール後、コマンドプロンプトを一度閉じて開き直してください** (PATHの反映に必要)。

コマンドプロンプトまたは PowerShell で以下を実行:

```
git --version
node --version
python --version
pip --version
```

4つともバージョン番号が表示されればOKです。

---

## 2. コードの取得

コマンドプロンプトを開き、配置したいフォルダに移動してから:

```
git clone https://github.com/akirasol/test.git
cd test
git checkout claude/pdf-bookmark-migration-aKLOD
```

---

## 3. 依存パッケージのインストール

```
pip install -r requirements.txt
npm install
```

---

## 4. 動作確認

### 4.1 サーバー起動

```
npm start
```

`PDF Migration Server running on http://localhost:3008` と表示されれば起動成功です。
**このウィンドウは閉じないでください** (閉じるとサーバーが止まります)。

### 4.2 ヘルスチェック

**もう1つ**コマンドプロンプトを開いて:

```
curl http://localhost:3008/api/health
```

`{"status":"ok"}` と返ればOKです。

> もし `curl` が使えない場合は、ブラウザで `http://localhost:3008/api/health` を開いて確認してください。

### 4.3 テスト用PDFで動作検証

```
python -c "import fitz; src=fitz.open(); [src.new_page() for _ in range(3)]; src.set_toc([[1,'Chapter 1',1],[1,'Chapter 2',2],[1,'Chapter 3',3]]); src.save('%TEMP%\\test_source.pdf'); src.close(); dst=fitz.open(); [dst.new_page() for _ in range(3)]; dst.save('%TEMP%\\test_dest.pdf'); dst.close(); print('テスト用PDF作成完了')"
```

```
curl -o "%TEMP%\test_output.pdf" -F "source=@%TEMP%\test_source.pdf" -F "dest=@%TEMP%\test_dest.pdf" -F "mode=both" http://localhost:3008/api/migrate
```

```
python -c "import fitz; doc=fitz.open('%TEMP%\\test_output.pdf'); toc=doc.get_toc(); print(f'しおり: {len(toc)} 件'); [print(f'  [{e[0]}] {e[1]} -> p.{e[2]}') for e in toc]; doc.close()"
```

以下のように表示されれば成功です:

```
しおり: 3 件
  [1] Chapter 1 -> p.1
  [1] Chapter 2 -> p.2
  [1] Chapter 3 -> p.3
```

> curl が使えない場合は、4.3 をスキップしてブラウザから直接テストしてもOKです (手順7参照)。

確認後、サーバーのウィンドウで Ctrl+C で停止してください。

---

## 5. PM2 で本番起動 (常時稼働)

```
npm install -g pm2
pm2 start ecosystem.config.js
```

コマンドプロンプトを閉じてもサーバーが動き続けます。

### PM2 基本操作

```
pm2 status                        # 状態確認
pm2 logs                          # ログ表示
pm2 restart pdf-migration-web     # 再起動
pm2 stop pdf-migration-web        # 停止
```

### Windows 再起動時に自動起動する設定 (任意)

```
npm install -g pm2-windows-startup
pm2-startup install
pm2 save
```

---

## 6. 他のPCからアクセスできるようにする

### 6.1 共有機のIPアドレスを確認

```
ipconfig
```

「IPv4 アドレス」の値 (例: `192.168.1.100`) をメモしてください。

### 6.2 ファイアウォールでポートを開放

1. スタートメニューで「Windows Defender ファイアウォール」を検索して開く
2. 左側の「詳細設定」をクリック
3. 「受信の規則」→ 右側の「新しい規則...」をクリック
4. 「ポート」を選択 → 次へ
5. 「TCP」を選択、「特定のローカルポート」に `3008` を入力 → 次へ
6. 「接続を許可する」→ 次へ
7. 3つのチェックすべてオン → 次へ
8. 名前を「PDF Migration Tool」として「完了」

---

## 7. ブラウザからアクセス

- 共有機自体: `http://localhost:3008`
- 他のPC: `http://共有機のIPアドレス:3008` (例: `http://192.168.1.100:3008`)

### 使い方

1. 「コピー元 PDF」を選択 (しおり・リンクが入っているPDF)
2. 「コピー先 PDF」を選択 (コピーしたいPDF)
3. コピー対象を選ぶ (両方 / しおりのみ / リンクのみ)
4. 「移行を実行」をクリック
5. 結果PDFが自動ダウンロードされる

---

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| `git` が認識されない | Git インストール後、コマンドプロンプトを開き直す |
| `python` が認識されない | Python インストール時に「Add Python to PATH」にチェックを忘れた。再インストールしてチェックを入れる |
| `node` が認識されない | Node.js インストール後、コマンドプロンプトを開き直す |
| `git clone` で認証エラー | リポジトリが private の場合、GitHub にログインが必要 |
| ポート 3008 が使えない | `set PORT=別の番号` → `npm start` で変更可能 |
| 他のPCからアクセスできない | 手順6.2のファイアウォール設定を確認 |
| `npm start` で Python エラー | `python --version` が動くか確認。動かなければ Python の PATH 設定を見直す |

---

## コードの更新方法

新しい変更が push されたら、共有機で以下を実行:

```
cd test
git pull origin claude/pdf-bookmark-migration-aKLOD
npm install
pip install -r requirements.txt
pm2 restart pdf-migration-web
```
