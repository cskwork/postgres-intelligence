# Install postgres-intelligence

<details>
<summary><strong>Claude Code</strong></summary>

### Install

```bash
claude plugin marketplace add cskwork/postgres-intelligence
claude plugin install postgres-intelligence@postgres-intelligence
```

Type `/postgres-intelligence`.

### Verify

```bash
claude plugin list
```

### Update

```bash
claude plugin marketplace update postgres-intelligence
```

### Uninstall

```bash
claude plugin uninstall postgres-intelligence
claude plugin marketplace remove postgres-intelligence
```

</details>

<details>
<summary><strong>Codex</strong></summary>

### Install

```bash
codex plugin marketplace add cskwork/postgres-intelligence --ref main
codex plugin add postgres-intelligence@postgres-intelligence
```

Type `$postgres-intelligence`.

### Verify

```bash
codex plugin list
```

### Uninstall

```bash
codex plugin remove postgres-intelligence
codex plugin marketplace remove postgres-intelligence
```

</details>

<details>
<summary><strong>Gemini CLI</strong></summary>

### Install (extension, always-on)

```bash
gemini extensions install https://github.com/cskwork/postgres-intelligence
```

### Install (command, opt-in)

```bash
mkdir -p ~/.gemini/commands
curl -fsSL https://raw.githubusercontent.com/cskwork/postgres-intelligence/main/skills/postgres-intelligence/agents/gemini.toml \
  -o ~/.gemini/commands/postgres-intelligence.toml
```

Type `/postgres-intelligence` in a new session.

### Verify

```bash
gemini extensions list
```

### Uninstall

```bash
gemini extensions uninstall postgres-intelligence
```

</details>

<details>
<summary><strong>Cursor, OpenCode, Amp, and other agent-skills harnesses</strong></summary>

### Install

```bash
npx skills add cskwork/postgres-intelligence
npx skills add cskwork/postgres-intelligence -g
```

Type `/postgres-intelligence` in a new agent chat.

### Verify

```bash
npx skills list
```

### Update

```bash
npx skills update postgres-intelligence
```

### Uninstall

```bash
npx skills remove postgres-intelligence
```

</details>

<details>
<summary><strong>Antigravity (agy)</strong></summary>

### Install

```bash
agy plugin install https://github.com/cskwork/postgres-intelligence
```

### Verify

```bash
agy plugin list
```

### Uninstall

```bash
agy plugin uninstall postgres-intelligence
```

</details>
