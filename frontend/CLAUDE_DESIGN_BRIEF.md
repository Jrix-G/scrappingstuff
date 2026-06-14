# Brief Claude Design — Tandor (SaaS)

> **À copier-coller dans Claude Design.** Ce brief décrit la mission, le design
> system EXISTANT à respecter scrupuleusement, et la liste exhaustive des pages
> à réaliser. Objectif : finir le produit avec un niveau de finition « 5 étoiles »
> qui inspire une confiance totale — surtout pas un rendu « généré par IA ».

---

## 0. Contexte & mission

Tandor est un SaaS de détection de produits e-commerce gagnants **avant** qu'ils
explosent (signal organique : Google Trends + Reddit + vélocité fournisseurs).
Le site existe déjà : une **landing** et un **dashboard** (React 19 + TypeScript,
Create React App, react-router) avec un design system mûr et une i18n FR/EN.

**Ta mission** : continuer sur la lancée existante et **réaliser les pages
manquantes** (listées en §6), dans le MÊME langage visuel, sans rien réinventer.
Le « Dashboard Home » est déjà fait et sert de référence de style : tu dois
t'aligner dessus, pas créer un nouveau style.

---

## 1. RÈGLE D'OR — inspirer la confiance, zéro « AI-like »

C'est le critère n°1. Un visiteur doit sentir un produit **construit par une
équipe exigeante**, pas généré. Concrètement, ce qui trahit l'IA et qu'il faut
**bannir** :

- ❌ Dégradés « blob » flous, glassmorphism cliché, formes 3D flottantes, halos néon.
- ❌ Emojis en guise d'icônes. → Utiliser **un seul jeu d'icônes cohérent** (le
  dashboard a déjà une fonction `ic()` avec des icônes au trait — la réutiliser).
- ❌ Cartes génériques « titre + phrase + emoji » alignées 3 par 3 sans hiérarchie.
- ❌ Microcopie vague (« Bienvenue sur votre dashboard ! »). → Texte **précis,
  confiant, spécifique au métier** (chiffres réels, vocabulaire e-commerce).
- ❌ Arc-en-ciel de couleurs. → **Un seul accent** (indigo), le vert UNIQUEMENT
  pour la data-viz.
- ❌ Espacements approximatifs, baselines non alignées, rayons incohérents.

Ce qui crée la confiance (à **viser**) :

- ✅ **Densité d'information crédible** façon « market desk » : de vraies données
  plausibles, des chiffres en `tabular-nums`, des tableaux denses mais lisibles —
  comme Linear et Stripe montrent toujours du contenu réaliste, jamais du lorem.
- ✅ **Typographie précise** : échelle de type nette, tracking serré sur les
  grands titres, `font-variant-numeric: tabular-nums` sur TOUTE donnée chiffrée.
- ✅ **Retenue** : beaucoup d'espace négatif maîtrisé, profondeur par les ombres
  douces définies (pas de drop-shadow lourde), bordures fines `--line`.
- ✅ **Cohérence pixel** : même rayon de carte, même traitement de bordure, même
  rythme d'espacement (grille 8px) partout.
- ✅ **États vides soignés** (jamais une zone blanche) et **skeleton loaders**
  (pas de spinners) pendant les chargements — très Linear/Stripe.

---

## 2. Design system à RESPECTER (ne rien inventer)

Tout est déjà défini dans `src/Styles/base.css`, `src/Styles/sections.css`
(landing) et `src/dashboard/app.css` (dashboard, scopé sous `.tandor-dash`).
**Réutiliser ces variables, ne pas en créer de nouvelles.**

### Polices (et leurs rôles)
- **Hanken Grotesk** (`--font-sans`) : tout le texte UI.
- **JetBrains Mono** (`--font-mono`) : chiffres, métriques, scores, prix, IDs —
  toujours en `tabular-nums`.
- **Instrument Serif** (`--font-serif`) : accents éditoriaux ponctuels (gros
  titres de section sur la landing, citations) — à doser, signe de raffinement.

### Couleurs (espace OKLCH — conserver)
- Surfaces : papier blanc chaud (`--paper`, `--paper-2`, `--paper-3`, `--card`).
- Encre : `--ink`, `--ink-2`, `--ink-soft`, `--ink-faint`.
- Lignes : `--line`, `--line-soft`.
- **Accent indigo « de confiance »** : `--accent` (oklch 0.52 0.16 264) + variantes
  `--accent-700/600/tint/line`.
- **Vert signal** (`--signal`) : RÉSERVÉ data-viz (courbes de vélocité, hausses).
- **Ambre** (`--warn`) : alertes/avertissements data-viz uniquement.
- Le dashboard est **light-first, « marché desk », accent indigo** (overridable en JS).

### Forme & mouvement
- Rayons : `--radius` 18px, `--radius-s` 12px, `--radius-l` 26px.
- Ombres en couches : `--shadow-s/m/l` (douces, jamais dures).
- Easing : `--ease` cubic-bezier(.22,.61,.36,1), `--ease-out` cubic-bezier(.16,1,.3,1).
- Largeur max contenu : `--maxw` 1200px.

---

## 3. Références visuelles

- **Linear** — pour : la sobriété, la vitesse perçue, les micro-interactions, la
  command palette (⌘K), les skeleton loaders, l'alignement chirurgical, le mode
  clair dense, les transitions de page rapides et discrètes.
- **Stripe** — pour : la crédibilité « entreprise », la qualité typographique, les
  schémas/diagrammes explicatifs, la mise en page éditoriale de la doc/pricing,
  la data-viz élégante.

On veut être **visuellement proche de ce niveau**. Ce n'est pas une référence
lointaine : c'est la barre à atteindre.

---

## 4. Principes d'animation (très important)

Le mouvement doit être **rapide, intentionnel, discret** — jamais ludique/rebondi.

- **Durées** : 150–260 ms pour l'UI (jamais lent). Easing = `--ease-out`.
- **Transitions de page** : fade + translation 8–12px, rapide.
- **Reveal au scroll** : une seule fois, en cascade (stagger 40–70 ms) — le
  système `reveal` existe déjà dans `base.css`, le réutiliser.
- **Data-viz** : les courbes se tracent, les barres poussent, **une fois**, à
  l'apparition. Compteurs KPI qui s'incrémentent.
- **Hover** : légère élévation des cartes (ombre `--shadow-m`), souligné accent
  sur les liens, états de curseur clairs.
- **Chargement** : skeletons aux formes réelles du contenu (pas de spinner).
- **Sidebar** : indicateur d'onglet actif qui glisse en douceur.
- **Respect impératif de `prefers-reduced-motion`** (déjà géré dans le code).

---

## 5. Contraintes techniques (à respecter)

- **Stack** : React 19 + TypeScript, Create React App (`react-scripts`),
  `react-router-dom`. Pas de migration de framework.
- **i18n FR/EN** : le système existe (dictionnaires dans `src/dashboard/data.ts`).
  Toute nouvelle chaîne doit être bilingue, via le même mécanisme.
- **Scoping CSS** : tout le style dashboard reste scopé sous `.tandor-dash`
  (cohabite avec la landing). Ne pas casser cette isolation.
- **Icônes** : réutiliser le jeu d'icônes existant (`ic()` dans le dashboard).
- **Données** : le dashboard lit l'API via `REACT_APP_API_URL` (`/api/products`,
  `/api/product/{id}`, `/api/meta`) avec fallback sur le JSON bundlé. Les nouvelles
  pages doivent consommer ce contrat (ou des données mock plausibles cohérentes
  en attendant l'endpoint correspondant — voir §6).
- **Réutiliser** les composants/charts existants (`src/dashboard/charts.ts`,
  cartes, KPI, radar, treemap) plutôt que d'en recréer.
- **Référence interne PRINCIPALE** : lire `DASHBOARD_SPEC.md` avant de commencer
  — c'est le cahier des charges UX/UI complet (contrat de données, design system,
  les 14 pages en détail, visualisations, animations, états, responsive,
  bibliothèque de composants). C'est la source de vérité.
- **Pour comprendre le SENS des données** (ce que valent les scores, la vélocité) :
  `scripts/organic_engine/DESIGN.md` — surtout de l'algorithme, optionnel.

---

## 6. Pages à réaliser (liste exhaustive)

> Le « Dashboard Home » est fait (référence de style). Tout le reste ci-dessous
> est à créer. Chaque page doit être **complète et crédible**, avec états vides,
> chargement, hover, responsive et i18n.

### A. Authentification (parcours d'entrée — confiance maximale)
1. **Login** — email + mot de passe + « continuer avec Google ». Lien mot de passe
   oublié. Design sobre, centré, rassurant (logo, micro-preuve sociale discrète).
2. **Register** — création de compte, validation en temps réel, force du mot de
   passe, CGU. Doit donner envie de s'inscrire (bénéfice clair, pas un formulaire nu).
3. **Mot de passe oublié** + **Réinitialisation** + **Vérification email** (écrans
   transactionnels cohérents).

### B. Pricing (conversion — doit respirer le premium)
4. **Pricing** — toggle mensuel/annuel, 2–3 plans (ex. Free / Pro / Scale),
   tableau comparatif des fonctionnalités, FAQ, réassurance (paiement sécurisé,
   sans engagement). Niveau Stripe.

### C. Pages du Dashboard (sidebar — actuellement « Bientôt disponible »)
**Groupe Découverte**
5. **Product Discovery** — exploration/filtrage du catalogue scoré : table dense
   (score Tandor, verdict BUY/WATCH/PASS, marge, vélocité), filtres (catégorie,
   verdict, score mini), tri, pagination, vue détail au clic.
6. **Opportunity Radar** — visualisation radar des opportunités (vélocité × marge ×
   saturation), sélection d'un produit → panneau détail.

**Groupe Analyse**
7. **Trend Analysis** (Analyse de tendances) — courbes Google Trends, comparaison
   de produits, fenêtres temporelles, accélération.
8. **Reddit Intelligence** — mentions Reddit dans le temps, subreddits sources,
   posts marquants, corrélation avec la vélocité produit.
9. **Market Signals** (Signaux marché) — vue agrégée des signaux composites,
   produits émergents, heatmap par catégorie.
10. **Analytics** — métriques d'usage/performance du portefeuille suivi, historique,
    validation des prédictions passées (preuve sociale).

**Groupe Mon espace**
11. **Saved** (Sauvegardés) — produits mis de côté par l'utilisateur, organisation,
    notes.
12. **Watchlists** — listes de surveillance, suivi de vélocité par liste, gestion.
13. **Alerts** (Alertes) — configuration d'alertes (seuil de vélocité, catégorie),
    canaux (email/webhook), historique des alertes déclenchées.

**Pied de sidebar (espace compte)**
14. **Settings** (Réglages) — préférences, langue, notifications, sécurité.
15. **Billing** (Facturation) — plan actuel, moyen de paiement, historique de
    factures, upgrade/downgrade (s'articule avec Stripe).
16. **Account** (Compte) — profil, email, mot de passe, suppression de compte.

### D. Landing (finition)
17. **Landing** — finir/polir l'existant : brancher le bouton « Se connecter »
    (lien mort actuellement), compléter les sections, cohérence FR/EN, CTA finaux.

### E. Pages utilitaires
18. **404 / Erreur** et **états vides génériques**, dans le même langage visuel.

---

## 7. Ajustements optionnels suggérés sur le Dashboard Home

(Le Home est globalement fini ; ces raffinements sont bienvenus s'ils restent
discrets et cohérents)
- Ajouter une **command palette ⌘K** (recherche produits/navigation) — très Linear.
- **Skeleton loaders** pendant le fetch API (remplacer tout spinner/écran vide).
- Affiner les **états de hover** des cartes produit et l'indicateur d'onglet actif.

---

## 8. Livrable attendu

- Pages React/TS intégrées au routing existant, i18n FR/EN, responsive (desktop
  d'abord, mobile correct), CSS scopé, animations conformes au §4.
- **Cohérence absolue** avec le Dashboard Home et la landing : un utilisateur ne
  doit jamais sentir une « couture » entre les pages d'origine et les nouvelles.
- Code propre, composants réutilisables, aucune dépendance lourde superflue.

**Critère de réussite** : on doit pouvoir montrer le produit à un client exigeant
sans qu'il devine une seconde que des pages ont été générées par IA. Confiance,
densité, précision, sobriété — niveau Linear / Stripe.
