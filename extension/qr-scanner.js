const $ = id => document.getElementById(id);

let currentUrl = '';
let currentResult = null;
let stream = null;
let scanTimer = null;
let detector = null;

function setStatus(text) {
  $('status').textContent = text;
}

function normalizeInputUrl(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  return /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(raw) ? raw : `https://${raw}`;
}

function reasonText(reason) {
  if (!reason) return '';
  return reason.detail ? `${reason.label}: ${reason.detail}` : reason.label;
}

function detectorReady() {
  return 'BarcodeDetector' in window;
}

async function getDetector() {
  if (!detector) detector = new BarcodeDetector({ formats: ['qr_code'] });
  return detector;
}

async function readQrFromSource(source) {
  if (!detectorReady()) throw new Error('BarcodeDetector is not supported');
  const reader = await getDetector();
  const codes = await reader.detect(source);
  return codes?.[0]?.rawValue || '';
}

function renderResult(rawValue) {
  const url = normalizeInputUrl(rawValue);
  if (!/^https?:\/\//i.test(url)) {
    setStatus('อ่าน QR ได้ แต่ข้อมูลไม่ใช่ URL ที่เปิดผ่านเว็บ');
    return;
  }

  currentUrl = url;
  currentResult = PhishRadarAnalyzer.analyzeUrl(url);
  const level = currentResult.score >= 60 ? 'bad' : currentResult.score >= 31 ? 'warn' : 'good';
  $('resultCard').hidden = false;
  $('decodedUrl').textContent = url;
  $('score').textContent = `${currentResult.score}/100`;
  $('riskBadge').className = level === 'bad' ? 'bad' : level === 'warn' ? 'warn' : '';
  $('riskBadge').textContent = currentResult.levelText;

  const reasons = $('reasons');
  reasons.innerHTML = '';
  const items = currentResult.reasons.length
    ? currentResult.reasons.slice(0, 6)
    : [{ label: 'ยังไม่พบสัญญาณเสี่ยงชัดเจน', detail: 'ยังควรตรวจสอบโดเมนก่อนกรอกข้อมูล' }];
  for (const reason of items) {
    const li = document.createElement('li');
    li.textContent = reasonText(reason);
    reasons.appendChild(li);
  }

  setStatus(`อ่าน QR สำเร็จ ตรวจ URL แล้ว: ${currentResult.score}/100`);
}

async function decodeImageFile(file) {
  if (!file) return;
  if (!detectorReady()) {
    setStatus('เบราว์เซอร์นี้ยังไม่รองรับ BarcodeDetector สำหรับอ่าน QR ใน extension page');
    return;
  }
  setStatus('กำลังอ่าน QR จากรูปภาพ...');
  try {
    const bitmap = await createImageBitmap(file);
    const value = await readQrFromSource(bitmap);
    bitmap.close?.();
    if (!value) {
      setStatus('ยังไม่พบ QR ในรูปนี้ ลองใช้ภาพที่เห็น QR ชัดขึ้น');
      return;
    }
    renderResult(value);
  } catch (error) {
    setStatus('อ่านรูป QR ไม่สำเร็จ');
  }
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    setStatus('เบราว์เซอร์นี้ยังเปิดกล้องไม่ได้');
    return;
  }
  if (!detectorReady()) {
    setStatus('เบราว์เซอร์นี้ยังไม่รองรับ BarcodeDetector สำหรับสแกน QR');
    return;
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
    $('qrVideo').srcObject = stream;
    await $('qrVideo').play();
    $('qrVideo').hidden = false;
    $('placeholder').hidden = true;
    $('startCamera').disabled = true;
    $('stopCamera').disabled = false;
    setStatus('กำลังสแกน QR จากกล้อง...');
    scanCameraFrame();
  } catch (error) {
    setStatus('เปิดกล้องไม่ได้ ตรวจสอบสิทธิ์การใช้กล้อง');
  }
}

async function scanCameraFrame() {
  if (!stream) return;
  try {
    const value = await readQrFromSource($('qrVideo'));
    if (value) {
      stopCamera();
      renderResult(value);
      return;
    }
  } catch (_) {}
  scanTimer = window.setTimeout(scanCameraFrame, 360);
}

function stopCamera() {
  if (scanTimer) window.clearTimeout(scanTimer);
  scanTimer = null;
  if (stream) stream.getTracks().forEach(track => track.stop());
  stream = null;
  $('qrVideo').hidden = true;
  $('qrVideo').srcObject = null;
  $('placeholder').hidden = false;
  $('startCamera').disabled = false;
  $('stopCamera').disabled = true;
}

$('startCamera').addEventListener('click', startCamera);
$('stopCamera').addEventListener('click', stopCamera);
$('qrFile').addEventListener('change', event => decodeImageFile(event.target.files?.[0]));

$('openWarning').addEventListener('click', () => {
  if (!currentUrl || !currentResult) return;
  chrome.runtime.sendMessage({ type: 'OPEN_WARNING', target: currentUrl, source: 'qr-scanner', result: currentResult });
});

$('copyUrl').addEventListener('click', async () => {
  if (!currentUrl) return;
  try {
    await navigator.clipboard.writeText(currentUrl);
    setStatus('คัดลอก URL จาก QR แล้ว');
  } catch (_) {
    setStatus('คัดลอก URL ไม่สำเร็จ');
  }
});

if (!detectorReady()) {
  setStatus('QR Scanner พร้อม แต่เบราว์เซอร์นี้ยังไม่รองรับ BarcodeDetector');
}
