#!/bin/bash
# Build Meeting Notes.app
#
#   ./build.sh            build into dist.noindex/ (Spotlight skips it, so only
#                         the installed app shows up there)
#   ./build.sh --install  build, then copy into /Applications
#   ./build.sh --make-identity
#                         once per Mac: a self-signed certificate in the login
#                         keychain to sign with, so macOS keeps the app's
#                         permissions (Accessibility, microphone) across rebuilds
#
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
say() { printf "\033[1m==>\033[0m %s\n" "$1"; }

# An ad-hoc signature changes with every build, and macOS takes each build for a
# new app that has to be given its permissions again. A certificate of our own
# keeps the signature's identity the same from one build to the next.
IDENTITY="Meeting Notes local signing"
has_identity() { security find-identity -p codesigning | grep -q "\"$IDENTITY\""; }

if [ "${1:-}" = "--make-identity" ]; then
  if has_identity; then say "Already in the keychain: $IDENTITY"; exit 0; fi
  TMP=$(mktemp -d)
  trap 'rm -rf "$TMP"' EXIT
  # The system's LibreSSL: its .p12 is one the keychain can import.
  /usr/bin/openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=$IDENTITY" \
    -addext "keyUsage=critical,digitalSignature" -addext "extendedKeyUsage=critical,codeSigning" \
    -keyout "$TMP/key.pem" -out "$TMP/cert.pem" 2>/dev/null
  /usr/bin/openssl pkcs12 -export -inkey "$TMP/key.pem" -in "$TMP/cert.pem" \
    -out "$TMP/identity.p12" -passout pass:meeting-notes
  security import "$TMP/identity.p12" -k "$HOME/Library/Keychains/login.keychain-db" \
    -P meeting-notes -T /usr/bin/codesign >/dev/null
  has_identity || { echo "The certificate did not make it into the keychain"; exit 1; }
  say "Made: $IDENTITY. Builds are signed with it from now on."
  exit 0
fi

if [ ! -x "$PY" ]; then
  say "Creating the virtualenv"
  BASE_PY=$(command -v python3.11 || command -v python3)
  "$BASE_PY" -m venv .venv
fi

say "Installing build dependencies"
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r requirements.txt py2app

say "Building the window (React)"
command -v npm >/dev/null || { echo "npm not found. Install it: brew install node"; exit 1; }
npm ci --prefix ui --no-audit --no-fund >/dev/null
npm run build --prefix ui >/dev/null

say "Building the recorder (Swift)"
mkdir -p build
swiftc -O -o build/mn-recorder recorder/main.swift \
  -framework CoreAudio -framework AVFoundation -framework AppKit -framework ApplicationServices 2>build/swiftc.log \
  || { echo "The recorder did not compile:"; cat build/swiftc.log; exit 1; }

say "Drawing the icons"
"$PY" assets/make_icon.py --icns >/dev/null

say "Building the app"
DIST=dist.noindex
rm -rf "$DIST" build/bdist* build/lib*
LOG=build/py2app.log
"$PY" setup.py py2app --dist-dir "$DIST" >"$LOG" 2>&1 || {
  echo "Build failed. Last lines of $LOG:"; tail -30 "$LOG"; exit 1; }

APP="$DIST/Meeting Notes.app"
[ -d "$APP" ] || { echo "No app produced; see $LOG"; exit 1; }

# Signed, so macOS keeps the app's permissions between launches instead of
# asking about Outlook and notifications every single time.
# Next to the app's own executable: started by the app, it is the app that
# macOS asks about the microphone and the system audio, not the helper.
cp build/mn-recorder "$APP/Contents/MacOS/mn-recorder"

if has_identity; then SIGN="$IDENTITY"; else SIGN=-; fi
say "Signing ($([ "$SIGN" = - ] && echo "ad-hoc; ./build.sh --make-identity keeps permissions across builds" || echo "$SIGN"))"
# An unsigned app loses its Keychain and Outlook permissions, so a failure here
# stops the build instead of producing an app that half works.
codesign --force --sign "$SIGN" "$APP/Contents/MacOS/mn-recorder" || { echo "codesign failed"; exit 1; }
codesign --force --deep --sign "$SIGN" "$APP" || { echo "codesign failed"; exit 1; }
codesign --verify --deep --strict "$APP" || { echo "the signature does not verify"; exit 1; }

say "Built: $APP  ($(du -sh "$APP" | cut -f1))"

if [ "${1:-}" = "--install" ]; then
  say "Installing to /Applications"
  rm -rf "/Applications/Meeting Notes.app"
  cp -R "$APP" /Applications/
  say "Open it from Launchpad, or: open '/Applications/Meeting Notes.app'"
else
  say "Try it: open '$APP'"
  say "Install it: ./build.sh --install"
fi
