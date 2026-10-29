/* Local presentation filter; it never changes Random Forest scores. */
(function () {
  'use strict';
  if (globalThis.__phishRadarAdFilterLoaded) return;
  globalThis.__phishRadarAdFilterLoaded = true;

  // Explicit ad markers and previously inspected banner-slot markup work on
  // any publisher; this is no longer a list of enabled website hostnames.
  const AD_SLOTS = 'ins.adsbygoogle,[data-ad-slot],[data-ad-unit],[data-ad-client],.advertisement,.ad-banner,.ad-container,.ad-slot,.ads-banner,.adsbox,[aria-label="Advertisement" i],[aria-label="โฆษณา"],.center_upmangaza,.center_upmanga,.center_upmangasolo,.center_finmangaza,.center_finmanga';
  const CLOSE_CONTROLS = 'button,[role="button"],.sticky-close,.close,.close-button,.popup-close,[aria-label*="close" i],[aria-label*="ปิด"]';
  const UI_GUARD = '[id^="phish-radar"],nav,header,[role="navigation"],[role="menu"],form,input,textarea,select,[contenteditable="true"]';
  const READING_CONTEXT = 'article,figure,[role="article"],.reading-content,.reader-area,#readerarea,.gallery,.book-card';
  const policy = globalThis.PhishRadarAdFilterPolicy;
  const hidden = new Map();
  const ownStyleWrites = new WeakMap();
  const imageLayout = new WeakMap();
  let items = new Map();
  let settings = { riskyAdProtection: true, adFilterAllowlist: [], adFilterMode: 'all' };
  let observer = null;
  let timer = null;
  const pendingRoots = new Set();
  let blockedClicks = 0;
  let blockedPopups = 0;

  function host(value) { return String(value || '').toLowerCase().replace(/\.$/, ''); }
  function httpUrl(value) {
    try {
      const url = new URL(value, location.href);
      if (!/^https?:$/.test(url.protocol)) return null;
      url.hash = '';
      return url;
    } catch (_) { return null; }
  }
  function enabled() {
    return /^https?:$/.test(location.protocol) && settings.riskyAdProtection !== false &&
      !globalThis.PhishRadarAppTrust?.isTrustedWebAppUrl(location.href) &&
      !(Array.isArray(settings.adFilterAllowlist) && settings.adFilterAllowlist.some(value => host(value) === host(location.hostname)));
  }
  function samePublisher(target) {
    return host(location.hostname).replace(/^www\./, '') === host(target.hostname).replace(/^www\./, '');
  }
  function protectedElement(element) {
    return !element || !!element.closest(UI_GUARD) || !!element.querySelector('form,input,textarea,select,[contenteditable="true"]');
  }

  function mediaDetails(media) {
    if (!media) return { width: 0, height: 0, creativeHint: false };
    const sources = ['src', 'data-src', 'data-lazy-src', 'data-original', 'data-wpfc-original-src'].map(name => media.getAttribute(name) || '').join(' ');
    const signature = sources + '|' + (media.getAttribute('width') || '') + '|' + (media.getAttribute('height') || '');
    const previous = imageLayout.get(media);
    const rect = media.getBoundingClientRect();
    let width = Number(media.getAttribute('width')) || media.naturalWidth || rect.width;
    let height = Number(media.getAttribute('height')) || media.naturalHeight || rect.height;
    // Dimension-named creative files are common even before lazy images load.
    const namedSize = sources.match(/(?:^|[^\d])(\d{2,4})x(\d{2,4})(?=[^\d]|$)/i);
    if (namedSize && (width <= 1 || height <= 1)) {
      width = Number(namedSize[1]); height = Number(namedSize[2]);
    }
    if ((width <= 1 || height <= 1) && previous?.signature === signature) {
      width = previous.width; height = previous.height;
    }
    if (width > 1 && height > 1) imageLayout.set(media, { signature, width, height });
    const creativeHint = !!namedSize || /(?:^|[\/_\-.])(?:ads?|banner|advert(?:isement)?|sponsor)(?=[\/_\-.\d]|$)/i.test(sources);
    return { width, height, creativeHint };
  }

  function isCloseControl(element) {
    const label = [element.getAttribute('aria-label'), element.title, element.textContent].filter(Boolean).join(' ').trim();
    return /(?:^|\s)(?:[×✕✖x]|close|dismiss)(?:$|\s)|ปิด|sticky-close|popup-close/i.test(label + ' ' + element.className);
  }

  function floatingImageSlot(anchor, dimensions) {
    if (dimensions.width < 80 || dimensions.height < 60 || dimensions.width > 900 || dimensions.height > 600) return null;
    for (let el = anchor.parentElement, depth = 0; el && el !== document.body && depth < 5; el = el.parentElement, depth++) {
      if (protectedElement(el) || el.closest(READING_CONTEXT)) return null;
      if (getComputedStyle(el).position !== 'fixed') continue;
      const controls = Array.from(el.querySelectorAll(CLOSE_CONTROLS));
      if (!controls.some(isCloseControl)) continue;
      const remainingText = (el.textContent || '').replace(/(?:close|dismiss|ปิดโฆษณา|ปิด|[×✕✖x])/gi, '').trim();
      const links = el.querySelectorAll('a[href]');
      if (remainingText.length <= 24 && links.length <= 3) return el;
    }
    return null;
  }

  function presentation(anchor, media) {
    const explicit = anchor.closest(AD_SLOTS);
    if (explicit && !protectedElement(explicit)) return { slot: explicit, identifiedAd: true };
    if (!media || media.tagName !== 'IMG' || anchor.closest(READING_CONTEXT)) return null;
    // A content image, social icon or a fixed-position link alone is not an ad.
    if ((anchor.textContent || '').trim() || anchor.querySelectorAll('img').length !== 1) return null;
    const dimensions = mediaDetails(media);
    const rel = new Set((anchor.getAttribute('rel') || '').toLowerCase().split(/\s+/));
    const floating = floatingImageSlot(anchor, dimensions);
    if (floating && (dimensions.creativeHint || rel.has('sponsored') || rel.has('nofollow'))) {
      return { slot: floating, identifiedAd: true };
    }
    const wide = dimensions.width >= 300 && dimensions.height >= 50 && dimensions.height <= 400 && dimensions.width / dimensions.height >= 2.5;
    if (wide && dimensions.creativeHint && (rel.has('nofollow') || rel.has('sponsored'))) {
      return { slot: null, identifiedAd: true };
    }
    return null;
  }
  function inspect(anchor) {
    if (protectedElement(anchor)) return null;
    const target = httpUrl(anchor.getAttribute('href'));
    if (!target || samePublisher(target)) return null;
    if (globalThis.PhishRadarAppTrust?.isTrustedWebAppUrl(target.href) ||
      ['accounts.google.com', 'login.microsoftonline.com', 'login.live.com', 'appleid.apple.com'].includes(host(target.hostname))) return null;
    const media = anchor.querySelector('img,video,iframe');
    const displayed = presentation(anchor, media);
    if (!displayed) return null;
    const adSlot = displayed.slot;
    const result = policy?.classifyCandidate({
      pageUrl: location.href, targetUrl: target.href,
      text: (adSlot || anchor).textContent.slice(0, 2000),
      label: [anchor.title, anchor.getAttribute('aria-label'), media?.getAttribute('alt'), media?.getAttribute('title')].filter(Boolean).join(' '),
      attributes: [anchor.getAttribute('data-ad-label'), media?.getAttribute('data-ad-label')].filter(Boolean).join(' '),
      adLike: true, identifiedAd: displayed.identifiedAd,
      mode: settings.adFilterMode === 'risky' ? 'risky' : 'all',
      overlay: false, media: !!media, hasForm: false
    });
    return result?.hide ? { url: target.href, reasons: result.reasons, slot: adSlot } : null;
  }

  function inspectFrame(frame) {
    if (protectedElement(frame)) return null;
    const slot = frame.closest(AD_SLOTS);
    if (!slot || protectedElement(slot)) return null;
    const target = httpUrl(frame.getAttribute('src'));
    if (!target || samePublisher(target) || globalThis.PhishRadarAppTrust?.isTrustedWebAppUrl(target.href) ||
      ['accounts.google.com', 'login.microsoftonline.com', 'login.live.com', 'appleid.apple.com'].includes(host(target.hostname))) return null;
    const result = policy?.classifyCandidate({ pageUrl: location.href, targetUrl: target.href,
      text: slot.textContent.slice(0, 2000), label: frame.title, media: true, adLike: true,
      identifiedAd: true, mode: settings.adFilterMode === 'risky' ? 'risky' : 'all' });
    return result?.hide ? { url: target.href, reasons: result.reasons, slot } : null;
  }
  function hide(element) {
    if (!hidden.has(element)) hidden.set(element, {
      display: element.style.getPropertyValue('display'),
      priority: element.style.getPropertyPriority('display')
    });
    if (element.style.getPropertyValue('display') !== 'none' || element.style.getPropertyPriority('display') !== 'important') {
      element.style.setProperty('display', 'none', 'important');
      ownStyleWrites.set(element, element.getAttribute('style'));
    }
  }
  function restore(element, previous) {
    // A site may change display immediately before the filter is switched off,
    // before MutationObserver has delivered that change. Keep the new value.
    if (element.style.getPropertyValue('display') !== 'none' || element.style.getPropertyPriority('display') !== 'important') {
      previous = { display: element.style.getPropertyValue('display'), priority: element.style.getPropertyPriority('display') };
    }
    if (previous.display) element.style.setProperty('display', previous.display, previous.priority);
    else element.style.removeProperty('display');
    hidden.delete(element);
    ownStyleWrites.set(element, element.getAttribute('style'));
  }
  function restoreAll() {
    for (const [element, previous] of hidden) restore(element, previous);
    items.clear();
  }
  function entirelyFilteredSlot(slot, next) {
    const links = Array.from(slot.querySelectorAll('a[href],iframe[src]')).filter(a => a.tagName === 'IFRAME' ||
      (a.getAttribute('href')?.trim() && a.getAttribute('href') !== '#'));
    return links.length > 0 && links.every(a => next.has(a));
  }
  function emptyFloatingAdWrapper(element, next) {
    if (protectedElement(element) || element.closest(READING_CONTEXT) ||
      getComputedStyle(element).position !== 'fixed' || !entirelyFilteredSlot(element, next)) return false;
    const controls = Array.from(element.querySelectorAll(CLOSE_CONTROLS));
    if (!controls.some(isCloseControl)) return false;
    const remainingText = (element.textContent || '').replace(/(?:close|dismiss|ปิดโฆษณา|ปิด|[×✕✖x])/gi, '').trim();
    if (remainingText.length > 0) return false;
    // A nested fixed wrapper can contain a second close icon. Collapse it only
    // when every image and interactive element belongs to a filtered ad or a
    // real close control; unrelated content in a shared wrapper stays visible.
    return Array.from(element.querySelectorAll('a,button,[role="button"],img,video,iframe')).every(child => {
      if (next.has(child) || next.has(child.closest('a[href]'))) return true;
      const control = child.matches(CLOSE_CONTROLS) ? child : child.closest(CLOSE_CONTROLS);
      return !!control && isCloseControl(control);
    });
  }
  function scan(changedRoots = null) {
    if (!enabled()) { restoreAll(); return; }
    const next = changedRoots ? new Map(items) : new Map();
    for (const element of next.keys()) {
      if (!element.isConnected || !element.matches('a[href],iframe[src]')) next.delete(element);
    }
    const desired = new Set();
    // Initial/settings scans cover the full page. Subsequent DOM mutations
    // inspect only changed subtrees; no first-5000 cutoff or animation rescan.
    const candidates = new Set();
    for (const root of changedRoots || [document.documentElement]) {
      if (!root?.isConnected) continue;
      if (root.matches?.('a[href],iframe[src]')) candidates.add(root);
      const link = root.closest?.('a[href]');
      if (link) candidates.add(link);
      for (const element of root.querySelectorAll?.('a[href],iframe[src]') || []) candidates.add(element);
    }
    const anchors = Array.from(candidates).filter(element => element.tagName === 'A');
    for (let index = 0; index < anchors.length; index++) {
      const anchor = anchors[index];
      const decision = inspect(anchor);
      if (decision) next.set(anchor, decision); else next.delete(anchor);
    }
    for (const frame of candidates) {
      if (frame.tagName !== 'IFRAME') continue;
      if (frame.closest('a[href]')) { next.delete(frame); continue; }
      const decision = inspectFrame(frame);
      if (decision) next.set(frame, decision); else next.delete(frame);
    }
    for (const element of next.keys()) desired.add(element);
    const slots = new Set(Array.from(next.values()).map(item => item.slot).filter(Boolean));
    for (const slot of slots) {
      if (protectedElement(slot)) continue;
      // Preserve mixed slots, including a publisher's own reading banner.
      if (entirelyFilteredSlot(slot, next)) desired.add(slot);
      for (let parent = slot.parentElement, depth = 0; parent && parent !== document.body && depth < 5; parent = parent.parentElement, depth++) {
        if (emptyFloatingAdWrapper(parent, next)) desired.add(parent);
      }
    }
    for (const [element, previous] of hidden) if (!desired.has(element)) restore(element, previous);
    for (const element of desired) hide(element);
    items = next;
  }
  function schedule() {
    if (timer !== null) return;
    timer = setTimeout(() => {
      timer = null;
      const roots = new Set(pendingRoots);
      pendingRoots.clear();
      scan(roots);
    }, 120);
  }
  function queueRoot(element) {
    if (!element?.querySelectorAll || element.closest('[id^="phish-radar"]')) return;
    const slot = element.closest(AD_SLOTS);
    pendingRoots.add(slot || element);
    schedule();
  }
  function syncSettings(value) {
    settings = { ...settings, ...(value || {}) };
    if (!enabled()) {
      if (timer !== null) { clearTimeout(timer); timer = null; }
      pendingRoots.clear();
      observer?.disconnect();
      restoreAll();
      return;
    }
    observer?.disconnect();
    observer = new MutationObserver(mutations => {
      for (const mutation of mutations) {
        const element = mutation.target.nodeType === 1 ? mutation.target : mutation.target.parentElement;
        if (!element || element.closest('[id^="phish-radar"]')) continue;
        if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
          if (ownStyleWrites.get(element) === element.getAttribute('style')) continue;
          const previous = hidden.get(element);
          if (previous && (element.style.getPropertyValue('display') !== 'none' || element.style.getPropertyPriority('display') !== 'important')) {
            previous.display = element.style.getPropertyValue('display');
            previous.priority = element.style.getPropertyPriority('display');
          }
          if (element === document.body || element === document.documentElement) continue;
        }
        for (let ancestor = element; ancestor; ancestor = ancestor.parentElement) {
          if (hidden.has(ancestor)) { queueRoot(ancestor); break; }
        }
        const nodes = mutation.type === 'childList'
          ? [...mutation.addedNodes, ...mutation.removedNodes] : [element];
        for (const node of nodes) {
          if (node.nodeType !== 1 || node.closest?.('[id^="phish-radar"]')) continue;
          if (node.matches?.('a[href],img,iframe,' + AD_SLOTS) || node.querySelector?.('a[href],img,iframe,' + AD_SLOTS)) queueRoot(node);
          // A close button may arrive after the image. Inspect its surrounding
          // floating box rather than waiting for another media mutation.
          if (node.matches?.(CLOSE_CONTROLS) || node.querySelector?.(CLOSE_CONTROLS)) queueRoot(node.parentElement);
        }
        if (element.closest('a[href],iframe,' + AD_SLOTS)) queueRoot(element);
        // Removing a candidate or changing a close control's marker also needs
        // cleanup, including for boxes whose selector no longer matches.
        if (mutation.type === 'childList' && Array.from(mutation.removedNodes).some(node =>
          node.nodeType === 1 && !node.closest?.('[id^="phish-radar"]'))) queueRoot(element);
        if (mutation.type === 'attributes' && element.parentElement?.querySelector('img') &&
          !element.matches('img,a,iframe')) queueRoot(element.parentElement);
      }
    });
    observer.observe(document.documentElement, { childList: true, subtree: true, attributes: true,
      attributeFilter: ['href', 'src', 'alt', 'title', 'class', 'id', 'style', 'data-ad-slot', 'data-ad-unit', 'data-ad-client', 'data-ad-label', 'aria-label', 'role', 'contenteditable',
        'rel', 'width', 'height', 'data-src', 'data-lazy-src', 'data-original', 'data-wpfc-original-src'] });
    scan();
  }
  function targetDecision(value) {
    const target = httpUrl(value);
    if (!enabled() || !target) return { blocked: false, pageUrl: location.href };
    scan();
    const item = Array.from(items.values()).find(item => item.url === target.href);
    return { blocked: !!item, reasons: item?.reasons || [], pageUrl: location.href };
  }
  function stats() {
    return { hiddenCount: items.size, blockedClicks, blockedPopups, enabled: enabled(),
      mode: settings.adFilterMode === 'risky' ? 'risky' : 'all',
      siteExempt: Array.isArray(settings.adFilterAllowlist) && settings.adFilterAllowlist.some(value => host(value) === host(location.hostname)) };
  }
  function preventAdClick(event) {
    if (!enabled()) return;
    const element = event.target instanceof Element ? event.target : event.target?.parentElement;
    const anchor = element?.closest('a[href]');
    if (!anchor) return;
    const decision = inspect(anchor);
    if (!decision) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    blockedClicks++;
    queueRoot(anchor);
  }
  document.addEventListener('click', preventAdClick, true);
  document.addEventListener('auxclick', preventAdClick, true);
  document.addEventListener('load', event => {
    if (event.target?.matches?.('img,iframe') && enabled()) queueRoot(event.target);
  }, true);

  const ready = (async () => {
    try { settings = { ...settings, ...await chrome.storage.sync.get(settings) }; } catch (_) {}
    if (!document.documentElement) await new Promise(resolve => document.addEventListener('DOMContentLoaded', resolve, { once: true }));
    syncSettings(settings);
  })();
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'sync') return;
    const changed = {};
    for (const key of ['riskyAdProtection', 'adFilterAllowlist', 'adFilterMode']) if (changes[key]) changed[key] = changes[key].newValue;
    if (Object.keys(changed).length) void ready.then(() => syncSettings(changed));
  });
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!['GET_AD_FILTER_STATS', 'CHECK_AD_FILTER_TARGET', 'AD_FILTER_POPUP_BLOCKED', 'SETTINGS_UPDATED'].includes(message?.type)) return;
    void ready.then(() => {
      if (message.type === 'SETTINGS_UPDATED') syncSettings(message.settings);
      if (message.type === 'AD_FILTER_POPUP_BLOCKED' && targetDecision(message.targetUrl).blocked) blockedPopups++;
      sendResponse(message.type === 'CHECK_AD_FILTER_TARGET'
        ? { ok: true, ...targetDecision(message.targetUrl) }
        : { ok: true, stats: stats() });
    }).catch(() => sendResponse({ ok: false }));
    return true;
  });
})();
