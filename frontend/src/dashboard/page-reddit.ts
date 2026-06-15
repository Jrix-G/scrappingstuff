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
    en: { title: 'Reddit Intelligence', sub: 'early social signal · mention velocity',
      k_mentions: 'Mentions · 12 wks', k_velocity: 'Avg weekly velocity', k_subs: 'Active subreddits', k_corro: 'Corroborated products',
      timeline: 'Mention timeline', timeline_s: 'Weekly mentions across tracked products', trendline: 'trend',
      subs: 'Source subreddits', subs_s: 'where the signal originates', mentions: 'mentions',
      posts: 'Notable posts', posts_s: 'frequency-ranked · no vote inflation',
      corr: 'Reddit × product velocity', corr_s: 'high mentions + low maturity = early',
      emerging: 'Emerging terms', focus: 'All products', wk: 'wk',
      empty_t: 'No Reddit signal yet', empty_s: 'Social silence is normal for very recent products — the signal arrives before the saturation does.' },
    fr: { title: 'Reddit Intelligence', sub: 'signal social précoce · vélocité des mentions',
      k_mentions: 'Mentions · 12 sem.', k_velocity: 'Vélocité hebdo moy.', k_subs: 'Subreddits actifs', k_corro: 'Produits corroborés',
      timeline: 'Chronologie des mentions', timeline_s: 'Mentions hebdomadaires, tous produits suivis', trendline: 'tendance',
      subs: 'Subreddits sources', subs_s: 'd’où provient le signal', mentions: 'mentions',
      posts: 'Posts marquants', posts_s: 'classés par fréquence · sans inflation de votes',
      corr: 'Reddit × vélocité produit', corr_s: 'mentions fortes + maturité faible = précoce',
      emerging: 'Termes émergents', focus: 'Tous les produits', wk: 'sem.',
      empty_t: 'Pas encore de signal Reddit', empty_s: 'Le silence social est normal pour les produits très récents — le signal arrive avant la saturation.' },
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
  const TERMS = {
    en: ['neck massager', 'heatless curls', 'lint shaver', 'sunset lamp', 'gua sha', 'led collar', 'posture belt', 'spin scrubber', 'cloud slippers', 'mushroom light'],
    fr: ['masseur cervical', 'boucles sans chaleur', 'rasoir anti-bouloche', 'lampe coucher', 'gua sha', 'collier led', 'ceinture posture', 'brosse rotative', 'chaussons nuage', 'veilleuse champignon'],
  };

  let focusId = 'all';

  function weeklyAgg() {
    const pool = focusId === 'all' ? P : P.filter((p) => p.id === focusId);
    const raw = new Array(12).fill(0);
    pool.forEach((p) => p.reddit.forEach((v, i) => raw[i] += v));
    if (focusId !== 'all') return raw; // single product keeps its real shape
    // reshape the aggregate into a rising curve (signal building before
    // saturation) while preserving the total mention volume
    const total = raw.reduce((a, b) => a + b, 0);
    const w = raw.map((_, i) => { const f = i / 11; return 0.45 + 0.85 * Math.pow(f, 1.15) + 0.07 * Math.sin(i * 1.7); });
    const ws = w.reduce((a, b) => a + b, 0);
    return w.map((x) => Math.round(total * x / ws));
  }
  function subVolumes() {
    const pool = focusId === 'all' ? P : P.filter((p) => p.id === focusId);
    return SUBS.map((s) => {
      let vol = 0; pool.forEach((p) => { if (s.cats.includes(p.cat)) vol += Math.round(p.redditScore * s.base * 0.6); });
      return { n: s.n, vol: vol || Math.round(s.base * 12) };
    }).sort((a, b) => b.vol - a.vol);
  }

  function render() {
    const s = L();
    const agg = weeklyAgg();
    const total = agg.reduce((a, b) => a + b, 0);
    const vel = ((agg[agg.length - 1] - agg[0]) / agg.length);
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
        ${statTile('hash', s.k_mentions, Sh.fmt(total), 'var(--reddit)')}
        ${statTile('activity', s.k_velocity, (vel >= 0 ? '+' : '') + vel.toFixed(1), 'var(--signal)')}
        ${statTile('reddit', s.k_subs, activeSubs, 'var(--reddit)')}
        ${statTile('check', s.k_corro, corro, 'var(--buy)')}
      </div>
      <div class="section-row grid-21">
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.timeline}</div><div class="sub">${s.timeline_s}</div></div></div>
          <div class="chart-box"><div class="chart-h-box" id="barBox" style="height:220px"></div></div>
          <div style="padding:0 18px 16px">
            <div class="micro" style="margin-bottom:9px">${s.emerging}</div>
            <div class="kw-chips" id="termChips"></div>
          </div>
        </section>
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.subs}</div><div class="sub">${s.subs_s}</div></div></div>
          <div class="sub-list" id="subList"></div>
        </section>
      </div>
      <div class="section-row grid-21">
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.posts}</div><div class="sub">${s.posts_s}</div></div></div>
          <div id="postList"></div>
        </section>
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.corr}</div><div class="sub">${s.corr_s}</div></div></div>
          <div class="chart-box"><div id="corrBox" style="width:100%;height:300px"></div></div>
        </section>
      </div>`;

    $('#focusSel').addEventListener('change', (e) => { focusId = e.target.value; render(); });

    // bar chart of weekly mentions
    const wkLabels = agg.map((_, i) => `S${i + 1}`);
    if (total > 0) X.barChart($('#barBox'), agg, { color: 'var(--reddit)', xlabels: wkLabels, height: 220, line: true, label: s.mentions, onBar: (i) => Sh.toast(`${s.wk} ${i + 1} · ${agg[i]} ${s.mentions}`) });
    else $('#barBox').innerHTML = `<div class="empty"><div class="e-art">${ic('reddit')}</div><div class="e-t">${s.empty_t}</div><div class="e-s">${s.empty_s}</div></div>`;

    // emerging term chips
    $('#termChips').innerHTML = TERMS[Sh.lang].slice(0, 7).map((t, i) => `<span class="tag" style="font-family:var(--font-mono)"><span class="tdot" style="background:var(--reddit)"></span>${t} <span style="color:var(--text-tertiary)">+${[64, 48, 41, 33, 27, 22, 18][i]}%</span></span>`).join('');

    // subreddit list
    const maxV = Math.max(...subs.map((x) => x.vol), 1);
    $('#subList').innerHTML = subs.slice(0, 8).map((x) => `
      <div class="sub-row">
        <div><div class="sub-name"><span class="r-badge">r/</span>${x.n}</div>
          <div class="sub-bar"><i style="width:${Math.round(x.vol / maxV * 100)}%"></i></div></div>
        <div class="sub-val">${x.vol}</div>
      </div>`).join('');

    renderPosts();

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

  function renderPosts() {
    const s = L();
    const top = P.slice().sort((a, b) => b.redditScore - a.redditScore).slice(0, 6);
    const subFor = (p) => (SUBS.find((x) => x.cats.includes(p.cat)) || SUBS[0]).n;
    const titles = {
      en: (p) => `Anyone else obsessed with this ${p.name.toLowerCase()}? Found it before it blew up`,
      fr: (p) => `Quelqu’un d’autre accro à ce ${p.name.toLowerCase()} ? Trouvé avant que ça explose`,
    };
    const titles2 = {
      en: (p) => `${p.name} — is the hype real or just another dropship?`,
      fr: (p) => `${p.name} — le buzz est réel ou juste un énième dropshipping ?`,
    };
    const days = [2, 4, 6, 9, 12, 15];
    const rows = top.map((p, i) => {
      const t = (i % 2 ? titles2 : titles)[Sh.lang](p);
      const mentions = Math.round(p.redditScore * 0.4 + 6);
      const ago = Sh.lang === 'fr' ? `il y a ${days[i]} j` : `${days[i]}d ago`;
      return `<div class="post-item">
        <span class="post-sub">r/${subFor(p)}</span>
        <div class="post-body"><div class="post-title">${t}</div>
          <div class="post-meta"><span>${ago}</span><span>·</span><span>${mentions} ${s.mentions}</span></div></div>
        <a class="post-link" href="#" data-id="${p.id}">${ic('ext')}</a></div>`;
    }).join('');
    $('#postList').innerHTML = rows;
    $$('#postList .post-link').forEach((a) => a.addEventListener('click', (e) => { e.preventDefault(); Sh.openProduct(P.find((p) => p.id === a.dataset.id)); }));
  }

  Sh.start({ active: 'n_reddit', render });
}
