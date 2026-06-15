/* eslint-disable */
// @ts-nocheck
export {};
/* ============================================================
   TANDOR — public.js
   Shared runtime for the public (pre-login) pages: Auth + Pricing.
   Ported from landing.js — same FR/EN contract (data-fr/data-en),
   same reveal/nav/FAQ/pricing-toggle behaviour, no parallax/hero.
   Load it on every public page; page-specific JS runs after.
   ============================================================ */
(function () {
  "use strict";
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };

  /* ---------- Nav scrolled state ---------- */
  var nav = $(".nav");
  if (nav) {
    var onScrollNav = function () { nav.classList.toggle("scrolled", window.scrollY > 24); };
    onScrollNav();
    window.addEventListener("scroll", onScrollNav, { passive: true });
  }

  /* ---------- Scroll reveals (rAF-free, robust in iframes) ---------- */
  var revEls = $$(".reveal, .reveal-scale, .reveal-x");
  function checkReveals() {
    var vh = window.innerHeight;
    for (var i = revEls.length - 1; i >= 0; i--) {
      var el = revEls[i], r = el.getBoundingClientRect();
      if (r.top < vh * 0.94 && r.bottom > 0) {
        el.classList.add("in");
        (function (node) { setTimeout(function () { node.classList.add("shown"); }, 1150); })(el);
        revEls.splice(i, 1);
      }
    }
  }
  if (reduce) { revEls.forEach(function (el) { el.classList.add("in"); }); revEls = []; }
  else {
    window.addEventListener("scroll", checkReveals, { passive: true });
    window.addEventListener("resize", checkReveals, { passive: true });
    checkReveals(); setTimeout(checkReveals, 60); setTimeout(checkReveals, 300);
  }

  /* ---------- FAQ accordion ---------- */
  $$(".faq-item").forEach(function (item) {
    var q = $(".faq-q", item), a = $(".faq-a", item);
    if (!q || !a) return;
    q.addEventListener("click", function () {
      var open = item.classList.contains("open");
      $$(".faq-item.open").forEach(function (o) { o.classList.remove("open"); $(".faq-a", o).style.maxHeight = null; });
      if (!open) { item.classList.add("open"); a.style.maxHeight = a.scrollHeight + "px"; }
    });
  });

  /* ---------- Pricing toggle (monthly / yearly) ---------- */
  var priceBtns = $$(".price-toggle button");
  function movePill() {
    var wrap = $(".price-toggle"); if (!wrap) return;
    var pill = $(".toggle-pill", wrap), on = $("button.on", wrap);
    if (pill && on) { pill.style.left = on.offsetLeft + "px"; pill.style.width = on.offsetWidth + "px"; }
  }
  priceBtns.forEach(function (b) {
    b.addEventListener("click", function () {
      priceBtns.forEach(function (x) { x.classList.remove("on"); });
      b.classList.add("on");
      movePill();
      var yearly = b.dataset.period === "yearly";
      document.querySelectorAll(".pricing-root").forEach(function (r) { r.classList.toggle("is-yearly", yearly); });
      $$(".pcard .pprice .amt").forEach(function (a) { a.textContent = yearly ? a.dataset.y : a.dataset.m; });
      $$(".pcard .pprice .per").forEach(function (p) {
        p.setAttribute("data-fr", yearly ? "/mois · facturé annuel" : "/mois");
        p.setAttribute("data-en", yearly ? "/mo · billed yearly" : "/mo");
        applyLangTo(p);
      });
      $$("[data-save]").forEach(function (s) { s.style.display = yearly ? "" : "none"; });
    });
  });
  if (priceBtns.length) { setTimeout(movePill, 30); window.addEventListener("resize", movePill, { passive: true }); }

  /* ---------- Language toggle FR / EN (shared with landing) ---------- */
  var lang = localStorage.getItem("tandor_lang") || (((navigator.language || "fr").toLowerCase().indexOf("fr") === 0) ? "fr" : "en");
  function applyLangTo(el) {
    var v = el.getAttribute("data-" + lang);
    if (v !== null) { if (el.dataset.attr) el.setAttribute(el.dataset.attr, v); else el.innerHTML = v; }
  }
  function applyLang() {
    document.documentElement.lang = lang;
    $$("[data-fr]").forEach(applyLangTo);
    $$(".lang-toggle button").forEach(function (b) { b.classList.toggle("active", b.dataset.lang === lang); });
    $$(".faq-item.open .faq-a").forEach(function (a) { a.style.maxHeight = a.scrollHeight + "px"; });
    document.dispatchEvent(new CustomEvent("tandor:lang", { detail: { lang: lang } }));
  }
  $$(".lang-toggle button").forEach(function (b) {
    b.addEventListener("click", function () { lang = b.dataset.lang; localStorage.setItem("tandor_lang", lang); applyLang(); });
  });
  applyLang();

  /* ---------- Smooth anchors + mobile burger ---------- */
  $$('a[href^="#"]').forEach(function (a) {
    a.addEventListener("click", function (e) {
      var id = a.getAttribute("href");
      if (id.length > 1) { var t = $(id); if (t) { e.preventDefault(); window.scrollTo({ top: t.getBoundingClientRect().top + window.scrollY - 70, behavior: reduce ? "auto" : "smooth" }); } }
    });
  });
  var burger = $(".nav-burger");
  if (burger && nav) {
    burger.addEventListener("click", function () { nav.classList.toggle("menu-open"); });
    $$(".nav-drawer a").forEach(function (a) { a.addEventListener("click", function () { nav.classList.remove("menu-open"); }); });
  }

  /* ---------- Year ---------- */
  var yr = $("#year"); if (yr) yr.textContent = new Date().getFullYear();

  /* expose for page scripts */
  window.TandorPublic = {
    get lang() { return lang; },
    applyLang: applyLang,
    refreshReveals: checkReveals,
    reduce: reduce,
    $: $, $$: $$,
  };
})();
