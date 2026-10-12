#!/usr/bin/env python3
"""
Script to add portfolio UI integration to streamlit_app.py with proper indentation.
This ensures clean integration without manual indentation errors.
"""

import re

# Read the current streamlit_app.py
with open('/workspace/streamlit_app.py', 'r') as f:
    content = f.read()

# 1. Add backtest mode selector after "Settings" header
mode_selector = '''        # Backtest mode selection
        backtest_mode = st.radio(
            "回測模式 / Backtest Mode",
            ["單一資產 / Single Asset", "投資組合 / Multi-Asset Portfolio"],
            help="選擇單一資產策略回測或多資產投資組合回測 / Choose single-asset strategy or multi-asset portfolio backtest"
        )
        
        st.markdown("---")
        
        # Strategy selection only for single asset mode
        if backtest_mode == "單一資產 / Single Asset":'''

# Replace the strategy_type definition
content = re.sub(
    r"        st\.header\(\"⚙️ 回測設定 / Settings\"\)\s+strategy_type = st\.selectbox",
    f'''        st.header("⚙️ 回測設定 / Settings")
        
{mode_selector}
            strategy_type = st.selectbox''',
    content
)

# 2. Wrap data source radio for single asset only
content = re.sub(
    r'        st\.subheader\("📊 數據來源 / Data Source"\)\s+data_source = st\.radio\(\s+"數據類型 / Data Type",',
    '''        st.subheader("📊 數據來源 / Data Source")
        
        # Portfolio mode only supports Yahoo Finance
        if backtest_mode == "投資組合 / Multi-Asset Portfolio":
            data_source = "Yahoo Finance"
            st.info("💡 投資組合模式僅支援 Yahoo Finance / Portfolio mode uses Yahoo Finance only")
        else:
            data_source = st.radio(
                "數據類型 / Data Type",''',
    content
)

# Save the modified content
with open('/workspace/streamlit_app.py', 'w') as f:
    f.write(content)

print("✓ Portfolio UI integration added to streamlit_app.py")
print("Note: Full UI integration requires additional manual steps for complex sections")
print("The core portfolio module is fully functional via examples/portfolio_demo.py")
