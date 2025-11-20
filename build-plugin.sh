#!/bin/bash
set -e

VERSION=${1:-1.0.0}
JELLYFIN_HOST=${JELLYFIN_HOST:-jellyfin}

echo "Building JellyStream Plugin v${VERSION} on ${JELLYFIN_HOST}..."

# Copy plugin source to Jellyfin server
echo "Copying source to ${JELLYFIN_HOST}..."
rsync -av --delete plugin/JellyStream/ ${JELLYFIN_HOST}:/tmp/jellystream-build/

# Build on Jellyfin server (has .NET)
echo "Building on ${JELLYFIN_HOST}..."
ssh ${JELLYFIN_HOST} "cd /tmp/jellystream-build && dotnet build -c Release"

# Create local releases directory
mkdir -p releases

# Package and copy back
echo "Packaging..."
ssh ${JELLYFIN_HOST} "cd /tmp/jellystream-build/bin/Release/net8.0 && \
    mkdir -p jellyfin-plugin-jellystream && \
    cp JellyStream.dll jellyfin-plugin-jellystream/ && \
    zip -r jellyfin-plugin-jellystream-${VERSION}.zip jellyfin-plugin-jellystream"

# Copy package back to local machine
scp ${JELLYFIN_HOST}:/tmp/jellystream-build/bin/Release/net8.0/jellyfin-plugin-jellystream-${VERSION}.zip releases/

# Generate checksum
CHECKSUM=$(md5sum releases/jellyfin-plugin-jellystream-${VERSION}.zip | awk '{print $1}')

echo ""
echo "✅ Plugin built successfully!"
echo "📦 Package: releases/jellyfin-plugin-jellystream-${VERSION}.zip"
echo "🔑 MD5 Checksum: ${CHECKSUM}"
echo ""
echo "Next steps:"
echo "1. Create a GitHub release with tag v${VERSION}"
echo "2. Upload releases/jellyfin-plugin-jellystream-${VERSION}.zip to the release"
echo "3. Update manifest.json:"
echo "   - sourceUrl: https://github.com/Macro002/JellyStream/releases/download/v${VERSION}/jellyfin-plugin-jellystream-${VERSION}.zip"
echo "   - checksum: ${CHECKSUM}"
echo "   - timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
