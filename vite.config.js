import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    {
      name: 'serve-wasm-onnx',
      configureServer(server) {
        // 直接拦截并 serve WASM/ONNX 文件，绕过 Vite 所有后续中间件
        // 避免 Vite 的 HTML fallback 或 asset transform 返回错误内容
        server.middlewares.use((req, res, next) => {
          const url = (req.url || '').split('?')[0]
          if (!url.endsWith('.wasm') && !url.endsWith('.onnx')) {
            return next()
          }
          const publicDir = path.resolve(__dirname, 'renderer/public')
          const filePath = path.join(publicDir, url)
          if (!fs.existsSync(filePath)) {
            return next()
          }
          const mime = url.endsWith('.wasm') ? 'application/wasm' : 'application/octet-stream'
          res.setHeader('Content-Type', mime)
          res.setHeader('Cross-Origin-Resource-Policy', 'cross-origin')
          fs.createReadStream(filePath).pipe(res)
        })
      }
    }
  ],
  root: path.resolve(__dirname, 'renderer'),
  base: './',
  publicDir: 'public',
  build: {
    outDir: path.resolve(__dirname, 'dist'),
    emptyOutDir: true,
    assetsDir: 'assets',
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'renderer/index.html'),
        plugin: path.resolve(__dirname, 'renderer/plugin.html')
      },
      external: []
    },
    commonjsOptions: {
      include: [/node_modules/]
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'renderer/src'),
      'vue': path.resolve(__dirname, 'node_modules/vue/dist/vue.esm-bundler.js')
    },
    dedupe: ['vue', 'pinia']
  },
  server: {
    port: 5173,
    strictPort: false,
    fs: {
      allow: ['..']
    },
    headers: {
      'Cross-Origin-Embedder-Policy': 'require-corp',
      'Cross-Origin-Opener-Policy': 'same-origin'
    },
    hmr: {
      overlay: false
    }
  },
  assetsInclude: [],
  optimizeDeps: {
    include: ['pinia', 'vue', '@vue/devtools-api', 'vue-demi'],
    exclude: ['onnxruntime-web']
  }
})
