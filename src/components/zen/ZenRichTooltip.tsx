import { Tooltip, type TooltipProps } from 'antd';

/** 与 `zen-theme.css` 中 `.zen-tooltip-rich` 配套，用于长说明类 Tooltip */
export const ZEN_RICH_TOOLTIP_CLASS = 'zen-tooltip-rich';

export function ZenRichTooltip({
  rootClassName,
  mouseEnterDelay = 0.12,
  ...rest
}: TooltipProps) {
  const mergedRoot = [ZEN_RICH_TOOLTIP_CLASS, rootClassName].filter(Boolean).join(' ');
  return <Tooltip {...rest} rootClassName={mergedRoot} mouseEnterDelay={mouseEnterDelay} />;
}
