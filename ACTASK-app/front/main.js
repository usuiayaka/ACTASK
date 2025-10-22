const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const video = document.getElementById("cameraVideo");
const logArea = document.getElementById("logArea");

let stream = null;
let intervalId = null; // 10秒ごとの送信制御用

// カメラ起動
startBtn.addEventListener("click", async () => {
  try {
    if (!stream) {
      stream = await navigator.mediaDevices.getUserMedia({ video: true });
      video.srcObject = stream;
    }

    // 10秒ごとに1枚キャプチャして送信
    if (!intervalId) {
      intervalId = setInterval(captureAndSend, 10000);
      appendLog("🔵 検出を開始しました（10秒ごとに送信）");
    }
  } catch (err) {
    appendLog("❌ カメラのアクセスに失敗しました: " + err);
  }
});

// カメラ停止
stopBtn.addEventListener("click", () => {
  if (intervalId) {
    clearInterval(intervalId);
    intervalId = null;
    appendLog("🛑 検出を停止しました");
  }

  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
  }
});

// 画像をキャプチャしてAPIへ送信
async function captureAndSend() {
  if (!video || video.readyState !== 4) return;

  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  const blob = await new Promise((resolve) =>
    canvas.toBlob(resolve, "image/jpeg")
  );

  const formData = new FormData();
  formData.append("file", blob, "capture.jpg");

  try {
    const response = await fetch("http://127.0.0.1:8000/call-cranberry", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const result = await response.json();
    appendLog("✅ Cranberry結果:\n" + JSON.stringify(result, null, 2));
  } catch (err) {
    appendLog("⚠️ 送信エラー: " + err);
  }
}

// ログを右側に追記
function appendLog(message) {
  const time = new Date().toLocaleTimeString();
  const entry = `[${time}] ${message}\n\n`;
  logArea.textContent += entry;
  logArea.scrollTop = logArea.scrollHeight; // 自動スクロール
}
