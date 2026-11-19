#!/usr/bin/env bash
# kind cluster, Istio, the sample app, then the BDD suite.
set -euo pipefail
cd "$(dirname "$0")/.."
ISTIO=1.24.2
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) PLATFORM=osx-arm64 ;; Darwin-x86_64) PLATFORM=osx-amd64 ;; Linux-x86_64) PLATFORM=linux-amd64 ;; Linux-aarch64) PLATFORM=linux-arm64 ;;
  *) echo "unsupported platform"; exit 1 ;;
esac
mkdir -p .cache
if [ ! -x ".cache/istio-$ISTIO/bin/istioctl" ]; then
  f="istioctl-$ISTIO-$PLATFORM.tar.gz"
  curl -fsSL -o ".cache/$f" "https://github.com/istio/istio/releases/download/$ISTIO/$f"
  curl -fsSL -o ".cache/$f.sha256" "https://github.com/istio/istio/releases/download/$ISTIO/$f.sha256"
  (cd .cache && echo "$(cut -d' ' -f1 "$f.sha256")  $f" | shasum -a 256 -c -)
  mkdir -p ".cache/istio-$ISTIO/bin" && tar -xzf ".cache/$f" -C ".cache/istio-$ISTIO/bin"
fi
export PATH="$PWD/.cache/istio-$ISTIO/bin:$PATH"
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python; export PYTHON=$PY

$PY -m pytest -q tests
kind delete cluster --name mesh-lab >/dev/null 2>&1 || true
kind create cluster --name mesh-lab --config mesh/kind.yaml --wait 120s >/dev/null
istioctl install --set profile=minimal -y >/dev/null
kubectl -n istio-system rollout status deploy/istiod --timeout=180s >/dev/null
kubectl apply -f mesh/app.yaml >/dev/null
for d in web-v1 web-v2 pay-good pay-bad client; do kubectl -n shop rollout status deploy/$d --timeout=240s >/dev/null; done
kubectl -n legacy rollout status deploy/legacy-client --timeout=120s >/dev/null
$PY -m meshctl apply mesh/traffic.yaml >/dev/null
$PY -m meshctl apply mesh/pay.yaml >/dev/null
istioctl analyze -n shop
$PY -m behave --no-capture features
echo "ALL PASS"
