#!/usr/bin/env bash
set -euo pipefail

LOG="/tmp/autoflow-full-validate-$(date +%s).log"
echo "Autoflow validation log - $(date)" > "$LOG"

echo "==== Repo top-level ====" | tee -a "$LOG"
ls -la . | tee -a "$LOG"

echo -e "\n==== Tree (depth=3) ====" | tee -a "$LOG"
if command -v tree >/dev/null 2>&1; then
tree -a -L 3 -I 'node_modules|venv|.venv|dist|build|.git|**pycache**' | tee -a "$LOG" || true
else
find . -maxdepth 3 -print | tee -a "$LOG"
fi

echo -e "\n==== Find literal-brace dirs ====" | tee -a "$LOG"
find . -type d ( -name '*{*' -o -name '*}*' ) -print | tee -a "$LOG" || true

echo -e "\n==== PYTHON: compileall ====" | tee -a "$LOG"
python3 -m compileall -q . 2>&1 | tee -a "$LOG" || true

echo -e "\n==== PYTHON: import checks ====" | tee -a "$LOG"

check_import() {
mod="$1"

python3 - <<PY 2>&1 | tee -a "$LOG"
import sys
import importlib

sys.path.insert(0, '')

try:
m = importlib.import_module("$mod")
print("Imported $mod OK")

```
if hasattr(m, "app"):
    print("$mod has app")

if callable(getattr(m, "create_app", None)):
    print("$mod exposes create_app")
```

except Exception as e:
print("Import error for $mod:", repr(e))
PY
}

for candidate in main app.main backend.main src.main app backend
do
check_import "$candidate"
done

echo -e "\n==== UVICORN ====" | tee -a "$LOG"

if command -v uvicorn >/dev/null 2>&1; then
uvicorn --version 2>&1 | tee -a "$LOG" || true
else
echo "uvicorn not installed" | tee -a "$LOG"
fi

echo -e "\n==== FRONTEND ====" | tee -a "$LOG"

if [ -d frontend ]; then
pushd frontend >/dev/null

if command -v npm >/dev/null 2>&1; then

```
npm ci --no-audit --no-fund 2>&1 | tee -a "$LOG" || \
npm install --no-audit --no-fund 2>&1 | tee -a "$LOG" || true

npx tsc --noEmit 2>&1 | tee -a "$LOG" || true

npm run build --if-present 2>&1 | tee -a "$LOG" || true
```

else
echo "npm not installed" | tee -a "$LOG"
fi

popd >/dev/null
fi

echo -e "\n==== DOCKER COMPOSE ====" | tee -a "$LOG"

if [ -f docker-compose.yml ]; then

if command -v docker-compose >/dev/null 2>&1; then
docker-compose -f docker-compose.yml config 2>&1 | tee -a "$LOG" || true

elif command -v docker >/dev/null 2>&1; then
docker compose -f docker-compose.yml config 2>&1 | tee -a "$LOG" || true

fi
fi

echo -e "\n==== ENV EXAMPLE ====" | tee -a "$LOG"

if [ -f .env.example ]; then
sed -n '1,200p' .env.example | tee -a "$LOG"
fi

echo -e "\nValidation finished"
echo "Log saved to: $LOG"

exit 0

