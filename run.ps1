# Run straight from the source tree on Windows, without building the app.
#
#   powershell -ExecutionPolicy Bypass -File run.ps1
#
# Sets up whatever is missing: virtualenv, dependencies, the window, the model,
# and then opens the window, with the icon in the tray. Safe to run again at any
# time. The macOS counterpart is run.sh.
# Exit codes are checked by hand: with "Stop", Windows PowerShell turns any line
# a program writes to stderr (a pip notice, a failed import) into a fatal error.
Set-Location $PSScriptRoot

$Py = ".venv\Scripts\python.exe"
function Say($text) { Write-Host "==> $text" -ForegroundColor Cyan }
function Die($text) { Write-Host "==> $text" -ForegroundColor Red; exit 1 }

# --- virtualenv ---------------------------------------------------------
if (-not (Test-Path $Py)) {
    Say "Creating the virtualenv"
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3.11 -m venv .venv }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { python -m venv .venv }
    else { Die "Python not found. Install Python 3.11 from python.org" }
    if (-not (Test-Path $Py)) { Die "The virtualenv was not created" }
}

# --- dependencies -------------------------------------------------------
& $Py -c "import webview, pystray, soundcard, watchdog, jinja2, dotenv, docx, requests, keyring" 2>$null
if ($LASTEXITCODE -ne 0) {
    Say "Installing dependencies"
    & $Py -m pip install -q --upgrade pip
    & $Py -m pip install -q -r requirements.txt
    if ($LASTEXITCODE -ne 0) { Die "pip could not install requirements.txt" }
}

# --- the window ---------------------------------------------------------
# Rebuilt whenever its source is newer than the last build.
$built = Get-Item ui\dist\index.html -ErrorAction SilentlyContinue
$sources = Get-ChildItem ui\src, ui\index.html, ui\package.json -Recurse -File
if (-not $built -or ($sources | Where-Object { $_.LastWriteTime -gt $built.LastWriteTime })) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Die "npm not found. Install Node.js from nodejs.org" }
    Say "Building the window"
    if (-not (Test-Path ui\node_modules)) { npm ci --prefix ui --no-audit --no-fund | Out-Null }
    npm run build --prefix ui | Out-Null
    if ($LASTEXITCODE -ne 0) { Die "The window did not build: npm run build --prefix ui" }
}

# Settings, notes and logs live in the data folder (%APPDATA%\Meeting Notes),
# not here. MEETING_NOTES_DATA overrides it, for a run that must not touch it.

# --- Ollama -------------------------------------------------------------
# Not started here: the app wakes it when a meeting needs summarising.
$found = & $Py -c "import desktop; print(desktop.find('ollama'))"
if (-not $found) { Die "Ollama not found. Install it from ollama.com" }

# --- model --------------------------------------------------------------
$Model = & $Py -c "import llm; print(llm.MODEL)"
& $Py -c "import llm, sys; sys.exit(0 if llm.model_on_disk('$Model') else 1)"
if ($LASTEXITCODE -ne 0) {
    Say "Model $Model is not downloaded"
    $answer = Read-Host "    Download it now? That is several GB. [Y/n]"
    if ($answer -match "^[Nn]") {
        Write-Host "    Skipped. Download it from the window's settings, or run: ollama pull $Model"
    } else {
        & $found pull $Model
    }
}

# --- go -----------------------------------------------------------------
Say "Model:    $Model"
Say "Data:     $(& $Py -c 'import paths; print(paths.DATA)')"
Say "Watching: $(& $Py -c 'import paths; print(paths.inbox())')"
Say "The window opens; closing it leaves the icon in the tray. Quit from the tray to stop."
& $Py tray.py
