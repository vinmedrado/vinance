type Properties = Record<string, unknown>;

const enabled = import.meta.env.VITE_ANALYTICS_ENABLED === 'true';
// PostHog's browser project identifier is intentionally public and embedded in the bundle.
const posthogKey = import.meta.env.VITE_POSTHOG_PROJECT_ID || '';
const apiHost = import.meta.env.VITE_POSTHOG_HOST || 'https://app.posthog.com';

let posthogReady = false;

export async function initAnalytics() {
  if (!enabled || !posthogKey) return;
  try {
    const posthog = await import('posthog-js');
    posthog.default.init(posthogKey, { api_host: apiHost, capture_pageview: true, autocapture: false });
    posthogReady = true;
  } catch {
    posthogReady = false;
  }
}

export async function track(event: string, properties: Properties = {}) {
  if (!enabled) return;
  try {
    if (posthogReady) {
      const posthog = await import('posthog-js');
      posthog.default.capture(event, properties);
      return;
    }
    // Sem provider configurado, analytics permanece desativado. Não existe
    // fallback browser→backend paralelo ao contrato canônico /api/v1.
    return;
  } catch {
    // analytics nunca deve quebrar UX
  }
}
