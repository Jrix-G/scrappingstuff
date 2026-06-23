/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-reddit.js   (Reddit Intelligence)
   Early social signal: mention velocity over time, source
   subreddits, notable posts, correlation with product velocity.
   Frequency of mentions only — never invented upvote counts.
   ============================================================ */
export function mountReddit() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR, C = window.Charts, X = window.ChartsX, P = T.PRODUCTS;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic, clamp = Sh.clamp;

  const STR = {
    en: { title: 'Reddit Intelligence', sub: 'early social signal · Reddit score',
      k_score: 'Avg Reddit score', k_velocity: 'Avg weekly velocity', k_subs: 'Likely subreddits', k_corro: 'Corroborated products',
      timeline: 'Mention timeline', timeline_s: 'no persisted Reddit time-series — score only', trendline: 'trend',
      subs: 'Likely source subreddits', subs_s: 'estimated from category × Reddit score', mentions: 'mentions',
      corr: 'Reddit × product velocity', corr_s: 'high Reddit score + high growth = early',
      focus: 'All products', wk: 'wk',
      empty_t: 'No Reddit time-series', empty_s: 'Reddit mentions are fetched live and never persisted in the DB, so there is no real weekly curve to draw. The per-product Reddit score below is real.',
      score_real: 'Reddit score (real)', est: 'estimate' },
    fr: { title: 'Reddit Intelligence', sub: 'signal social précoce · score Reddit',
      k_score: 'Score Reddit moyen', k_velocity: 'Vélocité hebdo moy.', k_subs: 'Subreddits probables', k_corro: 'Produits corroborés',
      timeline: 'Chronologie des mentions', timeline_s: 'aucune série temporelle Reddit persistée — score seul', trendline: 'tendance',
      subs: 'Subreddits sources probables', subs_s: 'estimés depuis catégorie × score Reddit', mentions: 'mentions',
      corr: 'Reddit × vélocité produit', corr_s: 'score Reddit fort + croissance forte = précoce',
      focus: 'Tous les produits', wk: 'sem.',
      empty_t: 'Pas de série temporelle Reddit', empty_s: 'Les mentions Reddit sont récupérées en direct et jamais stockées en base — il n’existe donc pas de vraie courbe hebdomadaire à tracer. Le score Reddit par produit ci-dessous est réel.',
      score_real: 'Score Reddit (réel)', est: 'estimation' },
  };
  const L = () => STR[Sh.lang];

  const SUBS = [
    { n: 'BuyItForLife', cats: ['HOME', 'KITCHEN', 'OUTDOOR'], base: 1.0 },
    { n: 'ProductPorn', cats: ['HOME', 'TECH'], base: 0.86 },
    { n: 'gadgets', cats: ['TECH'], base: 0.92 },
    { n: 'SkincareAddiction', cats: ['BEAUTY'], base: 0.78 },
    { n: 'declutter', cats: ['HOME', 'APPAREL'], base: 0.6 },
    { n: 'femalefashion', cats: ['APPAREL', 'BEAUTY'], base: 0.7 },
    { n: 'dogs', cats: ['PETS'], base: 0.66 },
    { n: 'homeautomation', cats: ['HOME', 'TECH'], base: 0.55 },
    { n: 'Fitness', cats: ['FITNESS', 'WELLNESS'], base: 0.74 },
    { n: 'BabyBumps', cats: ['BABY'], base: 0.48 },
  ];
  let focusId = 'all';

  function subVolumes() {
    const pool = focusId === 'all' ? P : P.filter((p) => p.id === focusId);
    return SUBS.map((s) => {
      let vol = 0; pool.forEach((p) => { if (s.cats.includes(p.cat)) vol += Math.round(p.redditScore * s.base * 0.6); });
      return { n: s.n, vol: vol || Math.round(s.base * 12) };
    }).sort((a, b) => b.vol - a.vol);
  }

  function render() {
    const s = L();
    const pool = focusId === 'all' ? P : P.filter((p) => p.id === focusId);
    // REAL: per-product redditScore. Average it for the headline KPI.
    const avgScore = pool.length ? Math.round(pool.reduce((a, p) => a + p.redditScore, 0) / pool.length) : 0;
    const subs = subVolumes();
    const activeSubs = subs.filter((x) => x.vol > 0).length;
    const corro = P.filter((p) => p.redditScore > 60 && p.trendsScore > 60).length;

    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div></div>
        <div class="sel-wrap"><select class="sel" id="focusSel">
          <option value="all">${s.focus}</option>
          ${P.slice().sort((a, b) => b.redditScore - a.redditScore).map((p) => `<option value="${p.id}" ${p.id === focusId ? 'selected' : ''}>${p.name}</option>`).join('')}
        </select></div>
      </div>
      <div class="kpi-mono-row rv">
        ${statTile('reddit', s.k_score, Sh.fmt(avgScore), 'var(--reddit)')}
        ${statTile('reddit', s.k_subs + ' (' + s.est + ')', activeSubs, 'var(--reddit)')}
        ${statTile('check', s.k_corro, corro, 'var(--buy)')}
      </div>
      <div class="section-row grid-21">
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.timeline}</div><div class="sub">${s.timeline_s}</div></div></div>
          <div class="chart-box"><div class="chart-h-box" id="barBox" style="height:220px"></div></div>
        </section>
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.subs}</div><div class="sub">${s.subs_s}</div></div></div>
          <div class="sub-list" id="subList"></div>
        </section>
      </div>
      <div class="section-row grid-21">
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.score_real}</div><div class="sub">${s.subs_s}</div></div></div>
          <div class="dg-scroll"><table class="dg"><thead><tr><th>${Sh.lang === 'fr' ? 'Produit' : 'Product'}</th><th class="num">Reddit</th></tr></thead><tbody id="scoreBody"></tbody></table></div>
        </section>
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.corr}</div><div class="sub">${s.corr_s}</div></div></div>
          <div class="chart-box"><div id="corrBox" style="width:100%;height:300px"></div></div>
        </section>
      </div>`;

    $('#focusSel').addEventListener('change', (e) => { focusId = e.target.value; render(); });

    // No real Reddit weekly time-series exists in the DB — show an explicit
    // empty-state rather than fabricating a curve from p.reddit.
    $('#barBox').innerHTML = `<div class="empty"><div class="e-art">${ic('reddit')}</div><div class="e-t">${s.empty_t}</div><div class="e-s">${s.empty_s}</div></div>`;

    // subreddit list — estimated from category × real Reddit score (labelled as estimate)
    const maxV = Math.max(...subs.map((x) => x.vol), 1);
    $('#subList').innerHTML = subs.slice(0, 8).map((x) => `
      <div class="sub-row">
        <div><div class="sub-name"><span class="r-badge">r/</span>${x.n}</div>
          <div class="sub-bar"><i style="width:${Math.round(x.vol / maxV * 100)}%"></i></div></div>
        <div class="sub-val">${x.vol}</div>
      </div>`).join('');

    // real per-product Reddit score table (replaces fabricated "notable posts")
    $('#scoreBody').innerHTML = P.slice().sort((a, b) => b.redditScore - a.redditScore).slice(0, 8).map((p) => `
      <tr data-id="${p.id}">
        <td><div class="cell-prod">${Sh.thumb(p, 30)}<div><div class="cp-name">${p.name}</div><div class="cp-sub">${T.CATS[p.cat][Sh.lang]}</div></div></div></td>
        <td class="num"><b>${p.redditScore}</b></td></tr>`).join('');
    $$('#scoreBody tr').forEach((r) => r.addEventListener('click', () => Sh.openProduct(P.find((p) => p.id === r.dataset.id))));

    // correlation scatter: x = reddit score, y = velocity(growth→0..100), size by margin
    const pts = P.map((p) => ({
      x: p.redditScore, y: clamp((p.growth + 0.5) / 2 * 100, 0, 100), r: 6 + p.gross / 3, color: `var(--${T.PHASES[p.phase].v})`, p,
      tip: `<div class="tip-h"><b>${p.name}</b><span class="tip-score">${p.tandor}</span></div><div class="tip-rows"><div><span>Reddit</span><b>${p.redditScore}</b></div><div><span>${Sh.lang === 'fr' ? 'Croissance' : 'Growth'}</span><b>${p.growth >= 0 ? '+' : ''}${Math.round(p.growth * 100)}%</b></div></div>`,
    }));
    X.scatter($('#corrBox'), pts, { xMax: 100, yMax: 100, xLabel: Sh.lang === 'fr' ? 'Mentions Reddit' : 'Reddit mentions', yLabel: Sh.lang === 'fr' ? 'Vélocité' : 'Velocity', height: 300, onPoint: (pt) => Sh.openProduct(pt.p) });
  }

  function statTile(icn, label, val, col) {
    return `<div class="stat-tile">
      <div class="st-l"><span class="st-ico" style="background:color-mix(in oklab, ${col} 14%, var(--surface-1));color:${col}">${ic(icn)}</span><span class="micro">${label}</span></div>
      <div class="st-v">${val}</div></div>`;
  }

  Sh.start({ active: 'n_reddit', render });
}
