import React, { useEffect } from 'react';
import '../Styles/base.css';
import '../Styles/sections.css';

const Home: React.FC = () => {
  useEffect(() => {
    (function () {
      "use strict";
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const $ = (s: string, c?: Element | Document): HTMLElement | null =>
        ((c || document).querySelector(s) as HTMLElement | null);
      const $$ = (s: string, c?: Element | Document): HTMLElement[] =>
        Array.prototype.slice.call((c || document).querySelectorAll(s));
      const RAF = (cb: (t: number) => void) =>
        setTimeout(() => cb(typeof performance !== "undefined" ? performance.now() : Date.now()), 16);

      /* Nav scrolled */
      const nav = $(".nav");
      if (!nav) return;
      const onScrollNav = () => {
        if (window.scrollY > 24) nav.classList.add("scrolled");
        else nav.classList.remove("scrolled");
      };
      onScrollNav();
      window.addEventListener("scroll", onScrollNav, { passive: true });

      /* Scroll reveals */
      let revEls = $$(".reveal, .reveal-scale, .reveal-x");
      const checkReveals = () => {
        const vh = window.innerHeight;
        for (let i = revEls.length - 1; i >= 0; i--) {
          const el = revEls[i];
          const r = el.getBoundingClientRect();
          if (r.top < vh * 0.92 && r.bottom > 0) {
            el.classList.add("in");
            const node = el;
            setTimeout(() => node.classList.add("shown"), 1150);
            const cb = (el.dataset as any).onreveal;
            if (cb && (window as any)[cb]) (window as any)[cb](el);
            revEls.splice(i, 1);
          }
        }
      };
      if (reduce) {
        revEls.forEach(el => {
          el.classList.add("in");
          const cb = (el.dataset as any).onreveal;
          if (cb && (window as any)[cb]) (window as any)[cb](el);
        });
        revEls = [];
      } else {
        window.addEventListener("scroll", checkReveals, { passive: true });
        window.addEventListener("resize", checkReveals, { passive: true });
        checkReveals();
        setTimeout(checkReveals, 60);
        setTimeout(checkReveals, 300);
      }

      /* Parallax halos */
      const halos = $$(".hero-bg .halo");
      const stage = $(".signal-stage");
      let ticking = false;
      const parallax = () => {
        const y = window.scrollY;
        halos.forEach((h, i) => { h.style.transform = `translateY(${y * (i + 1) * 0.04}px)`; });
        if (stage) {
          $$(".scard, .chip", stage).forEach(c => {
            const d = parseFloat((c.dataset as any).depth || "0");
            c.style.setProperty("--py", `${y * d * -0.05}px`);
          });
        }
        ticking = false;
      };
      const reqParallax = () => { if (!ticking && !reduce) { ticking = true; RAF(parallax); } };
      window.addEventListener("scroll", reqParallax, { passive: true });

      /* Mouse parallax */
      if (stage && !reduce) {
        const heroEl = $(".hero");
        if (heroEl) {
          heroEl.addEventListener("mousemove", (e: any) => {
            const r = heroEl.getBoundingClientRect();
            const mx = (e.clientX - r.left) / r.width - 0.5;
            const my = (e.clientY - r.top) / r.height - 0.5;
            $$(".scard, .chip", stage).forEach(c => {
              const d = parseFloat((c.dataset as any).depth || "1");
              c.style.setProperty("--mx", `${mx * d * 22}px`);
              c.style.setProperty("--my", `${my * d * 18}px`);
            });
          });
          heroEl.addEventListener("mouseleave", () => {
            $$(".scard, .chip", stage).forEach(c => {
              c.style.setProperty("--mx", "0px");
              c.style.setProperty("--my", "0px");
            });
          });
        }
      }

      /* Dashboard tilt */
      const browser = $(".browser");
      if (browser && !reduce) {
        const dashStage = $(".dash-stage");
        if (dashStage) {
          const tilt = () => {
            const r = dashStage.getBoundingClientRect();
            const prog = 1 - Math.max(0, Math.min(1, (r.top + r.height * 0.3) / window.innerHeight));
            const rot = (1 - prog) * 12;
            browser.style.transform = `rotateX(${rot.toFixed(2)}deg) translateY(${(1 - prog) * 10}px)`;
          };
          tilt();
          window.addEventListener("scroll", () => RAF(tilt), { passive: true });
        }
      }

      /* Velocity chart draw */
      (window as any).drawVelocity = () => {
        const chart = $(".velo-chart");
        if (!chart) return;
        const path = $(".velo-path", chart) as SVGPathElement & HTMLElement | null;
        if (path) {
          const len = (path as any).getTotalLength();
          path.style.setProperty("--len", String(len));
          RAF(() => path.classList.add("draw"));
        }
        setTimeout(() => { const a = $(".velo-area", chart); if (a) a.classList.add("show"); }, 80);
        $$(".velo-bar", chart).forEach((b, i) => setTimeout(() => b.classList.add("show"), 700 + i * 90));
        $$(".velo-dot", chart).forEach(d => setTimeout(() => d.classList.add("show"), 1400));
        setTimeout(() => chart.classList.add("settled"), 2300);
        $$(".velo-foot .n[data-count]", chart).forEach(el => countUp(el));
      };

      /* Sparkbar grow */
      (window as any).growBars = (root: HTMLElement) => {
        $$(".sparkbars i", root).forEach((b, i) => {
          const h = (b.dataset as any).h || "40";
          b.style.height = "0%";
          setTimeout(() => { b.style.transition = "height .7s cubic-bezier(.16,1,.3,1)"; b.style.height = h + "%"; }, i * 60);
          setTimeout(() => { b.style.transition = "none"; b.style.height = h + "%"; }, 1100 + i * 60);
        });
      };

      /* Count up */
      const countUp = (el: HTMLElement) => {
        if (reduce) { el.textContent = (el.dataset as any).count; return; }
        const target = parseFloat((el.dataset as any).count);
        const suffix = (el.dataset as any).suffix || "";
        const prefix = (el.dataset as any).prefix || "";
        const dec = ((el.dataset as any).count.indexOf(".") > -1) ? 1 : 0;
        let start: number | null = null;
        const step = (t: number) => {
          if (!start) start = t;
          const p = Math.min(1, (t - start) / 1400);
          el.textContent = prefix + (target * (1 - Math.pow(1 - p, 3))).toFixed(dec).replace(".", ",") + suffix;
          if (p < 1) RAF(step);
        };
        RAF(step);
      };
      let countEls = $$("[data-count]").filter(el => !el.closest(".velo-foot"));
      const checkCounts = () => {
        const vh = window.innerHeight;
        for (let i = countEls.length - 1; i >= 0; i--) {
          const el = countEls[i];
          const r = el.getBoundingClientRect();
          if (r.top < vh * 0.85 && r.bottom > 0) { countUp(el); countEls.splice(i, 1); }
        }
      };
      window.addEventListener("scroll", () => RAF(checkCounts), { passive: true });
      RAF(checkCounts);
      setTimeout(checkCounts, 200);

      /* FAQ accordion */
      $$(".faq-item").forEach(item => {
        const q = $(".faq-q", item);
        const a = $(".faq-a", item);
        if (q && a) {
          q.addEventListener("click", () => {
            const open = item.classList.contains("open");
            $$(".faq-item.open").forEach(o => {
              o.classList.remove("open");
              const fa = $(".faq-a", o);
              if (fa) fa.style.maxHeight = "";
            });
            if (!open) { item.classList.add("open"); a.style.maxHeight = a.scrollHeight + "px"; }
          });
        }
      });

      /* Pricing toggle */
      const priceBtns = $$(".price-toggle button");
      priceBtns.forEach(b => {
        b.addEventListener("click", () => {
          priceBtns.forEach(x => x.classList.remove("on"));
          b.classList.add("on");
          const yearly = (b.dataset as any).period === "yearly";
          $$(".pcard .pprice .amt").forEach(a => {
            a.textContent = yearly ? (a.dataset as any).y : (a.dataset as any).m;
          });
          $$(".pcard .pprice .per").forEach(p => {
            p.setAttribute("data-fr", yearly ? "/mois · facturé annuel" : "/mois");
            p.setAttribute("data-en", yearly ? "/mo · billed yearly" : "/mo");
            applyLangTo(p);
          });
        });
      });

      /* Language toggle */
      let lang = localStorage.getItem("tandor_lang") || "fr";
      const applyLangTo = (el: HTMLElement) => {
        const v = el.getAttribute("data-" + lang);
        if (v !== null) {
          if ((el.dataset as any).attr) el.setAttribute((el.dataset as any).attr, v);
          else el.innerHTML = v;
        }
      };
      const applyLang = () => {
        document.documentElement.lang = lang;
        $$("[data-fr]").forEach(applyLangTo);
        $$(".lang-toggle button").forEach(b =>
          b.classList.toggle("active", (b.dataset as any).lang === lang)
        );
        $$(".faq-item.open .faq-a").forEach(a => { a.style.maxHeight = a.scrollHeight + "px"; });
      };
      $$(".lang-toggle button").forEach(b => {
        b.addEventListener("click", () => {
          lang = (b.dataset as any).lang;
          localStorage.setItem("tandor_lang", lang);
          applyLang();
        });
      });
      applyLang();

      /* Smooth anchors */
      $$('a[href^="#"]').forEach(a => {
        a.addEventListener("click", (e: any) => {
          const id = a.getAttribute("href");
          if (id && id.length > 1) {
            const t = $(id);
            if (t) {
              e.preventDefault();
              window.scrollTo({ top: t.getBoundingClientRect().top + window.scrollY - 70, behavior: reduce ? "auto" : "smooth" });
            }
          }
        });
      });

      /* Mobile burger */
      const burger = $(".nav-burger");
      if (burger) {
        burger.addEventListener("click", () => nav.classList.toggle("menu-open"));
        $$(".nav-drawer a").forEach(a => a.addEventListener("click", () => nav.classList.remove("menu-open")));
      }

      /* Year */
      const yr = document.getElementById("year");
      if (yr) yr.textContent = String(new Date().getFullYear());
    })();
  }, []);

  return (
    <>
      {/* NAV */}
      <nav className="nav">
        <div className="container nav-inner">
          <a href="#top" className="brand">
            <span className="brand-mark">
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path d="M6.5 1.5v10M2 6h9M6.5 1.5 9 4M6.5 1.5 4 4" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </span>
            Tandor<span className="dot">.</span>
          </a>
          <div className="nav-links">
            <a href="#features" data-fr="Fonctionnalités" data-en="Features">Fonctionnalités</a>
            <a href="#how" data-fr="Comment ça marche" data-en="How it works">Comment ça marche</a>
            <a href="#dashboard" data-fr="Produit" data-en="Product">Produit</a>
            <a href="#pricing" data-fr="Tarifs" data-en="Pricing">Tarifs</a>
            <a href="#faq" data-fr="FAQ" data-en="FAQ">FAQ</a>
          </div>
          <div className="nav-right">
            <div className="lang-toggle">
              <button data-lang="fr">FR</button>
              <button data-lang="en">EN</button>
            </div>
            <a href="#" className="nav-login" data-fr="Se connecter" data-en="Log in">Se connecter</a>
            <a href="#pricing" className="btn btn-primary" data-fr="Essayer Tandor" data-en="Try Tandor">Essayer Tandor</a>
            <button className="nav-burger" aria-label="Menu"><span></span><span></span><span></span></button>
          </div>
        </div>
        <div className="nav-drawer">
          <a href="#features" data-fr="Fonctionnalités" data-en="Features">Fonctionnalités</a>
          <a href="#how" data-fr="Comment ça marche" data-en="How it works">Comment ça marche</a>
          <a href="#dashboard" data-fr="Produit" data-en="Product">Produit</a>
          <a href="#pricing" data-fr="Tarifs" data-en="Pricing">Tarifs</a>
          <a href="#faq" data-fr="FAQ" data-en="FAQ">FAQ</a>
          <a href="#" data-fr="Se connecter" data-en="Log in">Se connecter</a>
        </div>
      </nav>

      {/* HERO */}
      <header className="hero" id="top" data-variant="3">
        <div className="hero-bg">
          <div className="halo a"></div>
          <div className="halo b"></div>
          <div className="halo c"></div>
        </div>
        <div className="grid-fade"></div>
        <div className="container">
          <div className="hero-grid">
            <div className="hero-copy">
              <span className="eyebrow reveal" data-fr="Product research par signaux" data-en="Signal-based product research">Product research par signaux</span>
              <h1 className="display reveal" data-d="1">
                <span className="hl" data-hl="1" data-fr="Vends le produit gagnant <em>pendant</em> que les autres le découvrent." data-en="Sell the winning product <em>while</em> everyone else is still finding it.">Vends le produit gagnant <em>pendant</em> que les autres le découvrent.</span>
                <span className="hl" data-hl="2" data-fr="Repère les produits gagnants <em>4 à 6 semaines</em> avant tes concurrents." data-en="Spot winning products <em>4–6 weeks</em> before your competitors.">Repère les produits gagnants <em>4 à 6 semaines</em> avant tes concurrents.</span>
                <span className="hl" data-hl="3" data-fr="Le signal, <em>avant</em> le bruit." data-en="The signal, <em>before</em> the noise.">Le signal, <em>avant</em> le bruit.</span>
              </h1>
              <p className="lead reveal" data-d="2" data-fr="Tandor lit la vélocité des signaux organiques — Reddit, TikTok, Google — et la croise avec la marge et la concurrence en un score unique et actionnable." data-en="Tandor reads the velocity of organic signals — Reddit, TikTok, Google — and crosses it with margin and competition into a single, actionable score.">Tandor lit la vélocité des signaux organiques — Reddit, TikTok, Google — et la croise avec la marge et la concurrence en un score unique et actionnable.</p>
              <div className="hero-cta reveal" data-d="3">
                <a href="#pricing" className="btn btn-accent btn-lg" data-fr="Commencer gratuitement" data-en="Start for free">Commencer gratuitement</a>
                <a href="#dashboard" className="btn btn-ghost btn-lg" data-fr="Voir le produit <span class='arrow'>→</span>" data-en="See the product <span class='arrow'>→</span>">Voir le produit <span className="arrow">→</span></a>
              </div>
              <div className="hero-trust reveal" data-d="4">
                <div className="avatars">
                  <span style={{ background: 'linear-gradient(135deg,#f0a6c8,#c06ef3)' }}></span>
                  <span style={{ background: 'linear-gradient(135deg,#6dcbff,#5a47cd)' }}></span>
                  <span style={{ background: 'linear-gradient(135deg,#6dedc3,#34a853)' }}></span>
                  <span style={{ background: 'linear-gradient(135deg,#fdba09,#ff4500)' }}></span>
                </div>
                <div>
                  <span className="hero-stars">★★★★★</span>
                  <span data-fr="<strong>2 400+</strong> e-commerçants à l'avance" data-en="<strong>2,400+</strong> sellers ahead of the curve"><strong>2 400+</strong> e-commerçants à l'avance</span>
                </div>
              </div>
            </div>

            <div className="signal-stage reveal-scale" data-d="2">
              <div className="scard scard-main" data-depth="0.5">
                <div className="sc-head">
                  <div className="sc-thumb"></div>
                  <div>
                    <div className="sc-name" data-fr="Masseur cervical" data-en="Neck massager">Masseur cervical</div>
                    <div className="sc-cat">SKU-4471 · WELLNESS</div>
                  </div>
                  <div className="sc-badge" data-fr="Détecté il y a 38 j" data-en="Found 38 days ago">Détecté il y a 38 j</div>
                </div>
                <div className="sc-score">
                  <span className="big" data-count="92" data-suffix="">0</span>
                  <span className="of">/100</span>
                  <span className="tag">▲ <span data-fr="Tendance forte" data-en="Strong trend">Tendance forte</span></span>
                </div>
                <div className="sc-label" data-fr="Score Tandor" data-en="Tandor score">Score Tandor</div>
                <div className="sc-meter"><i style={{ '--v': '92%' } as React.CSSProperties}></i></div>
                <div className="sc-rows">
                  <div className="sc-row">
                    <span className="k">Reddit</span>
                    <svg className="spark" viewBox="0 0 100 22" preserveAspectRatio="none"><polyline points="0,18 14,17 28,15 42,12 56,9 70,6 84,3 100,1" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                    <span className="val up">+240%</span>
                  </div>
                  <div className="sc-row">
                    <span className="k">TikTok</span>
                    <svg className="spark" viewBox="0 0 100 22" preserveAspectRatio="none"><polyline points="0,19 16,18 30,16 44,14 58,9 72,7 86,4 100,2" fill="none" stroke="var(--signal)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                    <span className="val up">+180%</span>
                  </div>
                  <div className="sc-row">
                    <span className="k">Google</span>
                    <svg className="spark" viewBox="0 0 100 22" preserveAspectRatio="none"><polyline points="0,17 16,16 30,15 44,13 58,11 72,8 86,6 100,4" fill="none" stroke="#4285f4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                    <span className="val up">+96%</span>
                  </div>
                </div>
              </div>
              <div className="chip chip-reddit" data-depth="1.4">
                <span className="ico">r/</span>
                <div><div>r/SkincareAddiction</div><div className="sub" data-fr="pic de discussions" data-en="discussion spike">pic de discussions</div></div>
                <span className="pct">+240%</span>
              </div>
              <div className="chip chip-tiktok" data-depth="1.8">
                <span className="ico">♪</span>
                <div><div>#necktok</div><div className="sub" data-fr="format viral" data-en="viral format">format viral</div></div>
                <span className="pct">12,4M</span>
              </div>
              <div className="chip chip-google" data-depth="1.2">
                <span className="ico">G</span>
                <div><div data-fr="Recherches" data-en="Searches">Recherches</div><div className="sub">Google Trends ↗</div></div>
                <span className="pct">+96%</span>
              </div>
              <div className="chip chip-margin" data-depth="1.6">
                <span className="ico">€</span>
                <div><div data-fr="Marge AliExpress" data-en="AliExpress margin">Marge AliExpress</div><div className="sub" data-fr="3 fournisseurs" data-en="3 suppliers">3 fournisseurs</div></div>
                <span className="pct" style={{ color: 'var(--accent)' }}>×4,2</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* SOCIAL PROOF */}
      <section className="proof">
        <div className="container">
          <p className="proof-label" data-fr="Utilisé par les e-commerçants qui lancent en premier" data-en="Used by the sellers who launch first">Utilisé par les e-commerçants qui lancent en premier</p>
          <div className="marquee">
            <div className="marquee-track">
              <span className="logo">Nordsky</span><span className="logo">Maison&nbsp;RoHe</span><span className="logo">VOLT&nbsp;Goods</span><span className="logo">Brava</span><span className="logo">Lumen&nbsp;&amp;&nbsp;Co</span><span className="logo">Kindred</span><span className="logo">Atelier&nbsp;9</span>
              <span className="logo">Nordsky</span><span className="logo">Maison&nbsp;RoHe</span><span className="logo">VOLT&nbsp;Goods</span><span className="logo">Brava</span><span className="logo">Lumen&nbsp;&amp;&nbsp;Co</span><span className="logo">Kindred</span><span className="logo">Atelier&nbsp;9</span>
            </div>
          </div>
        </div>
      </section>

      {/* VELOCITY TIMELINE */}
      <section className="velocity section-pad" id="velocity">
        <div className="container">
          <div className="section-head reveal">
            <h2 className="section-title" data-fr="Le signal organique monte <em>avant</em> les pubs concurrentes." data-en="Organic signal rises <em>before</em> competitor ads.">Le signal organique monte <em>avant</em> les pubs concurrentes.</h2>
            <p className="lead" data-fr="Quand un produit décolle sur Reddit, TikTok et Google, les pubs payantes arrivent 4 à 6 semaines plus tard. Tandor t'alerte au premier instant — pas au dernier." data-en="When a product takes off on Reddit, TikTok and Google, paid ads follow 4–6 weeks later. Tandor alerts you at the first moment — not the last.">Quand un produit décolle sur Reddit, TikTok et Google, les pubs payantes arrivent 4 à 6 semaines plus tard. Tandor t'alerte au premier instant — pas au dernier.</p>
          </div>
          <div className="velo-wrap reveal-scale" data-onreveal="drawVelocity">
            <div className="velo-chart">
              <div className="velo-head">
                <div>
                  <div className="sc-name" style={{ fontSize: '1.05rem' }} data-fr="Vélocité du signal — Masseur cervical" data-en="Signal velocity — Neck massager">Vélocité du signal — Masseur cervical</div>
                  <div className="sc-cat" style={{ marginTop: '4px' }}>12 <span data-fr="semaines" data-en="weeks">semaines</span></div>
                </div>
                <div className="velo-legend">
                  <span><i className="lg-organic"></i> <span data-fr="Signal organique (Tandor)" data-en="Organic signal (Tandor)">Signal organique (Tandor)</span></span>
                  <span><i className="lg-ads"></i> <span data-fr="Pubs concurrentes" data-en="Competitor ads">Pubs concurrentes</span></span>
                </div>
              </div>
              <div className="velo-plot">
                <div className="velo-gap" style={{ left: '18%', width: '50%' }}>
                  <div className="gap-tag" data-fr="Ton avance : 4–6 semaines" data-en="Your lead: 4–6 weeks">Ton avance : 4–6 semaines</div>
                </div>
                <svg viewBox="0 0 800 240" preserveAspectRatio="none">
                  <defs>
                    <linearGradient id="veloFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="oklch(0.55 0.16 264 / .28)"/>
                      <stop offset="100%" stopColor="oklch(0.55 0.16 264 / 0)"/>
                    </linearGradient>
                  </defs>
                  <path className="velo-area" d="M0,210 C110,205 150,180 220,140 C300,96 360,52 470,36 C560,24 660,22 800,20 L800,240 L0,240 Z"/>
                  <path className="velo-path" d="M0,210 C110,205 150,180 220,140 C300,96 360,52 470,36 C560,24 660,22 800,20"/>
                  <rect className="velo-bar" x="556" y="150" width="34" height="90" rx="3"/>
                  <rect className="velo-bar" x="606" y="120" width="34" height="120" rx="3"/>
                  <rect className="velo-bar" x="656" y="86" width="34" height="154" rx="3"/>
                  <rect className="velo-bar" x="706" y="58" width="34" height="182" rx="3"/>
                  <circle className="velo-dot" cx="220" cy="140" r="6"/>
                  <circle className="velo-dot" cx="470" cy="36" r="6"/>
                </svg>
              </div>
              <div className="velo-axis"><span>S1</span><span>S2</span><span>S3</span><span>S4</span><span>S5</span><span>S6</span><span>S7</span><span>S8</span><span>S9</span><span>S10</span><span>S11</span><span>S12</span></div>
              <div className="velo-foot">
                <div className="vf"><div className="n"><em data-count="4.8" data-suffix="">0</em> <span data-fr="sem." data-en="wk">sem.</span></div><div className="t" data-fr="d'avance moyenne sur les annonceurs" data-en="average lead over advertisers">d'avance moyenne sur les annonceurs</div></div>
                <div className="vf"><div className="n"><em data-count="240" data-prefix="+" data-suffix="%">0</em></div><div className="t" data-fr="pic de discussions avant le mainstream" data-en="discussion spike before mainstream">pic de discussions avant le mainstream</div></div>
                <div className="vf"><div className="n"><em data-count="3" data-suffix="">0</em> <span data-fr="signaux" data-en="signals">signaux</span></div><div className="t" data-fr="croisés en un score unique" data-en="crossed into one score">croisés en un score unique</div></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section className="features section-pad" id="features">
        <div className="container">
          <div className="section-head reveal">
            <h2 className="section-title" data-fr="Un seul score. <em>Toute</em> la décision." data-en="One score. The <em>whole</em> decision.">Un seul score. <em>Toute</em> la décision.</h2>
            <p className="lead" data-fr="Tandor transforme le chaos des signaux en une réponse claire : lancer, surveiller, ou passer." data-en="Tandor turns signal chaos into a clear answer: launch, watch, or pass.">Tandor transforme le chaos des signaux en une réponse claire : lancer, surveiller, ou passer.</p>
          </div>
          <div className="features-grid">
            <div className="fcard span2 reveal" data-onreveal="growBars">
              <div className="ficon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 17l5-5 4 3 8-9"/><path d="M16 6h5v5"/></svg></div>
              <h3 data-fr="Lecture de vélocité en temps réel" data-en="Real-time velocity reading">Lecture de vélocité en temps réel</h3>
              <p data-fr="On ne mesure pas le volume, on mesure l'accélération. Un signal qui double chaque semaine vaut plus qu'un million de vues figées." data-en="We don't measure volume, we measure acceleration. A signal that doubles weekly beats a million flat views.">On ne mesure pas le volume, on mesure l'accélération. Un signal qui double chaque semaine vaut plus qu'un million de vues figées.</p>
              <div className="fviz"><div className="sparkbars"><i data-h="22"></i><i data-h="30"></i><i data-h="26"></i><i data-h="40"></i><i data-h="36"></i><i data-h="52"></i><i data-h="48"></i><i data-h="66"></i><i data-h="72"></i><i className="hi" data-h="88"></i><i className="hi" data-h="100"></i></div></div>
            </div>
            <div className="fcard reveal" data-d="1">
              <div className="ficon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg></div>
              <h3 data-fr="Signaux multi-sources" data-en="Multi-source signals">Signaux multi-sources</h3>
              <p data-fr="Discussions Reddit, formats TikTok, recherches Google — croisés, pondérés, dédupliqués." data-en="Reddit threads, TikTok formats, Google searches — crossed, weighted, deduplicated.">Discussions Reddit, formats TikTok, recherches Google — croisés, pondérés, dédupliqués.</p>
              <div className="fviz scorepills"><span className="on">Reddit</span><span className="on">TikTok</span><span className="on">Google</span><span>Amazon</span><span>Pinterest</span></div>
            </div>
            <div className="fcard reveal" data-d="2">
              <div className="ficon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v20M5 5h9a3.5 3.5 0 0 1 0 7H7a3.5 3.5 0 0 0 0 7h10"/></svg></div>
              <h3 data-fr="Marge & concurrence intégrées" data-en="Margin & competition built in">Marge &amp; concurrence intégrées</h3>
              <p data-fr="Le score croise la marge AliExpress et la saturation publicitaire. Un produit viral mais saturé est recalé." data-en="The score crosses AliExpress margin with ad saturation. A viral but saturated product gets flagged.">Le score croise la marge AliExpress et la saturation publicitaire. Un produit viral mais saturé est recalé.</p>
              <div className="fviz scorepills"><span className="on" data-fr="Marge ×4,2" data-en="Margin ×4.2">Marge ×4,2</span><span data-fr="Concurrence faible" data-en="Low competition">Concurrence faible</span></div>
            </div>
            <div className="fcard reveal" data-d="1">
              <div className="ficon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg></div>
              <h3 data-fr="Alertes au premier signal" data-en="First-signal alerts">Alertes au premier signal</h3>
              <p data-fr="Dès qu'un produit franchit ton seuil de vélocité, tu reçois l'alerte — avant que la fenêtre ne se ferme." data-en="The moment a product crosses your velocity threshold, you get the alert — before the window closes.">Dès qu'un produit franchit ton seuil de vélocité, tu reçois l'alerte — avant que la fenêtre ne se ferme.</p>
              <div className="fviz scorepills"><span className="on">Slack</span><span className="on">Email</span><span>Webhook</span></div>
            </div>
            <div className="fcard span2 reveal" data-d="2">
              <div className="ficon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M9 13h6M9 17h4"/></svg></div>
              <h3 data-fr="Verdict actionnable, pas un tableur" data-en="An actionable verdict, not a spreadsheet">Verdict actionnable, pas un tableur</h3>
              <p data-fr="Chaque produit reçoit un statut clair — Lancer, Surveiller, Passer — avec la raison, la fenêtre et les fournisseurs déjà identifiés." data-en="Every product gets a clear status — Launch, Watch, Pass — with the reason, the window and suppliers already identified.">Chaque produit reçoit un statut clair — Lancer, Surveiller, Passer — avec la raison, la fenêtre et les fournisseurs déjà identifiés.</p>
              <div className="fviz scorepills">
                <span className="on" style={{ background: 'var(--signal)', borderColor: 'var(--signal)' }} data-fr="● Lancer" data-en="● Launch">● Lancer</span>
                <span data-fr="● Surveiller" data-en="● Watch">● Surveiller</span>
                <span data-fr="● Passer" data-en="● Pass">● Passer</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* DASHBOARD PREVIEW */}
      <section className="dash section-pad" id="dashboard">
        <div className="container">
          <div className="section-head center reveal">
            <h2 className="section-title" data-fr="Ton radar produit, <em>en un écran</em>." data-en="Your product radar, <em>in one screen</em>.">Ton radar produit, <em>en un écran</em>.</h2>
          </div>
          <div className="dash-stage reveal-scale">
            <div className="dash-glow"></div>
            <div className="browser">
              <div className="browser-bar">
                <div className="browser-dots"><i></i><i></i><i></i></div>
                <div className="browser-url"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>app.tandor.io/radar</div>
              </div>
              <div className="browser-body">
                <aside className="dash-side">
                  <div className="ds-brand">Tandor<span className="dot">.</span></div>
                  <nav className="dash-nav">
                    <a className="on"><svg className="di" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg><span data-fr="Radar" data-en="Radar">Radar</span></a>
                    <a><svg className="di" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 17l5-5 4 3 8-9"/></svg><span data-fr="Tendances" data-en="Trends">Tendances</span></a>
                    <a><svg className="di" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/></svg><span data-fr="Alertes" data-en="Alerts">Alertes</span></a>
                    <a><svg className="di" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 7h-9M14 17H5M17 17h3M4 7h3"/><circle cx="14" cy="7" r="2.4"/><circle cx="10" cy="17" r="2.4"/></svg><span data-fr="Filtres" data-en="Filters">Filtres</span></a>
                    <a><svg className="di" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span data-fr="Listes" data-en="Lists">Listes</span></a>
                  </nav>
                  <div className="ds-up">
                    <b data-fr="3 nouveaux signaux" data-en="3 new signals">3 nouveaux signaux</b>
                    <p data-fr="franchissent ton seuil aujourd'hui." data-en="crossed your threshold today.">franchissent ton seuil aujourd'hui.</p>
                    <button data-fr="Voir le radar" data-en="Open radar">Voir le radar</button>
                  </div>
                </aside>
                <div className="dash-main">
                  <div className="dash-h">
                    <div><h4 data-fr="Radar produits" data-en="Product radar">Radar produits</h4><div className="dh-sub" data-fr="412 produits suivis · maj il y a 2 min" data-en="412 products tracked · updated 2 min ago">412 produits suivis · maj il y a 2 min</div></div>
                    <div className="dh-filter"><span className="on" data-fr="Vélocité" data-en="Velocity">Vélocité</span><span data-fr="Marge" data-en="Margin">Marge</span><span data-fr="Récents" data-en="Recent">Récents</span></div>
                  </div>
                  <div className="dash-kpis">
                    <div className="kpi"><div className="kl" data-fr="Signaux actifs" data-en="Active signals">Signaux actifs</div><div className="kv" data-count="48" data-suffix="">0</div><div className="kd">▲ 12 <span data-fr="cette semaine" data-en="this week">cette semaine</span></div></div>
                    <div className="kpi"><div className="kl" data-fr="Avance moyenne" data-en="Avg. lead">Avance moyenne</div><div className="kv mono">4,8<span style={{ fontSize: '.9rem' }}> sem.</span></div><div className="kd">▲ 0,6</div></div>
                    <div className="kpi"><div className="kl" data-fr="Verdicts « Lancer »" data-en="« Launch » verdicts">Verdicts « Lancer »</div><div className="kv" data-count="7" data-suffix="">0</div><div className="kd">▲ 3 <span data-fr="aujourd'hui" data-en="today">aujourd'hui</span></div></div>
                  </div>
                  <div className="dtable">
                    <div className="dt-head"><span data-fr="Produit" data-en="Product">Produit</span><span data-fr="Score & vélocité" data-en="Score & velocity">Score &amp; vélocité</span><span data-fr="Marge" data-en="Margin">Marge</span><span data-fr="Avance" data-en="Lead">Avance</span><span data-fr="Verdict" data-en="Verdict">Verdict</span></div>
                    <div className="dt-row"><div className="dt-prod"><div className="pmini"></div><div><div className="pn" data-fr="Masseur cervical" data-en="Neck massager">Masseur cervical</div><div className="pc">WELLNESS</div></div></div><div className="dt-score"><svg className="ring" viewBox="0 0 36 36"><circle cx="18" cy="18" r="15" fill="none" stroke="var(--line)" strokeWidth="4"/><circle cx="18" cy="18" r="15" fill="none" stroke="var(--signal)" strokeWidth="4" strokeLinecap="round" strokeDasharray="94 100" transform="rotate(-90 18 18)"/></svg><b>92</b><svg className="dt-spark" viewBox="0 0 70 26" preserveAspectRatio="none"><polyline points="0,22 14,18 28,14 42,8 56,5 70,2" fill="none" stroke="var(--signal)" strokeWidth="2"/></svg></div><div className="dt-margin">×4,2</div><div className="mono" style={{ fontWeight: 600 }}>5,2 <span data-fr="sem" data-en="wk">sem</span></div><div className="dt-stat win" data-fr="Lancer" data-en="Launch">Lancer</div></div>
                    <div className="dt-row"><div className="dt-prod"><div className="pmini"></div><div><div className="pn" data-fr="Lampe coucher de soleil" data-en="Sunset lamp">Lampe coucher de soleil</div><div className="pc">HOME</div></div></div><div className="dt-score"><svg className="ring" viewBox="0 0 36 36"><circle cx="18" cy="18" r="15" fill="none" stroke="var(--line)" strokeWidth="4"/><circle cx="18" cy="18" r="15" fill="none" stroke="var(--accent)" strokeWidth="4" strokeLinecap="round" strokeDasharray="78 100" transform="rotate(-90 18 18)"/></svg><b>78</b><svg className="dt-spark" viewBox="0 0 70 26" preserveAspectRatio="none"><polyline points="0,20 14,17 28,16 42,12 56,10 70,7" fill="none" stroke="var(--accent)" strokeWidth="2"/></svg></div><div className="dt-margin">×3,8</div><div className="mono" style={{ fontWeight: 600 }}>3,1 <span data-fr="sem" data-en="wk">sem</span></div><div className="dt-stat watch" data-fr="Surveiller" data-en="Watch">Surveiller</div></div>
                    <div className="dt-row"><div className="dt-prod"><div className="pmini"></div><div><div className="pn" data-fr="Brosse anti-peluches" data-en="Lint shaver">Brosse anti-peluches</div><div className="pc">APPAREL</div></div></div><div className="dt-score"><svg className="ring" viewBox="0 0 36 36"><circle cx="18" cy="18" r="15" fill="none" stroke="var(--line)" strokeWidth="4"/><circle cx="18" cy="18" r="15" fill="none" stroke="var(--signal)" strokeWidth="4" strokeLinecap="round" strokeDasharray="86 100" transform="rotate(-90 18 18)"/></svg><b>86</b><svg className="dt-spark" viewBox="0 0 70 26" preserveAspectRatio="none"><polyline points="0,21 14,19 28,13 42,11 56,6 70,3" fill="none" stroke="var(--signal)" strokeWidth="2"/></svg></div><div className="dt-margin">×5,1</div><div className="mono" style={{ fontWeight: 600 }}>4,4 <span data-fr="sem" data-en="wk">sem</span></div><div className="dt-stat win" data-fr="Lancer" data-en="Launch">Lancer</div></div>
                    <div className="dt-row"><div className="dt-prod"><div className="pmini"></div><div><div className="pn" data-fr="Mini imprimante photo" data-en="Mini photo printer">Mini imprimante photo</div><div className="pc">TECH</div></div></div><div className="dt-score"><svg className="ring" viewBox="0 0 36 36"><circle cx="18" cy="18" r="15" fill="none" stroke="var(--line)" strokeWidth="4"/><circle cx="18" cy="18" r="15" fill="none" stroke="var(--warn)" strokeWidth="4" strokeLinecap="round" strokeDasharray="41 100" transform="rotate(-90 18 18)"/></svg><b>41</b><svg className="dt-spark" viewBox="0 0 70 26" preserveAspectRatio="none"><polyline points="0,8 14,10 28,9 42,13 56,15 70,18" fill="none" stroke="var(--warn)" strokeWidth="2"/></svg></div><div className="dt-margin">×2,1</div><div className="mono" style={{ fontWeight: 600 }}>—</div><div className="dt-stat late" data-fr="Passer" data-en="Pass">Passer</div></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="how section-pad" id="how">
        <div className="container">
          <div className="section-head reveal">
            <h2 className="section-title" data-fr="Du signal brut au produit lancé, <em>en trois temps</em>." data-en="From raw signal to launched product, <em>in three steps</em>.">Du signal brut au produit lancé, <em>en trois temps</em>.</h2>
          </div>
          <div className="steps">
            <div className="step reveal" data-d="1">
              <div className="snum">01</div><div className="sline"></div>
              <h3 data-fr="Tandor écoute" data-en="Tandor listens">Tandor écoute</h3>
              <p data-fr="On scanne Reddit, TikTok et Google en continu pour mesurer l'accélération de chaque produit." data-en="We scan Reddit, TikTok and Google continuously to measure each product's acceleration.">On scanne Reddit, TikTok et Google en continu pour mesurer l'accélération de chaque produit.</p>
              <div className="svis"><div className="sc-rows">
                <div className="sc-row"><span className="k" style={{ width: '60px' }}>Reddit</span><svg className="spark" viewBox="0 0 100 22" preserveAspectRatio="none"><polyline points="0,18 30,15 60,9 100,2" fill="none" stroke="var(--accent)" strokeWidth="2"/></svg></div>
                <div className="sc-row"><span className="k" style={{ width: '60px' }}>TikTok</span><svg className="spark" viewBox="0 0 100 22" preserveAspectRatio="none"><polyline points="0,19 30,16 60,10 100,3" fill="none" stroke="var(--signal)" strokeWidth="2"/></svg></div>
                <div className="sc-row"><span className="k" style={{ width: '60px' }}>Google</span><svg className="spark" viewBox="0 0 100 22" preserveAspectRatio="none"><polyline points="0,17 30,14 60,11 100,5" fill="none" stroke="#4285f4" strokeWidth="2"/></svg></div>
              </div></div>
            </div>
            <div className="step reveal" data-d="2">
              <div className="snum">02</div><div className="sline"></div>
              <h3 data-fr="Tandor note" data-en="Tandor scores">Tandor note</h3>
              <p data-fr="Vélocité, marge et concurrence sont croisées en un score unique de 0 à 100, avec un verdict clair." data-en="Velocity, margin and competition are crossed into a single 0–100 score, with a clear verdict.">Vélocité, marge et concurrence sont croisées en un score unique de 0 à 100, avec un verdict clair.</p>
              <div className="svis" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '18px' }}>
                <svg width="92" height="92" viewBox="0 0 36 36"><circle cx="18" cy="18" r="15" fill="none" stroke="var(--line)" strokeWidth="3"/><circle cx="18" cy="18" r="15" fill="none" stroke="var(--signal)" strokeWidth="3" strokeLinecap="round" strokeDasharray="92 100" transform="rotate(-90 18 18)"/></svg>
                <div><div className="mono" style={{ fontSize: '1.8rem', fontWeight: 700, letterSpacing: '-.03em' }}>92</div><div className="dt-stat win" style={{ display: 'inline-block', marginTop: '4px' }} data-fr="Lancer" data-en="Launch">Lancer</div></div>
              </div>
            </div>
            <div className="step reveal" data-d="3">
              <div className="snum">03</div><div className="sline"></div>
              <h3 data-fr="Tu lances le premier" data-en="You launch first">Tu lances le premier</h3>
              <p data-fr="Fournisseurs, marge et fenêtre déjà prêts. Tu lances pendant que la concurrence cherche encore." data-en="Suppliers, margin and window ready. You launch while competitors are still searching.">Fournisseurs, marge et fenêtre déjà prêts. Tu lances pendant que la concurrence cherche encore.</p>
              <div className="svis" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '10px' }}>
                <div className="chip" style={{ position: 'static', boxShadow: 'none', borderColor: 'var(--line-soft)' }}><span className="ico" style={{ background: 'var(--signal)' }}>✓</span><div><div data-fr="Fournisseur validé" data-en="Supplier verified">Fournisseur validé</div><div className="sub" data-fr="×4,2 de marge" data-en="×4.2 margin">×4,2 de marge</div></div></div>
                <div className="chip" style={{ position: 'static', boxShadow: 'none', borderColor: 'var(--line-soft)' }}><span className="ico" style={{ background: 'var(--accent)' }}>⚡</span><div><div data-fr="Fenêtre ouverte" data-en="Window open">Fenêtre ouverte</div><div className="sub" data-fr="5,2 semaines d'avance" data-en="5.2 weeks lead">5,2 semaines d'avance</div></div></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* TESTIMONIALS */}
      <section className="testi section-pad" id="testi">
        <div className="container">
          <div className="section-head reveal">
            <h2 className="section-title" data-fr="L'avance, <em>racontée</em> par ceux qui l'ont prise." data-en="The lead, <em>told</em> by those who took it.">L'avance, <em>racontée</em> par ceux qui l'ont prise.</h2>
          </div>
          <div className="testi-grid">
            <div className="tcard feature reveal">
              <div className="tstars">★★★★★</div>
              <p className="tq" data-fr="On a lancé le masseur cervical <em>cinq semaines</em> avant la vague de pubs. Le produit était déjà rentable quand nos concurrents l'ont « découvert »." data-en="We launched the neck massager <em>five weeks</em> before the ad wave. The product was already profitable when our competitors « discovered » it.">On a lancé le masseur cervical <em>cinq semaines</em> avant la vague de pubs. Le produit était déjà rentable quand nos concurrents l'ont « découvert ».</p>
              <div className="tkpi"><div><div className="n">+38%</div><div className="l" data-fr="marge nette" data-en="net margin">marge nette</div></div><div><div className="n">5 sem.</div><div className="l" data-fr="d'avance" data-en="lead">d'avance</div></div></div>
              <div className="tmeta"><div className="tav" style={{ background: 'linear-gradient(135deg,#6dcbff,#5a47cd)' }}></div><div><div className="tn">CamilleRé</div><div className="tr" data-fr="Fondatrice · Nordsky" data-en="Founder · Nordsky">Fondatrice · Nordsky</div></div></div>
            </div>
            <div className="tcard reveal" data-d="1">
              <div className="tstars">★★★★★</div>
              <p className="tq" data-fr="Le score remplace deux heures de recherche par jour. Je vois la vélocité, la marge, la concurrence — et je décide en dix secondes." data-en="The score replaces two hours of research a day. I see velocity, margin, competition — and I decide in ten seconds.">Le score remplace deux heures de recherche par jour. Je vois la vélocité, la marge, la concurrence — et je décide en dix secondes.</p>
              <div className="tmeta"><div className="tav" style={{ background: 'linear-gradient(135deg,#6dedc3,#34a853)' }}></div><div><div className="tn">Yanis B.</div><div className="tr" data-fr="E-commerçant · 7 boutiques" data-en="Seller · 7 stores">E-commerçant · 7 boutiques</div></div></div>
            </div>
            <div className="tcard reveal" data-d="2">
              <div className="tstars">★★★★★</div>
              <p className="tq" data-fr="Les alertes au premier signal ont changé mon timing. J'arrête de copier les gagnants des autres — je suis le gagnant." data-en="First-signal alerts changed my timing. I've stopped copying others' winners — I am the winner.">Les alertes au premier signal ont changé mon timing. J'arrête de copier les gagnants des autres — je suis le gagnant.</p>
              <div className="tmeta"><div className="tav" style={{ background: 'linear-gradient(135deg,#fdba09,#ff4500)' }}></div><div><div className="tn">Sofia M.</div><div className="tr" data-fr="DTC · Maison RoHe" data-en="DTC · Maison RoHe">DTC · Maison RoHe</div></div></div>
            </div>
            <div className="tcard reveal" data-d="3">
              <div className="tstars">★★★★★</div>
              <p className="tq" data-fr="Enfin un outil qui pondère la marge AliExpress. Plus de produits viraux mais invendables." data-en="Finally a tool that weighs AliExpress margin. No more viral but unsellable products.">Enfin un outil qui pondère la marge AliExpress. Plus de produits viraux mais invendables.</p>
              <div className="tmeta"><div className="tav" style={{ background: 'linear-gradient(135deg,#f0a6c8,#c06ef3)' }}></div><div><div className="tn">Théo L.</div><div className="tr" data-fr="Dropshipping · VOLT Goods" data-en="Dropshipping · VOLT Goods">Dropshipping · VOLT Goods</div></div></div>
            </div>
          </div>
        </div>
      </section>

      {/* PRICING */}
      <section className="pricing section-pad" id="pricing">
        <div className="container">
          <div className="section-head center reveal">
            <h2 className="section-title" data-fr="Une longueur d'avance, <em>à chaque échelle</em>." data-en="A head start, <em>at every scale</em>.">Une longueur d'avance, <em>à chaque échelle</em>.</h2>
            <div className="price-toggle">
              <button className="on" data-period="monthly" data-fr="Mensuel" data-en="Monthly">Mensuel</button>
              <button data-period="yearly" data-fr="Annuel <span class='save'>−20%</span>" data-en="Yearly <span class='save'>−20%</span>">Annuel <span className="save">−20%</span></button>
            </div>
          </div>
          <div className="price-grid">
            <div className="pcard reveal" data-d="1">
              <div className="pname" data-fr="Éclaireur" data-en="Scout">Éclaireur</div>
              <div className="pdesc" data-fr="Pour tester l'avance sur une niche." data-en="To test the lead on one niche.">Pour tester l'avance sur une niche.</div>
              <div className="pprice"><span className="amt" data-m="0" data-y="0">0</span><span className="per" data-fr="/mois" data-en="/mo">/mois</span></div>
              <a href="#" className="btn btn-ghost pbtn" data-fr="Commencer" data-en="Get started">Commencer</a>
              <ul>
                <li><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M20 6 9 17l-5-5"/></svg><span data-fr="1 niche suivie" data-en="1 tracked niche">1 niche suivie</span></li>
                <li><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M20 6 9 17l-5-5"/></svg><span data-fr="Score Tandor de base" data-en="Basic Tandor score">Score Tandor de base</span></li>
                <li><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M20 6 9 17l-5-5"/></svg><span data-fr="Maj hebdomadaire" data-en="Weekly updates">Maj hebdomadaire</span></li>
                <li className="off"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M18 6 6 18M6 6l12 12"/></svg><span data-fr="Alertes temps réel" data-en="Real-time alerts">Alertes temps réel</span></li>
              </ul>
            </div>
            <div className="pcard pop reveal" data-d="2">
              <div className="ptag" data-fr="Le plus choisi" data-en="Most popular">Le plus choisi</div>
              <div className="pname" data-fr="Chasseur" data-en="Hunter">Chasseur</div>
              <div className="pdesc" data-fr="Pour lancer avant le marché, en continu." data-en="To launch ahead of the market, continuously.">Pour lancer avant le marché, en continu.</div>
              <div className="pprice"><span className="amt" data-m="49" data-y="39">49</span><span className="per" data-fr="/mois" data-en="/mo">/mois</span></div>
              <a href="#" className="btn btn-accent pbtn" data-fr="Essayer 14 jours" data-en="Try 14 days">Essayer 14 jours</a>
              <ul>
                <li><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M20 6 9 17l-5-5"/></svg><span data-fr="Niches illimitées" data-en="Unlimited niches">Niches illimitées</span></li>
                <li><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M20 6 9 17l-5-5"/></svg><span data-fr="Vélocité multi-sources" data-en="Multi-source velocity">Vélocité multi-sources</span></li>
                <li><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M20 6 9 17l-5-5"/></svg><span data-fr="Marge &amp; concurrence" data-en="Margin & competition">Marge &amp; concurrence</span></li>
                <li><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M20 6 9 17l-5-5"/></svg><span data-fr="Alertes temps réel" data-en="Real-time alerts">Alertes temps réel</span></li>
              </ul>
            </div>
            <div className="pcard reveal" data-d="3">
              <div className="pname" data-fr="Agence" data-en="Agency">Agence</div>
              <div className="pdesc" data-fr="Pour les équipes et portefeuilles de marques." data-en="For teams and brand portfolios.">Pour les équipes et portefeuilles de marques.</div>
              <div className="pprice"><span className="amt" data-m="149" data-y="119">149</span><span className="per" data-fr="/mois" data-en="/mo">/mois</span></div>
              <a href="#" className="btn btn-ghost pbtn" data-fr="Parler à l'équipe" data-en="Talk to sales">Parler à l'équipe</a>
              <ul>
                <li><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M20 6 9 17l-5-5"/></svg><span data-fr="Tout Chasseur, ×illimité" data-en="Everything in Hunter, ×unlimited">Tout Chasseur, ×illimité</span></li>
                <li><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M20 6 9 17l-5-5"/></svg><span data-fr="Sièges en équipe" data-en="Team seats">Sièges en équipe</span></li>
                <li><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M20 6 9 17l-5-5"/></svg><span data-fr="API &amp; webhooks" data-en="API & webhooks">API &amp; webhooks</span></li>
                <li><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M20 6 9 17l-5-5"/></svg><span data-fr="Accompagnement dédié" data-en="Dedicated support">Accompagnement dédié</span></li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="faq section-pad" id="faq">
        <div className="container">
          <div className="section-head center reveal">
            <h2 className="section-title" data-fr="Ce qu'on nous demande <em>souvent</em>." data-en="What people <em>often</em> ask.">Ce qu'on nous demande <em>souvent</em>.</h2>
          </div>
          <div className="faq-wrap reveal">
            <div className="faq-item"><button className="faq-q"><span data-fr="D'où viennent les signaux de Tandor ?" data-en="Where do Tandor's signals come from?">D'où viennent les signaux de Tandor ?</span><span className="fq-ico"></span></button><div className="faq-a"><div className="faq-a-inner" data-fr="Tandor agrège des sources publiques — discussions Reddit, formats et hashtags TikTok, recherches Google Trends — puis mesure leur accélération semaine après semaine. C'est la vélocité, pas le volume, qui prédit un produit gagnant." data-en="Tandor aggregates public sources — Reddit threads, TikTok formats and hashtags, Google Trends searches — then measures their week-over-week acceleration. It's velocity, not volume, that predicts a winning product.">Tandor agrège des sources publiques — discussions Reddit, formats et hashtags TikTok, recherches Google Trends — puis mesure leur accélération semaine après semaine.</div></div></div>
            <div className="faq-item"><button className="faq-q"><span data-fr="Comment le score est-il calculé ?" data-en="How is the score calculated?">Comment le score est-il calculé ?</span><span className="fq-ico"></span></button><div className="faq-a"><div className="faq-a-inner" data-fr="Le score de 0 à 100 croise trois axes : la vélocité du signal organique, la marge estimée côté fournisseurs (AliExpress), et la saturation publicitaire. Un produit viral mais à faible marge ou déjà saturé est automatiquement recalé." data-en="The 0–100 score crosses three axes: organic signal velocity, estimated supplier-side margin (AliExpress), and ad saturation. A viral product with thin margin or heavy saturation is automatically flagged down.">Le score de 0 à 100 croise trois axes : la vélocité du signal organique, la marge estimée côté fournisseurs (AliExpress), et la saturation publicitaire.</div></div></div>
            <div className="faq-item"><button className="faq-q"><span data-fr="Quelle avance puis-je vraiment espérer ?" data-en="What lead can I really expect?">Quelle avance puis-je vraiment espérer ?</span><span className="fq-ico"></span></button><div className="faq-a"><div className="faq-a-inner" data-fr="En moyenne, le signal organique précède la vague de publicités concurrentes de 4 à 6 semaines. Cette fenêtre est ton avantage : le temps de valider un fournisseur, créer ton offre et lancer avant que le marché ne se sature." data-en="On average, organic signal precedes the wave of competitor ads by 4 to 6 weeks. That window is your advantage: time to validate a supplier, build your offer and launch before the market saturates.">En moyenne, le signal organique précède la vague de publicités concurrentes de 4 à 6 semaines.</div></div></div>
            <div className="faq-item"><button className="faq-q"><span data-fr="Faut-il un engagement ?" data-en="Is there a commitment?">Faut-il un engagement ?</span><span className="fq-ico"></span></button><div className="faq-a"><div className="faq-a-inner" data-fr="Non. L'essai de 14 jours est sans carte bancaire, et tous les plans sont sans engagement — tu peux passer à l'année pour −20% quand tu es prêt, ou arrêter à tout moment." data-en="No. The 14-day trial needs no credit card, and all plans are commitment-free — switch to yearly for −20% when ready, or stop anytime.">Non. L'essai de 14 jours est sans carte bancaire, et tous les plans sont sans engagement.</div></div></div>
            <div className="faq-item"><button className="faq-q"><span data-fr="Tandor remplace-t-il mon outil d'ads ?" data-en="Does Tandor replace my ads tool?">Tandor remplace-t-il mon outil d'ads ?</span><span className="fq-ico"></span></button><div className="faq-a"><div className="faq-a-inner" data-fr="Non — Tandor intervient en amont. Là où les outils d'ads te montrent ce qui marche déjà (et que tout le monde voit), Tandor te montre ce qui va marcher, pendant que la fenêtre est encore ouverte." data-en="No — Tandor works upstream. Where ad tools show you what already works (and everyone sees), Tandor shows you what will work, while the window is still open.">Non — Tandor intervient en amont. Là où les outils d'ads te montrent ce qui marche déjà, Tandor te montre ce qui va marcher.</div></div></div>
          </div>
        </div>
      </section>

      {/* FINAL CTA */}
      <section className="cta">
        <div className="container">
          <div className="cta-box reveal-scale">
            <div className="halo x"></div>
            <div className="halo y"></div>
            <div className="cgrid"></div>
            <span className="eyebrow center" style={{ color: 'oklch(0.82 0.1 264)' }} data-fr="Prends l'avance" data-en="Take the lead">Prends l'avance</span>
            <h2 data-fr="Le prochain produit gagnant est <em>déjà</em> en train de monter." data-en="The next winning product is <em>already</em> rising.">Le prochain produit gagnant est <em>déjà</em> en train de monter.</h2>
            <p className="lead" data-fr="Sois là au premier signal. Commence gratuitement, sans carte bancaire." data-en="Be there at the first signal. Start free, no credit card.">Sois là au premier signal. Commence gratuitement, sans carte bancaire.</p>
            <div className="cta-actions">
              <a href="#" className="btn btn-light btn-lg" data-fr="Commencer gratuitement" data-en="Start for free">Commencer gratuitement</a>
              <a href="#dashboard" className="btn btn-lg" style={{ border: '1px solid oklch(0.6 0.04 264)', color: 'var(--paper)' }} data-fr="Voir une démo" data-en="See a demo">Voir une démo</a>
            </div>
            <div className="cta-note" data-fr="14 jours d'essai · sans engagement · annulable en un clic" data-en="14-day trial · no commitment · cancel in one click">14 jours d'essai · sans engagement · annulable en un clic</div>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="footer">
        <div className="container">
          <div className="footer-grid">
            <div className="footer-brand-col">
              <div className="brand">Tandor<span className="dot">.</span></div>
              <p className="footer-about" data-fr="Le product research par signaux. Détecte les produits gagnants 4 à 6 semaines avant qu'ils n'apparaissent dans les pubs des concurrents." data-en="Signal-based product research. Detect winning products 4 to 6 weeks before they show up in competitors' ads.">Le product research par signaux. Détecte les produits gagnants 4 à 6 semaines avant qu'ils n'apparaissent dans les pubs des concurrents.</p>
            </div>
            <div className="footer-col">
              <h5 data-fr="Produit" data-en="Product">Produit</h5>
              <a href="#features" data-fr="Fonctionnalités" data-en="Features">Fonctionnalités</a>
              <a href="#dashboard" data-fr="Le radar" data-en="The radar">Le radar</a>
              <a href="#pricing" data-fr="Tarifs" data-en="Pricing">Tarifs</a>
              <a href="#how" data-fr="Comment ça marche" data-en="How it works">Comment ça marche</a>
            </div>
            <div className="footer-col">
              <h5 data-fr="Ressources" data-en="Resources">Ressources</h5>
              <a href="#" data-fr="Blog" data-en="Blog">Blog</a>
              <a href="#faq" data-fr="FAQ" data-en="FAQ">FAQ</a>
              <a href="#" data-fr="Guide du timing" data-en="Timing guide">Guide du timing</a>
              <a href="#" data-fr="Centre d'aide" data-en="Help center">Centre d'aide</a>
            </div>
            <div className="footer-col">
              <h5 data-fr="Entreprise" data-en="Company">Entreprise</h5>
              <a href="#" data-fr="À propos" data-en="About">À propos</a>
              <a href="#" data-fr="Contact" data-en="Contact">Contact</a>
              <a href="#" data-fr="Confidentialité" data-en="Privacy">Confidentialité</a>
              <a href="#" data-fr="Conditions" data-en="Terms">Conditions</a>
            </div>
          </div>
          <div className="footer-bottom">
            <span className="mono">© <span id="year">2026</span> Tandor — <span data-fr="Tous droits réservés" data-en="All rights reserved">Tous droits réservés</span></span>
            <span className="mono" data-fr="Conçu pour ceux qui lancent en premier" data-en="Built for those who launch first">Conçu pour ceux qui lancent en premier</span>
          </div>
        </div>
      </footer>

      {/* Hero variant switcher */}
    </>
  );
};

export default Home;
