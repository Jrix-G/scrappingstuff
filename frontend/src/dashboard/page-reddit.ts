/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-reddit.js   (Reddit Intelligence)
   HONNÊTETÉ : il n'existe AUCUN flux Reddit réel par produit dans
   le projet (pas de mentions persistées, pas de subreddits, pas de
   série temporelle). Le SEUL signal Reddit réel est `redditScore`,
   et il n'est mesuré que pour les produits où `hasReddit === true`.
   Cette page n'affiche donc QUE ce score réel ; partout où le signal
   manque, elle montre un empty-state explicite. Aucun post, aucun
   compteur d'upvotes, aucune courbe ni subreddit n'est fabriqué.
   ============================================================ */
export function mountReddit() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR, C = window.Charts, X = window.ChartsX, P = T.PRODUCTS;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic;

  const STR = {
    en: { title: 'Reddit Intelligence', sub: 'real per-product Reddit score · measured only',
      k_measured: 'Products measured', k_score: 'Avg Reddit score (measured)', k_coverage: 'Coverage',
      list: 'Reddit score by product', list_s: 'real score — only products with a measured signal are shown',
      empty_list_t: 'No Reddit signal measured yet',
      empty_list_s: 'Reddit mentions are fetched live and never persisted per product, so a score only exists once a product has actually been measured. None have been yet — we never fabricate a score.',
      why_t: 'Why no threads, upvotes or subreddit breakdown?',
      why_s: 'Those would require a persisted per-product Reddit feed, which this pipeline does not collect. Rather than invent posts or mention counts, we show nothing where there is nothing to show. Only the score below is real.',
      none: '—', product: 'Product' },
    fr: { title: 'Reddit Intelligence', sub: 'score Reddit réel par produit · mesurés uniquement',
      k_measured: 'Produits mesurés', k_score: 'Score Reddit moyen (mesurés)', k_coverage: 'Couverture',
      list: 'Score Reddit par produit', list_s: 'score réel — seuls les produits avec un signal mesuré sont affichés',
      empty_list_t: 'Aucun signal Reddit mesuré pour l’instant',
      empty_list_s: 'Les mentions Reddit sont récupérées en direct et jamais persistées par produit : un score n’existe qu’une fois le produit réellement mesuré. Aucun ne l’est encore — nous ne fabriquons jamais de score.',
      why_t: 'Pourquoi aucun thread, upvote ni détail par subreddit ?',
      why_s: 'Cela exigerait un flux Reddit persisté par produit, que ce pipeline ne collecte pas. Plutôt que d’inventer des posts ou des compteurs de mentions, nous n’affichons rien là où il n’y a rien. Seul le score ci-dessous est réel.',
      none: '—', product: 'Produit' },
  };
  const L = () => STR[Sh.lang];

  // SIGNAL RÉEL : redditScore mesuré (hasReddit === true & valeur non nulle).
  function measured() {
    return P.filter((p) => p.hasReddit === true && p.redditScore != null)
      .slice().sort((a, b) => b.redditScore - a.redditScore);
  }

  function render() {
    const s = L();
    const meas = measured();
    const avg = meas.length ? Math.round(meas.reduce((a, p) => a + p.redditScore, 0) / meas.length) : null;
    const cov = P.length ? Math.round((meas.length / P.length) * 100) : 0;

    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div></div>
      </div>
      <div class="kpi-mono-row rv">
        ${statTile('reddit', s.k_measured, `${meas.length} / ${P.length}`, 'var(--reddit)')}
        ${statTile('reddit', s.k_score, avg == null ? s.none : Sh.fmt(avg), 'var(--reddit)')}
        ${statTile('signal', s.k_coverage, cov + '%', 'var(--reddit)')}
      </div>
      <div class="section-row grid-21">
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.list}</div><div class="sub">${s.list_s}</div></div></div>
          <div id="scoreBox"></div>
        </section>
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.why_t}</div></div></div>
          <div class="empty"><div class="e-art">${ic('reddit')}</div>
            <div class="e-t">${s.why_t}</div><div class="e-s">${s.why_s}</div></div>
        </section>
      </div>`;

    // Liste des produits AVEC un score Reddit réel — sinon empty-state honnête.
    if (!meas.length) {
      $('#scoreBox').innerHTML = `<div class="empty"><div class="e-art">${ic('reddit')}</div>
        <div class="e-t">${s.empty_list_t}</div><div class="e-s">${s.empty_list_s}</div></div>`;
      return;
    }
    $('#scoreBox').innerHTML = `<div class="dg-scroll"><table class="dg">
      <thead><tr><th>${s.product}</th><th class="num">Reddit</th></tr></thead>
      <tbody id="scoreBody">${meas.map((p) => `
        <tr data-id="${p.id}">
          <td><div class="cell-prod">${Sh.thumb(p, 30)}<div><div class="cp-name">${p.name}</div>
            <div class="cp-sub">${T.CATS[p.cat][Sh.lang]}</div></div></div></td>
          <td class="num"><b>${p.redditScore}</b></td></tr>`).join('')}
      </tbody></table></div>`;
    $$('#scoreBody tr').forEach((r) => r.addEventListener('click', () => Sh.openProduct(P.find((p) => p.id === r.dataset.id))));
  }

  function statTile(icn, label, val, col) {
    return `<div class="stat-tile">
      <div class="st-l"><span class="st-ico" style="background:color-mix(in oklab, ${col} 14%, var(--surface-1));color:${col}">${ic(icn)}</span><span class="micro">${label}</span></div>
      <div class="st-v">${val}</div></div>`;
  }

  Sh.start({ active: 'n_reddit', render });
}
