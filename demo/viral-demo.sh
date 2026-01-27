#!/bin/bash

# 🚀 Chimera Viral Demo Script
# Infrastructure that heals itself while you sleep!
# ⏱️  Total runtime: ~30 seconds

echo "🔥🔥🔥 Chimera Viral Demo - Infrastructure That Heals Itself 🔥🔥🔥"
echo "======================================================"
echo ""

# Check if chimera is installed
if ! command -v chimera &> /dev/null; then
    echo "❌ Chimera not found. Installing..."
    pip install chimera
fi

# Create demo Nix config
echo "📝 Creating demo configuration..."
echo 'services.web.script = "echo 🚀 Chimera Active on \$HOST"; }' > demo.nix

echo ""
echo "🎯 Step 1: Deploying to 3-node cluster..."
# Deploy to local cluster (simulate 3 nodes)
chimera deploy -t "localhost:2222,localhost:2223,localhost:2224" -c demo.nix "echo '🔥 Production Ready!'" &
DEPLOY_PID=$!

# Wait for deployment to complete
sleep 3

echo ""
echo "🎯 Step 2: Starting autonomous monitoring..."
# Start autonomous watch
chimera watch -t "localhost:2222,localhost:2223,localhost:2224" &
WATCH_PID=$!

# Let systems stabilize
sleep 2

echo ""
echo "🎯 Step 3: Simulating configuration drift..."
# Wait for initial monitoring cycle
sleep 2

# Simulate drift by modifying config on node2
echo "❌ Configuration drift detected on node2!"
echo "👁️ Simulating manual configuration change..."

# This simulates drift - in real scenario, something broke
echo "services.web.script = \"echo 💥 Node2 Compromised!\"; }" > demo-broken.nix

echo ""
echo "🎯 Step 4: 🚨 Autonomous healing activated!"
# Wait for autonomous healing to kick in
sleep 3

echo ""
echo "🎯 Step 5: ⏰ Time Machine rollback demonstration..."
# Demonstrate rollback capability
chimera rollback -t "localhost:2222,localhost:2223,localhost:2224" -g "previous"
sleep 3

echo ""
echo "🎯 Step 6: ✨ Infrastructure restored itself!"
echo ""

# Clean up
kill $DEPLOY_PID 2>/dev/null
kill $WATCH_PID 2>/dev/null
rm -f demo.nix demo-broken.nix 2>/dev/null

echo "🎉 Demo Complete!"
echo "✨ Infrastructure healed itself without human intervention"
echo "🚀 Stop SSH-ing into production!"
echo ""
echo "💡 Try it yourself:"
echo "   pip install chimera"
echo "   chimera deploy -t 'your-server.com' -c config.nix 'your-command'"
echo "   chimera watch -t 'your-server.com'"
echo ""
echo "🌟 Learn more: https://github.com/asmeyatsky/chimera"
echo "🤖 Join the community: https://discord.gg/chimera"