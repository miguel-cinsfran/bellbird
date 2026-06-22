# [windows-only]
# Manual verification scenarios for ChatPanel:
# - conversation_display is read-only
# - Enter sends message
# - Shift+Enter inserts newline
# - Escape aborts generation
# - File dialog opens on attach
# - Image files are base64-encoded
# - Text files are read as UTF-8
# - Attachment label updates
# - Buttons disable/enable correctly
#
# Run on Windows 11 with NVDA:
# - Tab through controls, NVDA announces
# - Enter sends, Shift+Enter newline
# - Attach file, verify label changes
# - Start generation, verify buttons disabled
