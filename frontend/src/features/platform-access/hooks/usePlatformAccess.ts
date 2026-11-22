import { useEffect, useState } from 'react';
import { getPlatformAccessProfile } from '../services/access.service';

export function usePlatformAccessProfile() {
  const [isPlatformAdmin, setIsPlatformAdmin] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getPlatformAccessProfile()
      .then((profile) => { if (active) setIsPlatformAdmin(profile.is_platform_admin); })
      .catch(() => { if (active) setIsPlatformAdmin(false); })
      .finally(() => { if (active) setIsLoading(false); });
    return () => { active = false; };
  }, []);

  return { isPlatformAdmin, isLoading };
}
