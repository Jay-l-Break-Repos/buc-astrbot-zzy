<template>
  <v-container fluid class="pa-6">
    <!-- Page Header -->
    <v-row class="mb-4" align="center">
      <v-col>
        <h1 class="text-h5 font-weight-bold">Notification Templates</h1>
        <p class="text-body-2 text-medium-emphasis mt-1">
          Manage reusable message templates with
          <code>{{ '{{ variable }}' }}</code> placeholders.
        </p>
      </v-col>
      <v-col cols="auto">
        <v-btn color="primary" prepend-icon="mdi-plus" @click="openCreateDialog">
          New Template
        </v-btn>
      </v-col>
    </v-row>

    <!-- Loading / Error states -->
    <v-row v-if="loading">
      <v-col class="text-center py-12">
        <v-progress-circular indeterminate color="primary" size="48" />
      </v-col>
    </v-row>

    <v-alert v-else-if="fetchError" type="error" class="mb-4" closable @click:close="fetchError = ''">
      {{ fetchError }}
    </v-alert>

    <!-- Empty state -->
    <v-row v-else-if="templates.length === 0">
      <v-col class="text-center py-12">
        <v-icon size="64" color="grey-lighten-1">mdi-bell-off-outline</v-icon>
        <p class="text-h6 text-medium-emphasis mt-4">No templates yet</p>
        <p class="text-body-2 text-medium-emphasis">
          Click <strong>New Template</strong> to create your first notification template.
        </p>
      </v-col>
    </v-row>

    <!-- Template cards -->
    <v-row v-else>
      <v-col
        v-for="tpl in templates"
        :key="tpl.id"
        cols="12"
        sm="6"
        lg="4"
      >
        <v-card variant="outlined" class="h-100 d-flex flex-column">
          <v-card-title class="text-subtitle-1 font-weight-medium pt-4 pb-1 px-4">
            <v-icon start size="18" color="primary">mdi-bell-outline</v-icon>
            {{ tpl.name }}
          </v-card-title>

          <v-card-text class="flex-grow-1 px-4 pb-2">
            <pre class="body-preview text-body-2 text-medium-emphasis">{{ tpl.body }}</pre>
            <div class="text-caption text-disabled mt-3">
              Created {{ formatTs(tpl.created_at) }}
              <span v-if="tpl.updated_at !== tpl.created_at">
                · Updated {{ formatTs(tpl.updated_at) }}
              </span>
            </div>
          </v-card-text>

          <v-divider />

          <v-card-actions class="px-3 py-2">
            <v-btn
              size="small"
              variant="text"
              color="primary"
              prepend-icon="mdi-eye-outline"
              @click="openPreviewDialog(tpl)"
            >
              Preview
            </v-btn>
            <v-spacer />
            <v-btn
              size="small"
              variant="text"
              prepend-icon="mdi-pencil-outline"
              @click="openEditDialog(tpl)"
            >
              Edit
            </v-btn>
            <v-btn
              size="small"
              variant="text"
              color="error"
              prepend-icon="mdi-delete-outline"
              @click="openDeleteDialog(tpl)"
            >
              Delete
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <!-- ------------------------------------------------------------------ -->
    <!-- Create / Edit Dialog                                                 -->
    <!-- ------------------------------------------------------------------ -->
    <v-dialog v-model="formDialog" max-width="600" persistent>
      <v-card>
        <v-card-title class="text-h6 pa-5 pb-3">
          {{ editingTemplate ? 'Edit Template' : 'New Template' }}
        </v-card-title>

        <v-card-text class="px-5 pb-2">
          <!-- Name conflict error banner -->
          <v-alert
            v-if="formConflictError"
            type="error"
            variant="tonal"
            class="mb-4"
            closable
            @click:close="formConflictError = ''"
          >
            {{ formConflictError }}
          </v-alert>

          <!-- Syntax error banner -->
          <v-alert
            v-if="formSyntaxError"
            type="warning"
            variant="tonal"
            class="mb-4"
            closable
            @click:close="formSyntaxError = ''"
          >
            {{ formSyntaxError }}
          </v-alert>

          <v-text-field
            v-model="formName"
            label="Template Name *"
            placeholder="e.g. welcome_message"
            :error-messages="formNameErrors"
            variant="outlined"
            density="comfortable"
            class="mb-3"
            autofocus
            @input="formNameErrors = []"
          />

          <v-textarea
            v-model="formBody"
            label="Template Body *"
            placeholder="Hello {{ username }}, your message: {{ message }}"
            :error-messages="formBodyErrors"
            variant="outlined"
            density="comfortable"
            rows="6"
            auto-grow
            @input="formBodyErrors = []"
          />

          <p class="text-caption text-medium-emphasis mt-1">
            Use <code>{{ '{{ variable_name }}' }}</code> for dynamic placeholders.
          </p>
        </v-card-text>

        <v-card-actions class="px-5 pb-4">
          <v-spacer />
          <v-btn variant="text" @click="closeFormDialog">Cancel</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :loading="formSaving"
            @click="saveTemplate"
          >
            {{ editingTemplate ? 'Save Changes' : 'Create' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ------------------------------------------------------------------ -->
    <!-- Delete Confirmation Dialog                                           -->
    <!-- ------------------------------------------------------------------ -->
    <v-dialog v-model="deleteDialog" max-width="420">
      <v-card>
        <v-card-title class="text-h6 pa-5 pb-3">Delete Template</v-card-title>
        <v-card-text class="px-5 pb-2">
          Are you sure you want to delete
          <strong>{{ deletingTemplate?.name }}</strong>? This action cannot be undone.
        </v-card-text>
        <v-card-actions class="px-5 pb-4">
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">Cancel</v-btn>
          <v-btn
            color="error"
            variant="flat"
            :loading="deleteLoading"
            @click="confirmDelete"
          >
            Delete
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ------------------------------------------------------------------ -->
    <!-- Preview Dialog                                                       -->
    <!-- ------------------------------------------------------------------ -->
    <v-dialog v-model="previewDialog" max-width="640">
      <v-card>
        <v-card-title class="text-h6 pa-5 pb-3">
          Preview — {{ previewTemplate?.name }}
        </v-card-title>

        <v-card-text class="px-5 pb-2">
          <p class="text-body-2 text-medium-emphasis mb-3">
            Provide variable values as JSON to render the template.
          </p>

          <v-textarea
            v-model="previewVariablesJson"
            label="Variables (JSON)"
            placeholder='{ "username": "Alice", "message": "Hello!" }'
            variant="outlined"
            density="comfortable"
            rows="4"
            :error-messages="previewJsonError ? [previewJsonError] : []"
            @input="previewJsonError = ''"
          />

          <v-btn
            color="primary"
            variant="tonal"
            class="mt-2"
            :loading="previewLoading"
            prepend-icon="mdi-play-outline"
            @click="renderPreview"
          >
            Render
          </v-btn>

          <v-divider v-if="previewResult !== null" class="my-4" />

          <div v-if="previewResult !== null">
            <p class="text-caption text-medium-emphasis mb-1">Rendered output:</p>
            <v-sheet
              color="grey-lighten-4"
              rounded
              class="pa-3"
            >
              <pre class="text-body-2" style="white-space: pre-wrap; word-break: break-word;">{{ previewResult }}</pre>
            </v-sheet>
          </div>

          <v-alert
            v-if="previewError"
            type="error"
            variant="tonal"
            class="mt-3"
            closable
            @click:close="previewError = ''"
          >
            {{ previewError }}
          </v-alert>
        </v-card-text>

        <v-card-actions class="px-5 pb-4">
          <v-spacer />
          <v-btn variant="text" @click="closePreviewDialog">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Global snackbar -->
    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      :timeout="3000"
      location="bottom right"
    >
      {{ snackbar.message }}
      <template #actions>
        <v-btn variant="text" @click="snackbar.show = false">Close</v-btn>
      </template>
    </v-snackbar>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface NotificationTemplate {
  id: number
  name: string
  body: string
  created_at: number
  updated_at: number
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const templates = ref<NotificationTemplate[]>([])
const loading = ref(false)
const fetchError = ref('')

// Form dialog
const formDialog = ref(false)
const editingTemplate = ref<NotificationTemplate | null>(null)
const formName = ref('')
const formBody = ref('')
const formNameErrors = ref<string[]>([])
const formBodyErrors = ref<string[]>([])
const formConflictError = ref('')
const formSyntaxError = ref('')
const formSaving = ref(false)

// Delete dialog
const deleteDialog = ref(false)
const deletingTemplate = ref<NotificationTemplate | null>(null)
const deleteLoading = ref(false)

// Preview dialog
const previewDialog = ref(false)
const previewTemplate = ref<NotificationTemplate | null>(null)
const previewVariablesJson = ref('{}')
const previewJsonError = ref('')
const previewLoading = ref(false)
const previewResult = ref<string | null>(null)
const previewError = ref('')

// Snackbar
const snackbar = ref({ show: false, message: '', color: 'success' })

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
const API_BASE = '/api/templates'

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('token') || sessionStorage.getItem('token') || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  return fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
      ...(options.headers as Record<string, string> || {}),
    },
  })
}

// ---------------------------------------------------------------------------
// Load templates
// ---------------------------------------------------------------------------
async function loadTemplates() {
  loading.value = true
  fetchError.value = ''
  try {
    const res = await apiFetch(API_BASE)
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      fetchError.value = data.error || `Failed to load templates (HTTP ${res.status})`
      return
    }
    templates.value = await res.json()
  } catch (e: any) {
    fetchError.value = e?.message || 'Network error'
  } finally {
    loading.value = false
  }
}

onMounted(loadTemplates)

// ---------------------------------------------------------------------------
// Create / Edit dialog
// ---------------------------------------------------------------------------
function openCreateDialog() {
  editingTemplate.value = null
  formName.value = ''
  formBody.value = ''
  formNameErrors.value = []
  formBodyErrors.value = []
  formConflictError.value = ''
  formSyntaxError.value = ''
  formDialog.value = true
}

function openEditDialog(tpl: NotificationTemplate) {
  editingTemplate.value = tpl
  formName.value = tpl.name
  formBody.value = tpl.body
  formNameErrors.value = []
  formBodyErrors.value = []
  formConflictError.value = ''
  formSyntaxError.value = ''
  formDialog.value = true
}

function closeFormDialog() {
  formDialog.value = false
  editingTemplate.value = null
}

async function saveTemplate() {
  // Client-side validation
  formNameErrors.value = []
  formBodyErrors.value = []
  formConflictError.value = ''
  formSyntaxError.value = ''

  if (!formName.value.trim()) {
    formNameErrors.value = ['Name is required']
    return
  }
  if (!formBody.value.trim()) {
    formBodyErrors.value = ['Body is required']
    return
  }

  formSaving.value = true
  try {
    let res: Response
    if (editingTemplate.value) {
      res = await apiFetch(`${API_BASE}/${editingTemplate.value.id}`, {
        method: 'PUT',
        body: JSON.stringify({ name: formName.value.trim(), body: formBody.value }),
      })
    } else {
      res = await apiFetch(API_BASE, {
        method: 'POST',
        body: JSON.stringify({ name: formName.value.trim(), body: formBody.value }),
      })
    }

    const data = await res.json().catch(() => ({}))

    if (res.status === 409) {
      formConflictError.value = data.error || 'A template with this name already exists.'
      return
    }
    if (res.status === 400 && data.error?.includes('模板语法')) {
      formSyntaxError.value = data.error
      return
    }
    if (!res.ok) {
      showSnackbar(data.error || `Error (HTTP ${res.status})`, 'error')
      return
    }

    showSnackbar(
      editingTemplate.value ? 'Template updated successfully.' : 'Template created successfully.',
      'success'
    )
    closeFormDialog()
    await loadTemplates()
  } catch (e: any) {
    showSnackbar(e?.message || 'Network error', 'error')
  } finally {
    formSaving.value = false
  }
}

// ---------------------------------------------------------------------------
// Delete dialog
// ---------------------------------------------------------------------------
function openDeleteDialog(tpl: NotificationTemplate) {
  deletingTemplate.value = tpl
  deleteDialog.value = true
}

async function confirmDelete() {
  if (!deletingTemplate.value) return
  deleteLoading.value = true
  try {
    const res = await apiFetch(`${API_BASE}/${deletingTemplate.value.id}`, {
      method: 'DELETE',
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      showSnackbar(data.error || `Error (HTTP ${res.status})`, 'error')
      return
    }
    showSnackbar('Template deleted.', 'success')
    deleteDialog.value = false
    deletingTemplate.value = null
    await loadTemplates()
  } catch (e: any) {
    showSnackbar(e?.message || 'Network error', 'error')
  } finally {
    deleteLoading.value = false
  }
}

// ---------------------------------------------------------------------------
// Preview dialog
// ---------------------------------------------------------------------------
function openPreviewDialog(tpl: NotificationTemplate) {
  previewTemplate.value = tpl
  previewVariablesJson.value = '{}'
  previewJsonError.value = ''
  previewResult.value = null
  previewError.value = ''
  previewDialog.value = true
}

function closePreviewDialog() {
  previewDialog.value = false
  previewTemplate.value = null
}

async function renderPreview() {
  if (!previewTemplate.value) return
  previewJsonError.value = ''
  previewError.value = ''
  previewResult.value = null

  let variables: Record<string, unknown>
  try {
    variables = JSON.parse(previewVariablesJson.value || '{}')
  } catch {
    previewJsonError.value = 'Invalid JSON — please check your input.'
    return
  }

  previewLoading.value = true
  try {
    const res = await apiFetch(`${API_BASE}/${previewTemplate.value.id}/preview`, {
      method: 'POST',
      body: JSON.stringify({ variables }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      previewError.value = data.error || `Error (HTTP ${res.status})`
      return
    }
    previewResult.value = data.rendered ?? ''
  } catch (e: any) {
    previewError.value = e?.message || 'Network error'
  } finally {
    previewLoading.value = false
  }
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function formatTs(ts: number): string {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString()
}

function showSnackbar(message: string, color: 'success' | 'error' | 'info' = 'success') {
  snackbar.value = { show: true, message, color }
}
</script>

<style scoped>
.body-preview {
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.8rem;
  line-height: 1.5;
}
</style>
