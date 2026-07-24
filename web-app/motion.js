(() => {
  'use strict';

  const reduceMotion = typeof window.matchMedia === 'function'
    ? window.matchMedia('(prefers-reduced-motion: reduce)')
    : { matches: false };
  const numberAnimations = new WeakMap();

  function animateNumber(element, target, options = {}) {
    if (!element || !Number.isFinite(Number(target))) return;
    const finalValue = Math.round(Number(target));
    const previousFrame = numberAnimations.get(element);
    if (previousFrame) window.cancelAnimationFrame(previousFrame);

    const parsedCurrent = Number(String(element.textContent || '').replace(/[^0-9.-]/g, ''));
    const startValue = Number.isFinite(options.from) ? Number(options.from) : (Number.isFinite(parsedCurrent) ? parsedCurrent : 0);
    if (reduceMotion.matches || startValue === finalValue) {
      element.textContent = String(finalValue);
      numberAnimations.delete(element);
      return;
    }

    const duration = Math.max(180, Number(options.duration) || 360);
    const startedAt = performance.now();
    const tick = now => {
      const progress = Math.min(1, (now - startedAt) / duration);
      const eased = 1 - Math.pow(1 - progress, 4);
      element.textContent = String(Math.round(startValue + (finalValue - startValue) * eased));
      if (progress < 1) numberAnimations.set(element, window.requestAnimationFrame(tick));
      else numberAnimations.delete(element);
    };
    numberAnimations.set(element, window.requestAnimationFrame(tick));
  }

  window.PhishRadarMotion = { animateNumber, version: '2.0.0' };

  function bindCommandPalette() {
    const dialog = document.querySelector('#commandPalette');
    const input = document.querySelector('#commandSearch');
    const triggers = Array.from(document.querySelectorAll('[data-command-open]'));
    const options = Array.from(dialog?.querySelectorAll('[data-command]') || []);
    if (!dialog || !input || !triggers.length || !options.length) return;

    let activeOption = null;
    let returnFocus = null;
    let closeTimer = null;

    const normalized = value => String(value || '').normalize('NFKD').toLocaleLowerCase('th');
    const visibleOptions = () => options.filter(option => !option.hidden);

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

    function filterCommands() {
      const query = normalized(input.value.trim());
      options.forEach(option => {
        option.hidden = !!query && !normalized(`${option.textContent} ${option.dataset.keywords || ''}`).includes(query);
      });
      setActive(visibleOptions()[0] || null);
    }

    function closePalette(afterClose) {
      window.clearTimeout(closeTimer);
      if (!dialog.open) {
        afterClose?.();
        return;
      }
      const finish = () => {
        if (dialog.open) dialog.close();
        dialog.classList.remove('is-closing');
        afterClose?.();
        returnFocus?.focus?.({ preventScroll: true });
      };
      if (reduceMotion.matches) return finish();
      dialog.classList.add('is-closing');
      closeTimer = window.setTimeout(finish, 150);
    }

    function openPalette(trigger) {
      if (dialog.open) return;
      returnFocus = trigger || document.activeElement;
      input.value = '';
      options.forEach(option => { option.hidden = false; });
      dialog.classList.remove('is-closing');
      dialog.showModal();
      setActive(options[0]);
      window.requestAnimationFrame(() => input.focus({ preventScroll: true }));
    }

    function runCommand(option) {
      if (!option || option.hidden) return;
      const action = option.dataset.command;
      closePalette(() => {
        if (['scan', 'qr', 'dashboard'].includes(action)) {
          location.hash = `#${action}`;
          if (action === 'scan') window.setTimeout(() => document.querySelector('#urlInput')?.focus(), 0);
          return;
        }
        if (action === 'settings') location.assign('settings.html');
        if (action === 'theme') document.querySelector('[data-theme-toggle]')?.click();
        if (action === 'privacy') document.querySelector('#privacyMode')?.click();
        if (action === 'logout') document.querySelector('#logoutButton')?.click();
      });
    }

    triggers.forEach(trigger => trigger.addEventListener('click', () => openPalette(trigger)));
    dialog.querySelector('[data-command-close]')?.addEventListener('click', () => closePalette());
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
    input.addEventListener('input', filterCommands);
    input.addEventListener('keydown', event => {
      const available = visibleOptions();
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
        dialog.open ? closePalette() : openPalette(document.querySelector('[data-command-open]'));
      }
    });
  }

  function bindScanFeedback() {
    const message = document.querySelector('#formMessage');
    const panel = document.querySelector('.result-panel');
    const button = document.querySelector('#scanButton');
    const result = document.querySelector('#resultContent');
    if (!message || !panel || !button) return;

    let wasAnalyzing = false;
    const revealResult = () => {
      if (!result || result.hidden) return;
      result.classList.remove('is-revealed');
      void result.offsetWidth;
      result.classList.add('is-revealed');
    };
    const update = () => {
      const analyzing = /กำลังวิเคราะห์|กำลังรวมผล/.test(message.textContent || '');
      panel.classList.toggle('is-analyzing', analyzing);
      button.classList.toggle('is-loading', analyzing);
      if (wasAnalyzing && !analyzing) revealResult();
      wasAnalyzing = analyzing;
    };
    new MutationObserver(update).observe(message, { childList: true, characterData: true, subtree: true });
    update();

    if (result) {
      new MutationObserver(() => {
        if (result.hidden) return;
        revealResult();
      }).observe(result, { attributes: true, attributeFilter: ['hidden'] });
    }
  }

  function bindQrFeedback() {
    const viewport = document.querySelector('.qr-viewport');
    const video = document.querySelector('#qrVideo');
    if (!viewport || !video) return;
    const update = () => viewport.classList.toggle('is-scanning', !video.hidden);
    new MutationObserver(update).observe(video, { attributes: true, attributeFilter: ['hidden'] });
    update();
  }

  function bindPageTransitions() {
    window.addEventListener('hashchange', () => {
      window.requestAnimationFrame(() => {
        const page = document.querySelector('.page.active');
        if (!page) return;
        page.classList.remove('is-entering');
        void page.offsetWidth;
        page.classList.add('is-entering');
        if (page.id === 'dashboard') {
          page.querySelectorAll('.metrics strong').forEach(metric => {
            const value = Number(metric.textContent);
            if (Number.isFinite(value)) animateNumber(metric, value, { from: 0, duration: 380 });
          });
        }
      });
    });
  }

  [bindCommandPalette, bindScanFeedback, bindQrFeedback, bindPageTransitions].forEach(bind => {
    try { bind(); }
    catch (error) { console.warn(`Motion module ${bind.name} could not start`, error); }
  });
})();
