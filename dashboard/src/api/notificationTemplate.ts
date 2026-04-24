/**
 * Notification Template API composable.
 *
 * Wraps every backend endpoint from NotificationTemplateRoute and exposes
 * typed helpers that the view layer can call directly.
 */

import axios from 'axios'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface NotificationTemplate {
  id: number
  name: string
  body: string
  created_at: number
  updated_at: number
}

export interface PreviewResult {
  template_id: number
  rendered: string
  placeholders: string[]
  missing: string[]
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

const BASE = '/api/notification_template'

/** Fetch all templates (ordered by created_at ASC). */
export async function fetchTemplates(): Promise<NotificationTemplate[]> {
  const res = await axios.get(`${BASE}/list`)
  if (res.data.status !== 'ok') throw new Error(res.data.message || '获取模板列表失败')
  return res.data.data.templates as NotificationTemplate[]
}

/** Create a new template. */
export async function createTemplate(name: string, body: string): Promise<NotificationTemplate> {
  const res = await axios.post(`${BASE}/create`, { name, body })
  if (res.data.status !== 'ok') throw new Error(res.data.message || '创建模板失败')
  return res.data.data as NotificationTemplate
}

/** Update an existing template (name and/or body). */
export async function updateTemplate(
  id: number,
  name?: string,
  body?: string
): Promise<NotificationTemplate> {
  const res = await axios.post(`${BASE}/update`, { id, name, body })
  if (res.data.status !== 'ok') throw new Error(res.data.message || '更新模板失败')
  return res.data.data as NotificationTemplate
}

/** Delete a template by ID. */
export async function deleteTemplate(id: number): Promise<void> {
  const res = await axios.post(`${BASE}/delete`, { id })
  if (res.data.status !== 'ok') throw new Error(res.data.message || '删除模板失败')
}

/** Render a template with the given variable values. */
export async function previewTemplate(
  id: number,
  variables: Record<string, string>
): Promise<PreviewResult> {
  const res = await axios.post(`${BASE}/preview`, { id, variables })
  if (res.data.status !== 'ok') throw new Error(res.data.message || '预览模板失败')
  return res.data.data as PreviewResult
}

/** Extract placeholder names from a stored template. */
export async function fetchPlaceholders(id: number): Promise<string[]> {
  const res = await axios.get(`${BASE}/placeholders`, { params: { id } })
  if (res.data.status !== 'ok') throw new Error(res.data.message || '获取占位符失败')
  return res.data.data.placeholders as string[]
}
