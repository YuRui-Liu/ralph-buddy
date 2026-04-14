import flirtManifest from './flirt/manifest.json'
import searchManifest from './search/manifest.json'

const plugins = [flirtManifest, searchManifest]

export function getPlugins() {
  return plugins
}

export function getPlugin(id) {
  return plugins.find(p => p.id === id) || null
}
