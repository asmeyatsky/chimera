# 🔌 Contributing to Chimera

We love contributions! Chimera follows Clean Architecture principles, making it easy to contribute high-quality code.

## 🎯 Quick Start

### 🏃️ Ready to Contribute?
```bash
# 1. Fork the repository
git clone https://github.com/yourname/chimera.git
cd chimera

# 2. Set up development environment
pip install -e ".[dev]"

# 3. Run tests to verify setup
pytest tests/

# 4. Check our contribution guidelines
cat docs/contributing.md
```

## 🏗️ What We Need Help With

### 🛡️ Code Contributions
- **Bug fixes** with comprehensive tests
- **Feature implementations** following our architecture patterns
- **Documentation improvements** and examples
- **Test coverage** for new features

### 🔧 Plugin Development
Chimera's plugin architecture enables extending capabilities:

```python
# Example: New adapter
class KubernetesAdapter(RemoteExecutorPort):
    """Deploy to Kubernetes with Chimera autonomous healing"""
    
    def __init__(self, kubeconfig_path: str):
        self.k8s_client = kubernetes.client.load_kube_config_from_file(kubeconfig_path)

    def exec_command(self, nodes: List[Node], command: str) -> bool:
        """Execute via Kubernetes pods"""
        # Implementation here
        pass

    def sync_closure(self, nodes: List[Node], closure_path: str) -> bool:
        """Sync Nix closure to Kubernetes PersistentVolume"""
        # Implementation here
        pass
```

### 🧩 Adapter Ecosystem We're Building
- **Kubernetes Adapter** - Deploy to K8s clusters
- **Terraform Adapter** - Manage Terraform state with autonomous healing
- **Ansible Adapter** - Extend to existing Ansible playbooks
- **Slack/Discord Notifications** - Real-time healing notifications
- **Prometheus Metrics** - Advanced monitoring and alerting

## 📋 Development Workflow

### 🔧 Step 1: Setup Development Environment
```bash
# Fork and clone
git clone https://github.com/asmeyatsky/chimera.git
cd chimera

# Create virtual environment
python -m venv
source venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Install dependencies for testing
pip install pytest pytest-cov
```

### 🔧 Step 2: Understand the Codebase

**Read our [Architecture Overview](docs/architecture.md)** first to understand:
- Clean DDD patterns we use
- Domain model design principles
- Port and adapter interfaces
- Layer separation

**Key Files to Study:**
- `chimera/domain/` - Core business logic
- `chimera/application/` - Use cases and workflows  
- `chimera/infrastructure/` - System integrations

### 🔧 Step 3: Find Good First Issues

Look for issues tagged:
- **Good First Issues** - Welcome to new contributors
- **Bug Reports** - Issues with clear reproduction steps
- **Enhancement Requests** - Well-defined feature requests
- **Documentation** - Gaps in documentation

### 🔧 Step 4: Run Tests Before Contributing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=chimera --cov-report=html
```

### 🔧 Step 5: Make Your First Pull Request

1. **Small, focused changes** - Fix a specific bug or add small feature
2. **Clear description** - Explain what you changed and why
3. **Tests included** - Ensure your changes are well-tested
4. **Follow patterns** - Mimic existing code style

## 🏗️ Contribution Guidelines

### ✅ Code Quality Standards

**Follow Clean Architecture:**
- Domain layer has **NO** dependencies on infrastructure
- Application layer depends **ONLY** on domain layer
- Infrastructure layer implements interfaces from domain
- Presentation layer only interacts with application layer

**Example (✅ Correct):**
```python
# Domain Layer - Pure business logic
class Deployment:
    def __init__(self, session_id: SessionId, config: NixConfig):
        self.session_id = session_id
        self.config = config

# Application Layer - Uses domain objects
class DeploymentService:
    def create_deployment(self, config: NixConfig) -> Deployment:
        deployment = Deployment(session_id=SessionId.generate(), config=config)
        return self.deployment_repository.save(deployment)

# Infrastructure Layer - Implements domain interfaces
class NixAdapter(NixPort):
    def build(self, path: str) -> NixHash:
        # Concrete implementation
        pass
```

### ❌ Anti-Patterns (❌ NEVER Do These)

**Domain Logic in Infrastructure:**
```python
# ❌ WRONG - Business logic in adapter
class NixAdapter:
    def build_and_heal(self, path: str):
        # Don't put business decisions here!
        if path.endswith(".broken"):
            return NixHash("healed-hash")  # ❌
```

**Mixing Layers:**
```python
# ❌ WRONG - Direct infrastructure calls in use case
class DeployFleet:
    def execute(self):
        # Don't call Fabric directly from here
        connection = self.remote_executor._get_connection(node) # ❌
        # Use the remote_executor port properly
```

### ✅ Documentation Requirements

Every contribution must include:

**For New Features:**
1. **Code Implementation** with clean architecture
2. **Unit Tests** for business logic
3. **Integration Tests** for adapters
4. **Documentation Update** explaining the change
5. **Type Annotations** for better maintainability

**For Bug Fixes:**
1. **Test Case** reproducing the issue
2. **Root Cause Analysis** in PR description
3. **Solution Explanation** in PR body
4. **Regression Tests** to prevent regression

### 🏗️ Pull Request Template

```markdown
## Description

### Problem
Briefly describe the issue you're fixing.

### Solution
Explain your approach and the technical implementation.

### Changes Made
List the specific files modified with line numbers.

### Testing
- [x] Unit tests added/modified
- [x] Integration tests added/modified
- [x] Manual verification steps

### Checklist
- [ ] Code follows Clean Architecture
- [ ] Tests pass all scenarios  
- [ ] Documentation updated
- [ ] No regression issues
```

## 🧛️ Recognition Program

Become a [Chimera Champion](docs/champions.md) by:

1. **Consistent Contributions:** Regular high-quality contributions
2. **Community Leadership:** Help others get started
3. **Technical Excellence:** Deep understanding of autonomous infrastructure
4. **Mentorship:** Guide new contributors

---

## 🏆 License

By contributing, you agree to the [MIT License](LICENSE) and your contributions will be licensed under the same terms as the main project.

## 🤝 Getting Started

Need help getting started? Ask in our [Discord](https://discord.gg/chimera) or create a [discussion](https://github.com/asmeyatsky/chimera/discussions).

We're here to help you succeed with your first contribution! 🚀