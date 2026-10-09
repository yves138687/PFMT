import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv, type Plugin, type UserConfig } from 'vite'

type ViteConfigWithTest = UserConfig & {
  test: {
    environment: string
    globals: boolean
    setupFiles: string
    css: boolean
  }
}

/**
 * A browser (or an automated scanner) can request Linux pseudo-files directly.
 * On Windows these paths do not exist, but allowing them to reach Vite's
 * transform middleware produces an ENOENT overlay instead of a normal 404.
 */
function blockLinuxPseudoFileRequests(): Plugin {
  return {
    name: 'pfmt:block-linux-pseudo-file-requests',
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const pathname = (request.url ?? '').split('?', 1)[0]
        if (!/^\/(?:proc|sys|dev)(?:\/|$)/i.test(pathname)) {
          next()
          return
        }
        response.statusCode = 404
        response.end('Not Found')
      })
    }
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const publicDevHost = env.VITE_PUBLIC_DEV_HOST?.trim()
  const disableHmr = ['1', 'true', 'yes', 'on'].includes((env.VITE_DISABLE_HMR ?? '').trim().toLowerCase())
  const allowedHosts = (env.VITE_ALLOWED_HOSTS ?? publicDevHost ?? '')
    .split(',')
    .map((host) => host.trim())
    .filter(Boolean)

  return {
    plugins: [blockLinuxPseudoFileRequests(), vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    server: {
      port: 5173,
      allowedHosts: allowedHosts.length > 0 ? allowedHosts : undefined,
      hmr: disableHmr
        ? false
        : publicDevHost
        ? {
            protocol: 'wss',
            host: publicDevHost,
            clientPort: 443
          }
        : undefined,
      proxy: {
        '/api': {
          target: env.VITE_DEV_API_TARGET ?? 'http://127.0.0.1:8000',
          changeOrigin: true
        }
      }
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: './tests/setup.ts',
      css: false
    }
  } as ViteConfigWithTest
})
