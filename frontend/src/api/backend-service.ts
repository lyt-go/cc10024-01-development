import { request } from './client'
import { moduleMeta } from '@/data/modules'
import type { ActionResult, EntryRow, OverviewResult, PageResult, RehearsalView } from '@/data/types'

export { moduleMeta }

export async function listEntries(
  key: string,
  filters: Record<string, string> = {},
): Promise<PageResult> {
  const query = new URLSearchParams(filters).toString()
  const response = await request(`/api/${key}?${query}`)
  if (!response.ok) throw new Error('业务数据读取失败')
  return await response.json()
}

export async function createEntry(
  key: string,
  values: Record<string, string>,
): Promise<ActionResult> {
  const response = await request(`/api/${key}`, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  return await response.json()
}

export async function runAction(
  key: string,
  id: number,
  action: string,
): Promise<ActionResult> {
  const response = await request(`/api/${key}/${id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  })
  return await response.json()
}

export async function downloadEntries(
  key: string,
  filters: Record<string, string> = {},
): Promise<void> {
  const query = new URLSearchParams(filters).toString()
  const response = await request(`/api/${key}/export?${query}`)
  if (!response.ok) throw new Error('业务数据导出失败')
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${key}.csv`
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export async function loadOverview(): Promise<OverviewResult> {
  const response = await request('/api/overview')
  if (!response.ok) throw new Error('运营概览读取失败')
  return await response.json()
}

/* ---------- 抽取锚点绑定预演 ---------- */

export async function loadRehearsal(template: string): Promise<RehearsalView> {
  const response = await request(`/api/rehearsal/${encodeURIComponent(template)}`)
  if (!response.ok) throw new Error('预演视图读取失败')
  return await response.json()
}

export async function runRehearsal(template: string, version: string): Promise<ActionResult> {
  const response = await request(`/api/rehearsal/${encodeURIComponent(template)}/run`, {
    method: 'POST',
    body: JSON.stringify({ 页面版本: version }),
  })
  return await response.json()
}

export async function confirmRehearsal(
  template: string,
  version: string,
  anchor: string,
): Promise<ActionResult> {
  const response = await request(`/api/rehearsal/${encodeURIComponent(template)}/confirm`, {
    method: 'POST',
    body: JSON.stringify({ 页面版本: version, 锚点编号: anchor }),
  })
  return await response.json()
}

export async function registerRehearsalPage(
  template: string,
  version: string,
  dom: string,
): Promise<ActionResult> {
  const response = await request('/api/rehearsal/pages', {
    method: 'POST',
    body: JSON.stringify({ 模板编号: template, 页面版本: version, dom }),
  })
  return await response.json()
}

export async function loadRehearsalSampleDom(): Promise<{ 页面版本: string; dom: string }> {
  const response = await request('/api/rehearsal/sample-dom')
  if (!response.ok) throw new Error('示例页面读取失败')
  return await response.json()
}
