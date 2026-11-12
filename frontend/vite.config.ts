import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'KOWALSKI_');
  const proxy = {
    '^/api/': {
      target: env.KOWALSKI_API_URL || 'http://127.0.0.1:5000',
      rewrite: (path: string) => path.replace(/^\/api/, ''),
    },
  };

  return {
    plugins: [react()],
    server: { host: '127.0.0.1', port: 3000, strictPort: true, proxy },
    preview: { host: '127.0.0.1', proxy },
  };
});
