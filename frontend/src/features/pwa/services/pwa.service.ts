const UPDATE_EVENT = 'vinance:pwa-update';

export function registerVinanceServiceWorker() {
  if (!('serviceWorker' in navigator) || import.meta.env.DEV) return;
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).then((registration) => {
      if (registration.waiting) window.dispatchEvent(new CustomEvent(UPDATE_EVENT, { detail: registration }));
      registration.addEventListener('updatefound', () => {
        const worker = registration.installing;
        worker?.addEventListener('statechange', () => {
          if (worker.state === 'installed' && navigator.serviceWorker.controller) {
            window.dispatchEvent(new CustomEvent(UPDATE_EVENT, { detail: registration }));
          }
        });
      });
    }).catch(() => undefined);
  }, { once: true });
}

export function subscribeToPwaUpdate(handler: (registration: ServiceWorkerRegistration) => void) {
  const listener = (event: Event) => handler((event as CustomEvent<ServiceWorkerRegistration>).detail);
  window.addEventListener(UPDATE_EVENT, listener);
  return () => window.removeEventListener(UPDATE_EVENT, listener);
}

export function activateWaitingServiceWorker(registration: ServiceWorkerRegistration) {
  navigator.serviceWorker.addEventListener('controllerchange', () => window.location.reload(), { once: true });
  registration.waiting?.postMessage({ type: 'SKIP_WAITING' });
}

export function isStandalone() {
  return window.matchMedia('(display-mode: standalone)').matches
    || Boolean((navigator as Navigator & { standalone?: boolean }).standalone);
}

export function isIosSafari() {
  const ua = navigator.userAgent;
  return /iPad|iPhone|iPod/.test(ua) && /Safari/.test(ua) && !/CriOS|FxiOS/.test(ua);
}
