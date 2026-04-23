<template>
  <div class="notification-template-page">
    <v-container fluid class="pa-0">

      <!-- Page header -->
      <v-row>
        <v-col cols="12">
          <h1 class="text-h4 font-weight-bold mb-2">
            <v-icon size="x-large" color="primary" class="me-2">mdi-bell-outline</v-icon>
            Notification Templates
          </h1>
          <p class="text-subtitle-1 text-medium-emphasis mb-4">
            Manage reusable Jinja2 message templates for bot notifications.
          </p>
        </v-col>
      </v-row>

      <!-- Toolbar -->
      <v-row class="mb-4">
        <v-col cols="12" class="d-flex align-center">
          <v-btn color="primary" prepend-icon="mdi-plus" @click="openCreateDialog">
            New Template
          </v-btn>
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-refresh" @click="fetchTemplates" :loading="loading">
            Refresh
          </v-btn>
        </v-col>
      </v-row>

      <!-- Template list -->
      <v-card elevation="2">
        <v-card-title class="d-flex align-center py-3 px-4">
          <v-icon color="primary" class="me-2">mdi-format-list-bulleted</v-icon>
          <span class="text-h6">Templates</span>
          <v-chip color="info" size="small" class="ml-2">{{ templates.length }}</v-chip>
        </v-card-title>
        <v-divider />

        <v-card-text class="pa-0">
          <!-- Loading skeleton -->
          <div v-if="loading" class="pa-4">
            <v-skeleton-loader v-for="n in 3" :key="n" type="list-item-two-line" class="mb-2" />
          </div>

          <!-- Empty state -->
          <div v-else-if="templates.length === 0" class="d-flex flex-column align-center py-10">
            <v-icon size="64" color="grey-lighten-1">mdi-bell-off-outline</v-icon>
            <span class="text-subtitle-1 text-disabled mt-3">No templates yet. Create one to get started.</span>
          </div>

          <!-- Template cards -->
          <v-list v-else lines="two" class="pa-2">
            <v-list-item
              v-for="tpl in templates"
              :key="tpl.id"
              class="template-list-item mb-2 rounded"
              rounded="lg"
            >
              <template v-slot:prepend>
                <v-avatar color="primary" variant="tonal" rounded="lg">
                  <v-icon>mdi-bell-outline</v-icon>
                </v-avatar>
              </template>

              <v-list-item-title class="font-weight-medium">{{ tpl.name }}</v-list-item-title>
              <v-list-item-subtitle class="template-body-preview text-truncate">
                {{ tpl.body }}
              </v-list-item-subtitle>

              <template v-slot:append>
                <div class="d-flex align-center gap-2">
                  <v-tooltip text="Preview / Render" location="top">
                    <template v-slot:activator="{ props }">
                      <v-btn
                        v-bind="props"
                        icon="mdi-play-circle-outline"
                        variant="text"
                        color="success"
                        size="small"
                        @click="openPreviewDialog(tpl)"
                      />
                    </template>
                  </v-tooltip>

                  <v-tooltip text="Edit" location="top">
                    <template v-slot:activator="{ props }">
                      <v-btn
                        v-bind="props"
                        icon="mdi-pencil-outline"
                        variant="text"
                        color="primary"
                        size="small"
                        @click="openEditDialog(tpl)"
                      />
                    </template>
                  </v-tooltip>

                  <v-tooltip text="Delete" location="top">
                    <template v-slot:activator="{ props }">
                      <v-btn
                        v-bind="props"
                        icon="mdi-delete-outline"
                        variant="text"
                        color="error"
                        size="small"
                        @click="openDeleteDialog(tpl)"
                      />
                    </template>
                  </v-tooltip>
                </div>
              </template>
            </v-list-item>
          </v-list>
        </v-card-text>
      </v-card>
    </v-container>

    <!-- ─── Create / Edit Dialog ─────────────────────────────────────── -->
    <v-dialog v-model="dialogForm" max-width="680px" persistent>
      <v-card>
        <v-card-title class="bg-primary text-white py-3 d-flex align-center">
          <v-icon color="white" class="me-2">{{ isEditing ? 'mdi-pencil' : 'mdi-plus' }}</v-icon>
          <span>{{ isEditing ? 'Edit Template' : 'New Template' }}</span>
        </v-card-title>

        <v-card-text class="py-4">
          <v-form ref="formRef" v-model="formValid">
            <!-- Name -->
            <v-text-field
              v-model="formData.name"
              label="Template Name"
              placeholder="e.g. welcome-message"
              variant="outlined"
              density="comfortable"
              class="mb-3"
              :rules="[v => !!v.trim() || 'Name is required']"
              :error-messages="formErrors.name"
              @input="formErrors.name = ''"
            />

            <!-- Body -->
            <v-textarea
              v-model="formData.body"
              label="Template Body"
              placeholder="Hello {{ username }}, your order {{ order_id }} is ready!"
              variant="outlined"
              rows="6"
              auto-grow
              :rules="[v => !!v.trim() || 'Body is required']"
              :error-messages="formErrors.body"
              @input="formErrors.body = ''"
              hint="Supports Jinja2 syntax: {{ variable }}, {% if %}, {{ var|upper }}, etc."
              persistent-hint
            />

            <!-- Syntax error banner -->
            <v-alert
              v-if="syntaxError"
              type="error"
              variant="tonal"
              class="mt-3"
              density="compact"
              closable
              @click:close="syntaxError = ''"
            >
              {{ syntaxError }}
            </v-alert>
          </v-form>
        </v-card-text>

        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="text" @click="closeFormDialog" :disabled="saving">Cancel</v-btn>
          <v-btn color="primary" @click="submitForm" :loading="saving">
            {{ isEditing ? 'Save Changes' : 'Create' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ─── Preview / Render Dialog ──────────────────────────────────── -->
    <v-dialog v-model="dialogPreview" max-width="720px">
      <v-card>
        <v-card-title class="bg-success text-white py-3 d-flex align-center">
          <v-icon color="white" class="me-2">mdi-play-circle-outline</v-icon>
          <span>Preview: {{ previewTemplate?.name }}</span>
        </v-card-title>

        <v-card-text class="py-4">
          <!-- Template body (read-only) -->
          <v-textarea
            :model-value="previewTemplate?.body"
            label="Template Body"
            variant="outlined"
            rows="4"
            readonly
            density="comfortable"
            class="mb-4"
          />

          <!-- Variables input -->
          <div class="mb-2 text-subtitle-2 font-weight-medium">
            Variables (JSON object)
          </div>
          <v-textarea
            v-model="previewVariablesRaw"
            label='e.g. { "username": "Alice", "order_id": "42" }'
            variant="outlined"
            rows="3"
            density="comfortable"
            :error-messages="previewVarError"
            @input="previewVarError = ''"
            class="mb-3 font-mono"
          />

          <v-btn color="success" prepend-icon="mdi-play" @click="runPreview" :loading="previewing" class="mb-4">
            Render
          </v-btn>

          <!-- Rendered output -->
          <div v-if="previewResult !== null">
            <v-divider class="mb-3" />
            <div class="text-subtitle-2 font-weight-medium mb-2">Rendered Output</div>
            <v-sheet
              color="grey-lighten-4"
              rounded="lg"
              class="pa-4 rendered-output"
            >
              <pre class="text-body-2">{{ previewResult }}</pre>
            </v-sheet>
          </div>

          <!-- Render error -->
          <v-alert
            v-if="previewError"
            type="error"
            variant="tonal"
            class="mt-3"
            density="compact"
          >
            {{ previewError }}
          </v-alert>
        </v-card-text>

        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="text" @click="dialogPreview = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ─── Delete Confirmation Dialog ───────────────────────────────── -->
    <v-dialog v-model="dialogDelete" max-width="480px">
      <v-card>
        <v-card-title class="bg-error text-white py-3 d-flex align-center">
          <v-icon color="white" class="me-2">mdi-alert</v-icon>
          <span>Delete Template</span>
        </v-card-title>

        <v-card-text class="py-4">
          <p>
            Are you sure you want to delete
            <strong>{{ deleteTarget?.name }}</strong>?
            This action cannot be undone.
          </p>
        </v-card-text>

        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="text" @click="dialogDelete = false" :disabled="deleting">Cancel</v-btn>
          <v-btn color="error" @click="confirmDelete" :loading="deleting">Delete</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ─── Snackbar ──────────────────────────────────────────────────── -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000" location="top">
      {{ snackbar.message }}
    </v-snackbar>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'NotificationTemplatePage',

  data() {
    return {
      // ── list ──────────────────────────────────────────────────────────
      templates: [],
      loading: false,

      // ── create / edit form ────────────────────────────────────────────
      dialogForm: false,
      isEditing: false,
      editingId: null,
      formValid: false,
      saving: false,
      formData: { name: '', body: '' },
      formErrors: { name: '', body: '' },
      syntaxError: '',

      // ── preview ───────────────────────────────────────────────────────
      dialogPreview: false,
      previewTemplate: null,
      previewVariablesRaw: '{}',
      previewVarError: '',
      previewing: false,
      previewResult: null,
      previewError: '',

      // ── delete ────────────────────────────────────────────────────────
      dialogDelete: false,
      deleteTarget: null,
      deleting: false,

      // ── snackbar ──────────────────────────────────────────────────────
      snackbar: { show: false, message: '', color: 'success' },
    };
  },

  mounted() {
    this.fetchTemplates();
  },

  methods: {
    // ── API helpers ──────────────────────────────────────────────────────

    async fetchTemplates() {
      this.loading = true;
      try {
        const resp = await axios.get('/api/templates');
        this.templates = resp.data;
      } catch (err) {
        this.notify('Failed to load templates: ' + (err.response?.data?.error || err.message), 'error');
      } finally {
        this.loading = false;
      }
    },

    // ── Create / Edit ────────────────────────────────────────────────────

    openCreateDialog() {
      this.isEditing = false;
      this.editingId = null;
      this.formData = { name: '', body: '' };
      this.formErrors = { name: '', body: '' };
      this.syntaxError = '';
      this.dialogForm = true;
    },

    openEditDialog(tpl) {
      this.isEditing = true;
      this.editingId = tpl.id;
      this.formData = { name: tpl.name, body: tpl.body };
      this.formErrors = { name: '', body: '' };
      this.syntaxError = '';
      this.dialogForm = true;
    },

    closeFormDialog() {
      this.dialogForm = false;
    },

    async submitForm() {
      const { valid } = await this.$refs.formRef.validate();
      if (!valid) return;

      this.saving = true;
      this.syntaxError = '';
      try {
        if (this.isEditing) {
          await axios.put(`/api/templates/${this.editingId}`, {
            name: this.formData.name.trim(),
            body: this.formData.body,
          });
          this.notify('Template updated successfully.', 'success');
        } else {
          await axios.post('/api/templates', {
            name: this.formData.name.trim(),
            body: this.formData.body,
          });
          this.notify('Template created successfully.', 'success');
        }
        this.dialogForm = false;
        await this.fetchTemplates();
      } catch (err) {
        const status = err.response?.status;
        const msg = err.response?.data?.error || err.message;
        if (status === 400) {
          // Jinja2 syntax error
          this.syntaxError = msg;
        } else if (status === 409) {
          this.formErrors.name = msg;
        } else {
          this.notify('Error: ' + msg, 'error');
        }
      } finally {
        this.saving = false;
      }
    },

    // ── Preview ──────────────────────────────────────────────────────────

    openPreviewDialog(tpl) {
      this.previewTemplate = tpl;
      this.previewVariablesRaw = '{}';
      this.previewVarError = '';
      this.previewResult = null;
      this.previewError = '';
      this.dialogPreview = true;
    },

    async runPreview() {
      // Validate variables JSON
      let variables;
      try {
        variables = JSON.parse(this.previewVariablesRaw);
        if (typeof variables !== 'object' || Array.isArray(variables)) {
          throw new Error('Must be a JSON object');
        }
      } catch (e) {
        this.previewVarError = 'Invalid JSON: ' + e.message;
        return;
      }

      this.previewing = true;
      this.previewResult = null;
      this.previewError = '';
      try {
        const resp = await axios.post(`/api/templates/${this.previewTemplate.id}/preview`, { variables });
        this.previewResult = resp.data.rendered;
      } catch (err) {
        this.previewError = err.response?.data?.error || err.message;
      } finally {
        this.previewing = false;
      }
    },

    // ── Delete ───────────────────────────────────────────────────────────

    openDeleteDialog(tpl) {
      this.deleteTarget = tpl;
      this.dialogDelete = true;
    },

    async confirmDelete() {
      this.deleting = true;
      try {
        await axios.delete(`/api/templates/${this.deleteTarget.id}`);
        this.notify(`Template "${this.deleteTarget.name}" deleted.`, 'success');
        this.dialogDelete = false;
        await this.fetchTemplates();
      } catch (err) {
        this.notify('Delete failed: ' + (err.response?.data?.error || err.message), 'error');
      } finally {
        this.deleting = false;
      }
    },

    // ── Utility ──────────────────────────────────────────────────────────

    notify(message, color = 'success') {
      this.snackbar = { show: true, message, color };
    },
  },
};
</script>

<style scoped>
.notification-template-page {
  padding: 20px;
}

.template-list-item {
  border: 1px solid rgba(0, 0, 0, 0.08);
  transition: box-shadow 0.2s ease;
}

.template-list-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.template-body-preview {
  font-family: 'Fira Code', 'Courier New', monospace;
  font-size: 0.82rem;
  opacity: 0.75;
}

.rendered-output pre {
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  font-family: 'Fira Code', 'Courier New', monospace;
}

.font-mono textarea {
  font-family: 'Fira Code', 'Courier New', monospace !important;
  font-size: 0.85rem;
}
</style>
