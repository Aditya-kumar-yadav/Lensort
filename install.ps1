# Lensort 1-Line Installer for Windows
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " 📸 Lensort — Installing Smart Media Sorter on your PC" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

$RepoUrl = "https://github.com/Aditya-kumar-yadav/Lensort.git"
$InstallDir = "$env:USERPROFILE\.lensort"

if (Test-Path $InstallDir) {
    Write-Host "Updating existing Lensort installation..." -ForegroundColor Yellow
    Set-Location $InstallDir
    git pull origin main
} else {
    Write-Host "Cloning Lensort repository..." -ForegroundColor Yellow
    git clone $RepoUrl $InstallDir
    Set-Location $InstallDir
}

# Install Python requirements
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "Installing Python requirements (Pillow, rich)..." -ForegroundColor Cyan
    python -m pip install -r requirements.txt --quiet
    python -m pip install -e . --quiet
    Write-Host "✅ Lensort Python CLI & Desktop GUI ready!" -ForegroundColor Green
    Write-Host "Launch GUI anytime by typing: python -m gallery_sorter.gui" -ForegroundColor White
}

# Build Rust Binary if Cargo is installed
if (Get-Command cargo -ErrorAction SilentlyContinue) {
    Write-Host "Building blazing-fast Rust engine..." -ForegroundColor Cyan
    Set-Location "$InstallDir\rust_engine"
    cargo build --release --quiet
    Write-Host "✅ Lensort-RS Native Engine compiled!" -ForegroundColor Green
}

Write-Host "`n🎉 Installation Complete!" -ForegroundColor Green
Write-Host "Run GUI: python $InstallDir\gui.py" -ForegroundColor Cyan
Write-Host "Run CLI: python $InstallDir\main.py <folder>" -ForegroundColor Cyan
