#!/usr/bin/env bash
# Lensort 1-Line Installer for macOS & Linux
set -e

echo -e "\033[1;36m==========================================================\033[0m"
echo -e "\033[1;32m 📸 Lensort — Installing Smart Media Sorter on your machine\033[0m"
echo -e "\033[1;36m==========================================================\033[0m"

INSTALL_DIR="$HOME/.lensort"
REPO_URL="https://github.com/Aditya-kumar-yadav/Lensort.git"

if [ -d "$INSTALL_DIR" ]; then
    echo -e "\033[1;33mUpdating existing Lensort installation...\033[0m"
    cd "$INSTALL_DIR" && git pull origin main
else
    echo -e "\033[1;33mCloning Lensort repository...\033[0m"
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

if command -v python3 &>/dev/null; then
    echo -e "\033[1;36mInstalling Python dependencies...\033[0m"
    python3 -m pip install -r requirements.txt --quiet || true
    python3 -m pip install -e . --quiet || true
    echo -e "\033[1;32m✅ Lensort Python CLI & GUI Ready!\033[0m"
fi

if command -v cargo &>/dev/null; then
    echo -e "\033[1;36mCompiling native Rust binary...\033[0m"
    cd "$INSTALL_DIR/rust_engine"
    cargo build --release --quiet || true
    echo -e "\033[1;32m✅ Lensort Rust Engine Ready!\033[0m"
fi

echo -e "\n\033[1;32m🎉 Installation Complete!\033[0m"
echo -e "Launch GUI: \033[1;36mpython3 $INSTALL_DIR/gui.py\033[0m"
echo -e "Launch CLI: \033[1;36mpython3 $INSTALL_DIR/main.py <folder>\033[0m"
