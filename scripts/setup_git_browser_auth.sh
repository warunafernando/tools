#!/bin/bash
# Setup Git to use browser popup for GitHub authentication
set -e

echo "Installing git-credential-oauth (browser-based auth)..."
sudo apt-get install -y git-credential-oauth

echo "Configuring Git credential helper..."
git config --global --unset-all credential.helper 2>/dev/null || true
git config --global --add credential.helper "cache --timeout 7200"
git config --global --add credential.helper oauth

echo "Done. Next time you run 'git push', a browser window will open for authentication."
echo "Test with: cd /home/mini/tools && git push origin main"
