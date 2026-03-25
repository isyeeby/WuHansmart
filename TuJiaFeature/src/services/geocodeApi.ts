import { apiClient } from '../config/api';

export interface GeocodeHit {
  latitude: number;
  longitude: number;
  display_name: string;
}

export async function forwardGeocode(query: string): Promise<GeocodeHit[]> {
  const q = query.trim();
  if (q.length < 2) return [];
  const { data } = await apiClient.get<{ results: GeocodeHit[] }>('/api/geocode/forward', {
    params: { q, limit: 5 },
  });
  return data.results ?? [];
}
