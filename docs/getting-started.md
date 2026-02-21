# 🚀 Getting Started with Chimera

## 🎯 Quick Overview

Chimera is an **autonomous deployment engine** that combines Nix reproducibility with self-healing capabilities. Think of it as infrastructure that monitors, detects issues, and fixes itself without human intervention.

### 🎬 Key Concepts

**Autonomous Healing:** Your infrastructure automatically detects when configuration drift occurs and fixes it automatically.

**Time Machine Rollback:** Instantly rollback to ANY previous generation of your system.

**Fleet Management:** Deploy and monitor multiple nodes from a single interface.

**Real-Time Monitoring:** Beautiful dashboard showing live fleet status and health.

---

## 🚀 Installation

### Prerequisites

```bash
# Required dependencies
- Python 3.11+
- Nix (for building)
- Fabric (for remote execution)  
- tmux (for session management)

# Optional but recommended
- docker-compose (for testing)
```

### Install Chimera

```bash
pip install chimera
```

### Verify Installation

```bash
chimera --version
```

---

## 🚀 5-Minute Tutorial

### Step 1: Create Your First Configuration

```bash
# Create a simple web service
echo 'services.web.script = "echo Hello Chimera!";' > demo.nix
```

### Step 2: Deploy Locally with Persistent Session

```bash
chimera run -c demo.nix -s my-session "echo '🔥 Chimera Active!'"
```

### Step 3: Try Autonomous Healing

```bash
# In a separate terminal, watch for drift
chimera watch -t "localhost" -c demo.nix

# Now break the configuration and watch it heal itself!
```

### Step 4: Deploy to a Fleet

```bash
# Replace with your actual servers
chimera deploy -t "user@server1:22,user@server2:22,user@server3:22" -c production.nix "echo '🚀 Production Ready!'"
```

---

## 🎯 Your First Autonomous Deployment

### Basic Fleet Deployment

```bash
# Deploy to multiple nodes
chimera deploy -t "user@server1,user@server2,user@server3" -c config.nix "your-application-command"

# Start autonomous monitoring
chimera watch -t "user@server1,user@server2,user@server3"
```

### What Happens Now?

1. **Continuous Monitoring**: Chimera checks your fleet every 10 seconds
2. **Drift Detection**: If any node's state diverges from expected, it's flagged immediately  
3. **Automatic Healing**: Chimera redeploys the correct configuration
4. **Time Machine**: Rollback to any previous generation if needed
5. **Real-Time Dashboard**: Visual dashboard shows live fleet status

---

## 🎛️ Troubleshooting

### Common Issues

**"chimera: command not found"**
```bash
# Ensure pip installation is in PATH
pip show chimera
# Or run with python -m chimera
python -m chimera <command>
```

**Build Failures**
```bash
# Ensure Nix is installed and accessible
nix --version
# Check PATH includes Nix store paths
```

**Connection Issues**
```bash
# Test SSH connectivity
ssh user@your-server "echo 'connection test'"
# Check that your user has necessary permissions
```

### Getting Help

```bash
chimera --help
chimera <command> --help
```

---

## 📚 Next Steps

- **Read [Architecture Overview](../architecture.md)** - Understand the design
- **Try [Fleet Management](../fleet-management.md)** - Scale your deployment
- **Explore [Autonomous Healing](../autonomous-healing.md)** - Deep dive into self-healing
- **Learn [Time Machine Rollbacks](../time-machine.md)** - Master rollback capabilities

---

## 🤝 Need Help?

- **Documentation**: Check the `docs/` folder for detailed guides
- **Community**: [Discord Server](https://discord.gg/chimera)
- **Issues**: [GitHub Issues](https://github.com/asmeyatsky/chimera/issues)
- **Discussions**: [GitHub Discussions](https://github.com/asmeyatsky/chimera/discussions)

---

*Ready to make your infrastructure autonomous? Let's get started!* 🚀