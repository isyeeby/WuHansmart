import { Navigate } from 'react-router-dom';

/** 原「价格洼地」独立页已合并至「投资分析 → 价格洼地」标签，保留路由以兼容书签与外链 */
export default function OpportunitiesRedirect() {
  return <Navigate to="/investment?tab=opportunities" replace />;
}
