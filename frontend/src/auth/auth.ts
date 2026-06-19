/* eslint-disable */
// @ts-nocheck
export {};
/* ============================================================
   TANDOR — auth.js
   Form behaviour for the auth screens. Progressive: validation,
   password strength, show/hide, submit → loading → done, code
   input, resend countdown. Bilingual messages via data-fr/data-en
   resolved through TandorPublic.lang. Demo only — no real auth.
   ============================================================ */
(function () {
  "use strict";
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
  var lang = function () { return (window.TandorPublic && window.TandorPublic.lang) || "fr"; };

  var MSG = {
    email_req: { fr: "Saisissez votre email.", en: "Enter your email." },
    email_bad: { fr: "Format d’email invalide.", en: "Invalid email format." },
    email_ok: { fr: "Email valide", en: "Looks good" },
    pw_req: { fr: "Saisissez un mot de passe.", en: "Enter a password." },
    pw_short: { fr: "Au moins 8 caractères.", en: "At least 8 characters." },
    pw_match: { fr: "Les mots de passe ne correspondent pas.", en: "Passwords don’t match." },
    name_req: { fr: "Indiquez votre nom.", en: "Enter your name." },
    terms_req: { fr: "Veuillez accepter les conditions.", en: "Please accept the terms." },
    strength: { fr: ["", "Faible", "Correct", "Bon", "Excellent"], en: ["", "Weak", "Fair", "Good", "Strong"] },
    code_bad: { fr: "Code incorrect. Réessayez.", en: "Wrong code. Try again." },
  };
  function t(k) { var m = MSG[k]; return m ? m[lang()] : k; }

  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

  function setState(fld, state, msg) {
    fld.classList.remove("ok", "err");
    if (state) fld.classList.add(state);
    var m = $(".fld-msg", fld);
    if (m && msg != null) m.textContent = msg;
  }

  /* ---------- password show / hide ---------- */
  $$(".pw-toggle").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var inp = $("input", btn.closest(".fld-input"));
      if (!inp) return;
      var show = inp.type === "password";
      inp.type = show ? "text" : "password";
      btn.innerHTML = show
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9.9 4.2A9.5 9.5 0 0 1 12 4c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4M6.6 6.6A17 17 0 0 0 2 11s3.5 7 10 7a9.4 9.4 0 0 0 4.3-1M3 3l18 18"/><path d="M9.5 9.5a3 3 0 0 0 4.2 4.2"/></svg>';
    });
  });

  /* ---------- email validation ---------- */
  function validateEmail(fld, live) {
    var inp = $("input", fld), v = inp.value.trim();
    if (!v) { if (!live) setState(fld, "err", t("email_req")); else setState(fld, null); return false; }
    if (!EMAIL_RE.test(v)) { setState(fld, "err", t("email_bad")); return false; }
    setState(fld, "ok"); var okm = $(".ok-msg", fld); if (okm) okm.textContent = t("email_ok"); return true;
  }
  $$('[data-validate="email"]').forEach(function (fld) {
    var inp = $("input", fld);
    inp.addEventListener("blur", function () { if (inp.value.trim()) validateEmail(fld, false); });
    inp.addEventListener("input", function () { if (fld.classList.contains("err")) validateEmail(fld, true); });
  });

  /* ---------- password strength ---------- */
  function scorePw(v) {
    var checks = { len: v.length >= 8, upper: /[A-Z]/.test(v), num: /[0-9]/.test(v), sym: /[^A-Za-z0-9]/.test(v) };
    var n = (checks.len ? 1 : 0) + (checks.upper ? 1 : 0) + (checks.num ? 1 : 0) + (checks.sym ? 1 : 0);
    return { level: n, checks: checks };
  }
  $$('[data-validate="password"]').forEach(function (fld) {
    var inp = $("input", fld);
    var strength = fld.querySelector(".pw-strength") || fld.parentNode.querySelector(".pw-strength") || document.querySelector(".pw-strength[data-for='" + inp.id + "']");
    var lbl = fld.querySelector(".pw-level-lbl");
    inp.addEventListener("input", function () {
      var v = inp.value;
      if (strength) {
        var r = scorePw(v);
        strength.setAttribute("data-level", v ? r.level : 0);
        if (lbl) lbl.textContent = v ? MSG.strength[lang()][r.level] : "";
        $$(".pw-check", strength).forEach(function (c) { c.classList.toggle("on", !!r.checks[c.dataset.check]); });
      }
      if (fld.classList.contains("err") && v.length >= 8) setState(fld, null);
    });
  });

  /* ---------- confirm password ---------- */
  function validateConfirm(fld) {
    var inp = $("input", fld), ref = document.getElementById(fld.dataset.match);
    if (!ref) return true;
    if (inp.value && inp.value !== ref.value) { setState(fld, "err", t("pw_match")); return false; }
    if (inp.value) setState(fld, "ok"); else setState(fld, null);
    return inp.value === ref.value;
  }
  $$("[data-match]").forEach(function (fld) {
    var inp = $("input", fld);
    inp.addEventListener("input", function () { if (fld.classList.contains("err") || inp.value) validateConfirm(fld); });
  });

  /* ---------- terms checkbox ---------- */
  $$(".chk-line").forEach(function (c) {
    c.addEventListener("click", function (e) {
      if (e.target.tagName === "A") return;
      c.classList.toggle("on");
      if (c.classList.contains("on")) c.classList.remove("err");
    });
  });

  /* ---------- submit → loading → done ---------- */
  function runSubmit(btn, onDone) {
    btn.setAttribute("data-state", "loading");
    setTimeout(function () {
      btn.setAttribute("data-state", "done");
      var lbl = $(".lbl", btn); if (lbl) lbl.textContent = btn.dataset.doneLabel || lbl.textContent;
      btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" style="width:20px;height:20px"><path d="M20 6 9 17l-5-5"/></svg><span class="lbl">' + (btn.dataset.doneLabel || (lang() === "fr" ? "Connecté" : "Signed in")) + "</span>";
      if (onDone) setTimeout(onDone, 700);
    }, 1150);
  }

  $$("form[data-auth]").forEach(function (form) {
    var kind = form.dataset.auth;
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var valid = true;
      // email
      var emailFld = $('[data-validate="email"]', form);
      if (emailFld && !validateEmail(emailFld, false)) valid = false;
      // name (register)
      var nameFld = $('[data-validate="name"]', form);
      if (nameFld) { var nv = $("input", nameFld).value.trim(); if (!nv) { setState(nameFld, "err", t("name_req")); valid = false; } else setState(nameFld, "ok"); }
      // password
      var pwFld = $('[data-validate="password"]', form);
      if (pwFld) {
        var pv = $("input", pwFld).value;
        if (!pv) { setState(pwFld, "err", t("pw_req")); valid = false; }
        else if (pv.length < 8) { setState(pwFld, "err", t("pw_short")); valid = false; }
      }
      // simple required password (login — no strength rule)
      var pwLogin = $('[data-validate="password-login"]', form);
      if (pwLogin) { var lv = $("input", pwLogin).value; if (!lv) { setState(pwLogin, "err", t("pw_req")); valid = false; } }
      // confirm
      var confFld = $("[data-match]", form);
      if (confFld && !validateConfirm(confFld)) valid = false;
      // terms
      var terms = $(".chk-line[data-required]", form);
      if (terms && !terms.classList.contains("on")) { terms.classList.add("err"); valid = false; }

      if (!valid) { var firstErr = $(".fld.err input, .chk-line.err", form); if (firstErr) firstErr.focus && firstErr.focus(); return; }

      var btn = $(".auth-submit", form);

      // Si supabase-handler.ts est chargé, il prend en charge la soumission réelle.
      if (window.TandorAuth && typeof window.TandorAuth.handle === "function") {
        var formData = {
          email: emailFld ? $("input", emailFld).value.trim() : "",
          password: pwFld ? $("input", pwFld).value : (pwLogin ? $("input", pwLogin).value : ""),
          name: nameFld ? $("input", nameFld).value.trim() : "",
          next: form.dataset.next || "/dashboard",
        };
        window.TandorAuth.handle(kind, formData, btn);
        return;
      }

      // Démo fallback (pas de Supabase configuré)
      runSubmit(btn, function () {
        var dest = form.dataset.next;
        if (dest) window.location.href = dest;
      });
    });
  });

  /* ---------- code input (verify email) ---------- */
  var code = $(".code-input");
  if (code) {
    var inputs = $$("input", code);
    inputs.forEach(function (inp, i) {
      inp.addEventListener("input", function () {
        inp.value = inp.value.replace(/\D/g, "").slice(0, 1);
        inp.classList.toggle("filled", !!inp.value);
        code.classList.remove("err");
        if (inp.value && inputs[i + 1]) inputs[i + 1].focus();
        maybeVerify();
      });
      inp.addEventListener("keydown", function (e) {
        if (e.key === "Backspace" && !inp.value && inputs[i - 1]) { inputs[i - 1].focus(); }
        if (e.key === "ArrowLeft" && inputs[i - 1]) inputs[i - 1].focus();
        if (e.key === "ArrowRight" && inputs[i + 1]) inputs[i + 1].focus();
      });
      inp.addEventListener("paste", function (e) {
        e.preventDefault();
        var d = (e.clipboardData.getData("text") || "").replace(/\D/g, "").slice(0, inputs.length);
        d.split("").forEach(function (ch, k) { if (inputs[k]) { inputs[k].value = ch; inputs[k].classList.add("filled"); } });
        if (inputs[Math.min(d.length, inputs.length - 1)]) inputs[Math.min(d.length, inputs.length - 1)].focus();
        maybeVerify();
      });
    });
    function maybeVerify() {
      var val = inputs.map(function (i) { return i.value; }).join("");
      if (val.length === inputs.length) {
        var btn = $(".auth-submit");
        // demo: any code ending in even digit "succeeds"
        if (parseInt(val.slice(-1), 10) % 2 === 0 || true) {
          if (btn) runSubmit(btn, function () { var d = code.dataset.next; if (d) window.location.href = d; });
        }
      }
    }
    var verifyForm = $("form[data-verify]");
    if (verifyForm) verifyForm.addEventListener("submit", function (e) { e.preventDefault(); maybeVerify(); });
  }

  /* ---------- resend countdown ---------- */
  $$("[data-resend]").forEach(function (btn) {
    var base = btn.innerHTML, secs = 0, timer = null;
    function start() {
      secs = 30; tick();
      timer = setInterval(function () { secs--; if (secs <= 0) { clearInterval(timer); btn.disabled = false; btn.innerHTML = base; window.TandorPublic && window.TandorPublic.applyLang(); } else tick(); }, 1000);
    }
    function tick() { btn.disabled = true; btn.textContent = (lang() === "fr" ? "Renvoyer dans " : "Resend in ") + secs + "s"; }
    btn.addEventListener("click", function () { if (btn.disabled) return; start(); });
  });

  /* re-apply localized messages on language switch for any active error */
  document.addEventListener("tandor:lang", function () {
    $$(".fld.err").forEach(function (fld) {
      var kind = fld.dataset.validate;
      if (kind === "email") validateEmail(fld, false);
    });
  });
})();
