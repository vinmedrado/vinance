type Properties = Record<string, unknown>;

const enabled = import.meta.env.VITE_ANALYTICS_ENABLED === 'true';
const posthogKey = import.meta.env.VITE_POSTHOG_KEY || '';
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
    await fetch(`${import.meta.env.VITE_API_URL || '/api'}/analytics/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event, properties }),
    });
  } catch {
    // analytics nunca deve quebrar UX
  }
}
