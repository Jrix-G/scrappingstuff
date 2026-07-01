#!/usr/bin/env node
/* Blog programmatique SEO (mirroir de gen_seo_pages.js).
 * Lit products.json -> génère un blog HTML STATIQUE pré-rendu :
 *   - public/blog/<slug>.html  (un article par croisement template × donnée)
 *   - public/blog.html         (le hub listant tous les articles)
 *   - public/sitemap.xml       (FUSION additive : on garde les /produit/, on AJOUTE /blog/)
 *
 * Pourquoi du statique ? CRA est rendu côté client : seul le HTML pré-rendu s'indexe
 * proprement. On suit donc EXACTEMENT le pattern de gen_seo_pages.js (mêmes conventions
 * SITE / esc() / slugify() / <title>/meta/OG/twitter/canonical/JSON-LD).
 *
 * Data-driven & SCALABLE : les articles ne sont PAS écrits à la main. Ils naissent de
 * « familles » de templates croisées avec la donnée (catégories, signaux de perte,
 * saisonnalité…). Ajouter une catégorie ou des produits multiplie automatiquement le
 * nombre d'articles -> conçu pour passer à des centaines de pages.
 *
 * Domaine : SITE_URL=https://mondomaine.com node scripts/gen_blog.js
 *
 * POINT D'EXTENSION LLM (voir loadBodyOverride()) : un générateur de build ne peut pas
 * appeler un LLM par article. Les templates ci-dessous produisent donc du contenu riche,
 * varié et spécifique à la donnée (anti-« thin content »). Quand on voudra un corps rédigé
 * par un LLM, il suffira de déposer un cache JSON (blog_bodies.json) généré HORS-LIGNE :
 * { "<slug>": "<html du corps>" } -> il surchargera le corps template sans rien casser.
 */
const fs = require('fs');
const path = require('path');

const SITE = (process.env.SITE_URL || 'https://tandor.app').replace(/\/+$/, '');
const ROOT = path.resolve(__dirname, '..');
const PUB = path.join(ROOT, 'public');
const OUT = path.join(PUB, 'blog');
const YEAR = new Date().getFullYear();
const SNAP = new Date().toLocaleDateString('fr-FR');
const TODAY = new Date().toISOString().slice(0, 10);

const raw = require(path.join(ROOT, 'src/dashboard/products.json'));
const products = Array.isArray(raw) ? raw : (raw.products || Object.values(raw)[0] || []);

/* --- helpers repris de gen_seo_pages.js (mêmes conventions exactes) --- */
const esc = (s) => String(s ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

const slugify = (s) => String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 70);

/* Bandes QUALITATIVES (identiques à gen_seo_pages.js) : le public a le sens, pas les chiffres. */
const marginPctOf = (p) => (p.retail && p.cost) ? Math.round((1 - p.cost / p.retail) * 100) : null;
const demandBand = (s) => s == null ? 'non mesurée' : s >= 10000 ? 'forte' : s >= 1000 ? 'soutenue' : s >= 100 ? 'modérée' : 'faible';
const marginBand = (pct) => pct == null ? 'à calculer' : pct >= 70 ? 'confortable' : pct >= 50 ? 'correcte' : pct >= 30 ? 'serrée' : 'faible';
const satBand = (listed) => listed == null ? 'non mesurée' : listed <= 10 ? 'peu saturé' : listed <= 40 ? 'concurrence modérée' : 'marché saturé';

/* On reconstruit le slug produit EXACTEMENT comme gen_seo_pages.js (même dédup) pour que
   les liens internes /produit/<slug>.html pointent vers des pages réellement générées. */
(function assignProductSlugs() {
  const seen = new Set();
  let i = 0;
  for (const p of products) {
    if (!p || !p.name) continue;
    let slug = slugify(p.name) || ('p-' + (p.id || i));
    if (seen.has(slug)) slug = `${slug}-${p.id || i}`;
    seen.add(slug);
    p.slug = slug;
    p._viable = (p.trapVerdict === 'VIABLE' || p.verdict === 'BUY');
    i++;
  }
})();
const valid = products.filter((p) => p && p.name && p.slug);

/* Libellés FR des catégories (la donnée stocke un code en MAJ). */
const CAT_FR = {
  WELLNESS: 'Bien-être', TECH: 'Tech & gadgets', HOME: 'Maison & déco',
  PETS: 'Animaux', APPAREL: 'Mode & accessoires', BEAUTY: 'Beauté & soin',
  OUTDOOR: 'Plein air & sport',
};
const catLabel = (c) => CAT_FR[c] || (c ? c.charAt(0) + c.slice(1).toLowerCase() : 'Divers');
const MONTHS = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];

/* Index par catégorie. */
const byCat = {};
for (const p of valid) { (byCat[p.cat] = byCat[p.cat] || []).push(p); }
const cats = Object.keys(byCat).sort((a, b) => byCat[b].length - byCat[a].length);

/* Définition des 6 signaux de perte (alignés sur lossFlags). Chaque signal porte sa
   propre pédagogie -> articles « comment repérer un piège à fric » non dupliqués. */
const FLAG_DEFS = {
  marge: {
    titre: 'la marge nette',
    sujet: 'une marge nette trop faible',
    pourquoi: "La marge nette (ce qui reste après le coût fournisseur, les frais de port et la commission plateforme) est ce qui décide si une vente te rapporte ou te coûte. Un produit peut sembler « pas cher à sourcer » et quand même te ruiner si le prix de revente ne laisse pas de place au coût d'acquisition client (CPA).",
    rouge: "marge serrée ou faible : chaque euro de pub mal placé te fait passer en perte.",
    vert: "marge confortable : tu absorbes un CPA élevé sans saigner.",
  },
  prix: {
    titre: 'le prix de vente',
    sujet: 'un prix hors de la zone d\'impulsion',
    pourquoi: "Le prix retail détermine la facilité de l'achat impulsif. Trop bas, la marge ne couvre pas la pub ; trop haut, le visiteur réfléchit, compare, abandonne. La « zone d'impulsion » est l'intervalle où l'on achète sans hésiter.",
    rouge: "prix hors zone d'impulsion : conversion en chute, CPA qui explose.",
    vert: "prix dans la zone d'impulsion : l'achat se fait à l'instinct.",
  },
  demande: {
    titre: 'la demande réelle',
    sujet: 'une demande non prouvée',
    pourquoi: "La demande est le carburant. Sans preuve d'achats récurrents (ventes marketplaces, achats mensuels constatés), tu paries sur un marché qui n'existe peut-être pas. La demande « prouvée » s'appuie sur des signaux publics, pas sur une intuition.",
    rouge: "demande faible ou non mesurée : tu crées un marché à tes frais.",
    vert: "demande prouvée : des gens achètent déjà, tu n'as qu'à mieux vendre.",
  },
  retour: {
    titre: 'le taux de retour',
    sujet: 'un risque de retours élevé',
    pourquoi: "Un produit fragile, à la taille incertaine ou décevant à la réception génère des retours. Chaque retour annule la marge de plusieurs ventes et plombe les avis. C'est le coût caché qui transforme un « gagnant » apparent en gouffre.",
    rouge: "signaux de retour élevés : la marge nette part en remboursements.",
    vert: "retours sous contrôle : la marge reste dans ta poche.",
  },
  saturation: {
    titre: 'la saturation du marché',
    sujet: 'un marché saturé',
    pourquoi: "Le nombre de vendeurs déjà positionnés mesure la concurrence. Sur un marché saturé, les enchères pub montent, les prix s'effondrent et les marges fondent. Un produit « peu saturé » laisse encore de l'air pour une offre différenciée.",
    rouge: "marché saturé : guerre des prix et CPA gonflé par les enchères.",
    vert: "marché peu saturé : de la place pour une offre qui se démarque.",
  },
  'déclin': {
    titre: 'le déclin de tendance',
    sujet: 'une tendance en déclin',
    pourquoi: "Un produit en fin de cycle aspire ton budget pendant que la demande s'effrite. Le déclin se lit dans la dérivée de la demande : pas le niveau d'aujourd'hui, mais sa pente. Lancer sur une courbe descendante, c'est courir après un train qui part.",
    rouge: "tendance en baisse : tu investis pile quand le marché se vide.",
    vert: "tendance stable ou montante : le timing joue pour toi.",
  },
};

const flagLevel = (p, name) => {
  const f = (p.lossFlags || []).find((x) => x.name === name);
  return f ? f.level : null;
};

/* =========================================================================
 * SHELL HTML COMMUN — même thème / mêmes balises SEO que gen_seo_pages.js.
 * ========================================================================= */
function articleShell({ slug, title, desc, h1, kicker, badge, breadcrumb, bodyHtml, jsonldGraph }) {
  const url = `${SITE}/blog/${slug}.html`;
  const jsonld = { '@context': 'https://schema.org', '@graph': jsonldGraph };
  const bc = breadcrumb.map((b, i) => i === breadcrumb.length - 1
    ? esc(b.name)
    : `<a href="${b.item.replace(SITE, '')}">${esc(b.name)}</a>`).join(' › ');
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
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font-family:'Hanken Grotesk',system-ui,sans-serif;line-height:1.65}
a{color:inherit}.wrap{max-width:760px;margin:0 auto;padding:32px 20px 64px}
.bc{font-size:13px;color:var(--muted);margin-bottom:24px}.bc a{text-decoration:none;border-bottom:1px solid var(--line)}
.kicker{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 10px}
h1{font-size:clamp(26px,5vw,38px);line-height:1.15;margin:0 0 16px;font-weight:800}
.badge{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;padding:6px 12px;border-radius:999px;border:1px solid var(--line);margin-bottom:20px}
.ok{color:var(--ok);border-color:#1f5e47}.bad{color:var(--bad);border-color:#5e1f1f}
.lead{font-size:18px;color:var(--muted);margin:0 0 28px}
.snap{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--muted);margin:0 0 24px}
h2{font-size:23px;margin:40px 0 10px;font-weight:800}h3{font-size:18px;margin:26px 0 6px}
p{margin:0 0 16px}ul,ol{margin:0 0 18px;padding-left:22px}li{margin:6px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:6px 20px;margin:24px 0}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:13px 4px;font-size:15px;border-bottom:1px solid var(--line)}
tr:last-child th,tr:last-child td{border-bottom:0}th{color:var(--muted);font-weight:500}td .pill{font-family:'JetBrains Mono',monospace;font-size:12px}
.tag-ok{color:var(--ok)}.tag-bad{color:var(--bad)}.tag-na{color:var(--muted)}
.cta{display:inline-block;margin-top:8px;background:var(--brand);color:#0a0b0d;font-weight:700;text-decoration:none;padding:14px 26px;border-radius:12px}
.related{margin:28px 0;padding:18px 20px;background:var(--card);border:1px solid var(--line);border-radius:14px}
.related h3{margin:0 0 10px;font-size:16px}.related ul{margin:0;list-style:none;padding:0}
.related li{padding:9px 0;border-bottom:1px solid var(--line)}.related li:last-child{border-bottom:0}
.related a{text-decoration:none;border-bottom:1px solid var(--line)}
footer{margin-top:48px;padding-top:24px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}
footer a{border-bottom:1px solid var(--line);text-decoration:none}
.disc{font-size:12px;color:#6b7075;margin-top:14px}
</style>
</head>
<body>
<main class="wrap">
<nav class="bc">${bc}</nav>
${kicker ? `<p class="kicker">${esc(kicker)}</p>` : ''}
${badge ? `<span class="badge ${badge.cls}">${esc(badge.text)}</span>` : ''}
<h1>${esc(h1)}</h1>
<span class="snap">📸 Snapshot du ${SNAP} · données rafraîchies en temps réel dans l'app</span>
${bodyHtml}
<div class="related">
<h3>🔒 Passe des signaux publics aux chiffres exacts</h3>
<p style="color:var(--muted);font-size:14px;margin:0 0 14px">Cet article s'appuie sur des bandes qualitatives. La marge nette en €, le CPA de rentabilité, les fournisseurs et les alertes de déclin sont dans l'app.</p>
<a class="cta" href="/register">Débloquer la version live — gratuit →</a>
&nbsp;<a href="/pricing" style="font-size:14px;color:var(--muted)">Voir les offres</a>
</div>
<p class="disc">Snapshot indicatif basé sur des signaux publics (marketplaces, tendances) au ${SNAP}. Non garanti — la donnée bouge chaque jour, les verdicts évoluent. Ceci n'est pas un conseil en investissement.</p>
<footer>© ${YEAR} Tandor — le détecteur de pièges à fric du dropshipping. <a href="/blog.html">Tous les articles</a> · <a href="/produits.html">Tous les produits</a> · <a href="/pricing">Tarifs</a></footer>
</main>
</body>
</html>`;
}

/* Carte d'un produit cité (lien interne vers la page SEO produit). */
function productRow(p) {
  const cls = p._viable ? 'tag-ok' : 'tag-bad';
  const tag = p._viable ? 'viable' : 'risqué';
  const mpct = marginPctOf(p);
  return `<tr><th scope="row"><a href="/produit/${p.slug}.html" style="text-decoration:none;border-bottom:1px solid var(--line)">${esc(p.name.length > 60 ? p.name.slice(0, 57) + '…' : p.name)}</a></th>`
    + `<td><span class="pill">marge ${marginBand(mpct)}</span></td>`
    + `<td><span class="pill">conc. ${satBand(p.listed)}</span></td>`
    + `<td><span class="pill ${cls}">${tag}</span></td></tr>`;
}

/* Bloc « liens internes » vers d'autres articles + produits. */
function relatedBlock(links) {
  if (!links.length) return '';
  return `<div class="related"><h3>À lire aussi</h3><ul>${
    links.map((l) => `<li><a href="${l.href}">${esc(l.text)}</a></li>`).join('')
  }</ul></div>`;
}

const breadcrumbLd = (items) => ({
  '@type': 'BreadcrumbList',
  itemListElement: items.map((b, i) => ({ '@type': 'ListItem', position: i + 1, name: b.name, item: b.item })),
});
const articleLd = (slug, title, desc) => ({
  '@type': 'Article', headline: title, description: desc,
  datePublished: TODAY, dateModified: TODAY,
  mainEntityOfPage: `${SITE}/blog/${slug}.html`,
  author: { '@type': 'Organization', name: 'Tandor' },
  publisher: { '@type': 'Organization', name: 'Tandor', logo: { '@type': 'ImageObject', url: `${SITE}/logo512.png` } },
});

/* Point d'extension LLM : corps rédigé hors-ligne, surchargé si présent. */
let BODY_OVERRIDES = {};
try {
  const cache = path.join(__dirname, 'blog_bodies.json');
  if (fs.existsSync(cache)) BODY_OVERRIDES = JSON.parse(fs.readFileSync(cache, 'utf8')) || {};
} catch (e) { /* cache absent ou invalide : on garde les corps template */ }

/* =========================================================================
 * FAMILLES DE TEMPLATES — chaque fonction renvoie un objet article complet.
 * Le contenu pioche dans la donnée (noms, bandes, compteurs) => unique par page.
 * ========================================================================= */
const articles = [];
const push = (a) => { a.slug = slugify(a.slug); articles.push(a); };

/* --- Famille A : Guide par catégorie ------------------------------------ */
function familyCategoryGuide() {
  for (const cat of cats) {
    const list = byCat[cat];
    const label = catLabel(cat);
    const viables = list.filter((p) => p._viable);
    const risky = list.filter((p) => !p._viable);
    const slug = `dropshipping-${cat.toLowerCase()}-${YEAR}-gagnants-vs-pieges`;
    const title = `Dropshipping ${label} en ${YEAR} : produits gagnants vs pièges à fric — Tandor`;
    const desc = `${list.length} produits ${label.toLowerCase()} passés au crible : ${viables.length} encore viables, ${risky.length} à risque. Marge, saturation, déclin — repère les pièges avant de lancer en ${YEAR}.`;
    const top = viables.slice(0, 8);
    const flagged = risky.slice(0, 6);
    const body = `
<p class="lead">La catégorie <strong>${esc(label)}</strong> est l'une des plus chassées en dropshipping. Tandor y a analysé <strong>${list.length} produits</strong> à partir de signaux publics : ${viables.length} ressortent encore viables, ${risky.length} portent des signaux de perte. Voici comment trier le gagnant du piège à fric en ${YEAR}.</p>
<h2>Pourquoi la plupart des produits ${esc(label.toLowerCase())} font perdre de l'argent</h2>
<p>Un produit n'est pas « bon » ou « mauvais » dans l'absolu : il l'est <em>à un prix d'acquisition donné</em>. La majorité des lancements ${esc(label.toLowerCase())} échouent pour trois raisons cumulées : une marge trop serrée pour absorber le coût pub, un marché déjà saturé qui gonfle les enchères, et une demande supposée plutôt que prouvée. Tandor mesure ces axes séparément pour éviter le piège classique du « ça a l'air de cartonner sur TikTok ».</p>
<h2>${top.length} produits ${esc(label.toLowerCase())} encore viables repérés</h2>
<p>Ces références cumulent des signaux favorables (marge tenable, concurrence respirable, demande constatée). Chaque fiche détaille le verdict :</p>
<div class="card"><table><tbody>
${top.map(productRow).join('\n')}
</tbody></table></div>
${flagged.length ? `<h2>Produits ${esc(label.toLowerCase())} à surveiller de près</h2>
<p>À l'inverse, ces produits portent au moins un signal rouge. Cela ne veut pas dire « jamais », mais « pas sans vérifier le détail » :</p>
<div class="card"><table><tbody>
${flagged.map(productRow).join('\n')}
</tbody></table></div>` : '<p>Bonne nouvelle pour cette catégorie : aucun produit de notre échantillon ne cumule de signaux disqualifiants ce mois-ci. Reste à valider le CPA réel.</p>'}
<h2>La méthode Tandor en ${esc(label.toLowerCase())}, en 4 réflexes</h2>
<ol>
<li><strong>La marge avant le buzz.</strong> Calcule la marge nette ; si elle est « serrée » ou « faible », un seul CPA élevé t'envoie en perte.</li>
<li><strong>Compte les vendeurs.</strong> Plus le marché est saturé, plus les enchères pub montent. Vise « peu saturé » ou « concurrence modérée ».</li>
<li><strong>Exige une demande prouvée.</strong> Des achats récurrents constatés, pas une vidéo virale isolée.</li>
<li><strong>Surveille la pente, pas le pic.</strong> Un produit ${esc(label.toLowerCase())} en déclin aspire ton budget pendant que la demande s'effrite.</li>
</ol>
<h2>Les 3 erreurs qui ruinent un lancement ${esc(label.toLowerCase())}</h2>
<p>La première, c'est de confondre <strong>tendance virale</strong> et <strong>demande durable</strong> : une vidéo qui explose attire des dizaines de revendeurs en quelques jours, la catégorie ${esc(label.toLowerCase())} se sature, et le coût d'acquisition double avant même que tu aies optimisé ta page. La deuxième, c'est de regarder la marge brute (prix moins coût fournisseur) en oubliant le port, les commissions et la provision pour retours : sur ${list.length} produits analysés ici, plusieurs affichent une marge brute flatteuse mais une marge nette qui ne tolère aucun écart de CPA. La troisième, c'est d'ignorer le calendrier : un produit ${esc(label.toLowerCase())} lancé après son pic de demande paie la publicité au prix fort sur une courbe qui redescend.</p>
<p>La parade est toujours la même : isoler chaque signal (marge, prix, demande, retour, saturation, déclin), refuser de lancer dès que deux signaux passent au rouge, et fixer un plafond de CPA <em>avant</em> de dépenser le premier euro. C'est exactement la grille que Tandor applique aux ${list.length} produits de la catégorie ${esc(label)}.</p>
<h2>Faut-il fuir toute la catégorie ${esc(label.toLowerCase())} ?</h2>
<p>Non. Une catégorie n'est jamais « morte » ou « gagnante » en bloc : elle contient à la fois des pièges et des fenêtres. ${viables.length > risky.length ? `Ici, le solde penche du bon côté (${viables.length} viables contre ${risky.length} à risque), preuve qu'il reste de la place pour une offre sérieuse.` : `Ici le terrain est plus miné (${risky.length} à risque sur ${list.length}) : raison de plus pour trier produit par produit plutôt que de suivre la hype.`} L'enjeu n'est pas de deviner « la » bonne niche, mais d'écarter méthodiquement les produits qui te feront perdre de l'argent.</p>
<p>Envie du détail chiffré (marge nette en €, CPA de rentabilité, fournisseurs, alerte déclin) ? C'est dans l'app.</p>
`;
    push({
      slug, title, desc, h1: `Dropshipping ${label} en ${YEAR} : gagnants vs pièges à fric`,
      kicker: `Guide catégorie · ${label}`,
      badge: { cls: viables.length >= risky.length ? 'ok' : 'bad', text: `${viables.length} viables / ${risky.length} à risque` },
      breadcrumb: [{ name: 'Tandor', item: `${SITE}/` }, { name: 'Blog', item: `${SITE}/blog.html` }, { name: `Guide ${label}`, item: `${SITE}/blog/${slug}.html` }],
      body, cat, family: 'guide',
      related: [
        { href: `/blog/${slugify(`produits-${cat.toLowerCase()}-viables-${YEAR}`)}.html`, text: `Les ${viables.length} produits ${label.toLowerCase()} viables repérés en ${YEAR}` },
        { href: `/blog/${slugify(`marge-rentable-${cat.toLowerCase()}-cpa-breakeven-${YEAR}`)}.html`, text: `Quelle marge pour ne pas perdre en ${label.toLowerCase()} ?` },
      ],
    });
  }
}

/* --- Famille B : Liste « X produits viables » par catégorie ------------- */
function familyViableList() {
  for (const cat of cats) {
    const viables = byCat[cat].filter((p) => p._viable);
    if (viables.length < 2) continue; // évite les listes trop maigres
    const label = catLabel(cat);
    const slug = `produits-${cat.toLowerCase()}-viables-${YEAR}`;
    const title = `${viables.length} produits ${label.toLowerCase()} viables repérés en ${YEAR} — Tandor`;
    const desc = `Sélection ${YEAR} : ${viables.length} produits ${label.toLowerCase()} qui passent le filtre anti-piège de Tandor (marge tenable, concurrence respirable, demande prouvée).`;
    const items = viables.slice(0, 15);
    const body = `
<p class="lead">Sur les produits <strong>${esc(label.toLowerCase())}</strong> analysés par Tandor, <strong>${viables.length}</strong> franchissent le filtre anti-piège à fric. « Viable » ne veut pas dire « facile » : ça veut dire que la marge, la concurrence et la demande laissent une fenêtre de rentabilité — à condition de tenir ton CPA.</p>
<h2>La sélection ${esc(label.toLowerCase())} ${YEAR}</h2>
<div class="card"><table><tbody>
${items.map(productRow).join('\n')}
</tbody></table></div>
<h2>Comment lire « viable »</h2>
<p>Un produit est marqué viable quand il ne déclenche aucun signal rouge disqualifiant et qu'au moins la demande et la marge sont au vert. Concrètement, ça signifie un seuil de CPA respirable : tant que ton coût d'acquisition reste sous ce plafond, chaque vente est bénéficiaire.</p>
<h3>Ce que « viable » ne garantit PAS</h3>
<ul>
<li>Que <em>ton</em> exécution (créa, offre, SAV) suivra — le produit ouvre la porte, c'est tout.</li>
<li>Que le marché le restera : la saturation et la tendance évoluent, d'où le suivi en continu.</li>
<li>Que les retours seront faibles si l'information manque encore (signal « inconnu »).</li>
</ul>
<h2>Comment cette sélection a été filtrée</h2>
<p>Aucune de ces ${viables.length} références n'a été retenue « à l'œil ». Chaque produit ${esc(label.toLowerCase())} est passé par les six signaux de perte de Tandor : marge nette, prix dans la zone d'impulsion, demande prouvée par des achats récents, taux de retour, nombre de vendeurs concurrents et tendance de la demande. Un produit n'entre dans cette liste que s'il ne déclenche aucun rouge disqualifiant — et il en ressort dès qu'un signal bascule. C'est pour ça que la sélection vit : elle est recalculée à chaque rafraîchissement de données, pas figée dans un article.</p>
<h2>Viable ne veut pas dire « facile »</h2>
<p>Un produit ${esc(label.toLowerCase())} viable t'offre une fenêtre de rentabilité, pas une garantie. Deux personnes qui lancent le même produit obtiennent des résultats opposés selon la qualité de l'offre, des créas publicitaires et du service après-vente. Ce que la mention « viable » te dit, c'est que le terrain de jeu n'est pas piégé d'avance : la marge laisse respirer ton CPA et la demande existe déjà. À toi de transformer cette fenêtre en marge réelle.</p>
<h2>Le réflexe avant de lancer</h2>
<p>Avant d'engager un budget pub, vérifie le plafond de CPA et la marge nette exacte de chaque produit dans l'app. C'est la différence entre « ça avait l'air bien » et « ça paie ».</p>
<p>Garde aussi en tête que cette liste ${esc(label.toLowerCase())} est un point de départ, pas une fin : la vraie décision se prend produit par produit, en croisant son plafond de CPA, sa marge nette réelle et l'état de la concurrence au moment où <em>toi</em> tu lances. Un produit viable aujourd'hui peut se saturer en quelques semaines si une vidéo virale attire une vague de revendeurs ; à l'inverse, un produit aujourd'hui à risque peut redevenir intéressant quand le bruit retombe. C'est pour ça que Tandor suit ces signaux en continu plutôt que de te laisser avec une capture figée.</p>
`;
    push({
      slug, title, desc, h1: `${viables.length} produits ${label.toLowerCase()} viables repérés en ${YEAR}`,
      kicker: `Sélection · ${label}`,
      badge: { cls: 'ok', text: `${viables.length} produits viables` },
      breadcrumb: [{ name: 'Tandor', item: `${SITE}/` }, { name: 'Blog', item: `${SITE}/blog.html` }, { name: `Viables ${label}`, item: `${SITE}/blog/${slug}.html` }],
      body, cat, family: 'liste',
      related: [
        { href: `/blog/${slugify(`dropshipping-${cat.toLowerCase()}-${YEAR}-gagnants-vs-pieges`)}.html`, text: `Guide complet : dropshipping ${label.toLowerCase()} en ${YEAR}` },
        { href: `/produits.html`, text: 'Voir les 60 produits analysés' },
      ],
    });
  }
}

/* --- Famille C : « Comment repérer un piège à fric » par signal --------- */
function familyFlagExplainer() {
  for (const [name, def] of Object.entries(FLAG_DEFS)) {
    const reds = valid.filter((p) => flagLevel(p, name) === 'red');
    const greens = valid.filter((p) => flagLevel(p, name) === 'green');
    const examplesRed = reds.slice(0, 5);
    const examplesGreen = greens.slice(0, 5);
    const slug = `comment-reperer-piege-a-fric-${slugify(name)}`;
    const title = `Comment repérer un piège à fric : ${def.titre} (${YEAR}) — Tandor`;
    const desc = `Repérer ${def.sujet} avant de lancer : pourquoi ${def.titre} fait perdre de l'argent en dropshipping, les signaux rouges et comment les vérifier en ${YEAR}.`;
    const body = `
<p class="lead">Sur les six signaux que Tandor surveille pour détecter un piège à fric, <strong>${esc(def.titre)}</strong> est l'un des plus traîtres : ${esc(def.pourquoi.split('.')[0].toLowerCase())}.</p>
<h2>Pourquoi ${esc(def.titre)} fait perdre de l'argent</h2>
<p>${esc(def.pourquoi)}</p>
<div class="card"><table><tbody>
<tr><th scope="row">Signal rouge 🔴</th><td>${esc(def.rouge)}</td></tr>
<tr><th scope="row">Signal vert 🟢</th><td>${esc(def.vert)}</td></tr>
</tbody></table></div>
<h2>Comment le vérifier en pratique</h2>
<ol>
<li><strong>Mesure, ne devine pas.</strong> Appuie-toi sur des données publiques (marketplaces, historique de demande) plutôt que sur une impression.</li>
<li><strong>Croise avec les autres signaux.</strong> ${esc(def.titre.charAt(0).toUpperCase() + def.titre.slice(1))} seule ne suffit pas : c'est l'accumulation de rouges qui condamne un produit.</li>
<li><strong>Refais le test dans le temps.</strong> Un signal au vert aujourd'hui peut virer au rouge ; le suivi en continu évite de lancer trop tard.</li>
</ol>
${examplesRed.length ? `<h2>Exemples de produits où ce signal est au rouge</h2>
<p>Dans notre échantillon, ces produits déclenchent l'alerte « ${esc(def.titre)} » — à vérifier avant tout budget :</p>
<div class="card"><table><tbody>
${examplesRed.map(productRow).join('\n')}
</tbody></table></div>` : ''}
${examplesGreen.length ? `<h2>À quoi ressemble le signal au vert</h2>
<p>À l'opposé, ces produits passent ce filtre sans encombre :</p>
<div class="card"><table><tbody>
${examplesGreen.map(productRow).join('\n')}
</tbody></table></div>` : ''}
<h2>Le scénario classique du piège</h2>
<p>Voilà comment ${esc(def.sujet)} fait perdre de l'argent en pratique. Tu repères un produit qui « cartonne », tu te fies à un signal flatteur (un buzz, un prix bas, une jolie marge brute) et tu ignores celui-ci. Les premières ventes tombent, l'euphorie monte, tu augmentes le budget. Puis le coût d'acquisition grimpe, la marge réelle se révèle, et chaque vente supplémentaire creuse le trou au lieu de le combler. Le produit n'a pas « changé » : c'est le signal que tu n'avais pas mesuré qui s'est rappelé à toi. Détecté <em>avant</em> le lancement, ce même signal t'aurait fait passer ton chemin — ou ajuster ton prix et ton plafond de CPA.</p>
<h2>Questions fréquentes</h2>
<h3>${esc(def.titre.charAt(0).toUpperCase() + def.titre.slice(1))} suffit-elle à condamner un produit ?</h3>
<p>Rarement seule. Un signal rouge isolé appelle la prudence, pas le rejet automatique. Ce qui condamne un produit, c'est l'accumulation : dès que deux signaux passent au rouge, la probabilité de perte grimpe fortement. ${esc(def.titre.charAt(0).toUpperCase() + def.titre.slice(1))} doit donc se lire en regard des cinq autres.</p>
<h3>Comment savoir si ce signal va évoluer ?</h3>
<p>En le mesurant dans le temps, pas une seule fois. ${reds.length ? `Sur notre échantillon, ${reds.length} produit(s) portent aujourd'hui ce signal au rouge` : 'Un signal au vert aujourd’hui peut basculer'} — et l'inverse est vrai. C'est précisément pourquoi Tandor rafraîchit ses données en continu plutôt que de figer un verdict.</p>
<h2>Le piège à fric, c'est l'addition</h2>
<p>Un produit gagnant n'a pas besoin d'être parfait sur les six signaux — mais il ne doit pas cumuler les rouges. ${esc(def.titre.charAt(0).toUpperCase() + def.titre.slice(1))} est une pièce du puzzle ; Tandor assemble les six (marge, prix, demande, retour, saturation, déclin) pour donner un verdict, et surtout un plafond de CPA au-delà duquel tu perds.</p>
`;
    push({
      slug, title, desc, h1: `Comment repérer un piège à fric : ${def.titre}`,
      kicker: 'Méthode anti-piège',
      badge: { cls: 'bad', text: `Signal : ${def.titre}` },
      breadcrumb: [{ name: 'Tandor', item: `${SITE}/` }, { name: 'Blog', item: `${SITE}/blog.html` }, { name: def.titre, item: `${SITE}/blog/${slug}.html` }],
      body, cat: null, family: 'methode',
      related: Object.entries(FLAG_DEFS).filter(([n]) => n !== name).slice(0, 3)
        .map(([n, d]) => ({ href: `/blog/${slugify(`comment-reperer-piege-a-fric-${slugify(n)}`)}.html`, text: `Repérer ${d.sujet}` })),
    });
  }
}

/* --- Famille D : Saisonnalité par catégorie ----------------------------- */
function familySeasonality() {
  for (const cat of cats) {
    const list = byCat[cat].filter((p) => p.seasonPeak && p._viable);
    if (list.length < 2) continue;
    const label = catLabel(cat);
    // pic dominant de la catégorie
    const counts = {};
    list.forEach((p) => { counts[p.seasonPeak] = (counts[p.seasonPeak] || 0) + 1; });
    const peakMonth = Number(Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0]);
    const slug = `saisonnalite-dropshipping-${cat.toLowerCase()}-${YEAR}`;
    const title = `Quand lancer un produit ${label.toLowerCase()} ? Saisonnalité ${YEAR} — Tandor`;
    const desc = `Timing ${YEAR} en ${label.toLowerCase()} : pic de demande autour de ${MONTHS[peakMonth]}, produits saisonniers et fenêtre de lancement pour ne pas arriver après la vague.`;
    const items = list.sort((a, b) => (a.seasonPeak - b.seasonPeak)).slice(0, 12);
    const body = `
<p class="lead">En <strong>${esc(label.toLowerCase())}</strong>, le timing change tout. Lancer trois semaines trop tard, c'est payer la pub au prix fort quand la demande redescend. D'après les pics observés, la fenêtre chaude de la catégorie tourne autour de <strong>${esc(MONTHS[peakMonth])}</strong>.</p>
<h2>Pourquoi la saisonnalité décide de ta rentabilité</h2>
<p>La demande d'un produit saisonnier n'est pas une ligne plate : c'est une vague. Le coût d'acquisition est faible en début de vague (peu de concurrents, demande qui monte) et devient ruineux au sommet puis sur la pente descendante. Le métier, c'est d'entrer <em>avant</em> le pic, pas pendant.</p>
<h2>Produits ${esc(label.toLowerCase())} et leur pic de demande</h2>
<p>Chaque produit a son propre pic ; voici les références viables triées par mois de pointe :</p>
<div class="card"><table><tbody>
${items.map((p) => `<tr><th scope="row"><a href="/produit/${p.slug}.html" style="text-decoration:none;border-bottom:1px solid var(--line)">${esc(p.name.length > 50 ? p.name.slice(0, 47) + '…' : p.name)}</a></th><td><span class="pill">pic : ${esc(MONTHS[p.seasonPeak] || '—')}</span></td><td><span class="pill ${p._viable ? 'tag-ok' : 'tag-bad'}">${p._viable ? 'viable' : 'risqué'}</span></td></tr>`).join('\n')}
</tbody></table></div>
<h2>Régler le timing en 3 étapes</h2>
<ol>
<li><strong>Repère le pic.</strong> Identifie le mois de pointe du produit (ici, beaucoup convergent vers ${esc(MONTHS[peakMonth])}).</li>
<li><strong>Recule de 4 à 6 semaines.</strong> Construis l'offre et chauffe les créas avant que les enchères pub ne s'enflamment.</li>
<li><strong>Prévois la sortie.</strong> Un produit saisonnier décline aussi vite qu'il monte : planifie l'arrêt pub pour ne pas brûler ta marge sur la pente.</li>
</ol>
<h2>Le vrai risque : arriver en retard</h2>
<p>En ${esc(label.toLowerCase())}, le danger n'est pas de choisir le mauvais produit, mais le mauvais moment. Le coût d'acquisition n'est pas constant : il est bas quand la demande monte et que peu de concurrents enchérissent, puis il explose au sommet de la vague, quand tout le monde se rue sur les mêmes audiences. Un produit parfaitement viable en avril peut devenir un gouffre en plein pic si tu n'arrives qu'à ce moment-là. C'est le paradoxe de la saisonnalité : plus un produit « marche » visiblement, plus il est cher à acquérir — et plus la fenêtre rentable s'est déjà refermée.</p>
<h2>Préparer la prochaine vague ${esc(label.toLowerCase())}</h2>
<p>Avec un pic dominant autour de ${esc(MONTHS[peakMonth])}, la fenêtre de préparation idéale commence plusieurs semaines avant. Profite du creux pour tester tes créas à petit budget, valider ta page produit et sécuriser ton sourcing : quand la demande décolle, tu veux être prêt à scaler, pas à débugger ta boutique. Et garde un œil sur la pente de demande de chaque référence : un produit dont la courbe pluriannuelle s'érode n'aura pas le même pic que l'an dernier, même au « bon » mois.</p>
<p>Un dernier rappel : la saisonnalité ne remplace pas les autres signaux, elle s'y ajoute. Un produit ${esc(label.toLowerCase())} parfaitement calé sur son pic reste un piège si sa marge est trop serrée ou son marché déjà saturé. Le bon timing maximise un produit sain ; il ne sauve pas un produit malade. Regarde donc d'abord le verdict global, puis sers-toi du calendrier pour choisir <em>quand</em> appuyer sur l'accélérateur.</p>
<p>Le multiplicateur saisonnier exact et l'historique de demande de chaque produit sont calculés dans l'app.</p>
`;
    push({
      slug, title, desc, h1: `Quand lancer un produit ${label.toLowerCase()} ? Saisonnalité ${YEAR}`,
      kicker: `Saisonnalité · ${label}`,
      badge: { cls: 'ok', text: `Pic : ${MONTHS[peakMonth]}` },
      breadcrumb: [{ name: 'Tandor', item: `${SITE}/` }, { name: 'Blog', item: `${SITE}/blog.html` }, { name: `Saisonnalité ${label}`, item: `${SITE}/blog/${slug}.html` }],
      body, cat, family: 'saison',
      related: [
        { href: `/blog/${slugify(`dropshipping-${cat.toLowerCase()}-${YEAR}-gagnants-vs-pieges`)}.html`, text: `Guide : dropshipping ${label.toLowerCase()} en ${YEAR}` },
      ],
    });
  }
}

/* --- Famille E : Marge & CPA breakeven par catégorie -------------------- */
function familyMargin() {
  for (const cat of cats) {
    const list = byCat[cat].filter((p) => marginPctOf(p) != null);
    if (list.length < 2) continue;
    const label = catLabel(cat);
    const withCpa = list.filter((p) => p.breakevenCpa != null);
    const avgMargin = Math.round(list.reduce((s, p) => s + marginPctOf(p), 0) / list.length);
    const slug = `marge-rentable-${cat.toLowerCase()}-cpa-breakeven-${YEAR}`;
    const title = `Quelle marge pour ne pas perdre d'argent en ${label.toLowerCase()} ? CPA breakeven ${YEAR} — Tandor`;
    const desc = `Marge moyenne ${avgMargin}% en ${label.toLowerCase()} ne suffit pas : c'est le CPA de rentabilité qui décide. Méthode ${YEAR} pour calculer ton plafond d'acquisition avant de lancer.`;
    const top = withCpa.sort((a, b) => (b.breakevenCpa || 0) - (a.breakevenCpa || 0)).slice(0, 10);
    const body = `
<p class="lead">En <strong>${esc(label.toLowerCase())}</strong>, la marge brute moyenne de notre échantillon tourne autour de <strong>${avgMargin}%</strong>. Mais une marge brute élevée ne garantit rien : ce qui décide, c'est le <strong>CPA de rentabilité</strong> — le coût d'acquisition au-delà duquel chaque vente te fait perdre de l'argent.</p>
<h2>Marge brute ≠ profit</h2>
<p>Beaucoup de débutants regardent l'écart entre coût fournisseur et prix de vente, et s'arrêtent là. Erreur. Entre les deux, il y a le port, la commission plateforme, les retours… et surtout la pub. Un produit à 80% de marge brute peut être déficitaire si ton CPA dépasse le seuil de rentabilité.</p>
<h2>Le bon indicateur : le CPA breakeven</h2>
<p>Le CPA breakeven est le montant maximum que tu peux dépenser pour acquérir un client tout en restant à l'équilibre. En dessous, tu gagnes ; au-dessus, tu perds. C'est le seul chiffre qui transforme « belle marge » en « business viable ».</p>
${top.length ? `<h2>Plafonds de CPA observés en ${esc(label.toLowerCase())}</h2>
<p>Voici, pour quelques produits viables de la catégorie, le plafond d'acquisition à ne pas dépasser :</p>
<div class="card"><table><tbody>
${top.map((p) => `<tr><th scope="row"><a href="/produit/${p.slug}.html" style="text-decoration:none;border-bottom:1px solid var(--line)">${esc(p.name.length > 48 ? p.name.slice(0, 45) + '…' : p.name)}</a></th><td><span class="pill">marge ${marginBand(marginPctOf(p))}</span></td><td><span class="pill">CPA max ≈ ${Math.round(p.breakevenCpa)}€</span></td></tr>`).join('\n')}
</tbody></table></div>` : ''}
<h2>Calculer ton plafond en 3 nombres</h2>
<ol>
<li><strong>Marge nette par vente</strong> = prix − coût fournisseur − port − commission − provision retours.</li>
<li><strong>Taux de conversion</strong> réaliste de ta page produit (souvent 1 à 3%).</li>
<li><strong>CPA breakeven</strong> = marge nette × taux de conversion : c'est ce que tu peux payer par clic/visiteur sans perdre.</li>
</ol>
<h2>Un exemple chiffré en ${esc(label.toLowerCase())}</h2>
<p>Prends un produit à 80% de marge brute — le genre de chiffre qui rassure. Sur un prix de revente de 40&nbsp;€, ça laisse 32&nbsp;€ avant pub. Mais retire 4&nbsp;€ de port, 2&nbsp;€ de commission plateforme et une provision retours de 3&nbsp;€ : ta marge nette tombe à 23&nbsp;€. Avec un taux de conversion de 2%, ton CPA de rentabilité réel n'est plus « 80% de 40&nbsp;€ », mais de l'ordre de la marge nette par visiteur converti. Le jour où ton coût d'acquisition dépasse ce seuil, chaque vente te coûte de l'argent — alors même que ton tableau de bord affiche fièrement « 80% de marge ». Voilà pourquoi la marge brute est un mirage et le CPA breakeven, la seule boussole.</p>
<h2>Pourquoi viser une marge confortable en ${esc(label.toLowerCase())}</h2>
<p>Plus ta marge nette est haute, plus ton plafond de CPA est élevé, et plus tu absorbes les jours où la publicité coûte cher sans passer en perte. Une marge « serrée » ne te laisse aucune marge d'erreur : un CPM qui monte, une audience qui se fatigue, un pic de retours, et la rentabilité disparaît. C'est tout l'intérêt de comparer les produits ${esc(label.toLowerCase())} sur leur plafond de CPA plutôt que sur leur marge brute affichée : le premier chiffre dit combien d'oxygène tu as, le second n'est qu'une promesse.</p>
<p>Tandor calcule ces trois nombres pour toi et te donne directement le plafond de CPA produit par produit — pour arrêter de lancer à l'aveugle.</p>
`;
    push({
      slug, title, desc, h1: `Quelle marge pour ne pas perdre d'argent en ${label.toLowerCase()} ?`,
      kicker: `Marge & CPA · ${label}`,
      badge: { cls: 'ok', text: `Marge moy. ~${avgMargin}%` },
      breadcrumb: [{ name: 'Tandor', item: `${SITE}/` }, { name: 'Blog', item: `${SITE}/blog.html` }, { name: `Marge ${label}`, item: `${SITE}/blog/${slug}.html` }],
      body, cat, family: 'marge',
      related: [
        { href: `/blog/${slugify('comment-reperer-piege-a-fric-marge')}.html`, text: 'Comment repérer une marge piège' },
        { href: `/blog/${slugify(`dropshipping-${cat.toLowerCase()}-${YEAR}-gagnants-vs-pieges`)}.html`, text: `Guide : dropshipping ${label.toLowerCase()} en ${YEAR}` },
      ],
    });
  }
}

/* --- Génération de tous les corps + assemblage final -------------------- */
familyCategoryGuide();
familyViableList();
familyFlagExplainer();
familySeasonality();
familyMargin();

/* =========================================================================
 * ÉCRITURE DES ARTICLES
 * ========================================================================= */
// Purge des articles orphelins (anciennes définitions) avant régénération.
fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(OUT, { recursive: true });
const seenSlug = new Set();
const written = [];
/* Ensemble des slugs réellement produits : sert à élaguer les liens internes « À lire
   aussi » qui pointeraient vers un article non généré (ex. une catégorie trop petite dont
   la liste/marge a été sautée). Évite tout lien interne 404 (mauvais pour le SEO). */
const articleSlugSet = new Set(articles.map((a) => a.slug));
const keepRelated = (links) => (links || []).filter((l) => {
  const m = /^\/blog\/([^/]+)\.html$/.exec(l.href);
  return !m || articleSlugSet.has(m[1]); // garde les liens non-blog (/produit/, /produits.html…) tels quels
});
for (const a of articles) {
  if (seenSlug.has(a.slug)) continue; // sécurité anti-collision
  seenSlug.add(a.slug);
  const bodyHtml = (BODY_OVERRIDES[a.slug] || a.body) + relatedBlock(keepRelated(a.related));
  const html = articleShell({
    slug: a.slug, title: a.title, desc: a.desc, h1: a.h1,
    kicker: a.kicker, badge: a.badge, breadcrumb: a.breadcrumb, bodyHtml,
    jsonldGraph: [articleLd(a.slug, a.title, a.desc), breadcrumbLd(a.breadcrumb)],
  });
  fs.writeFileSync(path.join(OUT, `${a.slug}.html`), html);
  written.push(a);
}

/* =========================================================================
 * HUB public/blog.html — liste tous les articles, groupés par famille.
 * ========================================================================= */
function hubHtml(list) {
  const url = `${SITE}/blog.html`;
  const title = `Blog Tandor : éviter les pièges à fric du dropshipping en ${YEAR}`;
  const desc = `${list.length} guides data-driven : produits gagnants vs pièges par catégorie, méthode anti-perte (marge, saturation, déclin), saisonnalité et CPA de rentabilité.`;
  const FAMILY_FR = { guide: 'Guides par catégorie', liste: 'Sélections de produits', methode: 'Méthode anti-piège', saison: 'Saisonnalité & timing', marge: 'Marge & rentabilité' };
  const order = ['guide', 'liste', 'methode', 'saison', 'marge'];
  const groups = order.filter((f) => list.some((a) => a.family === f)).map((f) => ({
    f, label: FAMILY_FR[f], items: list.filter((a) => a.family === f),
  }));
  const sections = groups.map((g) => `
<h2>${esc(g.label)}</h2>
<ul>${g.items.map((a) => `<li><a href="/blog/${a.slug}.html">${esc(a.h1)}</a>${a.badge ? ` <span class="${a.badge.cls === 'ok' ? 'ok' : 'bad'}">${esc(a.badge.text)}</span>` : ''}</li>`).join('\n')}</ul>`).join('\n');
  const itemListLd = {
    '@context': 'https://schema.org', '@type': 'ItemList',
    itemListElement: list.map((a, i) => ({ '@type': 'ListItem', position: i + 1, url: `${SITE}/blog/${a.slug}.html`, name: a.h1 })),
  };
  return `<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>${esc(title)}</title>
<meta name="description" content="${esc(desc)}"/>
<link rel="canonical" href="${url}"/>
<link rel="alternate" hreflang="fr" href="${url}"/>
<meta property="og:type" content="website"/>
<meta property="og:title" content="${esc(title)}"/><meta property="og:description" content="${esc(desc)}"/>
<meta property="og:url" content="${url}"/><meta property="og:image" content="${SITE}/logo512.png"/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="${esc(title)}"/><meta name="twitter:description" content="${esc(desc)}"/>
<link rel="icon" href="/favicon.ico"/>
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;600;800&display=swap" rel="stylesheet"/>
<script type="application/ld+json">${JSON.stringify(itemListLd)}</script>
<style>body{margin:0;background:#0a0b0d;color:#e8eaed;font-family:'Hanken Grotesk',system-ui,sans-serif;line-height:1.6}
.wrap{max-width:760px;margin:0 auto;padding:40px 20px 64px}h1{font-size:clamp(26px,5vw,38px);font-weight:800;margin:0 0 14px}
.lead{color:#9aa0a6;font-size:18px;margin:0 0 32px}h2{font-size:20px;margin:34px 0 10px;font-weight:800}
ul{list-style:none;padding:0;margin:0}li{padding:13px 0;border-bottom:1px solid #23262b}
li a{color:#e8eaed;text-decoration:none;border-bottom:1px solid #23262b}
.ok{color:#34d399;font-size:12px;font-family:'JetBrains Mono',monospace}.bad{color:#f87171;font-size:12px;font-family:'JetBrains Mono',monospace}
a.home{color:#9aa0a6;font-size:13px;text-decoration:none}
footer{margin-top:48px;padding-top:24px;border-top:1px solid #23262b;color:#9aa0a6;font-size:13px}footer a{color:#9aa0a6}</style>
</head><body><main class="wrap">
<a class="home" href="/">← Tandor</a>
<h1>Le blog anti-piège à fric</h1>
<p class="lead">${esc(desc)}</p>
${sections}
<footer>© ${YEAR} Tandor. <a href="/produits.html">Tous les produits analysés</a> · <a href="/pricing">Tarifs</a></footer>
</main></body></html>`;
}
fs.writeFileSync(path.join(PUB, 'blog.html'), hubHtml(written));

/* =========================================================================
 * SITEMAP — FUSION ADDITIVE.
 * gen_seo_pages.js écrit sitemap.xml avec les URLs / et /produit/.
 * Ici on LIT l'existant et on INJECTE les /blog/ avant </urlset>, sans rien
 * supprimer. Idempotent : un bloc balisé BLOG est remplacé à chaque run.
 * Ordre prebuild recommandé : gen_seo_pages.js PUIS gen_blog.js.
 * ========================================================================= */
function mergeSitemap() {
  const file = path.join(PUB, 'sitemap.xml');
  const blogUrls = [
    `<url><loc>${SITE}/blog.html</loc><lastmod>${TODAY}</lastmod><changefreq>weekly</changefreq></url>`,
    ...written.map((a) => `<url><loc>${SITE}/blog/${a.slug}.html</loc><lastmod>${TODAY}</lastmod><changefreq>weekly</changefreq></url>`),
  ];
  const block = `<!-- BLOG:START -->\n${blogUrls.join('\n')}\n<!-- BLOG:END -->`;

  let xml;
  if (fs.existsSync(file)) {
    xml = fs.readFileSync(file, 'utf8');
    // retire un ancien bloc blog éventuel (idempotence) sans toucher aux /produit/
    xml = xml.replace(/\n?<!-- BLOG:START -->[\s\S]*?<!-- BLOG:END -->\n?/g, '\n');
    if (/<\/urlset>/.test(xml)) {
      xml = xml.replace(/<\/urlset>/, `${block}\n</urlset>`);
    } else {
      // fichier présent mais sans urlset valide : on reconstruit proprement
      xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${block}\n</urlset>\n`;
    }
  } else {
    // sitemap absent (gen_seo_pages.js pas encore passé) : on crée un minimal
    xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${block}\n</urlset>\n`;
  }
  fs.writeFileSync(file, xml);
}
mergeSitemap();

console.log(`OK: ${written.length} articles blog + blog.html + sitemap.xml fusionné (base ${SITE})`);
console.log(`   familles -> guide:${written.filter(a=>a.family==='guide').length} liste:${written.filter(a=>a.family==='liste').length} methode:${written.filter(a=>a.family==='methode').length} saison:${written.filter(a=>a.family==='saison').length} marge:${written.filter(a=>a.family==='marge').length}`);
