/**
 * config_loader.js
 * Loaded by miniapp/index.html to replace all hardcoded dropdown arrays
 * and the hardcoded BASE URL with live values from the server.
 *
 * Exposes:
 *   window.OLM_CONFIG  — resolved after fetchTenantConfig() resolves
 *   populateDropdowns() — call once DOM is ready
 */

(function () {
  // ── BASE URL ─────────────────────────────────────────────────────────────────
  // Derive base from window.location so the mini-app works on any domain without
  // a hardcoded constant. The Telegram WebApp always opens from the server URL.
  const BASE = window.BASE || (window.location.origin + (window.location.pathname.replace(/\/[^/]*$/, '') || ''));
  window.BASE = BASE;

  // ── Fetch tenant config from server ──────────────────────────────────────────
  async function fetchTenantConfig() {
    try {
      const res = await fetch(`${BASE}/api/tenant-config`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const cfg = await res.json();
      window.OLM_CONFIG = cfg;
      return cfg;
    } catch (e) {
      console.warn('[OLM] Could not fetch tenant config, using fallback defaults.', e);
      // Fallback — keeps mini-app functional if server is unreachable
      window.OLM_CONFIG = {
        brand_name: 'OLM',
        brand_color: '#2196f3',
        stages: ['Foundation', 'Brick', 'Plastering', 'Ready'],
        materials: ['White', 'Colour', 'Aluminium'],
        work_statuses: ['Yet to Visit', 'Visited', 'Quoted', 'Negotiation in Progress', 'Won', 'Lost'],
      };
      return window.OLM_CONFIG;
    }
  }

  // ── Populate a <select> element from an array ────────────────────────────────
  function populateSelect(selectId, items, placeholder) {
    const el = document.getElementById(selectId);
    if (!el) return;
    // Keep current value so updates don't reset in-progress forms
    const current = el.value;
    el.innerHTML = `<option value="">${placeholder}</option>`;
    items.forEach(item => {
      const opt = document.createElement('option');
      opt.value = item;
      opt.textContent = item;
      if (item === current) opt.selected = true;
      el.appendChild(opt);
    });
  }

  // ── Main: fetch config then wire dropdowns ────────────────────────────────────
  window.populateDropdowns = async function () {
    const cfg = await fetchTenantConfig();

    populateSelect('workStatus',  cfg.work_statuses, 'Select work status');
    populateSelect('stage',       cfg.stages,        'Select stage');
    populateSelect('material',    cfg.materials,     'Select material');

    // Also populate update-form dropdowns if they exist
    populateSelect('u_workStatus', cfg.work_statuses, 'Select work status');
    populateSelect('u_stage',      cfg.stages,        'Select stage');
    populateSelect('u_material',   cfg.materials,     'Select material');

    // Apply brand name everywhere
    document.querySelectorAll('[data-brand-name]').forEach(el => {
      el.textContent = cfg.brand_name || 'OLM';
    });

    // Apply brand color as CSS variable
    if (cfg.brand_color) {
      document.documentElement.style.setProperty('--brand-color', cfg.brand_color);
    }

    console.log('[OLM] Tenant config loaded:', cfg.brand_name, '| stages:', cfg.stages.length);
    return cfg;
  };

  // ── Auto-run once DOM is ready ────────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', window.populateDropdowns);
  } else {
    window.populateDropdowns();
  }
})();
