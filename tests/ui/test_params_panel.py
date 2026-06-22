# [windows-only]
# Manual verification scenarios for ParamsPanel:
# - Panel construction with SplitterWindow parent
# - Sizer is wx.BoxSizer with wx.VERTICAL orientation
# - model_selector.GetCount() == 0 initially
# - set_models repopulates and selects first
# - get_model returns selected model
# - get_params returns correct defaults
# - Slider label updates on value change
# - Speech.speak called on slider change
#
# Run on Windows 11 with NVDA:
# - Tab through controls, NVDA announces labels
# - Change slider values, hear announcements
# - Verify reading order is correct
