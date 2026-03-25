/**
 * 短 TTL 内存缓存 + 进行中去重，减少多页面重复请求同一接口。
 */
type CacheEntry = { value: unknown; expiresAt: number };

const memory = new Map<string, CacheEntry>();
const inflight = new Map<string, Promise<unknown>>();

export function cachedRequest<T>(key: string, ttlMs: number, fetcher: () => Promise<T>): Promise<T> {
  const now = Date.now();
  const hit = memory.get(key);
  if (hit && hit.expiresAt > now) {
    return Promise.resolve(hit.value as T);
  }

  const pending = inflight.get(key);
  if (pending) {
    return pending as Promise<T>;
  }

  const promise = (async () => {
    try {
      const value = await fetcher();
      memory.set(key, { value, expiresAt: Date.now() + ttlMs });
      return value as T;
    } finally {
      inflight.delete(key);
    }
  })();

  inflight.set(key, promise);
  return promise;
}
