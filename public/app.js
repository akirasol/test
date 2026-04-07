(() => {
  const form = document.getElementById('migrate-form');
  const submitBtn = document.getElementById('submit-btn');
  const progressEl = document.getElementById('progress');
  const resultsEl = document.getElementById('results');
  const errorEl = document.getElementById('error');
  const errorMsg = document.getElementById('error-message');

  // ファイル選択時に名前を表示
  ['source', 'dest'].forEach((name) => {
    const input = document.getElementById(name);
    const drop = document.getElementById(name + '-drop');
    const nameEl = document.getElementById(name + '-name');

    input.addEventListener('change', () => {
      if (input.files.length > 0) {
        nameEl.textContent = input.files[0].name;
        drop.classList.add('has-file');
      } else {
        nameEl.textContent = '';
        drop.classList.remove('has-file');
      }
    });

    // ドラッグ&ドロップ視覚フィードバック
    drop.addEventListener('dragover', (e) => {
      e.preventDefault();
      drop.classList.add('dragover');
    });
    drop.addEventListener('dragleave', () => {
      drop.classList.remove('dragover');
    });
    drop.addEventListener('drop', () => {
      drop.classList.remove('dragover');
    });
  });

  function showProgress() {
    progressEl.classList.remove('hidden');
    resultsEl.classList.add('hidden');
    errorEl.classList.add('hidden');
    submitBtn.disabled = true;
  }

  function hideProgress() {
    progressEl.classList.add('hidden');
    submitBtn.disabled = false;
  }

  function showError(msg) {
    errorMsg.textContent = msg;
    errorEl.classList.remove('hidden');
    resultsEl.classList.add('hidden');
  }

  function displayStats(stats) {
    document.getElementById('stat-source-pages').textContent = stats.source_pages + ' ページ';
    document.getElementById('stat-dest-pages').textContent = stats.dest_pages + ' ページ';
    document.getElementById('stat-bookmarks').textContent =
      stats.bookmarks_applied + ' / ' + stats.bookmarks_found + ' 件適用';

    let linksText = stats.links_applied + ' / ' + stats.links_found + ' 件適用';
    if (stats.links_skipped > 0) {
      linksText += ' (' + stats.links_skipped + ' 件スキップ)';
    }
    document.getElementById('stat-links').textContent = linksText;

    resultsEl.classList.remove('hidden');
    errorEl.classList.add('hidden');
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const sourceFile = document.getElementById('source').files[0];
    const destFile = document.getElementById('dest').files[0];

    if (!sourceFile || !destFile) {
      showError('ソースPDFとコピー先PDFの両方を選択してください');
      return;
    }

    const formData = new FormData();
    formData.append('source', sourceFile);
    formData.append('dest', destFile);
    formData.append('mode', document.querySelector('input[name="mode"]:checked').value);

    showProgress();

    try {
      const response = await fetch('/api/migrate', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        let errData;
        try {
          errData = await response.json();
        } catch (_e) {
          throw new Error('サーバーエラー (' + response.status + ')');
        }
        throw new Error(errData.error || 'Migration failed');
      }

      // 統計ヘッダーを取得
      const statsHeader = response.headers.get('X-Migration-Stats');
      if (statsHeader) {
        try {
          displayStats(JSON.parse(statsHeader));
        } catch (_e) { /* ignore */ }
      }

      // PDF をダウンロード
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = destFile.name.replace(/\.pdf$/i, '_migrated.pdf');
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);

    } catch (err) {
      showError(err.message);
    } finally {
      hideProgress();
    }
  });
})();
