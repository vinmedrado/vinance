import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryProvider } from './providers/QueryProvider';
import { AppRoutes } from '../routes/AppRoutes';
import '../styles/global.css';
import '../styles/product.css';
import '../styles/financial-context.css';
import '../styles/access-pwa.css';
import { registerVinanceServiceWorker } from '../features/pwa/services/pwa.service';

registerVinanceServiceWorker();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryProvider>
  </React.StrictMode>,
);
