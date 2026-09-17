import { useEffect, useRef, useState } from 'react';
import jsQR from 'jsqr';
import { MotionFrame } from '../components/MotionFrame';
import { useApp } from '../contexts/AppContext';
import { useRouter } from '../contexts/RouterContext';

function readerName() {
  return 'BarcodeDetector' in window ? 'BarcodeDetector' : 'jsQR';
}

export function QrPage() {
  const { navigate } = useRouter();
  const { analyzeUrl } = useApp();
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [decodedUrl, setDecodedUrl] = useState('');
  const [status, setStatus] = useState('พร้อมอ่าน QR ที่เป็น URL');

  useEffect(() => {
    document.title = 'QR Scanner | Phish Radar AI';
    return stopCamera;
  }, []);

  async function readQrFromSource(source) {
    if ('BarcodeDetector' in window) {
      try {
        const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
        const codes = await detector.detect(source);
        if (codes[0]?.rawValue) return codes[0].rawValue;
      } catch {
        // Fall through to jsQR for broader browser support.
      }
    }

    const width = source.videoWidth || source.naturalWidth || source.width || 0;
    const height = source.videoHeight || source.naturalHeight || source.height || 0;
    if (!width || !height) return '';
    const canvas = canvasRef.current;
    const context = canvas.getContext('2d', { willReadFrequently: true });
    canvas.width = width;
    canvas.height = height;
    context.drawImage(source, 0, 0, width, height);
    const imageData = context.getImageData(0, 0, width, height);
    return jsQR(imageData.data, width, height, { inversionAttempts: 'attemptBoth' })?.data || '';
  }

  async function openResult(value) {
    stopCamera();
    try {
      const parsed = new URL(value);
      if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error();
      setDecodedUrl(parsed.href);
      setStatus('อ่าน QR สำเร็จ ตรวจสอบ URL ด้านล่างก่อนส่งวิเคราะห์');
    } catch { setDecodedUrl(''); setStatus('ข้อมูลใน QR ไม่ใช่ลิงก์ http หรือ https'); }
  }

  async function decodeImageFile(file) {
    setDecodedUrl('');
    setStatus(`กำลังอ่าน QR จากรูปด้วย ${readerName()}`);
    try {
      const image = await createImageBitmap(file);
      const value = await readQrFromSource(image);
      image.close?.();
      if (value) await openResult(value);
      else setStatus('ยังไม่พบ QR ในรูปนี้ ลองครอปรูปให้เห็น QR ชัดขึ้น');
    } catch {
      setStatus('อ่านไฟล์รูปไม่ได้ ลองใช้ภาพ PNG หรือ JPG ที่เห็น QR ชัดเจน');
    }
  }

  async function startCamera() {
    setDecodedUrl('');
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus('เบราว์เซอร์นี้ยังเปิดกล้องจากหน้าเว็บไม่ได้');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
        audio: false
      });
      streamRef.current = stream;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setCameraActive(true);
      setStatus(`กำลังสแกน QR ด้วย ${readerName()}`);

      const scan = async () => {
        if (!streamRef.current) return;
        try {
          const value = await readQrFromSource(videoRef.current);
          if (value) {
            await openResult(value);
            return;
          }
          setStatus(`กำลังสแกน QR ด้วย ${readerName()}`);
        } catch {
          setStatus('ยังอ่าน QR ไม่ได้ ลองขยับกล้องให้ภาพชัดขึ้น');
        }
        timerRef.current = window.setTimeout(scan, 360);
      };
      scan();
    } catch {
      setStatus('เปิดกล้องไม่ได้ ตรวจสอบสิทธิ์การใช้กล้อง');
    }
  }

  function stopCamera() {
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = null;
    if (streamRef.current) streamRef.current.getTracks().forEach(track => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraActive(false);
  }

  return (
    <MotionFrame>
      <section id="qr" className="page active">
        <section className="panel qr-panel" data-reveal>
          <div className="page-heading">
            <p className="eyebrow">QR SCANNER</p>
            <h1>อ่านลิงก์ก่อนเปิดจริง</h1>
            <p>ใช้กล้องหรืออัปโหลดภาพ QR ระบบจะส่ง URL ที่อ่านได้ไปยังขั้นตอนวิเคราะห์เดียวกับหน้า Scanner</p>
          </div>
          <div className="qr-grid">
            <div className="qr-viewport">
              <video ref={videoRef} playsInline muted hidden={!cameraActive} />
              <canvas ref={canvasRef} hidden />
              {!cameraActive && (
                <div className="qr-placeholder">
                  <strong>ยังไม่ได้เปิดกล้อง</strong>
                  <span>รองรับกล้องบน localhost และการอัปโหลดรูป QR</span>
                </div>
              )}
            </div>
            <div className="qr-controls">
              <button className="primary" type="button" onClick={startCamera} disabled={cameraActive}>
                เปิดกล้อง
              </button>
              <button className="secondary" type="button" onClick={stopCamera} disabled={!cameraActive}>
                หยุดกล้อง
              </button>
              <label className="file-picker">
                อัปโหลดรูป QR
                <input
                  type="file"
                  accept="image/*"
                  onChange={event => {
                    const file = event.target.files?.[0];
                    if (file) decodeImageFile(file);
                  }}
                />
              </label>
              <p aria-live="polite">{status}</p>
              {decodedUrl && <div className="qr-decoded"><h2>URL ที่อ่านได้</h2><p className="url-text">{decodedUrl}</p><button className="primary" onClick={() => { navigate('/scan'); analyzeUrl(decodedUrl, 'qr-scanner'); }}>ตรวจสอบ URL นี้</button><p>ยังไม่ได้เปิดเว็บไซต์ปลายทาง</p></div>}
            </div>
          </div>
        </section>
      </section>
    </MotionFrame>
  );
}
