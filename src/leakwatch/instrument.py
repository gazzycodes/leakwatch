"""Browser-side instrumentation injected before any page script runs.

The script wraps the handful of APIs that fingerprinting libraries abuse and
keeps a tally on ``window.__leakwatch``. It only ever counts calls — it never
reads page content, user input, or media. The engine reads the tally back after
the page settles via ``REPORT_EXPRESSION``.
"""

from __future__ import annotations

# Injected with page.add_init_script so it is installed on every frame before
# the page's own scripts execute.
INIT_SCRIPT = r"""
(() => {
  if (window.__leakwatch) return;
  const counts = {
    canvas: { technique: 'canvas', api: 'canvas.toDataURL/getImageData', count: 0 },
    webgl: { technique: 'webgl', api: 'WebGL.getParameter/readPixels', count: 0 },
    audio: { technique: 'audio', api: 'AudioContext', count: 0 },
    fonts: { technique: 'fonts', api: 'measureText/font enumeration', count: 0 },
    navigator: { technique: 'navigator', api: 'navigator probes', count: 0 },
  };
  window.__leakwatch = { fingerprints: counts };
  const bump = (k) => { try { counts[k].count++; } catch (e) {} };

  const wrap = (obj, name, key) => {
    if (!obj || !obj.prototype || !obj.prototype[name]) return;
    const orig = obj.prototype[name];
    obj.prototype[name] = function (...args) {
      bump(key);
      return orig.apply(this, args);
    };
  };

  // Canvas
  wrap(window.HTMLCanvasElement, 'toDataURL', 'canvas');
  wrap(window.CanvasRenderingContext2D, 'getImageData', 'canvas');
  wrap(window.CanvasRenderingContext2D, 'measureText', 'fonts');

  // WebGL
  if (window.WebGLRenderingContext) {
    wrap(window.WebGLRenderingContext, 'getParameter', 'webgl');
    wrap(window.WebGLRenderingContext, 'readPixels', 'webgl');
  }
  if (window.WebGL2RenderingContext) {
    wrap(window.WebGL2RenderingContext, 'getParameter', 'webgl');
  }

  // AudioContext
  const AC = window.AudioContext || window.webkitAudioContext;
  if (AC) {
    wrap(AC, 'createAnalyser', 'audio');
    wrap(AC, 'createOscillator', 'audio');
  }

  // Font enumeration via the FontFaceSet check API
  try {
    if (document.fonts && document.fonts.check) {
      const origCheck = document.fonts.check.bind(document.fonts);
      document.fonts.check = function (...args) {
        bump('fonts');
        return origCheck(...args);
      };
    }
  } catch (e) {}

  // High-entropy navigator probes
  const navProbes = ['hardwareConcurrency', 'deviceMemory', 'platform', 'languages'];
  navProbes.forEach((p) => {
    try {
      const proto = Object.getPrototypeOf(navigator);
      const desc = Object.getOwnPropertyDescriptor(proto, p);
      if (desc && desc.get) {
        Object.defineProperty(navigator, p, {
          get() { bump('navigator'); return desc.get.call(navigator); },
        });
      }
    } catch (e) {}
  });
})();
"""

# Evaluated after the page settles to pull the tally back into Python.
REPORT_EXPRESSION = (
    "() => (window.__leakwatch ? Object.values(window.__leakwatch.fingerprints) : [])"
)

# Read the storage written during the visit (keys only — never values).
STORAGE_EXPRESSION = r"""
() => {
  const out = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      out.push({ kind: 'local', key: localStorage.key(i), origin: location.origin });
    }
  } catch (e) {}
  try {
    for (let i = 0; i < sessionStorage.length; i++) {
      out.push({ kind: 'session', key: sessionStorage.key(i), origin: location.origin });
    }
  } catch (e) {}
  return out;
}
"""

# Detect a consent-management platform via standard APIs and known globals.
# Language- and DOM-independent: tells us a consent gate exists even when the
# accept button cannot be clicked, so a gated site is never reported as clean.
CMP_DETECT_EXPRESSION = r"""
() => {
  const out = { present: false, cmp: '' };
  const mark = (name) => { out.present = true; if (!out.cmp) out.cmp = name; };
  try { if (typeof window.__tcfapi === 'function') mark('IAB TCF'); } catch (e) {}
  try { if (typeof window.__gpp === 'function') mark('IAB GPP'); } catch (e) {}
  try { if (typeof window.__cmp === 'function') mark('IAB TCF v1'); } catch (e) {}
  try { if (window.OneTrust || window.Optanon) mark('OneTrust'); } catch (e) {}
  try { if (window.Cookiebot || window.CookieConsent) mark('Cookiebot'); } catch (e) {}
  try { if (window.Didomi) mark('Didomi'); } catch (e) {}
  try { if (window.__uspapi) mark('US Privacy'); } catch (e) {}
  try { if (window.Cookielaw) mark('OneTrust'); } catch (e) {}
  return out;
}
"""
