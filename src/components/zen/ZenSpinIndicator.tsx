import React from 'react';

/**
 * 与 antd Spin 配合的自定义指示器（cloneElement 会并入 ant-spin-dot 等 class/style）。
 * 尺寸随 Spin 的 sm / default / lg 通过 1em 随父级字号缩放。
 */
export const ZenSpinIndicator: React.FC<React.HTMLAttributes<HTMLSpanElement>> = ({ className, style, ...rest }) => (
  <span
    {...rest}
    className={['zen-spin-indicator', className].filter(Boolean).join(' ')}
    style={{ ...style, display: 'inline-flex', verticalAlign: 'middle' }}
    aria-hidden
  >
    <span className="zen-spin-indicator__orbit" />
    <span className="zen-spin-indicator__core" />
  </span>
);
