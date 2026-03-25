import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Spin } from 'antd';
import App from './App.tsx';
import { ZenSpinIndicator } from './components/zen/ZenSpinIndicator';
import './index.css';
import './styles/zen-theme.css';

Spin.setDefaultIndicator(<ZenSpinIndicator />);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
