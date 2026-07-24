(() => {
  'use strict';

  const reducedMotion = typeof window.matchMedia === 'function'
    ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
    : false;
  const finePointer = typeof window.matchMedia === 'function'
    ? window.matchMedia('(pointer: fine)').matches
    : false;

  window.PhishRadarAwwwardsMotion = {
    version: '2.0.0',
    reference: 'editorial-preloader-scroll-reveal',
  };

  if (reducedMotion) {
    document.documentElement.dataset.motion = 'reduced';
    return;
  }

  const gsap = window.gsap;
  const ScrollTrigger = window.ScrollTrigger;
  if (!gsap || !ScrollTrigger) {
    document.documentElement.dataset.motion = 'fallback';
    return;
  }

  gsap.registerPlugin(ScrollTrigger);
  gsap.config({ nullTargetWarn: false });
  document.documentElement.dataset.motion = 'enhanced';

  function animateScannerPage() {
    const preloader = document.querySelector('[data-motion-preloader]');
    const loaderWordmark = preloader?.querySelector('.motion-loader-wordmark');
    const titleLines = gsap.utils.toArray('.app-hero-title .hero-title-line');
    const timeline = gsap.timeline({
      defaults: { duration: 0.76, ease: 'power4.out' },
    });

    if (preloader && loaderWordmark) {
      document.body.classList.add('motion-loading');
      preloader.classList.add('is-active');
      gsap.set(preloader, { autoAlpha: 1, clipPath: 'inset(0% 0 0% 0)' });
      timeline
        .fromTo(loaderWordmark, {
          scale: 0.9,
          autoAlpha: 0,
          letterSpacing: '0.02em',
        }, {
          scale: 1,
          autoAlpha: 1,
          letterSpacing: '-0.045em',
          duration: 0.52,
          ease: 'power3.out',
        })
        .to(loaderWordmark, {
          scale: 0.94,
          autoAlpha: 0,
          duration: 0.34,
          ease: 'power2.in',
        }, '+=0.58')
        .to(preloader, {
          clipPath: 'inset(0% 0 100% 0)',
          duration: 0.72,
          ease: 'power4.inOut',
          onComplete: () => {
            preloader.classList.remove('is-active');
            preloader.style.display = 'none';
            document.body.classList.remove('motion-loading');
            ScrollTrigger.refresh();
          },
        }, '-=0.08')
        .addLabel('heroReveal', '-=0.56');
    } else {
      timeline.addLabel('heroReveal', 0);
    }

    timeline
      .fromTo('.topbar', {
        y: -22,
        autoAlpha: 0,
      }, {
        y: 0,
        autoAlpha: 1,
        duration: 0.58,
      }, 'heroReveal')
      .fromTo('.hero-radar-core', {
        scale: 0.74,
        rotation: -8,
        autoAlpha: 0,
      }, {
        scale: 1,
        rotation: 0,
        autoAlpha: 1,
        duration: 0.86,
      }, 'heroReveal+=0.08')
      .fromTo('.hero-context', {
        y: 18,
        autoAlpha: 0,
      }, {
        y: 0,
        autoAlpha: 1,
      }, 'heroReveal+=0.16')
      .fromTo(titleLines, {
        yPercent: 108,
        autoAlpha: 0,
      }, {
        yPercent: 0,
        autoAlpha: 1,
        stagger: 0.09,
        duration: 0.88,
      }, 'heroReveal+=0.18')
      .fromTo('.hero-lede', {
        y: 24,
        autoAlpha: 0,
      }, {
        y: 0,
        autoAlpha: 1,
      }, 'heroReveal+=0.38')
      .fromTo('.hero-actions > *', {
        y: 18,
        autoAlpha: 0,
      }, {
        y: 0,
        autoAlpha: 1,
        stagger: 0.08,
        duration: 0.6,
      }, 'heroReveal+=0.48')
      .fromTo('.hero-scan-form', {
        y: 22,
        autoAlpha: 0,
      }, {
        y: 0,
        autoAlpha: 1,
        duration: 0.66,
      }, 'heroReveal+=0.56');

    gsap.to('.hero-radar-core img', {
      y: -7,
      rotation: 0.7,
      duration: 2.8,
      repeat: -1,
      yoyo: true,
      ease: 'sine.inOut',
    });

    gsap.timeline({
      scrollTrigger: {
        trigger: '.app-hero',
        start: 'top top',
        end: 'bottom 34%',
        scrub: 1,
      },
    })
      .to('.hero-radar', { y: -74, scale: 0.82, autoAlpha: 0.08, ease: 'none' }, 0)
      .to('.hero-context', { y: -58, autoAlpha: 0, ease: 'none' }, 0)
      .to('.app-hero-title', { y: -108, scale: 0.93, autoAlpha: 0.12, ease: 'none' }, 0)
      .to('.hero-lede', { y: -78, autoAlpha: 0, ease: 'none' }, 0)
      .to('.hero-actions, .hero-scan-form', { y: -62, autoAlpha: 0, ease: 'none' }, 0);

    gsap.fromTo('.scanner-workbench', {
      y: 104,
      scale: 0.94,
      autoAlpha: 0.15,
    }, {
      y: 0,
      scale: 1,
      autoAlpha: 1,
      ease: 'none',
      scrollTrigger: {
        trigger: '.scanner-workbench',
        start: 'top 94%',
        end: 'top 58%',
        scrub: 0.85,
      },
    });

    gsap.utils.toArray('.scanner-workbench .output-heading, .scanner-workbench .preview, .scanner-workbench .empty').forEach(element => {
      gsap.fromTo(element, {
        y: 48,
        scale: 0.97,
        autoAlpha: 0.12,
      }, {
        y: 0,
        scale: 1,
        autoAlpha: 1,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: element,
          start: 'top 92%',
          end: 'top 70%',
          scrub: 0.65,
          once: true,
        },
      });
    });

    gsap.from('.capability-marquee', {
      y: 42,
      autoAlpha: 0,
      duration: 0.82,
      ease: 'power3.out',
      scrollTrigger: {
        trigger: '.capability-marquee',
        start: 'top 90%',
        once: true,
      },
    });
  }

  function animateAuthPage() {
    const timeline = gsap.timeline({
      defaults: { duration: 0.72, ease: 'power4.out' },
    });

    timeline
      .from('.auth-header', { y: -20, autoAlpha: 0, duration: 0.56 })
      .from('.auth-intro > *', {
        y: 28,
        autoAlpha: 0,
        stagger: 0.08,
      }, '-=0.34')
      .from('.auth-radar-visual', {
        scale: 0.86,
        rotation: -5,
        autoAlpha: 0,
        duration: 0.86,
      }, '-=0.58')
      .from('.auth-panel', {
        y: 38,
        scale: 0.985,
        autoAlpha: 0,
        duration: 0.86,
      }, '-=0.68')
      .from('.auth-footer', { y: 12, autoAlpha: 0, duration: 0.48 }, '-=0.4');
  }

  function animateSettingsPage() {
    const timeline = gsap.timeline({
      defaults: { duration: 0.72, ease: 'power4.out' },
    });

    timeline
      .from('.settings-topbar', { y: -20, autoAlpha: 0, duration: 0.56 })
      .from('.settings-heading > *', {
        y: 24,
        autoAlpha: 0,
        stagger: 0.08,
      }, '-=0.32')
      .from('.identity-strip', {
        y: 30,
        scale: 0.985,
        autoAlpha: 0,
      }, '-=0.48')
      .from('.settings-panel', {
        y: 36,
        scale: 0.98,
        autoAlpha: 0,
        stagger: 0.1,
      }, '-=0.5')
      .from('.security-note', { y: 24, autoAlpha: 0 }, '-=0.46');
  }

  function animateActiveToolPage() {
    const page = document.querySelector('.page.active');
    if (!page || page.id === 'scan') return;

    const cards = page.id === 'dashboard'
      ? page.querySelectorAll('.dash-grid > .panel')
      : page.querySelectorAll('.panel');

    gsap.fromTo(cards, {
      y: 36,
      scale: 0.982,
      autoAlpha: 0,
    }, {
      y: 0,
      scale: 1,
      autoAlpha: 1,
      duration: 0.72,
      stagger: 0.08,
      ease: 'power3.out',
      clearProps: 'transform,opacity,visibility',
    });
  }

  function bindPrimaryMagnetism() {
    if (!finePointer) return;
    document.querySelectorAll('.hero-primary, .submit-button').forEach(button => {
      button.addEventListener('pointermove', event => {
        const rect = button.getBoundingClientRect();
        const x = ((event.clientX - rect.left) / rect.width - 0.5) * 6;
        const y = ((event.clientY - rect.top) / rect.height - 0.5) * 4;
        gsap.to(button, { x, y, duration: 0.22, ease: 'power2.out', overwrite: true });
      });
      button.addEventListener('pointerleave', () => {
        gsap.to(button, { x: 0, y: 0, duration: 0.42, ease: 'elastic.out(1, 0.45)', overwrite: true });
      });
    });
  }

  function start() {
    if (document.querySelector('.auth-layout')) animateAuthPage();
    else if (document.body.classList.contains('settings-page')) animateSettingsPage();
    else animateScannerPage();

    bindPrimaryMagnetism();
    window.addEventListener('hashchange', () => {
      window.requestAnimationFrame(() => {
        animateActiveToolPage();
        ScrollTrigger.refresh();
      });
    });
    window.addEventListener('load', () => ScrollTrigger.refresh(), { once: true });
  }

  function startWhenReady() {
    if (!document.body.classList.contains('auth-pending')) {
      window.requestAnimationFrame(start);
      return;
    }

    let started = false;
    const observer = new MutationObserver(() => {
      if (started || document.body.classList.contains('auth-pending')) return;
      started = true;
      observer.disconnect();
      window.requestAnimationFrame(start);
    });
    observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    window.setTimeout(() => {
      if (started || !document.body.isConnected) return;
      started = true;
      observer.disconnect();
      window.requestAnimationFrame(start);
    }, 2600);
  }

  startWhenReady();
})();
