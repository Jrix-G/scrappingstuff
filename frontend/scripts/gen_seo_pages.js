#!/usr/bin/env node
/* SEO programmatique (audit Partie 3).
 * Lit products.json -> génère une page HTML STATIQUE pré-rendue par produit
 * dans public/produit/<slug>.html + un hub public/produits.html + sitemap.xml.
 * Ces pages sont indépendantes du SPA React : aucun composant front modifié.
 * Domaine: SITE_URL=https://mondomaine.com node scripts/gen_seo_pages.js
 */
const fs = require('fs');
const path = require('path');

const SITE = (process.env.SITE_URL || 'https://tandor.app').replace(/\/+$/, '');
const ROOT = path.resolve(__dirname, '..');
const PUB = path.join(ROOT, 'public');
const OUT = path.join(PUB, 'produit');
const YEAR = new Date().getFullYear();

const raw = require(path.join(ROOT, 'src/dashboard/products.json'));
const products = Array.isArray(raw) ? raw : (raw.products || Object.values(raw)[0] || []);

const esc = (s) => String(s ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

const slugify = (s) => String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 70);

const VERDICT_FR = { BUY: 'À acheter', WATCH: 'À surveiller', AVOID: 'À éviter', PASS: 'À éviter' };

/* Bandes QUALITATIVES : la page publique donne le sens, pas les chiffres exacts.
   Les valeurs précises (marge €, coût, score, fournisseurs) restent derrière l'app. */
const demandBand = (s) => s == null ? 'Non mesurée' : s >= 10000 ? 'Forte' : s >= 1000 ? 'Soutenue' : s >= 100 ? 'Modérée' : 'Faible';
const marginBand = (pct) => pct == null ? 'À calculer' : pct >= 70 ? 'Confortable' : pct >= 50 ? 'Correcte' : pct >= 30 ? 'Serrée' : 'Faible';
const satBand = (listed) => listed == null ? 'Non mesurée' : listed <= 10 ? 'Peu saturé' : listed <= 40 ? 'Concurrence modérée' : 'Marché saturé';

function pageHtml(p) {
  const name = p.name || 'Produit';
  const slug = p.slug;
  const url = `${SITE}/produit/${slug}.html`;
  const marginPct = (p.retail && p.cost) ? Math.round((1 - p.cost / p.retail) * 100) : null;
  const verdict = VERDICT_FR[p.verdict] || (p.trapVerdict === 'VIABLE' ? 'À surveiller' : 'À éviter');
  const viable = p.trapVerdict === 'VIABLE' || p.verdict === 'BUY';
  const demand = demandBand(p.aliExpressSold);
  const margin = marginBand(marginPct);
  const sat = satBand(p.listed);
  const SNAP = new Date().toLocaleDateString('fr-FR');
  const title = `${name} : encore rentable en dropshipping en ${YEAR} ? — Tandor`;
  const desc = `Demande ${demand.toLowerCase()}, marge ${margin.toLowerCase()}, concurrence « ${sat.toLowerCase()} » : verdict Tandor pour le ${name}. Évite de lancer un produit piège en ${YEAR}.`;
  const lead = `${viable ? `✅ Encore viable en ${YEAR}` : `⚠️ Produit à risque en ${YEAR}`} — demande ${demand.toLowerCase()}, marge ${margin.toLowerCase()}, concurrence « ${sat.toLowerCase()} », d'après les signaux croisés de Tandor.`;

  const faq = [
    {
      q: `Le ${name} est-il encore rentable en ${YEAR} ?`,
      a: `Verdict Tandor : ${verdict.toLowerCase()}. Demande ${demand.toLowerCase()}, marge ${margin.toLowerCase()}, concurrence « ${sat.toLowerCase()} ». ${viable ? 'Encore lançable avec une bonne offre.' : 'Risque élevé de perte — à éviter ou à valider de près.'}`,
    },
    {
      q: `Le ${name} est-il saturé ?`,
      a: `Niveau de concurrence : « ${sat.toLowerCase()} ». ${viable ? 'Le marché laisse encore de la place.' : 'Le marché est tendu, prudence avant de miser un budget pub.'}`,
    },
    {
      q: `Combien rapporte une vente du ${name} ?`,
      a: `La marge est jugée « ${margin.toLowerCase()} ». Les chiffres exacts — coût fournisseur, prix conseillé et marge nette en €/vente — sont calculés dans l'app Tandor.`,
    },
  ];

  const jsonld = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Product', name, category: p.cat || undefined,
        description: desc,
      },
      {
        '@type': 'FAQPage',
        mainEntity: faq.map((f) => ({ '@type': 'Question', name: f.q, acceptedAnswer: { '@type': 'Answer', text: f.a } })),
      },
      { '@type': 'BreadcrumbList', itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Produits', item: `${SITE}/produits.html` },
        { '@type': 'ListItem', position: 2, name, item: url },
      ] },
    ],
  };

  const row = (k, v) => `<tr><th scope="row">${esc(k)}</th><td>${esc(v)}</td></tr>`;

  return `<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>${esc(title)}</title>
<meta name="description" content="${esc(desc)}"/>
<link rel="canonical" href="${url}"/>
<link rel="alternate" hreflang="fr" href="${url}"/>
<link rel="alternate" hreflang="x-default" href="${url}"/>
<meta property="og:type" content="article"/>
<meta property="og:title" content="${esc(title)}"/>
<meta property="og:description" content="${esc(desc)}"/>
<meta property="og:url" content="${url}"/>
<meta property="og:image" content="${SITE}/logo512.png"/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="${esc(title)}"/>
<meta name="twitter:description" content="${esc(desc)}"/>
<link rel="icon" href="/favicon.ico"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet"/>
<script type="application/ld+json">${JSON.stringify(jsonld)}</script>
<style>
:root{--bg:#0a0b0d;--card:#141619;--line:#23262b;--txt:#e8eaed;--muted:#9aa0a6;--ok:#34d399;--bad:#f87171;--brand:#f5f5f5}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font-family:'Hanken Grotesk',system-ui,sans-serif;line-height:1.6}
a{color:inherit}.wrap{max-width:760px;margin:0 auto;padding:32px 20px 64px}
.bc{font-size:13px;color:var(--muted);margin-bottom:24px}.bc a{text-decoration:none;border-bottom:1px solid var(--line)}
h1{font-size:clamp(26px,5vw,38px);line-height:1.15;margin:0 0 16px;font-weight:800}
.badge{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;padding:6px 12px;border-radius:999px;border:1px solid var(--line);margin-bottom:20px}
.ok{color:var(--ok);border-color:#1f5e47}.bad{color:var(--bad);border-color:#5e1f1f}
.lead{font-size:18px;color:var(--muted);margin:0 0 28px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:6px 20px;margin:24px 0}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:14px 4px;font-size:15px;border-bottom:1px solid var(--line)}
tr:last-child th,tr:last-child td{border-bottom:0}th{color:var(--muted);font-weight:500;width:55%}td{font-family:'JetBrains Mono',monospace}
h2{font-size:22px;margin:40px 0 8px}.faq{border-top:1px solid var(--line);padding:18px 0}.faq h3{margin:0 0 6px;font-size:17px}.faq p{margin:0;color:var(--muted)}
.cta{display:inline-block;margin-top:8px;background:var(--brand);color:#0a0b0d;font-weight:700;text-decoration:none;padding:14px 26px;border-radius:12px}
footer{margin-top:48px;padding-top:24px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}
.disc{font-size:12px;color:#6b7075;margin-top:14px}
.snap{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--muted);margin:0 0 24px}
.locked{position:relative;background:linear-gradient(180deg,rgba(20,22,25,.4),var(--card));border:1px dashed var(--line);border-radius:14px;padding:22px 20px;margin:28px 0}
.locked h3{margin:0 0 4px;font-size:17px}.locked .sub{color:var(--muted);font-size:14px;margin:0 0 16px}
.lk-row{display:flex;align-items:center;gap:10px;padding:11px 0;border-bottom:1px solid var(--line);color:var(--muted);font-size:15px}
.lk-row:last-of-type{border-bottom:0}.lk-row .v{margin-left:auto;font-family:'JetBrains Mono',monospace;filter:blur(5px);user-select:none;color:var(--txt)}
</style>
</head>
<body>
<main class="wrap">
<nav class="bc"><a href="/">Tandor</a> › <a href="/produits.html">Produits</a> › ${esc(name)}</nav>
<span class="badge ${viable ? 'ok' : 'bad'}">${viable ? '✅' : '⚠️'} Verdict : ${esc(verdict)}</span>
<h1>Le ${esc(name)} est-il encore rentable en dropshipping en ${YEAR} ?</h1>
<p class="lead">${esc(lead)}</p>
<span class="snap">📸 Snapshot du ${SNAP} · données rafraîchies en temps réel dans l'app</span>
<div class="card"><table>
${row('Catégorie', p.cat || '—')}
${row('Demande', demand)}
${row('Marge', margin)}
${row('Concurrence', sat)}
${p.phase ? row('Phase de cycle', p.phase) : ''}
${row('Verdict Tandor', verdict)}
</table></div>
<h2>Questions fréquentes</h2>
${faq.map((f) => `<div class="faq"><h3>${esc(f.q)}</h3><p>${esc(f.a)}</p></div>`).join('\n')}
<div class="locked">
<h3>🔒 La version live, dans l'app</h3>
<p class="sub">Ce snapshot date du ${SNAP}. Les données qui font gagner ou perdre de l'argent bougent chaque jour — voici ce que Tandor te donne en direct :</p>
<div class="lk-row">Marge nette exacte (€/vente)<span class="v">••,•• €</span></div>
<div class="lk-row">Coût fournisseur &amp; prix conseillé<span class="v">••,•• €</span></div>
<div class="lk-row">Score Tandor détaillé /100<span class="v">••</span></div>
<div class="lk-row">Fournisseurs identifiés<span class="v">•••</span></div>
<div class="lk-row">Alerte si ce produit décline<span class="v">•••</span></div>
<a class="cta" href="/register">Débloquer la version live — gratuit →</a>
</div>
<p class="disc">Snapshot indicatif basé sur des signaux publics (marketplaces, tendances) au ${SNAP}. Non garanti. Les valeurs floutées sont des exemples — les données réelles sont dans l'app.</p>
<footer>© ${YEAR} Tandor — le détecteur de pièges à fric du dropshipping. <a href="/produits.html">Voir tous les produits</a> · <a href="/blog.html">Le blog</a></footer>
</main>
</body>
</html>`;
}

function hubHtml(items) {
  const url = `${SITE}/produits.html`;
  const title = `Quels produits dropshipping sont rentables en ${YEAR} ? — Tandor`;
  const desc = `${items.length} produits passés au crible : demande, marge, saturation et déclin. Repère les pièges à fric AVANT de lancer.`;
  const list = items.map((p) =>
    `<li><a href="/produit/${p.slug}.html">${esc(p.name)}</a> <span class="${(p.trapVerdict==='VIABLE'||p.verdict==='BUY')?'ok':'bad'}">${(p.trapVerdict==='VIABLE'||p.verdict==='BUY')?'viable':'risqué'}</span></li>`
  ).join('\n');
  return `<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>${esc(title)}</title>
<meta name="description" content="${esc(desc)}"/>
<link rel="canonical" href="${url}"/>
<meta property="og:title" content="${esc(title)}"/><meta property="og:description" content="${esc(desc)}"/>
<meta property="og:url" content="${url}"/><meta property="og:image" content="${SITE}/logo512.png"/>
<meta name="twitter:card" content="summary_large_image"/>
<link rel="icon" href="/favicon.ico"/>
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;600;800&display=swap" rel="stylesheet"/>
<style>body{margin:0;background:#0a0b0d;color:#e8eaed;font-family:'Hanken Grotesk',system-ui,sans-serif;line-height:1.6}
.wrap{max-width:760px;margin:0 auto;padding:40px 20px 64px}h1{font-size:clamp(26px,5vw,38px);font-weight:800;margin:0 0 14px}
.lead{color:#9aa0a6;font-size:18px;margin:0 0 32px}ul{list-style:none;padding:0;margin:0}
li{padding:14px 0;border-bottom:1px solid #23262b}li a{color:#e8eaed;text-decoration:none;border-bottom:1px solid #23262b}
.ok{color:#34d399;font-size:13px}.bad{color:#f87171;font-size:13px}a.home{color:#9aa0a6;font-size:13px;text-decoration:none}</style>
</head><body><main class="wrap">
<a class="home" href="/">← Tandor</a>
<h1>Quels produits sont encore rentables en ${YEAR} ?</h1>
<p class="lead">${esc(desc)}</p>
<ul>${list}</ul>
<p style="margin-top:32px"><a class="home" href="/blog.html">Lire le blog : guides anti-pièges →</a></p>
</main></body></html>`;
}

function sitemap(items) {
  const stat = ['/', '/produits.html', '/pricing', '/homeby'];
  const today = new Date().toISOString().slice(0, 10);
  const urls = [
    ...stat.map((u) => `<url><loc>${SITE}${u}</loc><changefreq>weekly</changefreq></url>`),
    ...items.map((p) => `<url><loc>${SITE}/produit/${p.slug}.html</loc><lastmod>${today}</lastmod><changefreq>weekly</changefreq></url>`),
  ];
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.join('\n')}\n</urlset>\n`;
}

// --- run ---
// Purge des slugs orphelins (anciens products.json) : sinon des pages mortes,
// hors sitemap et non liées, restent crawlables et créent du contenu thin.
fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(OUT, { recursive: true });
const seen = new Set();
const items = [];
for (const p of products) {
  if (!p || !p.name) continue;
  let slug = slugify(p.name) || ('p-' + (p.id || items.length));
  if (seen.has(slug)) slug = `${slug}-${p.id || items.length}`;
  seen.add(slug);
  p.slug = slug;
  fs.writeFileSync(path.join(OUT, `${slug}.html`), pageHtml(p));
  items.push(p);
}
fs.writeFileSync(path.join(PUB, 'produits.html'), hubHtml(items));
fs.writeFileSync(path.join(PUB, 'sitemap.xml'), sitemap(items));
console.log(`OK: ${items.length} pages produit + produits.html + sitemap.xml (base ${SITE})`);
