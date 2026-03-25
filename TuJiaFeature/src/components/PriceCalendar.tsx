import React, { useState, useMemo, useEffect } from 'react';
import { Modal, Spin, Badge, Tooltip } from 'antd';
import { LeftOutlined, RightOutlined, CalendarOutlined } from '@ant-design/icons';
import type { PriceCalendarResponse, PriceCalendarItem } from '../services/listingsApi';

interface PriceCalendarProps {
  visible: boolean;
  onClose: () => void;
  data: PriceCalendarResponse | null;
  loading: boolean;
}

// 获取月份天数
const getDaysInMonth = (year: number, month: number) => {
  return new Date(year, month + 1, 0).getDate();
};

// 获取月份第一天是星期几
const getFirstDayOfMonth = (year: number, month: number) => {
  return new Date(year, month, 1).getDay();
};

// 格式化日期
const formatDate = (dateStr: string) => {
  const date = new Date(dateStr);
  return {
    year: date.getFullYear(),
    month: date.getMonth(),
    day: date.getDate(),
    dateStr,
  };
};

// 获取价格颜色（根据价格相对于平均值的比例）
const getPriceColor = (price: number, avg: number) => {
  const ratio = price / avg;
  if (ratio < 0.8) return '#5a8a6e'; // 绿色 - 低价
  if (ratio > 1.2) return '#c45c3e'; // 红色 - 高价
  return '#1a1a1a'; // 黑色 - 正常价
};

export const PriceCalendar: React.FC<PriceCalendarProps> = ({
  visible,
  onClose,
  data,
  loading,
}) => {
  const [currentMonth, setCurrentMonth] = useState(new Date().getMonth());
  const [currentYear, setCurrentYear] = useState(new Date().getFullYear());

  // 有数据时默认跳到接口返回区间的起始月，避免历史价落在「上个月」却默认显示当月空白
  useEffect(() => {
    if (!visible || !data?.date_range?.start) return;
    const d = new Date(data.date_range.start + 'T12:00:00');
    if (!Number.isNaN(d.getTime())) {
      setCurrentYear(d.getFullYear());
      setCurrentMonth(d.getMonth());
    }
  }, [visible, data?.date_range?.start]);

  // 将日历数据转换为Map，方便查询
  const calendarMap = useMemo(() => {
    const map = new Map<string, PriceCalendarItem>();
    data?.calendar.forEach((item) => {
      map.set(item.date, item);
    });
    return map;
  }, [data]);

  // 月份名称
  const monthNames = [
    '一月', '二月', '三月', '四月', '五月', '六月',
    '七月', '八月', '九月', '十月', '十一月', '十二月'
  ];

  // 星期标题
  const weekDays = ['日', '一', '二', '三', '四', '五', '六'];

  // 切换到上一个月
  const prevMonth = () => {
    if (currentMonth === 0) {
      setCurrentMonth(11);
      setCurrentYear(currentYear - 1);
    } else {
      setCurrentMonth(currentMonth - 1);
    }
  };

  // 切换到下一个月
  const nextMonth = () => {
    if (currentMonth === 11) {
      setCurrentMonth(0);
      setCurrentYear(currentYear + 1);
    } else {
      setCurrentMonth(currentMonth + 1);
    }
  };

  // 生成日历网格
  const generateCalendarDays = () => {
    const daysInMonth = getDaysInMonth(currentYear, currentMonth);
    const firstDay = getFirstDayOfMonth(currentYear, currentMonth);
    const days = [];

    // 填充空白（上个月）
    for (let i = 0; i < firstDay; i++) {
      days.push(<div key={`empty-${i}`} className="h-20" />);
    }

    // 填充日期
    for (let day = 1; day <= daysInMonth; day++) {
      const dateStr = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const dayData = calendarMap.get(dateStr);

      days.push(
        <div
          key={day}
          className={`h-20 border border-[#f5f2ed] p-2 flex flex-col justify-between ${
            dayData?.can_booking === false ? 'bg-[#faf9f8]' : 'bg-white'
          }`}
        >
          <div className="flex justify-between items-start">
            <span className={`text-sm ${
              new Date().toDateString() === new Date(dateStr).toDateString()
                ? 'w-6 h-6 rounded-full bg-[#c45c3e] text-white flex items-center justify-center'
                : 'text-[#6b6b6b]'
            }`}>
              {day}
            </span>
            {dayData?.can_booking === false && (
              <span className="text-xs text-[#999]">满房</span>
            )}
          </div>
          {dayData && (
            <Tooltip title={dayData.can_booking ? '可预订' : '已满房'}>
              <div className="text-right">
                <span
                  className="text-sm font-medium"
                  style={{ color: getPriceColor(dayData.price, data?.price_stats.avg || dayData.price) }}
                >
                  ¥{Math.round(dayData.price)}
                </span>
              </div>
            </Tooltip>
          )}
        </div>
      );
    }

    return days;
  };

  return (
    <Modal
      open={visible}
      onCancel={onClose}
      footer={null}
      width={720}
      className="!rounded-sm"
      title={
        <div className="flex items-center justify-between pr-8">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-[#f5f2ed] flex items-center justify-center">
              <CalendarOutlined className="text-[#b8956e]" />
            </div>
            <div>
              <div className="font-serif text-lg font-semibold text-[#1a1a1a]">价格日历</div>
              <div className="text-xs text-[#999]">{data?.title}</div>
            </div>
          </div>
          {data?.price_stats && (
            <div className="flex items-center gap-4 text-xs">
              <span className="text-[#6b6b6b]">
                最低 <span className="text-[#5a8a6e] font-medium">¥{Math.round(data.price_stats.min)}</span>
              </span>
              <span className="text-[#6b6b6b]">
                平均 <span className="text-[#1a1a1a] font-medium">¥{Math.round(data.price_stats.avg)}</span>
              </span>
              <span className="text-[#6b6b6b]">
                最高 <span className="text-[#c45c3e] font-medium">¥{Math.round(data.price_stats.max)}</span>
              </span>
            </div>
          )}
        </div>
      }
    >
      <Spin spinning={loading}>
        <div className="py-4">
          {/* 月份导航 */}
          <div className="flex items-center justify-between mb-4 px-2">
            <button
              onClick={prevMonth}
              className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-[#f5f2ed] transition-colors"
            >
              <LeftOutlined className="text-[#6b6b6b]" />
            </button>
            <span className="text-lg font-medium text-[#1a1a1a]">
              {currentYear}年 {monthNames[currentMonth]}
            </span>
            <button
              onClick={nextMonth}
              className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-[#f5f2ed] transition-colors"
            >
              <RightOutlined className="text-[#6b6b6b]" />
            </button>
          </div>

          {/* 星期标题 */}
          <div className="grid grid-cols-7 gap-0 border-b border-[#ebe7e0] pb-2 mb-2">
            {weekDays.map((day) => (
              <div key={day} className="text-center text-sm text-[#999] py-2">
                {day}
              </div>
            ))}
          </div>

          {/* 日历网格 */}
          <div className="grid grid-cols-7 gap-0">
            {generateCalendarDays()}
          </div>

          {/* 图例 */}
          <div className="flex items-center justify-center gap-6 mt-4 pt-4 border-t border-[#f5f2ed]">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-[#5a8a6e]" />
              <span className="text-xs text-[#6b6b6b]">低价</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-[#1a1a1a]" />
              <span className="text-xs text-[#6b6b6b]">正常</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-[#c45c3e]" />
              <span className="text-xs text-[#6b6b6b]">高价</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-[#ebe7e0]" />
              <span className="text-xs text-[#6b6b6b]">满房</span>
            </div>
          </div>
        </div>
      </Spin>
    </Modal>
  );
};
