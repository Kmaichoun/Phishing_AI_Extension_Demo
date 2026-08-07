(() => {
  'use strict';

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  function bindCommandPalette() {
    const dialog = document.getElementById('popupCommandPalette');
    const trigger = document.getElementById('popupCommandOpen');
    const input = document.getElementById('popupCommandSearch');
    const options = Array.from(dialog?.querySelectorAll('[data-popup-command]') || []);
    if (!dialog || !trigger || !input || !options.length) return;

    let activeOption = null;
    let returnFocus = null;
    let closeTimer = null;

    const normalized = value => String(value || '').normalize('NFKD').toLocaleLowerCase('th');
    const visible = () => options.filter(option => !option.hidden);

    function setActive(option) {
      options.forEach(item => {
        const selected = item === option;
        item.classList.toggle('is-active', selected);
        item.setAttribute('aria-selected', String(selected));
      });
      activeOption = option || null;
      input.setAttribute('aria-activedescendant', activeOption?.id || '');
      activeOption?.scrollIntoView({ block: 'nearest' });
    }

    function filterOptions() {
      const query = normalized(input.value.trim());
      options.forEach(option => {
        option.hidden = !!query && !normalized(`${option.textContent} ${option.dataset.keywords || ''}`).includes(query);
      });
      setActive(visible()[0] || null);
    }

    function closePalette(afterClose) {
      window.clearTimeout(closeTimer);
      const finish = () => {
        if (dialog.open) dialog.close();
        dialog.classList.remove('is-closing');
        afterClose?.();
        returnFocus?.focus?.({ preventScroll: true });
      };
      if (!dialog.open || reduceMotion.matches) return finish();
      dialog.classList.add('is-closing');
      closeTimer = window.setTimeout(finish, 150);
    }

    function openPalette(source = trigger) {
      if (dialog.open) return;
      returnFocus = source || document.activeElement;
      input.value = '';
      options.forEach(option => { option.hidden = false; });
      dialog.classList.remove('is-closing');
      dialog.showModal();
      setActive(options[0]);
      window.requestAnimationFrame(() => input.focus({ preventScroll: true }));
    }

    function runCommand(option) {
      if (!option || option.hidden) return;
      const targets = {
        'page-scan': 'pageScanningEnabled',
        scan: 'scanLinks',
        qr: 'openQrScanner',
        web: 'openWebApp',
        clipboard: 'checkClipboard',
        privacy: 'privacyMode',
        llm: 'llmEnabled',
        theme: 'popupThemeToggle'
      };
      const targetId = targets[option.dataset.popupCommand];
      closePalette(() => document.getElementById(targetId)?.click());
    }

    trigger.addEventListener('click', () => openPalette(trigger));
    dialog.querySelector('[data-popup-command-close]')?.addEventListener('click', () => closePalette());
    dialog.addEventListener('cancel', event => {
      event.preventDefault();
      closePalette();
    });
    dialog.addEventListener('click', event => {
      if (event.target === dialog) closePalette();
    });
    options.forEach(option => {
      option.addEventListener('pointermove', () => setActive(option));
      option.addEventListener('click', () => runCommand(option));
    });
    input.addEventListener('input', filterOptions);
    input.addEventListener('keydown', event => {
      const available = visible();
      if (event.key === 'Escape') {
        event.preventDefault();
        closePalette();
        return;
      }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (!available.length) return;
        const currentIndex = Math.max(0, available.indexOf(activeOption));
        const direction = event.key === 'ArrowDown' ? 1 : -1;
        setActive(available[(currentIndex + direction + available.length) % available.length]);
      }
      if (event.key === 'Enter') {
        event.preventDefault();
        runCommand(activeOption);
      }
    });
    document.addEventListener('keydown', event => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === 'k') {
        event.preventDefault();
        dialog.open ? closePalette() : openPalette(trigger);
      }
    });
  }

  function bindAnalysisFeedback() {
    const status = document.getElementById('status');
    const verdict = document.getElementById('verdictText');
    const card = document.getElementById('scoreCard');
    const toast = document.getElementById('toast');
    if (status && card) {
      const update = () => {
        const message = `${status.textContent || ''} ${verdict?.textContent || ''}`;
        card.classList.toggle('is-analyzing', /กำลัง|วิเคราะห์/.test(message));
      };
      new MutationObserver(update).observe(status, { childList: true, characterData: true, subtree: true });
      if (verdict) new MutationObserver(update).observe(verdict, { childList: true, characterData: true, subtree: true });
      update();
    }
    if (toast) {
      new MutationObserver(() => {
        if (!toast.textContent.trim()) return;
        toast.classList.remove('is-updating');
        void toast.offsetWidth;
        toast.classList.add('is-updating');
      }).observe(toast, { childList: true, characterData: true, subtree: true });
    }
  }

  bindCommandPalette();
  bindAnalysisFeedback();
})();
