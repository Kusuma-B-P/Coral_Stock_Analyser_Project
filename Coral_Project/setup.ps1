# setup.ps1 -- One-click setup for Stock Move Analyzer on Windows
# Run with: powershell -ExecutionPolicy Bypass -File setup.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Stock Move Analyzer -- Setup for Windows"      -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# -- Step 1: Install Coral -----------------------------------------------
Write-Host "Step 1: Installing Coral CLI..." -ForegroundColor Yellow

$coralZip  = "coral-x86_64-pc-windows-msvc.zip"
$coralDir  = "coral-bin"
# Install into the project folder on D: to avoid C: space issues
$coralDest = (Get-Location).Path

$env:TEMP = "D:\Temp"
$env:TMP  = "D:\Temp"
New-Item -ItemType Directory -Force -Path "D:\Temp" | Out-Null

Invoke-WebRequest `
  -Uri "https://github.com/withcoral/coral/releases/latest/download/$coralZip" `
  -OutFile $coralZip

Expand-Archive -Path $coralZip -DestinationPath $coralDir -Force
Copy-Item "$coralDir\coral.exe" "$coralDest\coral.exe" -Force

# Add project folder to PATH for this session and permanently for user
if ($env:Path -notlike "*$coralDest*") {
    [Environment]::SetEnvironmentVariable(
        "Path",
        "$coralDest;$([Environment]::GetEnvironmentVariable('Path','User'))",
        "User"
    )
    $env:Path = "$coralDest;$env:Path"
}

$coralVersion = & "$coralDest\coral.exe" --version 2>&1
Write-Host "Coral installed: $coralVersion" -ForegroundColor Green

# -- Step 2: Python dependencies -----------------------------------------
Write-Host ""
Write-Host "Step 2: Installing Python dependencies..." -ForegroundColor Yellow
$pipExe = Join-Path (Get-Location).Path "venv\Scripts\pip3.exe"
if (Test-Path $pipExe) {
    & $pipExe install yfinance requests python-dotenv groq google-genai mplfinance matplotlib
} else {
    pip install yfinance requests python-dotenv groq google-genai mplfinance matplotlib
}
Write-Host "Python dependencies installed." -ForegroundColor Green

# -- Step 3: Create data directory ----------------------------------------
New-Item -ItemType Directory -Force -Path "data" | Out-Null

# -- Step 4: Configure API keys -------------------------------------------
Write-Host ""
Write-Host "Step 3: Configure API keys" -ForegroundColor Yellow
Write-Host "  Finnhub (free):  https://finnhub.io"
Write-Host "  Groq (free):     https://console.groq.com"
Write-Host "  Gemini (free):   https://aistudio.google.com/app/apikey"
Write-Host ""

$finnhubKey = Read-Host "Enter your Finnhub API key"
$groqKey    = Read-Host "Enter your Groq API key"
$geminiKey  = Read-Host "Enter your Gemini API key"

@"
FINNHUB_API_KEY=$finnhubKey
GROQ_API_KEY=$groqKey
GEMINI_API_KEY=$geminiKey
"@ | Out-File -FilePath ".env" -Encoding UTF8

Write-Host ".env file created." -ForegroundColor Green

# -- Step 5: Patch absolute path in stock_prices.yaml --------------------
Write-Host ""
Write-Host "Step 4: Patching absolute path into stock_prices.yaml..." -ForegroundColor Yellow

$absPath  = (Get-Location).Path.Replace("\", "/")
$yamlPath = "sources/stock_prices.yaml"
(Get-Content $yamlPath) `
    -replace "REPLACE_WITH_ABSOLUTE_PATH", $absPath | `
    Set-Content $yamlPath

Write-Host "Path set to: $absPath" -ForegroundColor Green

# -- Step 6: Register Coral sources --------------------------------------
Write-Host ""
Write-Host "Step 5: Registering Coral sources..." -ForegroundColor Yellow
$env:FINNHUB_API_KEY = $finnhubKey
$coral = "$coralDest\coral.exe"

Write-Host "  Adding finnhub..."
& $coral source add --file ./sources/finnhub.yaml

Write-Host "  Adding sec_edgar..."
& $coral source add --file ./sources/sec_edgar.yaml

Write-Host "  Adding stock_prices..."
& $coral source add --file ./sources/stock_prices.yaml

Write-Host ""
& $coral source list

# -- Done ----------------------------------------------------------------
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Setup Complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Run your first analysis:"
Write-Host "  .\venv\Scripts\python.exe analyze.py NVDA" -ForegroundColor Yellow
Write-Host ""