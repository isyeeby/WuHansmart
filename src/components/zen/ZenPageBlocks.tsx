import React from 'react';
import { Card, Typography } from 'antd';

const { Text } = Typography;

export type ZenAccent = 'ochre' | 'jade' | 'gold' | 'ink';

export const ACCENT_BAR: Record<ZenAccent, string> = {
  ochre: 'bg-[var(--ochre)]',
  jade: 'bg-[var(--jade)]',
  gold: 'bg-[var(--gold)]',
  ink: 'bg-[var(--ink-black)]',
};

export const ZenPanel: React.FC<{
  accent: ZenAccent;
  title: React.ReactNode;
  extra?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  titleCaps?: boolean;
  loading?: boolean;
}> = ({ accent, title, extra, children, className = '', titleCaps = true, loading }) => (
  <Card
    bordered={false}
    loading={loading}
    className={`zen-panel h-full !rounded-xl !border !border-[var(--paper-warm)] !shadow-[var(--shadow-soft)] transition-[box-shadow] duration-300 hover:!shadow-[var(--shadow-medium)] ${className}`}
    title={
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className={`h-4 w-1 shrink-0 rounded-full ${ACCENT_BAR[accent]}`} aria-hidden />
          <Text
            className={`text-xs font-medium text-[var(--ink-muted)] ${titleCaps ? 'uppercase tracking-[0.15em]' : 'tracking-normal'}`}
          >
            {title}
          </Text>
        </div>
        {extra}
      </div>
    }
    styles={{ body: { padding: 'var(--space-md) var(--space-lg)' } }}
  >
    {children}
  </Card>
);

export const ZenSection: React.FC<{ title: string; accent: ZenAccent; children: React.ReactNode }> = ({
  title,
  accent,
  children,
}) => (
  <section className="zen-page-section space-y-5">
    <div className="flex items-center gap-3">
      <span className={`block h-0.5 w-9 rounded-full ${ACCENT_BAR[accent]}`} aria-hidden />
      <h2
        className="m-0 text-base font-semibold tracking-tight text-[var(--ink-black)] sm:text-lg"
        style={{ fontFamily: 'var(--font-serif)' }}
      >
        {title}
      </h2>
    </div>
    {children}
  </section>
);
