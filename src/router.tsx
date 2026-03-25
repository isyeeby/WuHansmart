import { lazy, Suspense, type ReactNode } from 'react';
import { createBrowserRouter } from 'react-router-dom';
import { Spin } from 'antd';
import MainLayout from './layout/MainLayout';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';

const PageFallback = () => (
  <div className="flex items-center justify-center min-h-[40vh]">
    <Spin size="large" tip="加载页面..." />
  </div>
);

const Login = lazy(() => import('./pages/Login'));
const Home = lazy(() => import('./pages/Home'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Analysis = lazy(() => import('./pages/Analysis'));
const Prediction = lazy(() => import('./pages/Prediction'));
const Recommendation = lazy(() => import('./pages/Recommendation'));
const Competitor = lazy(() => import('./pages/Competitor'));
const Favorites = lazy(() => import('./pages/Favorites'));
const ListingDetail = lazy(() => import('./pages/ListingDetail'));
const Listings = lazy(() => import('./pages/Listings'));
const MyListings = lazy(() => import('./pages/MyListings'));
const ApiTest = lazy(() => import('./pages/ApiTest'));
const Investment = lazy(() => import('./pages/Investment'));
const Comparison = lazy(() => import('./pages/Comparison'));
const Opportunities = lazy(() => import('./pages/Opportunities'));
const Profile = lazy(() => import('./pages/Profile'));

const withSuspense = (node: ReactNode) => <Suspense fallback={<PageFallback />}>{node}</Suspense>;

export const router = createBrowserRouter([
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
        element: withSuspense(<Analysis />),
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
        path: 'api-test',
        element: withSuspense(<ApiTest />),
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
]);
