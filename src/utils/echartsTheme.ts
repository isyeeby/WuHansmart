/**
 * ECharts 主题配置 - 墨白禅意风格
 * 统一图表配色和样式，保持视觉一致性
 */

// 墨白主题色板
export const ZEN_COLORS = {
  // 主色调
  ochre: '#c45c3e',      // 赭石/朱砂
  jade: '#5a8a6e',       // 青玉
  gold: '#b8956e',       // 赤金

  // 辅助色
  inkBlack: '#1a1a1a',   // 墨色
  inkDark: '#2d2d2d',    // 深墨
  inkMedium: '#4a4a4a',  // 中墨
  inkLight: '#6b6b6b',   // 浅墨
  inkMuted: '#999999',   // 淡墨

  // 背景色
  paperWhite: '#faf8f5', // 宣纸白
  paperCream: '#f5f2ed', // 米白
  paperWarm: '#ebe7e0',  // 暖灰
  paperGray: '#d4d0c8',  // 灰白

  // 图表配色序列
  chartColors: ['#c45c3e', '#5a8a6e', '#b8956e', '#1a1a1a', '#6b6b6b', '#d4d0c8'],
};

// 通用图表配置
export const commonChartConfig = {
  // 背景色
  backgroundColor: 'transparent',

  // 文字样式
  textStyle: {
    fontFamily: "'Noto Sans SC', -apple-system, sans-serif",
    color: ZEN_COLORS.inkMedium,
  },

  // 标题样式
  title: {
    textStyle: {
      fontFamily: "'Noto Serif SC', serif",
      fontWeight: 600,
      color: ZEN_COLORS.inkBlack,
    },
    subtextStyle: {
      color: ZEN_COLORS.inkLight,
    },
  },

  // 图例样式
  legend: {
    textStyle: {
      color: ZEN_COLORS.inkLight,
    },
    bottom: 0,
    itemGap: 20,
  },

  // 提示框样式
  tooltip: {
    backgroundColor: ZEN_COLORS.paperWhite,
    borderColor: ZEN_COLORS.paperWarm,
    borderWidth: 1,
    textStyle: {
      color: ZEN_COLORS.inkBlack,
    },
    extraCssText: 'box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08); border-radius: 4px;',
  },

  // 坐标轴样式
  categoryAxis: {
    axisLine: {
      lineStyle: { color: ZEN_COLORS.paperWarm },
    },
    axisTick: { show: false },
    axisLabel: {
      color: ZEN_COLORS.inkLight,
      fontSize: 12,
    },
    splitLine: {
      lineStyle: { color: ZEN_COLORS.paperCream },
    },
  },

  valueAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: ZEN_COLORS.inkMuted,
    },
    splitLine: {
      lineStyle: { color: ZEN_COLORS.paperCream },
    },
    nameTextStyle: {
      color: ZEN_COLORS.inkMuted,
    },
  },

  // 网格配置
  grid: {
    left: '3%',
    right: '4%',
    bottom: '12%',
    top: '15%',
    containLabel: true,
  },
};

// 折线图配置
export const lineChartConfig = {
  smooth: true,
  symbol: 'circle',
  symbolSize: 8,
  lineStyle: {
    width: 2,
  },
  itemStyle: {
    borderWidth: 2,
    borderColor: '#fff',
  },
  emphasis: {
    scale: 1.5,
  },
};

// 面积图渐变
export const areaGradient = (color: string) => ({
  type: 'linear',
  x: 0,
  y: 0,
  x2: 0,
  y2: 1,
  colorStops: [
    { offset: 0, color: color.replace(')', ', 0.2)').replace('rgb', 'rgba') },
    { offset: 1, color: color.replace(')', ', 0)').replace('rgb', 'rgba') },
  ],
});

// 柱状图配置
export const barChartConfig = {
  barWidth: '60%',
  barGap: '20%',
  itemStyle: {
    borderRadius: [2, 2, 0, 0],
  },
  emphasis: {
    itemStyle: {
      shadowBlur: 10,
      shadowColor: 'rgba(0, 0, 0, 0.1)',
    },
  },
};

// 雷达图配置
export const radarChartConfig = {
  axisName: {
    color: ZEN_COLORS.inkMuted,
    fontSize: 12,
  },
  splitArea: {
    areaStyle: {
      color: [ZEN_COLORS.paperWhite, ZEN_COLORS.paperCream],
    },
  },
  axisLine: {
    lineStyle: { color: ZEN_COLORS.paperWarm },
  },
  splitLine: {
    lineStyle: { color: ZEN_COLORS.paperWarm },
  },
};

// 饼图配置
export const pieChartConfig = {
  radius: ['45%', '75%'],
  center: ['50%', '50%'],
  itemStyle: {
    borderRadius: 4,
    borderColor: ZEN_COLORS.paperWhite,
    borderWidth: 2,
  },
  label: {
    color: ZEN_COLORS.inkMedium,
  },
  emphasis: {
    itemStyle: {
      shadowBlur: 10,
      shadowOffsetX: 0,
      shadowColor: 'rgba(0, 0, 0, 0.1)',
    },
  },
};

// 散点图/热力图配置
export const scatterChartConfig = {
  symbolSize: 12,
  itemStyle: {
    opacity: 0.8,
  },
  emphasis: {
    itemStyle: {
      opacity: 1,
      borderColor: '#fff',
      borderWidth: 2,
    },
  },
};

// 词云配置
export const wordCloudConfig = {
  shape: 'circle',
  sizeRange: [12, 48],
  rotationRange: [-30, 30],
  rotationStep: 15,
  gridSize: 8,
  textStyle: {
    fontFamily: "'Noto Sans SC', sans-serif",
    fontWeight: 500,
  },
  emphasis: {
    focus: 'self',
    textStyle: {
      textShadowBlur: 10,
      textShadowColor: 'rgba(0, 0, 0, 0.2)',
    },
  },
};

// 创建标准折线图配置
export const createLineOption = (
  data: number[],
  xAxisData: string[],
  color: string = ZEN_COLORS.jade,
  name: string = ''
) => ({
  grid: commonChartConfig.grid,
  tooltip: {
    ...commonChartConfig.tooltip,
    trigger: 'axis',
  },
  xAxis: {
    type: 'category',
    data: xAxisData,
    ...commonChartConfig.categoryAxis,
  },
  yAxis: {
    type: 'value',
    ...commonChartConfig.valueAxis,
  },
  series: [
    {
      type: 'line',
      name,
      data,
      ...lineChartConfig,
      lineStyle: { color, width: 2 },
      itemStyle: { color, borderColor: '#fff', borderWidth: 2 },
      areaStyle: {
        color: areaGradient(color),
      },
    },
  ],
});

// 创建标准柱状图配置
export const createBarOption = (
  data: { name: string; value: number; itemStyle?: object }[],
  color?: string
) => ({
  grid: commonChartConfig.grid,
  tooltip: {
    ...commonChartConfig.tooltip,
    trigger: 'axis',
  },
  xAxis: {
    type: 'category',
    data: data.map((d) => d.name),
    ...commonChartConfig.categoryAxis,
  },
  yAxis: {
    type: 'value',
    ...commonChartConfig.valueAxis,
  },
  series: [
    {
      type: 'bar',
      data,
      ...barChartConfig,
      itemStyle: {
        ...barChartConfig.itemStyle,
        color: color || ZEN_COLORS.ochre,
      },
    },
  ],
});

// 创建标准雷达图配置
export const createRadarOption = (
  indicators: { name: string; max: number }[],
  data: { name: string; value: number[]; itemStyle?: object; areaStyle?: object }[]
) => ({
  radar: {
    indicator: indicators,
    ...radarChartConfig,
  },
  legend: commonChartConfig.legend,
  series: [
    {
      type: 'radar',
      data,
      symbol: 'circle',
      symbolSize: 6,
    },
  ],
});

// 创建标准饼图配置
export const createPieOption = (
  data: { name: string; value: number }[],
  colors: string[] = ZEN_COLORS.chartColors
) => ({
  color: colors,
  tooltip: {
    ...commonChartConfig.tooltip,
    trigger: 'item',
  },
  legend: {
    ...commonChartConfig.legend,
    bottom: 0,
  },
  series: [
    {
      type: 'pie',
      data,
      ...pieChartConfig,
      label: {
        show: true,
        formatter: '{b}\n{d}%',
        color: ZEN_COLORS.inkMedium,
      },
    },
  ],
});

export default {
  ZEN_COLORS,
  commonChartConfig,
  lineChartConfig,
  areaGradient,
  barChartConfig,
  radarChartConfig,
  pieChartConfig,
  scatterChartConfig,
  wordCloudConfig,
  createLineOption,
  createBarOption,
  createRadarOption,
  createPieOption,
};
