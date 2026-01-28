module.exports = {
  apps: [
    {
      name: 'backend',
      cwd: '/app/holdem/backend',
      script: './venv/bin/python',
      args: '-m uvicorn app.main:app --host 0.0.0.0 --port 8000',
      autorestart: true,
      max_memory_restart: '512M',
    },
    {
      name: 'admin-backend',
      cwd: '/app/holdem/admin-backend',
      script: './venv/bin/python',
      args: '-m uvicorn app.main:app --host 0.0.0.0 --port 8001',
      autorestart: true,
      max_memory_restart: '256M',
    },
    {
      name: 'frontend',
      cwd: '/app/holdem/frontend/.next/standalone',
      script: 'server.js',
      env: {
        NODE_ENV: 'production',
        PORT: 3000,
        HOSTNAME: '0.0.0.0',
      },
      autorestart: true,
      max_memory_restart: '256M',
    },
    {
      name: 'admin-frontend',
      cwd: '/app/holdem/admin-frontend/.next/standalone',
      script: 'server.js',
      env: {
        NODE_ENV: 'production',
        PORT: 3001,
        HOSTNAME: '0.0.0.0',
      },
      autorestart: true,
      max_memory_restart: '256M',
    },
  ],
};
