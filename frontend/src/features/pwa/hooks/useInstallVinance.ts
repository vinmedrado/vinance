import { useEffect, useState } from 'react';
import { isIosSafari, isStandalone } from '../services/pwa.service';

type InstallPromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }> };

export function useInstallVinance() {
  const [prompt, setPrompt] = useState<InstallPromptEvent | null>(null);
  const standalone = typeof window !== 'undefined' && isStandalone();
  const ios = typeof window !== 'undefined' && isIosSafari();

  useEffect(() => {
    const listener = (event: Event) => { event.preventDefault(); setPrompt(event as InstallPromptEvent); };
    window.addEventListener('beforeinstallprompt', listener);
    return () => window.removeEventListener('beforeinstallprompt', listener);
  }, []);

  async function install() {
    if (!prompt) return false;
    await prompt.prompt();
    const choice = await prompt.userChoice;
    if (choice.outcome === 'accepted') setPrompt(null);
    return choice.outcome === 'accepted';
  }

  return { canInstall: Boolean(prompt), standalone, ios, install };
}
