import { useEffect, useRef, useState } from 'react';
import { useApp } from '../contexts/AppContext';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';
import { flattenReason, riskLevel } from '../services/risk';
import { basicChatReply, CHAT_GREETING, extractChatUrls } from '../services/chat.mjs';
import './chat.css';

function ChatIcon() {
  return <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-6 3V6a2 2 0 0 1 2-2Z" /><path d="M7 9h10M7 13h6" /></svg>;
}

export function ChatWidget() {
  const { user } = useAuth();
  const { privacyMode } = useApp();
  // Switching accounts or privacy mode discards conversation and cancels pending chat.
  return <ChatSession key={`${user?.user_id}:${privacyMode}`} />;
}

function ChatSession() {
  const { privacyMode, analyzeUrl, analysisPhase, current } = useApp();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [messages, setMessages] = useState([{ role: 'assistant', content: CHAT_GREETING, source: 'Phish Radar' }]);
  const [pending, setPending] = useState('');
  const [error, setError] = useState('');
  const [scan, setScan] = useState(null);
  const input = useRef(null);
  const launcher = useRef(null);
  const log = useRef(null);
  const request = useRef(null);
  const alive = useRef(true);
  const busy = useRef(false);
  const scanning = ['analyzing', 'explaining'].includes(analysisPhase);
  const latest = scan || (analysisPhase === 'done' ? current : null);

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; request.current?.abort(); };
  }, []);
  useEffect(() => { if (open) input.current?.focus(); }, [open]);
  useEffect(() => { if (log.current) log.current.scrollTop = log.current.scrollHeight; }, [messages, pending, open]);

  function close() { setOpen(false); launcher.current?.focus(); }

  async function send(value = draft) {
    const message = value.trim();
    if (!message || busy.current || scanning) return;
    if (message.length > 2000) { setError('ส่งข้อความได้ไม่เกิน 2,000 ตัวอักษรครับ'); return; }
    const urls = extractChatUrls(message);
    if (urls.length > 1) { setError('กรุณาส่งครั้งละหนึ่งลิงก์ เพื่อให้ผลตรวจชัดเจนครับ'); return; }
    busy.current = true;
    setError(''); setDraft('');
    setMessages(previous => [...previous, { role: 'user', content: message }]);
    setPending(urls.length ? 'กำลังตรวจลิงก์และเตรียมคำอธิบาย…' : 'กำลังเตรียมคำตอบ…');
    try {
      let answer;
      if (urls.length) {
        const result = await analyzeUrl(urls[0], 'web-app-chat');
        if (!alive.current) return;
        if (!result) throw new Error('ยังตรวจลิงก์นี้ไม่สำเร็จ กรุณาตรวจรูปแบบลิงก์แล้วลองใหม่');
        setScan(result);
        const level = riskLevel(result.riskScore, result.warningThreshold, result.blockingThreshold);
        answer = {
          role: 'assistant', source: result.privacy ? 'กฎในเครื่อง · Privacy Mode' : result.modelStatus === 'ready' ? 'ผลจากระบบตรวจสอบ' : 'ผลเบื้องต้น · กฎในเครื่อง',
          result: { url: result.displayUrl, score: result.riskScore, label: level.label, tone: level.tone },
          content: `${result.llm?.explanation || 'ตรวจลิงก์แล้ว'}\n\n${result.llm?.advice || ''}\n\nผลนี้ไม่รับรองว่าลิงก์ปลอดภัยแน่นอน`,
        };
      } else {
        let response;
        if (!privacyMode) {
          request.current = new AbortController();
          try {
            response = await api.chat({
              message,
              history: messages.slice(1).slice(-8).map(({ role, content }) => ({ role, content: content.slice(0, 4000) })),
              context: latest ? {
                url: latest.url, score: latest.riskScore ?? latest.finalScore,
                decision: latest.decision, model_status: latest.modelStatus || 'unavailable',
                reasons: (latest.reasons || []).slice(0, 7).map(flattenReason).filter(Boolean),
              } : null,
            }, request.current.signal);
          } catch { /* An explicitly labelled local answer remains available offline. */ }
        }
        answer = {
          role: 'assistant',
          source: response?.ok ? 'AI · Ollama' : privacyMode ? 'คำแนะนำพื้นฐาน · Privacy Mode' : 'คำแนะนำสำรอง · AI ยังไม่พร้อม',
          content: response?.ok && response.reply ? response.reply : basicChatReply(message, latest),
        };
      }
      if (alive.current) setMessages(previous => [...previous, answer]);
    } catch (failure) {
      if (alive.current) { setError(failure.message || 'ยังตอบไม่ได้ กรุณาลองใหม่'); setDraft(message); }
    } finally {
      busy.current = false;
      if (alive.current) { setPending(''); input.current?.focus(); }
    }
  }

  return <aside className="radar-chat" aria-label="ผู้ช่วย Phish Radar">
    {open && <section className="radar-chat-panel" role="dialog" aria-modal="false" aria-labelledby="radar-chat-title" onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); close(); } }}>
      <header className="radar-chat-header"><span className="radar-chat-mark"><ChatIcon /></span><div><h2 id="radar-chat-title">คุยกับ Phish Radar</h2><p>ถามให้เข้าใจ ตรวจให้มั่นใจขึ้น</p></div><button type="button" onClick={close} aria-label="ปิดแชท">×</button></header>
      <div className="radar-chat-notice">{privacyMode ? 'Privacy Mode · ตรวจและตอบพื้นฐานในเครื่องเท่านั้น' : 'ข้อความส่งให้ AI ประมวลผล · อย่าส่งรหัสผ่านหรือ OTP'}</div>
      <div className="radar-chat-log" ref={log} role="log" aria-label="บทสนทนา" aria-live="polite" aria-relevant="additions">
        {messages.map((item, index) => <article key={index} className={`radar-chat-message ${item.role}`}>
          <small>{item.role === 'user' ? 'คุณ' : item.source}</small>
          {item.result && <div className="radar-chat-result"><span>{item.result.url}</span><strong className={item.result.tone}>{item.result.score}<small>/100</small> · {item.result.label}</strong></div>}
          <p>{item.content}</p>
        </article>)}
        {pending && <p className="radar-chat-pending" role="status">{pending}</p>}
      </div>
      <div className="radar-chat-suggestions" aria-label="คำถามแนะนำ">
        {(latest ? ['อธิบายผลตรวจล่าสุด', 'เผลอคลิกลิงก์แล้วทำอย่างไร'] : ['Phishing คืออะไร', 'ช่วยตรวจลิงก์ให้หน่อย']).map(question => <button key={question} type="button" disabled={!!pending || scanning} onClick={() => send(question)}>{question}</button>)}
      </div>
      {error && <p className="radar-chat-error" role="alert">{error}</p>}
      <form className="radar-chat-compose" onSubmit={event => { event.preventDefault(); send(); }}>
        <label className="radar-chat-input-label" htmlFor="radar-chat-input">ข้อความหรือ URL ที่ต้องการตรวจ</label>
        <div><textarea id="radar-chat-input" ref={input} value={draft} onChange={event => setDraft(event.target.value)} maxLength={2000} rows={2} placeholder="พิมพ์คำถาม หรือวาง https://…" onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send(); } }} /><button className="primary" type="submit" disabled={!draft.trim() || !!pending || scanning} aria-label="ส่งข้อความ">ส่ง</button></div>
        <footer><span>{scanning && !pending ? 'รอการตรวจลิงก์ปัจจุบันให้เสร็จก่อน' : 'Enter ส่ง · Shift + Enter ขึ้นบรรทัดใหม่'}</span><button type="button" disabled={!!pending} onClick={() => { setMessages([{ role: 'assistant', content: CHAT_GREETING, source: 'Phish Radar' }]); setScan(null); setError(''); setDraft(''); }}>ล้างแชท</button></footer>
      </form>
    </section>}
    <button type="button" className="radar-chat-launcher" ref={launcher} aria-expanded={open} aria-label={open ? 'ปิดแชทผู้ช่วย' : 'เปิดแชทผู้ช่วย'} onClick={() => open ? close() : setOpen(true)}><ChatIcon /><span>ถาม / ตรวจลิงก์</span></button>
  </aside>;
}
