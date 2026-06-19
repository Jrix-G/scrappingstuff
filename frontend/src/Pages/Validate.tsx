import React, { useState, useRef } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface ValidateResult {
  keyword: string;
  query: string;
  cj_match: {
    name: string | null;
    cost_eur: number | null;
    listed_num: number | null;
    age_days: number | null;
    image: string | null;
    suggest_price: number | null;
  } | null;
  sellability: {
    sellability: number;
    verdict: string;
    cost_eur: number;
    retail_eur: number;
    gross_margin_eur: number;
    net_after_cpa_eur: number;
    margin_pct: number;
    scores: { margin: number; price: number; saturation: number; freshness: number };
    reason: string;
    error?: string;
  };
  organic: {
    score: number;
    phase: string;
    monthly_growth: number;
    confidence: number;
    reasons: string[];
  };
  seasonality: {
    multiplier: number;
    profile: string | null;
    peak_month: number | null;
    label: string;
  };
  signals: {
    trends: { available: boolean; points: number };
    reddit: { available: boolean; points: number };
    amazon: {
      available?: boolean;
      keyword?: string;
      maxBought?: number | null;
      medianBought?: number | null;
      nWithVelocity?: number;
      nResults?: number;
      blocked?: boolean;
    };
  };
  tandor_score: number;
  verdict: string;
  processing_time_s: number;
}

// ─── Verdict helpers ──────────────────────────────────────────────────────────

const VERDICT_META: Record<string, { label: string; color: string; bg: string; desc: string }> = {
  BUY: {
    label: 'ACHETER',
    color: '#00d97e',
    bg: 'rgba(0,217,126,0.12)',
    desc: 'Produit vendable, demande réelle, marge positive.',
  },
  WATCH: {
    label: 'SURVEILLER',
    color: '#f5a623',
    bg: 'rgba(245,166,35,0.12)',
    desc: 'Potentiel mais signal insuffisant ou marge limite.',
  },
  PASS: {
    label: 'PASSER',
    color: '#f0506e',
    bg: 'rgba(240,80,110,0.12)',
    desc: 'Marge nulle ou marché saturé. À éviter.',
  },
  UNKNOWN: {
    label: 'INCONNU',
    color: '#8a9bb8',
    bg: 'rgba(138,155,184,0.12)',
    desc: 'Données insuffisantes pour conclure.',
  },
};

function verdictMeta(v: string) {
  return VERDICT_META[v] ?? VERDICT_META['UNKNOWN'];
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function ScoreBar({ label, value, max = 1 }: { label: string; value: number; max?: number }) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  const color = pct >= 65 ? '#00d97e' : pct >= 40 ? '#f5a623' : '#f0506e';
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 12, color: '#8a9bb8' }}>
        <span>{label}</span>
        <span style={{ color, fontWeight: 600 }}>{pct}%</span>
      </div>
      <div style={{ height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.06)' }}>
        <div style={{ height: '100%', borderRadius: 2, width: `${pct}%`, background: color, transition: 'width 0.6s ease' }} />
      </div>
    </div>
  );
}

function SignalBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11,
      padding: '3px 8px', borderRadius: 4,
      background: ok ? 'rgba(0,217,126,0.1)' : 'rgba(138,155,184,0.1)',
      color: ok ? '#00d97e' : '#8a9bb8',
      border: `1px solid ${ok ? 'rgba(0,217,126,0.25)' : 'rgba(138,155,184,0.15)'}`,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor', display: 'inline-block' }} />
      {label}
    </span>
  );
}

function Spinner() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, padding: '40px 0' }}>
      <div style={{
        width: 36, height: 36, borderRadius: '50%',
        border: '3px solid rgba(0,217,126,0.15)',
        borderTopColor: '#00d97e',
        animation: 'spin 0.8s linear infinite',
      }} />
      <span style={{ color: '#8a9bb8', fontSize: 14 }}>Analyse en cours… (10–30 s)</span>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function Validate() {
  const [query, setQuery] = useState('');
  const [geo, setGeo] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ValidateResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const api = process.env.REACT_APP_API_URL ?? 'http://localhost:8000';

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await fetch(`${api.replace(/\/$/, '')}/api/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim(), geo: geo.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);
      setResult(data as ValidateResult);
    } catch (err: any) {
      setError(err.message ?? 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  }

  const vm = result ? verdictMeta(result.verdict) : null;

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0d1117',
      color: '#c9d1d9',
      fontFamily: '"Hanken Grotesk", "Inter", sans-serif',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '48px 16px 80px',
    }}>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(16px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .val-input:focus { outline: none; border-color: #00d97e !important; }
        .val-btn:hover { background: #00bf6e !important; }
        .val-btn:disabled { opacity: 0.45; cursor: not-allowed; }
        .val-card { animation: fadeUp 0.4s ease both; }
      `}</style>

      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: 40, maxWidth: 560 }}>
        <a href="/" style={{ display: 'inline-flex', alignItems: 'center', gap: 7, marginBottom: 24, textDecoration: 'none', color: '#c9d1d9' }}>
          <svg width="14" height="14" viewBox="0 0 13 13" fill="none">
            <path d="M6.5 1.5v10M2 6h9M6.5 1.5 9 4M6.5 1.5 4 4" stroke="#00d97e" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span style={{ fontWeight: 700, fontSize: 15, letterSpacing: '0.02em' }}>Tandor<span style={{ color: '#00d97e' }}>.</span></span>
        </a>
        <h1 style={{ fontSize: 28, fontWeight: 700, margin: '0 0 10px', lineHeight: 1.2 }}>
          Valider un produit
        </h1>
        <p style={{ fontSize: 15, color: '#8a9bb8', margin: 0, lineHeight: 1.6 }}>
          Colle une URL Amazon / AliExpress ou tape un nom de produit.
          On calcule si ça vaut la peine d'y aller.
        </p>
      </div>

      {/* Search form */}
      <form onSubmit={handleSubmit} style={{ width: '100%', maxWidth: 640, marginBottom: 32 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
          <input
            ref={inputRef}
            className="val-input"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="yoga mat  ·  https://www.amazon.com/…  ·  portable blender"
            style={{
              flex: 1, padding: '13px 16px', borderRadius: 8, fontSize: 14,
              background: '#161b22', border: '1.5px solid #30363d', color: '#c9d1d9',
              transition: 'border-color 0.2s',
            }}
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="val-btn"
            style={{
              padding: '13px 22px', borderRadius: 8, border: 'none', cursor: 'pointer',
              background: '#00d97e', color: '#0d1117', fontWeight: 700, fontSize: 14,
              transition: 'background 0.15s', whiteSpace: 'nowrap',
            }}
          >
            {loading ? '…' : 'Analyser'}
          </button>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <label style={{ fontSize: 12, color: '#8a9bb8', whiteSpace: 'nowrap' }}>Marché :</label>
          <input
            className="val-input"
            value={geo}
            onChange={e => setGeo(e.target.value.toUpperCase())}
            placeholder="FR  ·  US  ·  vide = monde"
            maxLength={2}
            style={{
              width: 100, padding: '7px 10px', borderRadius: 6, fontSize: 13,
              background: '#161b22', border: '1.5px solid #30363d', color: '#c9d1d9',
            }}
          />
          <span style={{ fontSize: 12, color: '#4a5568' }}>Code pays Google Trends (optionnel)</span>
        </div>
      </form>

      {/* States */}
      {loading && <Spinner />}
      {error && (
        <div style={{
          width: '100%', maxWidth: 640, padding: '14px 18px', borderRadius: 8,
          background: 'rgba(240,80,110,0.1)', border: '1px solid rgba(240,80,110,0.3)',
          color: '#f0506e', fontSize: 14,
        }}>
          {error}
        </div>
      )}

      {/* Results */}
      {result && vm && (
        <div className="val-card" style={{ width: '100%', maxWidth: 640, display: 'flex', flexDirection: 'column', gap: 14 }}>

          {/* Verdict hero */}
          <div style={{
            padding: '24px 24px 20px',
            borderRadius: 12,
            border: `1.5px solid ${vm.color}44`,
            background: vm.bg,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <div style={{ fontSize: 11, color: '#8a9bb8', marginBottom: 6, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                  Verdict Tandor — « {result.keyword} »
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{
                    fontSize: 22, fontWeight: 800, color: vm.color,
                    letterSpacing: '0.06em',
                  }}>{vm.label}</span>
                  <span style={{
                    fontSize: 32, fontWeight: 800, color: '#e6edf3',
                  }}>{result.tandor_score}<span style={{ fontSize: 16, color: '#8a9bb8', fontWeight: 400 }}>/100</span></span>
                </div>
                <div style={{ fontSize: 13, color: '#8a9bb8', marginTop: 6 }}>{vm.desc}</div>
              </div>
              {result.cj_match?.image && (
                <img
                  src={result.cj_match.image}
                  alt=""
                  style={{ width: 72, height: 72, borderRadius: 8, objectFit: 'cover', border: '1px solid #30363d' }}
                />
              )}
            </div>

            {/* Signal badges */}
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 14 }}>
              <SignalBadge ok={result.signals.trends.available} label={`Trends (${result.signals.trends.points} pts)`} />
              <SignalBadge ok={result.signals.reddit.available} label={`Reddit (${result.signals.reddit.points} pts)`} />
              <SignalBadge
                ok={!result.signals.amazon.blocked && (result.signals.amazon.maxBought ?? 0) > 0}
                label={result.signals.amazon.blocked ? 'Amazon (bloqué)' : result.signals.amazon.maxBought ? `Amazon (${result.signals.amazon.maxBought.toLocaleString()}/m)` : 'Amazon (pas de badge)'}
              />
              {result.cj_match && <SignalBadge ok label="CJ trouvé" />}
            </div>
          </div>

          {/* 3 colonnes : vendabilité / organique / sourcing */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>

            {/* Vendabilité */}
            <div style={cardStyle}>
              <div style={cardTitle}>Vendabilité financière</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#e6edf3', marginBottom: 14 }}>
                {result.sellability.sellability?.toFixed(0) ?? '–'}<span style={{ fontSize: 14, color: '#8a9bb8', fontWeight: 400 }}>/100</span>
              </div>
              {result.sellability.scores && <>
                <ScoreBar label="Marge" value={result.sellability.scores.margin} />
                <ScoreBar label="Prix d'impulsion" value={result.sellability.scores.price} />
                <ScoreBar label="Saturation offre" value={result.sellability.scores.saturation} />
                <ScoreBar label="Fraîcheur" value={result.sellability.scores.freshness} />
              </>}
              <div style={{ fontSize: 12, color: '#8a9bb8', marginTop: 8, lineHeight: 1.5 }}>
                {result.sellability.reason}
              </div>
            </div>

            {/* Organic */}
            <div style={cardStyle}>
              <div style={cardTitle}>Demande organique</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#e6edf3', marginBottom: 14 }}>
                {result.organic.score}<span style={{ fontSize: 14, color: '#8a9bb8', fontWeight: 400 }}>/100</span>
              </div>
              <div style={kv}>Phase<span style={{ color: phaseColor(result.organic.phase) }}>{result.organic.phase}</span></div>
              <div style={kv}>Croissance/mois<span>{(result.organic.monthly_growth * 100).toFixed(1)}%</span></div>
              <div style={kv}>Confiance<span>{(result.organic.confidence * 100).toFixed(0)}%</span></div>
              {result.organic.reasons.length > 0 && (
                <ul style={{ margin: '10px 0 0', padding: '0 0 0 14px', fontSize: 12, color: '#8a9bb8', lineHeight: 1.6 }}>
                  {result.organic.reasons.slice(0, 3).map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              )}
              {result.organic.reasons.length === 0 && (
                <div style={{ fontSize: 12, color: '#4a5568', marginTop: 8 }}>Signaux insuffisants pour l'analyse de tendance.</div>
              )}
            </div>

            {/* Sourcing + saison */}
            <div style={cardStyle}>
              <div style={cardTitle}>Sourcing & saison</div>
              {result.cj_match ? <>
                <div style={kv}>Coût CJ<span>{result.cj_match.cost_eur ? `${result.cj_match.cost_eur.toFixed(2)} €` : '–'}</span></div>
                <div style={kv}>Retail estimé<span>{result.sellability.retail_eur ? `${result.sellability.retail_eur.toFixed(2)} €` : '–'}</span></div>
                <div style={kv}>Marge brute<span>{result.sellability.gross_margin_eur ? `${result.sellability.gross_margin_eur.toFixed(2)} €` : '–'}</span></div>
                <div style={kv}>Net après CPA<span style={{ color: (result.sellability.net_after_cpa_eur ?? 0) > 0 ? '#00d97e' : '#f0506e' }}>
                  {result.sellability.net_after_cpa_eur ? `${result.sellability.net_after_cpa_eur.toFixed(2)} €` : '–'}
                </span></div>
                <div style={kv}>Vendeurs CJ<span>{result.cj_match.listed_num ?? '–'}</span></div>
                {result.cj_match.name && (
                  <div style={{ fontSize: 11, color: '#4a5568', marginTop: 8, lineHeight: 1.4 }}>
                    Correspondance : {result.cj_match.name.slice(0, 60)}{result.cj_match.name.length > 60 ? '…' : ''}
                  </div>
                )}
              </> : (
                <div style={{ fontSize: 12, color: '#4a5568', marginTop: 4 }}>
                  Aucun produit CJ trouvé en base locale.<br />Le scoring de marge est indisponible.
                </div>
              )}
              <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid #21262d' }}>
                <div style={{ fontSize: 11, color: '#8a9bb8', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Saisonnalité</div>
                <div style={{ fontSize: 13, color: seasonColor(result.seasonality.multiplier) }}>
                  ×{result.seasonality.multiplier.toFixed(2)}
                </div>
                <div style={{ fontSize: 11, color: '#4a5568', marginTop: 3, lineHeight: 1.4 }}>
                  {result.seasonality.label}
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div style={{ fontSize: 11, color: '#4a5568', textAlign: 'right', paddingTop: 4 }}>
            Analysé en {result.processing_time_s} s · <a href="/dashboard" style={{ color: '#4a5568' }}>Dashboard</a>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Styles constants ─────────────────────────────────────────────────────────

const cardStyle: React.CSSProperties = {
  padding: '18px 18px 16px',
  borderRadius: 10,
  background: '#161b22',
  border: '1px solid #21262d',
};

const cardTitle: React.CSSProperties = {
  fontSize: 11,
  color: '#8a9bb8',
  textTransform: 'uppercase',
  letterSpacing: '0.07em',
  marginBottom: 10,
};

const kv: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  fontSize: 13,
  color: '#8a9bb8',
  padding: '3px 0',
  borderBottom: '1px solid #21262d',
};

function phaseColor(phase: string): string {
  if (phase === 'accelerating') return '#00d97e';
  if (phase === 'growing') return '#64d97e';
  if (phase === 'declining') return '#f0506e';
  return '#8a9bb8';
}

function seasonColor(mult: number): string {
  if (mult >= 1.3) return '#00d97e';
  if (mult >= 0.9) return '#f5a623';
  return '#f0506e';
}
