import { createApp, ref, onMounted, defineComponent, h } from 'vue'
import { getPlugin } from './plugins/registry.js'

const pluginComponents = {
  flirt: () => import('./plugins/flirt/FlirtPlugin.vue'),
  search: () => import('./plugins/search/SearchPlugin.vue'),
}

const PluginApp = defineComponent({
  setup() {
    const pluginId = ref(null)
    const pluginComponent = ref(null)
    const manifest = ref(null)

    onMounted(async () => {
      pluginId.value = await window.pluginAPI?.getPluginId()
        || new URLSearchParams(window.location.search).get('id')
      if (!pluginId.value) return

      manifest.value = getPlugin(pluginId.value)
      if (!manifest.value) return

      document.title = manifest.value.name

      const loader = pluginComponents[pluginId.value]
      if (loader) {
        const mod = await loader()
        pluginComponent.value = mod.default
      }
    })

    return () => {
      if (pluginComponent.value) {
        return h(pluginComponent.value, { manifest: manifest.value })
      }
      return h('div', { style: 'padding: 20px; color: #888;' }, 'Loading...')
    }
  }
})

createApp(PluginApp).mount('#plugin-app')
