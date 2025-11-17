#!/bin/bash

set -e

echo "🔨 Building JellyStream Plugin..."

cd JellyStream

echo "📦 Restoring dependencies..."
dotnet restore

echo "🏗️  Building Release..."
dotnet build --configuration Release

echo ""
echo "✅ Build complete!"
echo ""
echo "📁 Plugin files: $(pwd)/bin/Release/net8.0/"
echo ""
echo "📝 To install:"
echo "   sudo mkdir -p /var/lib/jellyfin/plugins/JellyStream"
echo "   sudo cp bin/Release/net8.0/* /var/lib/jellyfin/plugins/JellyStream/"
echo "   sudo systemctl restart jellyfin"
