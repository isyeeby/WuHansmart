import { lazy, type ComponentType, type LazyExoticComponent } from 'react';

const CHUNK_RELOAD_KEY = '__vite_chunk_reload_once';

function isChunkLoadError(e: unknown): boolean {
  if (!(e instanceof Error)) return false;
  const m = e.message.toLowerCase();
  return (
    m.includes('failed to fetch dynamically imported module') ||
    m.includes('importing a module script failed') ||
    m.includes('error loading dynamically imported module')
  );
}

/**
 * 与 `lazy()` 相同，但在「动态 chunk 拉取失败」时自动整页刷新一次。
 * 常见于：发版后用户仍持有旧版 index.html，引用的带 hash 的 js 已被删除。
 */
export function lazyWithRetry<T extends ComponentType<unknown>>(
  importFn: () => Promise<{ default: T }>
): LazyExoticComponent<T> {
  return lazy(async () => {
    try {
      return await importFn();
    } catch (err) {
      if (isChunkLoadError(err) && !sessionStorage.getItem(CHUNK_RELOAD_KEY)) {
        sessionStorage.setItem(CHUNK_RELOAD_KEY, '1');
        window.location.reload();
        return { default: (() => null) as unknown as T };
      }
      throw err;
    }
  });
}

/** 应用成功启动后调用，允许下次发版再次自动刷新 */
export function clearChunkReloadFlag(): void {
  try {
    sessionStorage.removeItem(CHUNK_RELOAD_KEY);
  } catch {
    /* private mode */
  }
}
