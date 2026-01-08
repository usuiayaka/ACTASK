// === API エンドポイント（環境別） ===
// ローカル・Cloud Run 両方で機能するように相対パスを使用
const API_URL = "/api/call-cranberry";
const COORDS_API_URL = "/api/cranberry/mask_coords"; // 追加: 座標取得API
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const video = document.getElementById("cameraVideo");
const logArea = document.getElementById("logArea");
const overlayCanvas = document.getElementById("overlayCanvas");
const videoPlaceholder = document.getElementById("videoPlaceholder");
let stream = null;
let intervalId = null; // 10秒ごとの送信制御用
let maskCoordinates = []; // 追加: バックエンドから取得した座標を保持

// === 新機能: カレンダー座標の取得 ===
async function fetchMaskCoordinates() {
  try {
    const response = await fetch(COORDS_API_URL);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    if (data && data.coordinates) {
      maskCoordinates = data.coordinates;
      appendLog(
        `✅ マスク座標をバックエンドから取得しました (${maskCoordinates.length}個)。`
      );
    }
  } catch (error) {
    appendLog(`❌ 座標取得エラー: ${error.message}`);
  }
}

// === 新機能: Canvas上に座標を赤枠として描画 (requestAnimationFrameを削除) ===
function drawMasks() {
  const canvas = overlayCanvas;
  const ctx = canvas.getContext("2d");

  // Canvasをクリア
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (maskCoordinates.length === 0) return;

  // ビデオの幅と高さを取得（Canvasのサイズ）
  const videoWidth = canvas.width;
  const videoHeight = canvas.height;

  // 描画スタイル設定
  ctx.strokeStyle = "rgba(255, 0, 0, 0.8)"; // 赤枠
  ctx.lineWidth = 3; // 見やすく太くしました
  ctx.font = "24px Arial"; // フォントサイズを見やすくしました
  ctx.fillStyle = "rgba(255, 0, 0, 0.8)";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle"; // テキストを中央寄せにする

  maskCoordinates.forEach((mask) => {
    // 修正されたPythonコードに合わせ、mask.box が配列であることを前提とする
    const [x_min_norm, y_min_norm, x_max_norm, y_max_norm] = mask.box;

    // 正規化座標 (0.0-1.0) を絶対座標に変換
    const x = x_min_norm * videoWidth;
    const y = y_min_norm * videoHeight;
    const w = (x_max_norm - x_min_norm) * videoWidth;
    const h = (y_max_norm - y_min_norm) * videoHeight;

    // 赤い四角形を描画
    ctx.strokeRect(x, y, w, h);

    // マス目番号を表示 (四角形の中心に配置)
    ctx.fillText(mask.day, x + w / 2, y + h / 2);
  });
}

// 検出を開始する
async function startDetection() {
  if (!stream) {
    appendLog("🔵 カメラを起動中です...");
    try {
      // 環境に応じて背面カメラを優先
      stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "environment",
        },
      });
      video.srcObject = stream;
      videoPlaceholder.style.display = "none";
      video.play();

      // 映像のメタデータが読み込まれるのを待つ
      await new Promise((resolve) => (video.onloadedmetadata = resolve));

      // Canvasのサイズをビデオに合わせる
      overlayCanvas.width = video.videoWidth;
      overlayCanvas.height = video.videoHeight;

      // === 新機能: カメラ起動と同時に座標を取得し、描画を開始 ===
      await fetchMaskCoordinates();
      // =========================================================
    } catch (err) {
      appendLog("❌ カメラのアクセスに失敗しました: " + err.name);
      startBtn.disabled = false;
      stopBtn.disabled = true;
      return;
    }
  }

  if (intervalId) {
    clearInterval(intervalId);
  }

  // 初回実行
  captureAndSend();

  // 10秒ごとに1枚キャプチャして送信
  intervalId = setInterval(captureAndSend, 10000);
  appendLog("🔵 検出サイクルを開始しました（10秒ごとに送信）");

  startBtn.disabled = true;
  stopBtn.disabled = false;
}

// カメラ停止 (stopDetection 関数は変更なし)
stopBtn.addEventListener("click", stopDetection);

function stopDetection() {
  if (intervalId) {
    clearInterval(intervalId);
    intervalId = null;
    appendLog("🛑 検出を停止しました");
  }

  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
    videoPlaceholder.style.display = "flex";
  }

  startBtn.disabled = false;
  stopBtn.disabled = true;
}

// startBtn.addEventListener("click", async () => { ... }) の代わりに、上記 startDetection 関数を使用する
startBtn.addEventListener("click", startDetection);

// 画像をキャプチャしてAPIへ送信 (captureAndSend 関数は変更なし)
async function captureAndSend() {
  // video.readyState === 4 はビデオデータの準備が完了していることを示す
  if (!video || video.readyState !== 4) return;

  appendLog("🔵 フレームをキャプチャし、OCRサービスに送信します...");

  const canvas = overlayCanvas; // 既存のoverlayCanvasを使用
  const ctx = canvas.getContext("2d");

  // フレームを描画
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  // PromiseベースでBlobを取得（JPEG形式で圧縮）
  const blob = await new Promise(
    (resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9) // 圧縮率 0.9
  );

  if (!blob) {
    return appendLog("❌ 画像キャプチャに失敗しました (Blob取得エラー)。");
  }
  drawMasks();

  const formData = new FormData();
  formData.append("file", blob, "capture.jpg");

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      body: formData,
    });

    const result = await response.json();

    if (!response.ok) {
      // API側でエラーが返された場合
      const errorMsg = result.detail || result.error || "不明なエラー";
      return appendLog(`⚠️ 送信エラー (${response.status}): ${errorMsg}`);
    }

    // 成功ログ表示
    appendLog(`✅ OCRとカレンダー処理が完了しました。
- 予定名: ${result.parsed_summary || "未検出"}
- 登録時間: ${new Date(result.start_time).toLocaleString("ja-JP")}
- ステータス: ${result.calendar_status} (ID: ${result.event_id || "N/A"})
- OCR: ${result.cranberry_ocr_text.substring(0, 30).replace(/\n/g, " ")}...`);
  } catch (err) {
    appendLog("⚠️ ネットワークエラー: " + err.message);
  }
}

// ログを右側に追記 (appendLog 関数は変更なし)
function appendLog(message) {
  const time = new Date().toLocaleTimeString("ja-JP");

  const newLog = document.createElement("p");
  // メッセージの内容に基づいてログの色を決定
  const colorClass = message.startsWith("✅")
    ? "text-green-600"
    : message.startsWith("🔵")
    ? "text-blue-600"
    : message.startsWith("🛑")
    ? "text-gray-600"
    : message.startsWith("❌") || message.startsWith("⚠️")
    ? "text-red-600"
    : "text-gray-700";

  // Tailwindクラスを使用してスタイルを適用
  newLog.className = `border-b border-gray-100 text-sm ${colorClass}`;
  newLog.style.padding = "2px 0";
  newLog.style.whiteSpace = "pre-wrap";

  // HTMLコンテンツを設定し、改行を <br> に変換
  newLog.innerHTML = `<span class="text-gray-400 mr-2">${time}</span> ${message.replace(
    /\n/g,
    "<br>"
  )}`;

  // === ここを修正: ログエリアの末尾に新しいログを追加 ===
  logArea.appendChild(newLog);

  // ログが多すぎる場合、古いもの（先頭）を削除
  while (logArea.children.length > 50) {
    logArea.removeChild(logArea.firstChild); // firstChildを削除
  }
  // === 追加されたロジック: 最新のログに自動スクロール ===
  logArea.scrollTop = logArea.scrollHeight;
}

// 初期化とイベントリスナー (変更なし)
window.onload = () => {
  // startBtn.addEventListener("click", startDetection); // すでに上記で設定済み
  // stopBtn.addEventListener("click", stopDetection);   // すでに上記で設定済み

  // 初期メッセージ
  if (logArea.children.length === 0) {
    appendLog(
      "システムが起動しました。'検出を開始する' を押してカメラを起動してください。"
    );
  }
};
