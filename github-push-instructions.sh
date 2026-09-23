#!/bin/bash
# Instructions to manually push to GitHub from your local machine
# Run this script from the project root directory

set -e

# 1. Create the GitHub repository (if using gh CLI)
gh repo create patrick-ckf/algo-trading-backtester \
  --public \
  --description "Python algorithmic trading backtesting system with Streamlit dashboard" \
  --source=. \
  --remote=github \
  --push

# OR if gh is not available, do it manually:
# 1. Go to https://github.com/new
# 2. Create repo: patrick-ckf/algo-trading-backtester (public)
# 3. Then run:
#    git remote add github https://github.com/patrick-ckf/algo-trading-backtester.git
#    git push github main

echo "✅ Successfully pushed to GitHub!"
echo "Repository URL: https://github.com/patrick-ckf/algo-trading-backtester"
echo ""
echo "Next steps for Streamlit Cloud:"
echo "1. Go to https://share.streamlit.io"
echo "2. Click 'New app'"
echo "3. Repository: patrick-ckf/algo-trading-backtester"
echo "4. Branch: main"
echo "5. Main file path: streamlit_app.py"
echo "6. Click 'Deploy!'"
