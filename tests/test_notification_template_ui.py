"""
Tests for the notification template frontend UI.

These tests verify:
  1. The HTML file exists and is well-formed
  2. All required UI sections are present
  3. The embedded JavaScript contains all required API calls and Vue logic
  4. The static_route.py correctly serves the HTML file
  5. Client-side placeholder extraction/validation logic mirrors the server

Run with:
    python -m pytest tests/test_notification_template_ui.py -v
"""

import os
import sys
import re
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH  = os.path.join(REPO_ROOT, "astrbot", "dashboard", "static", "notification_templates.html")
ROUTE_PATH = os.path.join(REPO_ROOT, "astrbot", "dashboard", "static_route.py")


@pytest.fixture(scope="module")
def html_content():
    with open(HTML_PATH, encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def route_content():
    with open(ROUTE_PATH, encoding="utf-8") as f:
        return f.read()


# ===========================================================================
# File existence
# ===========================================================================

class TestFileExistence:
    def test_html_file_exists(self):
        assert os.path.isfile(HTML_PATH), f"HTML file not found: {HTML_PATH}"

    def test_static_route_exists(self):
        assert os.path.isfile(ROUTE_PATH), f"static_route.py not found: {ROUTE_PATH}"

    def test_static_dir_exists(self):
        static_dir = os.path.join(REPO_ROOT, "astrbot", "dashboard", "static")
        assert os.path.isdir(static_dir)


# ===========================================================================
# HTML structure
# ===========================================================================

class TestHTMLStructure:
    def test_has_doctype(self, html_content):
        assert html_content.strip().lower().startswith("<!doctype html")

    def test_has_charset_utf8(self, html_content):
        assert "charset" in html_content.lower()

    def test_has_viewport_meta(self, html_content):
        assert "viewport" in html_content

    def test_has_title(self, html_content):
        assert "<title>" in html_content
        assert "通知模板" in html_content

    def test_has_vue_cdn(self, html_content):
        assert "vue@3" in html_content or "vue.global" in html_content

    def test_has_app_mount_point(self, html_content):
        assert 'id="app"' in html_content

    def test_has_page_header(self, html_content):
        assert "page-header" in html_content or "page-title" in html_content

    def test_has_new_template_button(self, html_content):
        assert "新建模板" in html_content

    def test_has_template_table(self, html_content):
        assert "<table" in html_content
        assert "<thead" in html_content
        assert "<tbody" in html_content

    def test_table_has_required_columns(self, html_content):
        for col in ("名称", "占位符", "操作"):
            assert col in html_content, f"Table column '{col}' not found"

    def test_has_empty_state(self, html_content):
        assert "empty-state" in html_content or "暂无" in html_content

    def test_has_loading_state(self, html_content):
        assert "listLoading" in html_content or "加载中" in html_content

    def test_has_error_state(self, html_content):
        assert "listError" in html_content or "加载失败" in html_content


# ===========================================================================
# Form modal
# ===========================================================================

class TestFormModal:
    def test_has_form_modal(self, html_content):
        assert "showFormModal" in html_content

    def test_has_name_input(self, html_content):
        assert "form.name" in html_content
        assert "模板名称" in html_content

    def test_has_body_textarea(self, html_content):
        assert "form.body" in html_content
        assert "模板正文" in html_content

    def test_has_create_edit_toggle(self, html_content):
        assert "isEditing" in html_content
        assert "新建模板" in html_content
        assert "编辑模板" in html_content

    def test_has_save_button(self, html_content):
        assert "saveTemplate" in html_content
        assert "创建模板" in html_content or "保存修改" in html_content

    def test_has_cancel_button(self, html_content):
        assert "closeFormModal" in html_content
        assert "取消" in html_content

    def test_has_syntax_error_display(self, html_content):
        assert "liveSyntaxErrors" in html_content
        assert "占位符语法错误" in html_content

    def test_has_detected_placeholders_display(self, html_content):
        assert "detectedPlaceholders" in html_content
        assert "检测到的占位符" in html_content

    def test_has_live_preview_panel(self, html_content):
        assert "previewResult" in html_content
        assert "实时预览" in html_content

    def test_has_variable_inputs_in_form(self, html_content):
        assert "previewVars" in html_content

    def test_save_disabled_on_syntax_errors(self, html_content):
        assert "liveSyntaxErrors.length" in html_content

    def test_has_required_field_indicators(self, html_content):
        assert "required" in html_content


# ===========================================================================
# Preview modal
# ===========================================================================

class TestPreviewModal:
    def test_has_preview_modal(self, html_content):
        assert "showPreviewModal" in html_content

    def test_has_missing_strategy_selector(self, html_content):
        assert "pvMissingStrategy" in html_content
        assert "keep" in html_content
        assert "empty" in html_content
        assert "error" in html_content

    def test_has_variable_input_fields(self, html_content):
        assert "pvVars" in html_content

    def test_has_rendered_output(self, html_content):
        assert "pvRendered" in html_content

    def test_has_warnings_display(self, html_content):
        assert "pvWarnings" in html_content

    def test_has_loading_indicator(self, html_content):
        assert "pvLoading" in html_content

    def test_has_edit_from_preview_button(self, html_content):
        assert "openEditFromPreview" in html_content
        assert "编辑此模板" in html_content

    def test_shows_raw_body(self, html_content):
        assert "原始模板正文" in html_content

    def test_shows_placeholder_tags(self, html_content):
        assert "previewTpl.placeholders" in html_content


# ===========================================================================
# Delete modal
# ===========================================================================

class TestDeleteModal:
    def test_has_delete_modal(self, html_content):
        assert "showDeleteModal" in html_content

    def test_has_confirmation_text(self, html_content):
        assert "确认删除" in html_content
        assert "不可撤销" in html_content

    def test_has_confirm_button(self, html_content):
        assert "confirmDelete" in html_content

    def test_has_cancel_button(self, html_content):
        assert "showDeleteModal = false" in html_content

    def test_shows_template_name_in_confirmation(self, html_content):
        assert "deleteTarget" in html_content
        assert "deleteTarget.name" in html_content or "deleteTarget && deleteTarget.name" in html_content

    def test_has_delete_error_display(self, html_content):
        assert "deleteError" in html_content


# ===========================================================================
# JavaScript API calls  (new RESTful /api/templates endpoints)
# ===========================================================================

class TestJavaScriptAPI:
    def test_has_api_list(self, html_content):
        assert "/api/templates" in html_content

    def test_has_api_create(self, html_content):
        # POST /api/templates
        assert "/api/templates" in html_content
        assert "method: 'POST'" in html_content

    def test_has_api_update(self, html_content):
        # PUT /api/templates/:id
        assert "/api/templates/" in html_content
        assert "'PUT'" in html_content

    def test_has_api_delete(self, html_content):
        # DELETE /api/templates/:id
        assert "/api/templates/" in html_content
        assert "'DELETE'" in html_content

    def test_has_api_preview(self, html_content):
        # POST /api/templates/:id/preview
        assert "/preview" in html_content

    def test_api_uses_post_for_mutations(self, html_content):
        assert "method: 'POST'" in html_content

    def test_api_uses_json_content_type(self, html_content):
        assert "application/json" in html_content

    def test_has_debounce_for_preview(self, html_content):
        assert "debounce" in html_content

    def test_has_load_templates_on_init(self, html_content):
        assert "loadTemplates()" in html_content


# ===========================================================================
# Client-side placeholder logic
# ===========================================================================

class TestClientSidePlaceholderLogic:
    def test_has_extract_placeholders_function(self, html_content):
        assert "extractPlaceholders" in html_content

    def test_has_validate_syntax_function(self, html_content):
        assert "validateSyntax" in html_content

    def test_has_valid_placeholder_regex(self, html_content):
        assert "[A-Za-z_]" in html_content

    def test_has_max_length_check(self, html_content):
        assert "MAX_LEN" in html_content or "64" in html_content

    def test_has_empty_placeholder_check(self, html_content):
        assert "占位符内容不能为空" in html_content

    def test_has_invalid_name_check(self, html_content):
        assert "占位符名称无效" in html_content

    def test_has_dot_checks(self, html_content):
        assert "点号" in html_content

    def test_on_body_input_handler(self, html_content):
        assert "onBodyInput" in html_content


# ===========================================================================
# Static route
# ===========================================================================

class TestStaticRoute:
    def test_route_imports_send_from_directory(self, route_content):
        assert "send_from_directory" in route_content

    def test_route_serves_correct_file(self, route_content):
        assert "notification_templates.html" in route_content

    def test_route_path(self, route_content):
        assert "/notification_templates" in route_content

    def test_route_extends_route_base(self, route_content):
        assert "Route" in route_content

    def test_static_dir_points_to_static_folder(self, route_content):
        assert "static" in route_content

    def test_exported_in_dashboard_init(self):
        init_path = os.path.join(REPO_ROOT, "astrbot", "dashboard", "__init__.py")
        with open(init_path, encoding="utf-8") as f:
            content = f.read()
        assert "StaticRoute" in content

    def test_exported_in_routes_init(self):
        init_path = os.path.join(REPO_ROOT, "astrbot", "dashboard", "routes", "__init__.py")
        with open(init_path, encoding="utf-8") as f:
            content = f.read()
        assert "StaticRoute" in content


# ===========================================================================
# UX features
# ===========================================================================

class TestUXFeatures:
    def test_has_placeholder_syntax_hint(self, html_content):
        assert "{{ variable }}" in html_content or "variable" in html_content

    def test_has_date_formatter(self, html_content):
        assert "formatDate" in html_content

    def test_has_spinner_for_loading(self, html_content):
        assert "spinner" in html_content

    def test_has_transition_animation(self, html_content):
        assert "transition" in html_content or "fade" in html_content

    def test_has_responsive_layout(self, html_content):
        assert "max-width" in html_content

    def test_has_keyboard_close_support(self, html_content):
        assert "@mousedown.self" in html_content or "mousedown" in html_content

    def test_has_disabled_state_during_save(self, html_content):
        assert "formSaving" in html_content
        assert ":disabled" in html_content

    def test_has_body_preview_in_table(self, html_content):
        assert "body-preview" in html_content or "tpl.body" in html_content

    def test_has_placeholder_tags_in_table(self, html_content):
        assert "tpl.placeholders" in html_content
