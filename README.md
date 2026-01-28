# 🚀 Chimera: Autonomous Infrastructure Engine

> **Deploy to 1000+ nodes, let it heal itself forever. Never SSH into production again.**

[![Stars](https://img.shields.io/github/stars/asmeyatsky/chimera?style=social)](https://github.com/asmeyatsky/chimera)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/asmeyatsky/chimera/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://github.com/asmeyatsky/chimera)
[![Build Status](https://img.shields.io/github/actions/workflow/yourname/chimera?label=build)
[![Codecov](https://img.shields.io/codecov/c/github/yourname/chimera?branch=main)](https://codecov.io/gh/yourname/chimera)

## 🔥 What is Chimera?

**Chimera** is the world's first **autonomous deployment engine** that combines Nix reproducibility with self-healing capabilities and revolutionary "Time Machine" rollback functionality.

### 🎯 The Magic
```bash
# Deploy to fleet
chimera deploy -t "user@server1,user@server2,user@server3" -c production.nix

# Start autonomous monitoring
chimera watch -t "user@server1,user@server2,user@server3"

# ✨ Infrastructure fixes itself while you sleep!
```

### 🛡️ Core Features

- **🔥 Autonomous Self-Healing** - Detects drift and fixes automatically
- **⏰ Time Machine Rollback** - Instantly rollback to ANY previous generation  
- **📊 Real-Time Fleet Dashboard** - Beautiful TUI monitoring interface
- **🎯 Deterministic Deployments** - Math-based convergence guarantees
- **🧛 Zero-Downtime Operations** - Never break production again
- **🏗️ Clean Architecture** - Following DDD and hexagonal patterns

---

## 🚀 Quick Start

## 📋 Installation
```bash
pip install chimera
```

### 5-Minute Demo
```bash
# Create a simple Nix config
echo "services.web.script = ''echo Hello Chimera!''; }" > demo.nix

# Deploy locally with persistent session
chimera run -c demo.nix -s chimera-demo "echo '🔥 Chimera Active!'"

# Deploy to fleet (replace with your servers)
chimera deploy -t "user@your-server.com" -c demo.nix "echo '🚀 Production Ready!'"

# Start autonomous monitoring
chimera watch -t "user@your-server.com"
```

### 🎮 Try the Viral Demo (30 seconds!)
```bash
# Interactive demo showing autonomous healing
curl -sSL https://raw.githubusercontent.com/asmeyatsky/chimera/main/demo/viral-demo.sh | bash

# Or download and run locally
wget https://raw.githubusercontent.com/asmeyatsky/chimera/main/demo/viral-demo.sh
chmod +x viral-demo.sh
./viral-demo.sh
```

### 🔥 Experience the Magic (Watch What Happens!)
```bash
# The demo will show:
# 1. Deploying to 3-node cluster
# 2. Simulating configuration drift  
# 3. 🚨 Autonomous healing activated automatically
# 4. ⏰ Time Machine rollback demonstration
# 5. ✨ Infrastructure restored without any human intervention
```

### Try the Viral Demo
```bash
curl -sSL https://raw.githubusercontent.com/yourname/chimera/main/demo/viral-demo.sh | bash
```

---

## 🎬 Live Demo

**Watch Chimera heal itself in 30 seconds:**

[![Demo GIF](https://github.com/asmeyatsky/chimera/raw/main/assets/demo.gif)]

*Infrastructure that fixed itself while we slept - no human intervention required!*

---

## 💡 Use Cases

### 🏢 Production Fleets
- Deploy configurations to 1000+ nodes
- Autonomous monitoring and healing 24/7
- Zero-downtime rollbacks

### 🧪 Development Environments  
- Consistent development setups
- Automatic drift correction
- Time-travel debugging

### 🏭️ Compliance & Auditing
- Generation-based rollbacks for compliance
- Automatic convergence verification
- Audit trail of all changes

---

## 🏗️ Architecture

Chimera follows **Clean Architecture** with **Domain-Driven Design** principles, ensuring maintainable and extensible code:

```
┌─────────────────────────────────────────┐
│             Presentation Layer                │
│  CLI Interface & TUI Dashboard          │
│  ┌─────────────────────────────────┤
│             Application Layer                │
│  Use Cases & Business Logic           │
│  ┌─────────────────────────────────┤
│               Domain Layer                   │
│  Core Business Logic & Models         │
│  ┌─────────────────────────────────┘
│           Infrastructure Layer               │
│  External Integrations (Fabric, Nix, Tmux)│
└─────────────────────────────────────────┘
```

### 🔧 Core Components

- **Autonomous Loop** (`chimera/application/use_cases/autonomous_loop.py`)
  ```python
  while True:
      congruence_reports = self._check_congruence(nodes, expected_hash)
      drifted_nodes = [report.node for report in congruence_reports if not report.is_congruent]
      
      if drifted_nodes:
          print(f"[!] Drift detected on {len(drifted_nodes)} nodes! Initiating Self-Healing...")
          self.deploy_fleet.execute(config_path, healing_command, session_name, drifted_targets)
  ```
  **Purpose:** Continuously monitors fleet and triggers healing when drift is detected

- **Time Machine Rollback** (`chimera/application/use_cases/rollback_deployment.py`)
  ```python
  def rollback(self, nodes: List[Node], generation: Optional[str] = None) -> bool:
      cmd = f"nix-env --switch-generation {generation}" if generation else "nix-env --rollback"
  ```
  **Purpose:** Instant rollback to any previous system generation using NixOS capabilities

- **Fleet Manager** (`chimera/application/use_cases/deploy_fleet.py`)
  ```python
  def execute(self, config_path: str, command: str, session_name: str, targets: List[str]) -> bool:
      nix_hash = self.nix_port.build(str(config.path))
      if not self.remote_executor.sync_closure(nodes, str(nix_hash)): return False
      if not self.remote_executor.exec_command(nodes, session_cmd): return False
  ```
  **Purpose:** Orchestrates deployment across multiple nodes with automatic coordination

- **Real-Time Dashboard** (`chimera/presentation/tui/dashboard.py`)
  ```python
  async def update_fleet_status(self):
      for node in self.targets:
          h = await loop.run_in_executor(None, self.adapter.get_current_hash, node)
          status = "Online" if h else "Unreachable"
          # Update dashboard with real-time fleet status
  ```
  **Purpose:** Visual monitoring of fleet health and congruence status

### 🧛 Domain-Driven Design

#### **Domain Layer** (Pure Business Logic)
- **Entities**: `Deployment`, `Node`, `NixConfig` - Core business objects
- **Value Objects**: `NixHash`, `SessionId`, `CongruenceReport` - Immutable concepts
- **Domain Services**: `AutonomousLoop`, `DeployFleet` - Business use case orchestration

#### **Application Layer** (Use Case Coordination)
- **Use Cases**: `ExecuteLocalDeployment`, `RollbackDeployment` - Application workflows
- **DTOs**: Data transfer objects between layers
- **Application Services**: Higher-level business operations

#### **Infrastructure Layer** (External Systems)
- **Adapters**: `FabricAdapter`, `NixAdapter`, `TmuxAdapter` - External system integrations
- **Repositories**: Data access and state persistence
- **Configuration**: System configuration and dependency injection

### 🎯 Design Patterns

- **Ports & Adapters**: Abstract interfaces enable easy testing and new integrations
- **Dependency Injection**: Loose coupling between layers
- **Immutable Models**: Domain objects that ensure state consistency
- **Event-Driven Architecture**: Decoupled components for extensibility

---

Chimera follows **Clean Architecture** with **Domain-Driven Design** principles:

```
┌─────────────────────────────────────────────────┐
│             Presentation Layer                │
├─────────────────────────────────────────────────┤
│             Application Layer                │
├─────────────────────────────────────────────────┤
│               Domain Layer                   │
├─────────────────────────────────────────────────┤
│           Infrastructure Layer               │
└─────────────────────────────────────────────────┘
```

### 🔧 Core Components

- **Autonomous Loop** - Drift detection and self-healing (`chimera/application/use_cases/autonomous_loop.py`)
  - **Time Machine** - Generation-based rollback system (`chimera/application/use_cases/rollback_deployment.py`)  
- **Fleet Manager** - Multi-node orchestration (`chimera/application/use_cases/deploy_fleet.py`)
- **Real-Time Dashboard** - Visual fleet monitoring (`chimera/presentation/tui/dashboard.py`)

---

## 📖 Documentation

### 📚 User Guides
- [Getting Started Guide](docs/getting-started.md)
- [Fleet Management](docs/fleet-management.md)
- [Autonomous Healing Guide](docs/autonomous-healing.md) - 📋 Learn how drift detection and self-repair work
- [Time Machine Rollbacks](docs/time-machine.md) - ⏰️ Instant recovery to any generation
- [Dashboard Usage](docs/dashboard.md) - 📊 Real-time fleet monitoring

### 🔧 Developer Guide
- [Architecture Overview](docs/architecture.md) - 🏗️ Clean DDD implementation
- [Contributing Guidelines](docs/contributing.md) - 🤝 Join our community
- [API Reference](docs/api.md) - 🔌 Integrate with your tools
- [Plugin Development](docs/plugins.md) - 🔌 Extend Chimera capabilities

---

## 🌟 Why Chimera?

### ❌ The Old Way
```bash
# Manual deployment nightmare 😱
ssh user@server1
ssh user@server2  
ssh user@server3
# ... repeat 1000 times
# Hope nothing breaks at 3AM

# PagerDuty calls at 2AM...
# Configuration drift across cluster...
# Manual rollbacks take hours...
# Coffee addiction intensifies... 😫
```

### ✅ The Chimera Way
```bash
# Autonomous magic ✨
chimera deploy -t "user@server{1..1000}" -c production.nix
chimera watch -t "user@server{1..1000}"
# 🛌 Sleep peacefully, infrastructure handles itself

# Result:
# ✅ 3AM: Configuration drift detected on server12
# 🚀 Autonomous healing initiated at 3:02AM
# ✅ 3:03AM: All systems restored automatically
# 🎯 Your PagerDuty app stays silent all night
# 🏖️ You arrive to perfectly healthy infrastructure
# 💰 No coffee required (okay, maybe some) ☕
```

### 🎯 Unique Advantages

1. **🔥 First Autonomous Healing** - Industry-first infrastructure that detects and fixes drift automatically
2. **⏰️ Time Machine Rollbacks** - Instant recovery to ANY previous generation - revolutionary rollback concept
3. **📊 Real-Time Fleet Monitoring** - Beautiful Textual dashboard showing live system state
4. **🎯 Deterministic Guarantees** - Math-based convergence verification across all nodes
5. **🏗️ Clean DDD Architecture** - Maintainable codebase following Clean Architecture principles
6. **🧛 Zero-Downtime Operations** - Infrastructure that heals itself 24/7
7. **⚀ Autonomous Intelligence** - Systems that think before they act, preventing issues proactively

---

## 🤝 Community

### 🚀 Get Started
- [Discord Server](https://discord.gg/chimera) - Chat with users and developers
- [GitHub Discussions](https://github.com/asmeyatsky/chimera/discussions) - Questions and ideas
- [Twitter/X](https://twitter.com/chimera_ops) - Latest updates and viral clips

### 🌟 Contributing
We love contributions! See [Contributing Guidelines](docs/contributing.md) for details.

**Quick Start:**
```bash
# Fork, clone, and set up development environment
git clone https://github.com/your-username/chimera.git
cd chimera
pip install -e ".[dev]"
pytest tests/
```

### 🏆 Champions Program
Become a [Chimera Champion](docs/champions.md) and help shape the future of autonomous infrastructure!

---

## 📈 Roadmap

### ✅ v1.0 (Current)
- [x] Autonomous healing loop
- [x] Time machine rollbacks  
- [x] Real-time dashboard
- [x] Fleet deployment
- [x] Nix + Fabric integration

### 🚧 v1.1 (Next)
- [ ] Kubernetes adapter
- [ ] Slack/Discord notifications
- [ ] Advanced healing patterns
- [ ] Metrics and analytics
- [ ] Plugin ecosystem

### 🎯 v2.0 (Future)
- [ ] Machine learning predictions
- [ ] Multi-cloud support
- [ ] Enterprise compliance features
- [ ] Advanced analytics dashboard
- [ ] API for integration

---

## 📊 Stats

![GitHub stars](https://img.shields.io/github/stars/yourname/chimera?style=flat-square)
![GitHub forks](https://img.shields.io/github/forks/yourname/chimera?style=flat-square)
![GitHub issues](https://img.shields.io/github/issues/yourname/chimera?style=flat-square)
![GitHub pull requests](https://img.shields.io/github/issues-pr/yourname/chimera?style=flat-square)

---

## 📄 License

Chimera is licensed under the [MIT License](LICENSE).

---

## 🙏 Acknowledgments

- **Nix Team** - For reproducible packaging innovation
- **Fabric Team** - For remote execution capabilities  
- **Tmux Team** - For persistent session management
- **Clean Architecture Community** - For architectural guidance

---

## 🎪 Show Your Support

If Chimera makes your life easier, please consider:

- ⭐ Starring the repository
- 🐦 Reporting bugs and suggesting features
- 💬 Sharing with your colleagues
- 📢 Writing about your experience
- 🤝 Contributing code or documentation

---

<div align="center">

**🔥 Deploy Once, Heal Forever with Chimera**

[![Chimera Logo](https://github.com/yourname/chimera/raw/main/assets/logo.png)]

</div>