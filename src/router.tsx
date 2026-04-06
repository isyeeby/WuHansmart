import { Suspense, type ReactNode } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { Spin } from 'antd';
import MainLayout from './layout/MainLayout';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import RouteErrorFallback from './components/RouteErrorFallback';
import { lazyWithRetry } from './utils/lazyWithRetry';

const PageFallback = () => (
  <div className="flex items-center justify-center min-h-[40vh]">
    <Spin size="large" tip="加载页面..." />
  </div>
);

const Login = lazyWithRetry(() => import('./pages/Login'));
const Home = lazyWithRetry(() => import('./pages/Home'));
const Dashboard = lazyWithRetry(() => import('./pages/Dashboard'));
const Prediction = lazyWithRetry(() => import('./pages/Prediction'));
const Recommendation = lazyWithRetry(() => import('./pages/Recommendation'));
const Competitor = lazyWithRetry(() => import('./pages/Competitor'));
const Favorites = lazyWithRetry(() => import('./pages/Favorites'));
const ListingDetail = lazyWithRetry(() => import('./pages/ListingDetail'));
const Listings = lazyWithRetry(() => import('./pages/Listings'));
const MyListings = lazyWithRetry(() => import('./pages/MyListings'));
const Investment = lazyWithRetry(() => import('./pages/Investment'));
const Comparison = lazyWithRetry(() => import('./pages/Comparison'));
const Opportunities = lazyWithRetry(() => import('./pages/Opportunities'));
const Profile = lazyWithRetry(() => import('./pages/Profile'));

const withSuspense = (node: ReactNode) => <Suspense fallback={<PageFallback />}>{node}</Suspense>;

export const router = createBrowserRouter([
  {
    errorElement: <RouteErrorFallback />,
    children: [
      {
        path: '/login',
        element: (
          <AuthProvider>
            {withSuspense(<Login />)}
          </AuthProvider>
        ),
      },
      {
        path: '/',
        element: (
          <AuthProvider>
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          </AuthProvider>
        ),
        children: [
          {
            index: true,
            element: withSuspense(<Home />),
          },
          {
            path: 'dashboard',
            element: withSuspense(<Dashboard />),
          },
          {
            path: 'competitor',
            element: withSuspense(<Competitor />),
          },
          {
            path: 'analysis',
            element: <Navigate to="/dashboard?tab=districts" replace />,
          },
          {
            path: 'prediction',
            element: withSuspense(<Prediction />),
          },
          {
            path: 'recommendation',
            element: withSuspense(<Recommendation />),
          },
          {
            path: 'listings',
            element: withSuspense(<Listings />),
          },
          {
            path: 'listing/:id',
            element: withSuspense(<ListingDetail />),
          },
          {
            path: 'listing/:id/detail',
            element: withSuspense(<ListingDetail />),
          },
          {
            path: 'my-listings',
            element: withSuspense(<MyListings />),
          },
          {
            path: 'favorites',
            element: withSuspense(<Favorites />),
          },
          {
            path: 'investment',
            element: withSuspense(<Investment />),
          },
          {
            path: 'comparison',
            element: withSuspense(<Comparison />),
          },
          {
            path: 'opportunities',
            element: withSuspense(<Opportunities />),
          },
          {
            path: 'profile',
            element: withSuspense(<Profile />),
          },
        ],
      },
    ],
  },
]);
