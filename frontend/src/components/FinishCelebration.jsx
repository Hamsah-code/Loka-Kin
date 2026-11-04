import { useEffect } from "react";
import "./FinishCelebration.css";

/**
 * Animasi karakter tersenyum saat laporan harian ditandai Finish dan berhasil disimpan.
 * Tutup otomatis setelah beberapa detik, atau dengan mengklik di mana saja.
 */
export default function FinishCelebration({ onClose, durationMs = 3800 }) {
  useEffect(() => {
    const timer = setTimeout(onClose, durationMs);
    return () => clearTimeout(timer);
  }, [onClose, durationMs]);

  return (
    <div className="finish-celebration-backdrop" role="status" aria-live="polite" onClick={onClose} data-testid="finish-celebration">
      <div className="finish-celebration-card">
        <svg className="finish-character" viewBox="0 0 200 200" aria-hidden="true">
          {/* sinar matahari berputar */}
          <g className="finish-rays">
            {Array.from({ length: 12 }).map((_, i) => (
              <rect key={i} x="95" y="6" width="10" height="26" rx="5" fill="#facc15" transform={`rotate(${i * 30} 100 100)`} />
            ))}
          </g>
          {/* lengan melambai */}
          <g className="finish-arm finish-arm-left">
            <path d="M40 110 Q14 90 22 62" stroke="#f59e0b" strokeWidth="11" strokeLinecap="round" fill="none" />
            <circle cx="22" cy="58" r="9" fill="#fde68a" />
          </g>
          <g className="finish-arm finish-arm-right">
            <path d="M160 110 Q186 90 178 62" stroke="#f59e0b" strokeWidth="11" strokeLinecap="round" fill="none" />
            <circle cx="178" cy="58" r="9" fill="#fde68a" />
          </g>
          {/* badan karakter (matahari) yang memantul */}
          <g className="finish-body">
            <circle cx="100" cy="100" r="58" fill="#fde047" stroke="#f59e0b" strokeWidth="4" />
            <circle cx="80" cy="92" r="6" fill="#1e293b" className="finish-eye" />
            <circle cx="120" cy="92" r="6" fill="#1e293b" className="finish-eye" />
            <circle cx="72" cy="112" r="7" fill="#fb7185" opacity="0.7" />
            <circle cx="128" cy="112" r="7" fill="#fb7185" opacity="0.7" />
            <path d="M74 110 Q100 138 126 110" stroke="#1e293b" strokeWidth="5" strokeLinecap="round" fill="none" />
          </g>
        </svg>
        <div className="finish-sparkles" aria-hidden="true">
          <span>✨</span><span>🎉</span><span>⭐</span>
        </div>
        <h3 className="finish-title">Terima Kasih Anda Telah Menyelesaikan Laporan Harian</h3>
        <p className="finish-hint">Klik di mana saja untuk menutup</p>
      </div>
    </div>
  );
}
