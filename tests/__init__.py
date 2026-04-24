
Tests for the notification template frontend UI.

These tests verify:
  1. The HTML file exists and is well-formed
  2. All required UI sections are present
  3. The embedded JavaScript contains all required API calls and Vue logic
  4. The static_route.py correctly serves the HTML file
  5. Client-side placeholder extraction/validation logic mirrors the server

Run with:
    python -m pytest tests/test_notification_template_ui.py -v
