import { useMemo } from 'react';
import { isRouteErrorResponse, useNavigate, useRouteError } from 'react-router-dom';
import { Button, Result } from 'antd';
import { ReloadOutlined, HomeOutlined } from '@ant-design/icons';

function messageFromError(err: unknown): { title: string; sub: string; isChunk: boolean } {
  if (isRouteErrorResponse(err)) {
    return {
      title: '请求异常',
      sub: `${err.status} ${err.statusText || ''}`.trim(),
      isChunk: false,
    };
  }
  if (err instanceof Error) {
    const m = err.message;
    const isChunk =
      m.includes('Failed to fetch dynamically imported module') ||
      m.includes('Importing a module script failed') ||
      m.includes('error loading dynamically imported module');
    if (isChunk) {
      return {
        title: '页面脚本加载失败',
        sub: '站点可能刚更新，浏览器仍在使用旧版资源。请点击下方刷新；若仍失败，请尝试强制刷新（清除缓存）或稍后再试。',
        isChunk: true,
      };
    }
    return {
      title: '页面出错了',
      sub: m || '发生未知错误',
      isChunk: false,
    };
  }
  return {
    title: '页面出错了',
    sub: '发生未知错误',
    isChunk: false,
  };
}

/**
 * React Router 6.4+ route.errorElement：动态导入失败等运行时错误时的墨白风兜底页
 */
export default function RouteErrorFallback() {
  const err = useRouteError();
  const navigate = useNavigate();
  const { title, sub, isChunk } = useMemo(() => messageFromError(err), [err]);

  const hardRefresh = () => {
    const url = new URL(window.location.href);
    url.searchParams.set('_v', String(Date.now()));
    window.location.replace(url.toString());
  };

  return (
    <div className="paper-texture flex min-h-[100dvh] min-h-screen items-center justify-center px-4 py-12">
      <Result
        className="max-w-lg rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-white)] px-4 py-8 shadow-[var(--shadow-medium)]"
        status="warning"
        title={<span className="font-serif text-lg text-[var(--ink-black)]">{title}</span>}
        subTitle={<span className="text-sm leading-relaxed text-[var(--ink-muted)]">{sub}</span>}
        extra={
          <div className="mt-2 flex flex-wrap justify-center gap-3">
            <Button
              type="primary"
              icon={<ReloadOutlined />}
              className="!border-none !bg-[var(--ink-black)] hover:!bg-[var(--ink-dark)]"
              onClick={() => window.location.reload()}
            >
              刷新页面
            </Button>
            {isChunk ? (
              <Button icon={<ReloadOutlined />} onClick={hardRefresh}>
                强制获取最新版
              </Button>
            ) : null}
            <Button type="default" icon={<HomeOutlined />} onClick={() => navigate('/', { replace: true })}>
              回首页
            </Button>
          </div>
        }
      />
    </div>
  );
}
