import type { Page, Route } from '@playwright/test';

export type FixtureUser = {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
};

type BrowserSessionOptions = {
  token: string;
  user: FixtureUser;
  active?: boolean;
  headers?: Record<string, string>;
  maxSuccessfulRefreshes?: number;
};

export type BrowserSessionController = {
  activate: (token: string, user: FixtureUser) => void;
  deactivate: () => void;
  token: () => string;
  user: () => FixtureUser;
};

function json(route: Route, body: unknown, status: number, headers: Record<string, string>) {
  if (route.request().method() === 'OPTIONS') {
    return route.fulfill({ status: 204, headers });
  }
  return route.fulfill({
    status,
    headers,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

/**
 * Models the production browser contract: access tokens live only in memory and
 * a page load restores an active server-side session through the refresh cookie.
 */
export async function mockBrowserSession(
  page: Page,
  options: BrowserSessionOptions,
): Promise<BrowserSessionController> {
  let active = options.active ?? true;
  let currentToken = options.token;
  let currentUser = options.user;
  let successfulRefreshes = 0;
  const headers = options.headers ?? {};

  const controller: BrowserSessionController = {
    activate(token, user) {
      currentToken = token;
      currentUser = user;
      active = true;
    },
    deactivate() {
      active = false;
    },
    token: () => currentToken,
    user: () => currentUser,
  };

  await page.route('**/api/v1/refresh', (route) => (
    active && (options.maxSuccessfulRefreshes === undefined || successfulRefreshes++ < options.maxSuccessfulRefreshes)
      ? json(route, { access_token: currentToken, token_type: 'bearer', user: currentUser }, 200, headers)
      : json(route, { detail: 'Invalid session' }, 401, headers)
  ));
  await page.route('**/api/v1/logout', async (route) => {
    controller.deactivate();
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
    return route.fulfill({ status: 204, headers });
  });

  return controller;
}
