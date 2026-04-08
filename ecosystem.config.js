module.exports = {
  apps: [{
    name: 'pdf-migration-web',
    script: 'server.js',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '500M',
    env: {
      NODE_ENV: 'production',
      PORT: 3008,
      UPLOAD_MAX_SIZE_MB: 50,
      PYTHON_PATH: 'python',
      SCRIPT_TIMEOUT_MS: 60000,
    },
  }],
};
