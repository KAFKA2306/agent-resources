(() => {
  'use strict';

  const root = document.documentElement;
  const searchInput = document.querySelector('#project-search');
  const rows = [...document.querySelectorAll('#project-rows tr')];
  const count = document.querySelector('#project-count');
  const reset = document.querySelector('#reset-controls');
  const copyButton = document.querySelector('#copy-code');
  const copyStatus = document.querySelector('#copy-status');
  const code = document.querySelector('#code-example code');

  const allowedThemes = ['terminal', 'paper'];
  const allowedDensities = ['compact', 'comfortable'];

  function readPreference(key, fallback, allowed) {
    try {
      const value = localStorage.getItem(key);
      return allowed.includes(value) ? value : fallback;
    } catch {
      return fallback;
    }
  }

  function writePreference(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch {
      // Presentation preferences are optional.
    }
  }

  function updatePressed(selector, value, attribute) {
    document.querySelectorAll(selector).forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset[attribute] === value));
    });
  }

  function applyTheme(theme, persist = true) {
    if (!allowedThemes.includes(theme)) return;
    root.dataset.theme = theme;
    updatePressed('[data-theme-button]', theme, 'themeButton');
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'terminal' ? '#07090c' : '#f4f1e9');
    if (persist) writePreference('kafka-evidence-theme', theme);
  }

  function applyDensity(density, persist = true) {
    if (!allowedDensities.includes(density)) return;
    root.dataset.density = density;
    updatePressed('[data-density-button]', density, 'densityButton');
    if (persist) writePreference('kafka-evidence-density', density);
  }

  function filterRows() {
    const query = (searchInput?.value ?? '').trim().toLowerCase();
    let visible = 0;
    rows.forEach((row) => {
      const haystack = `${row.dataset.search ?? ''} ${row.textContent ?? ''}`.toLowerCase();
      const matches = !query || haystack.includes(query);
      row.classList.toggle('k-hidden', !matches);
      if (matches) visible += 1;
    });
    if (count) count.textContent = `${visible} ${visible === 1 ? 'row' : 'rows'}`;
  }

  document.querySelectorAll('[data-theme-button]').forEach((button) => {
    button.addEventListener('click', () => applyTheme(button.dataset.themeButton));
  });

  document.querySelectorAll('[data-density-button]').forEach((button) => {
    button.addEventListener('click', () => applyDensity(button.dataset.densityButton));
  });

  searchInput?.addEventListener('input', filterRows);

  reset?.addEventListener('click', () => {
    if (searchInput) searchInput.value = '';
    applyTheme('terminal');
    applyDensity('compact');
    filterRows();
    searchInput?.focus();
  });

  copyButton?.addEventListener('click', async () => {
    const text = code?.textContent ?? '';
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      if (copyStatus) copyStatus.textContent = 'Copied to clipboard.';
    } catch {
      const area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.append(area);
      area.select();
      const copied = document.execCommand('copy');
      area.remove();
      if (copyStatus) copyStatus.textContent = copied ? 'Copied to clipboard.' : 'Copy failed. Select the code manually.';
    }
  });

  applyTheme(readPreference('kafka-evidence-theme', 'terminal', allowedThemes), false);
  applyDensity(readPreference('kafka-evidence-density', 'compact', allowedDensities), false);
  filterRows();
})();
