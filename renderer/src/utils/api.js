/**
 * 统一 API 调用基地址管理
 *
 * 所有组件从此处导入 apiFetch，不再各自拼接 http://127.0.0.1:${port}
 *
 * 用法：
 *   import { apiFetch, apiUrl } from '@/utils/api'
 *   const res = await apiFetch('/api/chat', { method: 'POST', body: ... })
 */

let _baseUrl = null

export async function getApiBase () {
  if (_baseUrl) return _baseUrl
  const port = await window.electronAPI?.getPythonPort?.()
    || await window.pluginAPI?.getPythonPort?.()
    || 18765
  _baseUrl = `http://127.0.0.1:${port}`
  return _baseUrl
}

export async function apiFetch (path, options = {}) {
  const base = await getApiBase()
  return fetch(`${base}${path}`, options)
}

/**
 * 获取完整 API URL（用于非 fetch 场景，如 Audio src）
 */
export async function apiUrl (path) {
  const base = await getApiBase()
  return `${base}${path}`
}
