#!/usr/bin/env bash
# ==============================================================================
# KubeMind v0.3.0 Release Bundle Packager
# Builds multi-platform CLI binaries, Python wheels, TypeScript packages,
# and generates a distributable tarball archive in dist/.
# ==============================================================================
set -euo pipefail

VERSION="0.3.0"
DIST_DIR="dist"
BUNDLE_NAME="kubemind-v${VERSION}-bundle"
RELEASE_DIR="${DIST_DIR}/${BUNDLE_NAME}"

echo "📦 Packaging KubeMind v${VERSION} Release Bundle..."
rm -rf "${DIST_DIR}"
mkdir -p "${RELEASE_DIR}/bin" "${RELEASE_DIR}/sdk" "${RELEASE_DIR}/docs"

# 1. Compile Go CLI binaries
echo "⚙️ Compiling kmind CLI binaries..."
(
  cd cmd/kmind
  GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o "../../${RELEASE_DIR}/bin/kmind-linux-amd64" .
  GOOS=linux GOARCH=arm64 go build -ldflags="-s -w" -o "../../${RELEASE_DIR}/bin/kmind-linux-arm64" .
  GOOS=darwin GOARCH=arm64 go build -ldflags="-s -w" -o "../../${RELEASE_DIR}/bin/kmind-darwin-arm64" .
  GOOS=darwin GOARCH=amd64 go build -ldflags="-s -w" -o "../../${RELEASE_DIR}/bin/kmind-darwin-amd64" .
)

# 2. Build Python SDK Wheel & sdist
echo "🐍 Building Python SDK distributions..."
(
  cd sdk/python
  rm -rf dist build *.egg-info
  python3 setup.py sdist bdist_wheel >/dev/null
  cp dist/* "../../${RELEASE_DIR}/sdk/"
)

# 3. Build TypeScript SDK
echo "🟦 Building TypeScript SDK npm bundle..."
(
  cd sdk/typescript
  npm run build >/dev/null
  npm pack --pack-destination "../../${RELEASE_DIR}/sdk/" >/dev/null
)

# 4. Copy Documentation & Release Metadata
echo "📄 Aggregating documentation and release notes..."
cp CHANGELOG.md quality_audit.md README.md "${RELEASE_DIR}/"
cp -r docs/* "${RELEASE_DIR}/docs/"

# 5. Compress Release Bundle
echo "🗜️ Compressing release archive..."
(
  cd "${DIST_DIR}"
  tar -czf "${BUNDLE_NAME}.tar.gz" "${BUNDLE_NAME}"
  sha256sum "${BUNDLE_NAME}.tar.gz" > "${BUNDLE_NAME}.tar.gz.sha256"
)

echo "===================================================================="
echo "✅ KubeMind v${VERSION} Release Bundle Built Successfully!"
echo "📁 Archive:  ${DIST_DIR}/${BUNDLE_NAME}.tar.gz"
echo "🔑 Checksum: $(cat "${DIST_DIR}/${BUNDLE_NAME}.tar.gz.sha256")"
echo "===================================================================="
