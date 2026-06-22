# [windows-only]
# Manual verification scenarios for MainWindow:
# - Frame size is 1100x700
# - Splitter has ParamsPanel (left 280px) and ChatPanel (right)
# - Menu bar: Archivo (4 items), Ayuda (2 items)
# - AcceleratorTable: Ctrl+N, Ctrl+O, Ctrl+S, F5, Escape
# - StatusBar has 3 fields
# - Startup Ollama check: dialog shown when down
# - Startup Ollama check: models populated when up
# - Send message flow works end-to-end
# - Save/Load conversation works
# - Abort generation works
#
# Run on Windows 11 with NVDA:
# - Startup verification
# - Send message, streamed audio response
# - Attach image, verify vision
# - Save/load conversation
# - Abort with Escape
