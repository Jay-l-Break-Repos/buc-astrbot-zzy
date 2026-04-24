<template>
  <div class="dashboard-page notification-template-page" :class="{ 'is-dark': isDark }">
    <v-container fluid class="dashboard-shell pa-4 pa-md-6">

      <!-- ================================================================
           Page header
      ================================================================ -->
      <div class="dashboard-header">
        <div class="dashboard-header-main">
          <div class="dashboard-eyebrow">消息管理</div>
          <h1 class="dashboard-title">通知模板</h1>
          <p class="dashboard-subtitle">
            创建和管理带有 <code class="inline-code">{{ '{{ variable }}' }}</code> 占位符的可复用消息模板，
            在发送通知时动态填充变量值。
          </p>
        </div>
        <div class="dashboard-header-actions">
          <v-btn
            variant="text"
            color="primary"
            :loading="loading"
            prepend-icon="mdi-refresh"
            @click="loadTemplates"
          >
            刷新
          </v-btn>
          <v-btn
            variant="tonal"
            color="primary"
            prepend-icon="mdi-plus"
            @click="openCreate"
          >
            新建模板
          </v-btn>
        </div>
      </div>

      <!-- ================================================================
           Overview cards
      ================================================================ -->
      <div class="dashboard-overview-grid tpl-overview-grid">
        <section class="dashboard-card dashboard-overview-card">
          <div class="dashboard-card-icon">
            <v-icon size="18">mdi-file-document-multiple-outline</v-icon>
          </div>
          <div class="dashboard-card-label">模板总数</div>
          <div class="dashboard-card-value">{{ templates.length }}</div>
          <div class="dashboard-card-note">已保存的通知模板</div>
        </section>
        <section class="dashboard-card dashboard-overview-card">
          <div class="dashboard-card-icon">
            <v-icon size="18">mdi-code-braces</v-icon>
          </div>
          <div class="dashboard-card-label">含占位符的模板</div>
          <div class="dashboard-card-value">{{ templatesWithPlaceholders }}</div>
          <div class="dashboard-card-note">包含 {{ '{{ variable }}' }} 变量</div>
        </section>
      </div>

      <!-- ================================================================
           Template list
      ================================================================ -->
      <div class="dashboard-section-head">
        <div>
          <div class="dashboard-section-title">所有模板</div>
          <div class="dashboard-section-subtitle">点击模板卡片可查看详情、编辑或预览渲染结果</div>
        </div>
      </div>

      <!-- Loading state -->
      <div v-if="loading && !templates.length" class="state-panel">
        <v-progress-circular indeterminate size="22" width="2" color="primary" />
        <span>加载中...</span>
      </div>

      <!-- Empty state -->
      <div v-else-if="!templates.length" class="state-panel">
        <v-icon size="40" color="primary" class="mb-2">mdi-file-document-outline</v-icon>
        <span class="state-title">暂无模板</span>
        <span class="state-sub">点击「新建模板」创建第一个通知模板</span>
        <v-btn variant="tonal" color="primary" prepend-icon="mdi-plus" class="mt-4" @click="openCreate">
          新建模板
        </v-btn>
      </div>

      <!-- Template grid -->
      <div v-else class="tpl-grid">
        <div
          v-for="tpl in templates"
          :key="tpl.id"
          class="tpl-card dashboard-card"
          @click="openDetail(tpl)"
        >
          <!-- Card header -->
          <div class="tpl-card-header">
            <div class="tpl-card-icon">
              <v-icon size="16">mdi-file-document-outline</v-icon>
            </div>
            <div class="tpl-card-name">{{ tpl.name }}</div>
            <div class="tpl-card-actions" @click.stop>
              <v-btn
                icon
                size="x-small"
                variant="text"
                color="primary"
                title="编辑"
                @click="openEdit(tpl)"
              >
                <v-icon size="16">mdi-pencil-outline</v-icon>
              </v-btn>
              <v-btn
                icon
                size="x-small"
                variant="text"
                color="error"
                title="删除"
                @click="confirmDelete(tpl)"
              >
                <v-icon size="16">mdi-trash-can-outline</v-icon>
              </v-btn>
            </div>
          </div>

          <!-- Body preview -->
          <div class="tpl-card-body">{{ truncate(tpl.body, 120) }}</div>

          <!-- Placeholder chips -->
          <div v-if="getPlaceholders(tpl.body).length" class="tpl-card-chips">
            <v-chip
              v-for="ph in getPlaceholders(tpl.body)"
              :key="ph"
              size="x-small"
              color="primary"
              variant="tonal"
              label
            >
              {{ ph }}
            </v-chip>
          </div>
          <div v-else class="tpl-card-no-vars">无占位符</div>

          <!-- Footer timestamps -->
          <div class="tpl-card-footer">
            <span>创建于 {{ formatDate(tpl.created_at) }}</span>
            <span v-if="tpl.updated_at !== tpl.created_at">· 更新于 {{ formatDate(tpl.updated_at) }}</span>
          </div>
        </div>
      </div>

      <!-- ================================================================
           Snackbar
      ================================================================ -->
      <v-snackbar v-model="snackbar.show" :color="snackbar.color" timeout="2800">
        {{ snackbar.message }}
      </v-snackbar>

      <!-- ================================================================
           Create / Edit dialog
      ================================================================ -->
      <v-dialog v-model="formDialog" max-width="640" persistent>
        <v-card class="dashboard-dialog-card">
          <v-card-title class="text-h6 pt-5 px-5">
            {{ isEditing ? '编辑模板' : '新建通知模板' }}
          </v-card-title>
          <v-card-subtitle class="px-5 text-body-2 text-medium-emphasis">
            在模板正文中使用 <code class="inline-code">{{ '{{ variable_name }}' }}</code> 语法插入变量占位符
          </v-card-subtitle>

          <v-card-text class="px-5 pb-2">
            <div class="dashboard-form-grid dashboard-form-grid--single">

              <!-- Name field -->
              <v-text-field
                v-model="form.name"
                label="模板名称"
                placeholder="例如：welcome_message"
                variant="outlined"
                density="comfortable"
                :error-messages="formErrors.name"
                @input="formErrors.name = ''"
              />

              <!-- Body field -->
              <div>
                <v-textarea
                  v-model="form.body"
                  label="模板正文"
                  placeholder="例如：你好 {{ username }}，欢迎使用 {{ platform }}！"
                  variant="outlined"
                  density="comfortable"
                  rows="5"
                  auto-grow
                  :error-messages="formErrors.body"
                  @input="onBodyInput"
                />

                <!-- Live placeholder chips -->
                <div v-if="formPlaceholders.length" class="form-placeholder-row">
                  <span class="form-placeholder-label">检测到的变量：</span>
                  <v-chip
                    v-for="ph in formPlaceholders"
                    :key="ph"
                    size="x-small"
                    color="primary"
                    variant="tonal"
                    label
                  >
                    {{ ph }}
                  </v-chip>
                </div>

                <!-- Syntax error banner -->
                <v-alert
                  v-if="formSyntaxError"
                  type="error"
                  variant="tonal"
                  density="compact"
                  class="mt-2"
                  :text="formSyntaxError"
                />
              </div>
            </div>
          </v-card-text>

          <v-card-actions class="justify-end px-5 pb-5">
            <v-btn variant="text" @click="closeFormDialog">取消</v-btn>
            <v-btn
              variant="tonal"
              color="primary"
              :loading="formSaving"
              :disabled="!!formSyntaxError"
              @click="submitForm"
            >
              {{ isEditing ? '保存修改' : '创建模板' }}
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <!-- ================================================================
           Detail / Preview dialog
      ================================================================ -->
      <v-dialog v-model="detailDialog" max-width="700">
        <v-card v-if="detailTemplate" class="dashboard-dialog-card">
          <v-card-title class="text-h6 pt-5 px-5 d-flex align-center justify-space-between">
            <span>{{ detailTemplate.name }}</span>
            <div class="d-flex gap-2">
              <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-pencil-outline" @click="openEditFromDetail">
                编辑
              </v-btn>
              <v-btn size="small" variant="text" color="error" prepend-icon="mdi-trash-can-outline" @click="confirmDeleteFromDetail">
                删除
              </v-btn>
            </div>
          </v-card-title>

          <v-card-text class="px-5 pb-4">

            <!-- Template body (read-only) -->
            <div class="detail-section-label">模板正文</div>
            <div class="detail-body-box">{{ detailTemplate.body }}</div>

            <!-- Placeholder list -->
            <div class="detail-section-label mt-4">占位符变量</div>
            <div v-if="detailPlaceholders.length" class="detail-chips">
              <v-chip
                v-for="ph in detailPlaceholders"
                :key="ph"
                size="small"
                color="primary"
                variant="tonal"
                label
              >
                {{ ph }}
              </v-chip>
            </div>
            <div v-else class="detail-empty">此模板没有占位符变量</div>

            <v-divider class="my-4" />

            <!-- Preview section -->
            <div class="detail-section-label">预览渲染</div>
            <div class="detail-section-sub">为每个变量填入示例值，查看渲染后的效果</div>

            <!-- Variable input fields -->
            <div v-if="detailPlaceholders.length" class="preview-vars-grid">
              <v-text-field
                v-for="ph in detailPlaceholders"
                :key="ph"
                v-model="previewVars[ph]"
                :label="ph"
                :placeholder="`{{ ${ph} }} 的值`"
                variant="outlined"
                density="compact"
                hide-details
                class="preview-var-field"
              />
            </div>

            <!-- Render button -->
            <v-btn
              variant="tonal"
              color="primary"
              :loading="previewing"
              prepend-icon="mdi-eye-outline"
              class="mt-3"
              @click="runPreview"
            >
              渲染预览
            </v-btn>

            <!-- Preview result -->
            <div v-if="previewResult !== null" class="preview-result-wrap mt-3">
              <div class="preview-result-label">渲染结果</div>
              <div class="preview-result-box">{{ previewResult.rendered }}</div>

              <!-- Missing variables warning -->
              <v-alert
                v-if="previewResult.missing.length"
                type="warning"
                variant="tonal"
                density="compact"
                class="mt-2"
              >
                以下变量未提供值，在渲染结果中保持原样：
                <strong>{{ previewResult.missing.join('、') }}</strong>
              </v-alert>
            </div>

            <!-- Preview error -->
            <v-alert
              v-if="previewError"
              type="error"
              variant="tonal"
              density="compact"
              class="mt-3"
              :text="previewError"
            />

            <!-- Timestamps -->
            <div class="detail-timestamps mt-4">
              <span>创建于 {{ formatDate(detailTemplate.created_at) }}</span>
              <span v-if="detailTemplate.updated_at !== detailTemplate.created_at">
                · 最后更新 {{ formatDate(detailTemplate.updated_at) }}
              </span>
            </div>
          </v-card-text>

          <v-card-actions class="justify-end px-5 pb-5">
            <v-btn variant="text" @click="detailDialog = false">关闭</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <!-- ================================================================
           Delete confirmation dialog
      ================================================================ -->
      <v-dialog v-model="deleteDialog" max-width="420">
        <v-card class="dashboard-dialog-card">
          <v-card-title class="text-h6 pt-5 px-5">确认删除</v-card-title>
          <v-card-text class="px-5">
            确定要删除模板
            <strong>「{{ deleteTarget?.name }}」</strong>
            吗？此操作不可撤销。
          </v-card-text>
          <v-card-actions class="justify-end px-5 pb-5">
            <v-btn variant="text" @click="deleteDialog = false">取消</v-btn>
            <v-btn variant="tonal" color="error" :loading="deleting" @click="executeDelete">
              确认删除
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

    </v-container>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useTheme } from 'vuetify'
import {
  fetchTemplates,
  createTemplate,
  updateTemplate,
  deleteTemplate,
  previewTemplate,
  type NotificationTemplate,
  type PreviewResult,
} from '@/api/notificationTemplate'

// ---------------------------------------------------------------------------
// Theme
// ---------------------------------------------------------------------------
const theme = useTheme()
const isDark = computed(() => theme.global.current.value.dark)

// ---------------------------------------------------------------------------
// Placeholder extraction (client-side, mirrors backend logic)
// ---------------------------------------------------------------------------
const VALID_PH_RE = /\{\{\s*([A-Za-z_]\w*)\s*\}\}/g
const SYNTAX_ERRORS = [
  { re: /\{\{(?![\s\S]*?\}\})/, msg: '存在未闭合的 \'{{\'（缺少对应的 \'}}\'）' },
  { re: /\{\{\s*\}\}/, msg: '占位符变量名不能为空（{{ }}）' },
  { re: /\{\{\s*\d/, msg: '变量名不能以数字开头' },
  { re: /\{\{[^}]*[ \-\.@#][^}]*\}\}/, msg: '变量名只能包含字母、数字和下划线' },
]

function extractPlaceholders(body: string): string[] {
  const seen = new Map<string, null>()
  let m: RegExpExecArray | null
  const re = new RegExp(VALID_PH_RE.source, 'g')
  while ((m = re.exec(body)) !== null) {
    seen.set(m[1], null)
  }
  return [...seen.keys()]
}

function detectSyntaxError(body: string): string {
  // Check unclosed {{ first
  const stripped = body.replace(/\{\{[\s\S]*?\}\}/g, '')
  if (stripped.includes('{{')) return '存在未闭合的 \'{{\'（缺少对应的 \'}}\'）'
  if (stripped.includes('}}')) return '存在多余的 \'}}\'（没有对应的 \'{{\'）'

  // Check content of each {{ … }}
  const anyRe = /\{\{([\s\S]*?)\}\}/g
  let m: RegExpExecArray | null
  while ((m = anyRe.exec(body)) !== null) {
    const inner = m[1].trim()
    if (!inner) return `占位符 '${m[0]}' 的变量名不能为空`
    if (!/^[A-Za-z_]\w*$/.test(inner)) {
      return `占位符 '${m[0]}' 包含无效的变量名 '${inner}'（只能包含字母、数字和下划线，且不能以数字开头）`
    }
  }
  return ''
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const loading = ref(false)
const templates = ref<NotificationTemplate[]>([])

const snackbar = ref({ show: false, message: '', color: 'success' as 'success' | 'error' | 'warning' })

// --- Form dialog ---
const formDialog = ref(false)
const formSaving = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const form = ref({ name: '', body: '' })
const formErrors = ref({ name: '', body: '' })
const formSyntaxError = ref('')
const formPlaceholders = computed(() => extractPlaceholders(form.value.body))

// --- Detail dialog ---
const detailDialog = ref(false)
const detailTemplate = ref<NotificationTemplate | null>(null)
const detailPlaceholders = computed(() =>
  detailTemplate.value ? extractPlaceholders(detailTemplate.value.body) : []
)
const previewVars = ref<Record<string, string>>({})
const previewing = ref(false)
const previewResult = ref<PreviewResult | null>(null)
const previewError = ref('')

// --- Delete dialog ---
const deleteDialog = ref(false)
const deleteTarget = ref<NotificationTemplate | null>(null)
const deleting = ref(false)

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------
const templatesWithPlaceholders = computed(
  () => templates.value.filter((t) => extractPlaceholders(t.body).length > 0).length
)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function toast(message: string, color: 'success' | 'error' | 'warning' = 'success') {
  snackbar.value = { show: true, message, color }
}

function truncate(str: string, len: number): string {
  return str.length <= len ? str : str.slice(0, len) + '…'
}

function formatDate(ts: number): string {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

function getPlaceholders(body: string): string[] {
  return extractPlaceholders(body)
}

// ---------------------------------------------------------------------------
// Load
// ---------------------------------------------------------------------------
async function loadTemplates() {
  loading.value = true
  try {
    templates.value = await fetchTemplates()
  } catch (e: any) {
    toast(e?.message || '加载模板列表失败', 'error')
  } finally {
    loading.value = false
  }
}

// ---------------------------------------------------------------------------
// Create / Edit form
// ---------------------------------------------------------------------------
function openCreate() {
  isEditing.value = false
  editingId.value = null
  form.value = { name: '', body: '' }
  formErrors.value = { name: '', body: '' }
  formSyntaxError.value = ''
  formDialog.value = true
}

function openEdit(tpl: NotificationTemplate) {
  isEditing.value = true
  editingId.value = tpl.id
  form.value = { name: tpl.name, body: tpl.body }
  formErrors.value = { name: '', body: '' }
  formSyntaxError.value = detectSyntaxError(tpl.body)
  formDialog.value = true
}

function closeFormDialog() {
  formDialog.value = false
}

function onBodyInput() {
  formErrors.value.body = ''
  formSyntaxError.value = detectSyntaxError(form.value.body)
}

async function submitForm() {
  // Client-side validation
  let valid = true
  if (!form.value.name.trim()) {
    formErrors.value.name = '模板名称不能为空'
    valid = false
  }
  if (!form.value.body.trim()) {
    formErrors.value.body = '模板正文不能为空'
    valid = false
  }
  if (formSyntaxError.value) {
    valid = false
  }
  if (!valid) return

  formSaving.value = true
  try {
    if (isEditing.value && editingId.value !== null) {
      const updated = await updateTemplate(editingId.value, form.value.name.trim(), form.value.body)
      const idx = templates.value.findIndex((t) => t.id === editingId.value)
      if (idx !== -1) templates.value[idx] = updated
      toast('模板已更新')
    } else {
      const created = await createTemplate(form.value.name.trim(), form.value.body)
      templates.value.push(created)
      toast('模板已创建')
    }
    formDialog.value = false
  } catch (e: any) {
    // Server-side errors (e.g. duplicate name, syntax error)
    const msg: string = e?.message || '操作失败'
    if (msg.includes('名称') || msg.includes('已存在')) {
      formErrors.value.name = msg
    } else if (msg.includes('语法') || msg.includes('占位符') || msg.includes('变量')) {
      formSyntaxError.value = msg
    } else {
      toast(msg, 'error')
    }
  } finally {
    formSaving.value = false
  }
}

// ---------------------------------------------------------------------------
// Detail / Preview
// ---------------------------------------------------------------------------
function openDetail(tpl: NotificationTemplate) {
  detailTemplate.value = tpl
  previewVars.value = {}
  previewResult.value = null
  previewError.value = ''
  // Pre-fill empty strings for each placeholder
  extractPlaceholders(tpl.body).forEach((ph) => {
    previewVars.value[ph] = ''
  })
  detailDialog.value = true
}

function openEditFromDetail() {
  if (!detailTemplate.value) return
  detailDialog.value = false
  openEdit(detailTemplate.value)
}

function confirmDeleteFromDetail() {
  if (!detailTemplate.value) return
  detailDialog.value = false
  confirmDelete(detailTemplate.value)
}

async function runPreview() {
  if (!detailTemplate.value) return
  previewing.value = true
  previewResult.value = null
  previewError.value = ''
  try {
    // Only pass non-empty values
    const vars: Record<string, string> = {}
    for (const [k, v] of Object.entries(previewVars.value)) {
      if (v !== '') vars[k] = v
    }
    previewResult.value = await previewTemplate(detailTemplate.value.id, vars)
  } catch (e: any) {
    previewError.value = e?.message || '预览失败'
  } finally {
    previewing.value = false
  }
}

// Keep detail template in sync when list updates (e.g. after edit)
watch(templates, (list) => {
  if (detailTemplate.value) {
    const fresh = list.find((t) => t.id === detailTemplate.value!.id)
    if (fresh) {
      detailTemplate.value = fresh
      // Reset preview when template body changes
      previewResult.value = null
      previewError.value = ''
    }
  }
})

// ---------------------------------------------------------------------------
// Delete
// ---------------------------------------------------------------------------
function confirmDelete(tpl: NotificationTemplate) {
  deleteTarget.value = tpl
  deleteDialog.value = true
}

async function executeDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await deleteTemplate(deleteTarget.value.id)
    templates.value = templates.value.filter((t) => t.id !== deleteTarget.value!.id)
    toast(`模板「${deleteTarget.value.name}」已删除`)
    deleteDialog.value = false
    // Close detail dialog if the deleted template was open
    if (detailTemplate.value?.id === deleteTarget.value.id) {
      detailDialog.value = false
    }
  } catch (e: any) {
    toast(e?.message || '删除失败', 'error')
  } finally {
    deleting.value = false
  }
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------
onMounted(() => {
  loadTemplates()
})
</script>

<style scoped>
@import '@/styles/dashboard-shell.css';

/* ── Page ─────────────────────────────────────────────────────────────── */
.notification-template-page {
  padding-bottom: 48px;
}

.inline-code {
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 0.85em;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(var(--v-theme-primary), 0.1);
  color: rgb(var(--v-theme-primary));
}

/* ── Overview grid (2 cards) ──────────────────────────────────────────── */
.tpl-overview-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  max-width: 560px;
}

/* ── State panel ──────────────────────────────────────────────────────── */
.state-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 260px;
  border: 1px dashed var(--dashboard-border-strong);
  border-radius: 16px;
  color: var(--dashboard-muted);
  font-size: 14px;
  text-align: center;
  padding: 32px;
}

.state-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--dashboard-text);
}

.state-sub {
  color: var(--dashboard-muted);
  font-size: 13px;
}

/* ── Template card grid ───────────────────────────────────────────────── */
.tpl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.tpl-card {
  padding: 18px 20px 16px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tpl-card:hover {
  border-color: rgba(var(--v-theme-primary), 0.4);
  box-shadow: 0 4px 20px rgba(var(--v-theme-primary), 0.08);
}

/* Card header */
.tpl-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.tpl-card-icon {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--dashboard-soft);
  color: rgb(var(--v-theme-primary));
}

.tpl-card-name {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  font-weight: 650;
  color: var(--dashboard-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tpl-card-actions {
  flex-shrink: 0;
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}

.tpl-card:hover .tpl-card-actions {
  opacity: 1;
}

/* Card body */
.tpl-card-body {
  font-size: 13px;
  color: var(--dashboard-muted);
  line-height: 1.6;
  overflow-wrap: anywhere;
  flex: 1;
}

/* Placeholder chips */
.tpl-card-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tpl-card-no-vars {
  font-size: 12px;
  color: var(--dashboard-subtle);
}

/* Footer */
.tpl-card-footer {
  font-size: 11px;
  color: var(--dashboard-subtle);
  margin-top: 2px;
}

/* ── Form dialog ──────────────────────────────────────────────────────── */
.form-placeholder-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
}

.form-placeholder-label {
  font-size: 12px;
  color: var(--dashboard-muted);
}

/* ── Detail dialog ────────────────────────────────────────────────────── */
.detail-section-label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--dashboard-muted);
  margin-bottom: 8px;
}

.detail-section-sub {
  font-size: 13px;
  color: var(--dashboard-subtle);
  margin-top: -4px;
  margin-bottom: 12px;
}

.detail-body-box {
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 13px;
  line-height: 1.7;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.04);
  border: 1px solid var(--dashboard-border);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--dashboard-text);
}

.detail-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.detail-empty {
  font-size: 13px;
  color: var(--dashboard-subtle);
}

/* Preview */
.preview-vars-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
  margin-bottom: 4px;
}

.preview-result-wrap {
  border: 1px solid var(--dashboard-border);
  border-radius: 12px;
  overflow: hidden;
}

.preview-result-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--dashboard-muted);
  padding: 8px 14px 6px;
  background: rgba(var(--v-theme-primary), 0.04);
  border-bottom: 1px solid var(--dashboard-border);
}

.preview-result-box {
  font-size: 14px;
  line-height: 1.7;
  padding: 12px 14px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--dashboard-text);
}

/* Timestamps */
.detail-timestamps {
  font-size: 12px;
  color: var(--dashboard-subtle);
}

/* ── Responsive ───────────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .tpl-overview-grid {
    grid-template-columns: 1fr;
    max-width: 100%;
  }

  .tpl-grid {
    grid-template-columns: 1fr;
  }

  .preview-vars-grid {
    grid-template-columns: 1fr;
  }
}
</style>
