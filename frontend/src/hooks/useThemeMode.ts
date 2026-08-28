import { useEffect, useState } from 'react';

export function useThemeMode() {
  const [mode, setMode] = useState<'dark' | 'light'>(() => (localStorage.getItem('vinance_theme') as 'dark' | 'light') || 'dark');

  useEffect(() => {
    document.documentElement.dataset.theme = mode;
    localStorage.setItem('vinance_theme', mode);
  }, [mode]);

  return { mode, setMode };
}
