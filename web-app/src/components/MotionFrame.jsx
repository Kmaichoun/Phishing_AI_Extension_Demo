import { useRef } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';

gsap.registerPlugin(useGSAP);

export function MotionFrame({ children, className = '' }) {
  const root = useRef(null);

  useGSAP(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const targets = root.current.querySelectorAll('[data-reveal]');
    gsap.fromTo(
      targets,
      { opacity: 0, y: 22, filter: 'blur(8px)' },
      {
        opacity: 1,
        y: 0,
        filter: 'blur(0px)',
        duration: 0.75,
        stagger: 0.07,
        ease: 'power3.out',
        clearProps: 'transform,filter'
      }
    );
  }, { scope: root });

  return <div ref={root} className={className}>{children}</div>;
}

export function MotionPreloader() {
  const root = useRef(null);

  useGSAP(() => {
    const node = root.current;
    if (!node || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const timeline = gsap.timeline();
    timeline
      .set(node, { visibility: 'visible', clipPath: 'inset(0% 0 0% 0)' })
      .fromTo(
        node.querySelector('.motion-loader-wordmark'),
        { opacity: 0, letterSpacing: '0.34em' },
        { opacity: 1, letterSpacing: '0.2em', duration: 0.35, ease: 'power2.out' }
      )
      .to(node, {
        clipPath: 'inset(0% 0 100% 0)',
        duration: 0.7,
        delay: 0.08,
        ease: 'power4.inOut'
      })
      .set(node, { visibility: 'hidden' });
  }, { scope: root });

  return (
    <div ref={root} className="motion-preloader" aria-hidden="true" style={{ visibility: 'hidden' }}>
      <span className="motion-loader-wordmark">PHISH RADAR AI</span>
    </div>
  );
}
