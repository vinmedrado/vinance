import { api } from '../../../services/api';

export type NotificationPreferences = {
  push_enabled: boolean;
  account_events_enabled: boolean;
  household_invites_enabled: boolean;
  financial_alerts_enabled: boolean;
  analysis_updates_enabled: boolean;
};

const INSTALLATION_KEY = 'vinance:pwa-installation-id';

function installationId() {
  const existing = localStorage.getItem(INSTALLATION_KEY);
  if (existing) return existing;
  const created = crypto.randomUUID();
  localStorage.setItem(INSTALLATION_KEY, created);
  return created;
}

function urlBase64ToUint8Array(value: string) {
  const padding = '='.repeat((4 - value.length % 4) % 4);
  const base64 = (value + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((character) => character.charCodeAt(0)));
}

export async function getNotificationCapabilities() {
  const { data } = await api.get<{ web_push_enabled: boolean; vapid_public_key: string | null }>('/notifications/capabilities');
  return data;
}

export async function getNotificationPreferences() {
  const { data } = await api.get<NotificationPreferences>('/notifications/preferences');
  return data;
}

export async function saveNotificationPreferences(payload: Partial<NotificationPreferences>) {
  const { data } = await api.patch<NotificationPreferences>('/notifications/preferences', payload);
  return data;
}

export async function enablePushForCurrentInstallation() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
    throw new Error('Este navegador não oferece notificações Web Push.');
  }
  const capabilities = await getNotificationCapabilities();
  if (!capabilities.web_push_enabled || !capabilities.vapid_public_key) {
    throw new Error('As notificações ainda não estão configuradas no servidor.');
  }
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new Error('A permissão de notificações não foi concedida.');
  const registration = await navigator.serviceWorker.getRegistration();
  if (!registration?.active) {
    throw new Error('O serviço de notificações ainda não está ativo. Recarregue o Vinance e tente novamente.');
  }
  const previous = await registration.pushManager.getSubscription();
  const subscription = previous ?? await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(capabilities.vapid_public_key),
  });
  await api.post('/notifications/subscriptions', {
    installation_id: installationId(),
    subscription: subscription.toJSON(),
  });
  return saveNotificationPreferences({ push_enabled: true });
}

export async function disablePushForCurrentInstallation() {
  const id = localStorage.getItem(INSTALLATION_KEY);
  if (id) await api.delete(`/notifications/subscriptions/${encodeURIComponent(id)}`);
  if ('serviceWorker' in navigator) {
    const registration = await navigator.serviceWorker.getRegistration().catch(() => undefined);
    const subscription = await registration?.pushManager.getSubscription();
    await subscription?.unsubscribe().catch(() => false);
  }
  return getNotificationPreferences();
}

export async function isPushEnabledForCurrentInstallation() {
  if (!localStorage.getItem(INSTALLATION_KEY) || !('serviceWorker' in navigator)) return false;
  const registration = await navigator.serviceWorker.getRegistration().catch(() => undefined);
  const subscription = await registration?.pushManager.getSubscription();
  return Boolean(subscription);
}

export async function detachPushBeforeLogout() {
  const id = localStorage.getItem(INSTALLATION_KEY);
  if (id) await api.delete(`/notifications/subscriptions/${encodeURIComponent(id)}`).catch(() => undefined);
  if ('serviceWorker' in navigator) {
    const registration = await navigator.serviceWorker.getRegistration().catch(() => undefined);
    const subscription = await registration?.pushManager.getSubscription();
    await subscription?.unsubscribe().catch(() => false);
  }
  return id;
}

export function forgetPushInstallation() {
  localStorage.removeItem(INSTALLATION_KEY);
}

export async function sendTestNotification() {
  const { data } = await api.post<{ status: string; message: string; queued: number }>('/notifications/test');
  return data;
}
