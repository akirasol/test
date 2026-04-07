const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs/promises');
const fsSync = require('fs');
const { execFile } = require('child_process');
const { v4: uuidv4 } = require('uuid');

const app = express();

const PORT = process.env.PORT || 3000;
const UPLOAD_MAX_SIZE_MB = parseInt(process.env.UPLOAD_MAX_SIZE_MB || '50', 10);
const PYTHON_PATH = process.env.PYTHON_PATH || 'python3';
const SCRIPT_TIMEOUT_MS = parseInt(process.env.SCRIPT_TIMEOUT_MS || '60000', 10);
const UPLOADS_DIR = path.join(__dirname, 'uploads');
const SCRIPT_PATH = path.join(__dirname, 'pdf_bookmark_migration.py');

// uploads ディレクトリ作成
fsSync.mkdirSync(UPLOADS_DIR, { recursive: true });

// Multer 設定
const storage = multer.diskStorage({
  destination: (req, _file, cb) => {
    if (!req.uploadDir) {
      req.uploadDir = path.join(UPLOADS_DIR, uuidv4());
      fsSync.mkdirSync(req.uploadDir, { recursive: true });
    }
    cb(null, req.uploadDir);
  },
  filename: (_req, file, cb) => {
    cb(null, file.fieldname + '.pdf');
  },
});

const fileFilter = (_req, file, cb) => {
  const ext = path.extname(file.originalname).toLowerCase();
  if (ext !== '.pdf') {
    return cb(new Error('PDF ファイルのみアップロードできます'));
  }
  cb(null, true);
};

const upload = multer({
  storage,
  fileFilter,
  limits: { fileSize: UPLOAD_MAX_SIZE_MB * 1024 * 1024 },
});

const uploadFields = upload.fields([
  { name: 'source', maxCount: 1 },
  { name: 'dest', maxCount: 1 },
]);

// 静的ファイル配信
app.use(express.static(path.join(__dirname, 'public')));
app.disable('x-powered-by');

// ヘルスチェック
app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok' });
});

// メインAPI
app.post('/api/migrate', (req, res) => {
  uploadFields(req, res, async (uploadErr) => {
    const uploadDir = req.uploadDir;

    // クリーンアップ関数
    const cleanup = async () => {
      if (uploadDir) {
        try {
          await fs.rm(uploadDir, { recursive: true, force: true });
        } catch (_e) { /* ignore */ }
      }
    };

    try {
      // Multer エラー処理
      if (uploadErr) {
        if (uploadErr.code === 'LIMIT_FILE_SIZE') {
          return res.status(413).json({ error: `ファイルサイズが上限 (${UPLOAD_MAX_SIZE_MB}MB) を超えています` });
        }
        return res.status(400).json({ error: uploadErr.message });
      }

      // ファイル存在チェック
      if (!req.files || !req.files.source || !req.files.dest) {
        return res.status(400).json({ error: 'ソースPDFとコピー先PDFの両方をアップロードしてください' });
      }

      const sourcePath = req.files.source[0].path;
      const destPath = req.files.dest[0].path;
      const outputPath = path.join(uploadDir, 'output.pdf');

      // モード判定
      const mode = req.body.mode || 'both';
      const args = [SCRIPT_PATH, sourcePath, destPath, '-o', outputPath, '--json'];

      if (mode === 'bookmarks') {
        args.push('--bookmarks-only');
      } else if (mode === 'links') {
        args.push('--links-only');
      }

      // Python 実行
      const stats = await new Promise((resolve, reject) => {
        execFile(PYTHON_PATH, args, { timeout: SCRIPT_TIMEOUT_MS }, (err, stdout, stderr) => {
          if (err) {
            const msg = stderr ? stderr.trim() : err.message;
            return reject(new Error(msg));
          }
          try {
            resolve(JSON.parse(stdout));
          } catch (_e) {
            reject(new Error('スクリプトの出力を解析できませんでした'));
          }
        });
      });

      // 結果PDFを返却
      res.setHeader('X-Migration-Stats', JSON.stringify(stats));
      res.setHeader('Content-Type', 'application/pdf');
      res.setHeader('Content-Disposition', 'attachment; filename="migrated.pdf"');

      const fileStream = fsSync.createReadStream(outputPath);
      fileStream.pipe(res);
      fileStream.on('end', cleanup);
      fileStream.on('error', (streamErr) => {
        cleanup();
        if (!res.headersSent) {
          res.status(500).json({ error: streamErr.message });
        }
      });

    } catch (err) {
      await cleanup();
      if (!res.headersSent) {
        res.status(500).json({ error: err.message || '処理中にエラーが発生しました' });
      }
    }
  });
});

// 定期クリーンアップ (5分ごとに15分以上古いディレクトリを削除)
const CLEANUP_INTERVAL_MS = 5 * 60 * 1000;
const MAX_AGE_MS = 15 * 60 * 1000;

setInterval(async () => {
  try {
    const entries = await fs.readdir(UPLOADS_DIR, { withFileTypes: true });
    const now = Date.now();
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const dirPath = path.join(UPLOADS_DIR, entry.name);
      const stat = await fs.stat(dirPath);
      if (now - stat.mtimeMs > MAX_AGE_MS) {
        await fs.rm(dirPath, { recursive: true, force: true });
      }
    }
  } catch (_e) { /* ignore */ }
}, CLEANUP_INTERVAL_MS);

app.listen(PORT, () => {
  console.log(`PDF Migration Server running on http://localhost:${PORT}`);
});
