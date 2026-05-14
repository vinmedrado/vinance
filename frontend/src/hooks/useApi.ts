import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';

export function useApi<T>(key: string[], url: string) {
  return useQuery({
    queryKey: key,
    queryFn: async (): Promise<T> => (await api.get(url)).data,
    retry: 1,
  });
}
