# AI Product Agents

A multi-agent system that takes a product idea and a design intent, then configures, evaluates, and builds it — automatically.

```
Your idea  →  "electric mountain bike"
Your intent →  "maximum range, cost under €2000"

  Product Family Agent     — defines features, options, constraints, variants
  Competitive Analysis     — finds real market competitors and their specs
  Configurator Agent       — selects a valid configuration and builds a BOM
  Evaluator Agent          — scores the design against what matters for this product
  Optimizer Agent          — fixes issues and improves scores iteratively
  Builder Agent            — writes the result to Airtable
  CAD Agent (optional)     — generates a parametric 3D model in Onshape
  Image Agent (optional)   — renders a product image via DALL-E 3
```

Works for any product — bikes, robots, cameras, machines, drones, appliances.

---

## How it works

**1. You give it a product idea.**
Anything: `inspection robot`, `portable solar station`, `espresso machine for cafes`.

**2. The system defines the product family.**
It creates a structured feature model — features, options per feature, cross-feature constraints, and 2–3 predefined variants. Like a configurator in Configit or pure::variants, but generated from scratch.

**3. Competitive landscape is mapped.**
4–5 real market competitors are identified with pricing, key specs, weaknesses, and positioning — giving context for where your design should differentiate.

**4. You define your intent.**
Based on the product family it just built, the system shows you the relevant features and scoring dimensions, then asks:
- What do you want to optimise for?
- What are your hard constraints?

**5. The agents run.**
Configuration → Evaluation → Optimization loop → Airtable → optional CAD in Onshape or image via DALL-E 3.

---

## HTML Report

After every run, a self-contained HTML report opens automatically in your browser.

```
┌─────────────────────────────────────────────────────────────┐
│  WoodShell RPi Cases                                        │
│  Raspberry Pi enclosure family · Generated 2026-04-06      │
├──────────────────────────┬──────────────────────────────────┤
│  Score Radar             │  Optimization Journey            │
│  (spider chart,          │  (line chart showing score       │
│   all dimensions)        │   evolution across iterations)   │
├──────────────────────────┴──────────────────────────────────┤
│  Issues          ✓ No critical issues                       │
├──────────────────────────┬──────────────────────────────────┤
│  Selected Configuration  │  Product Variants                │
│  Material = Walnut       │  • entry-level — plywood, bare   │
│  Finish   = Oil          │  • standard    — walnut, oiled   │
│  Fit      = Pi 5         │  • pro         — CNC + lacquer   │
├──────────────────────────┴──────────────────────────────────┤
│  Competitive Landscape                                       │
│  Argon ONE  · €25 · aluminium shell · heavy · premium feel │
│  Flirc Case · €15 · passive cooling · no GPIO · minimalist  │
│  ...                                                        │
├─────────────────────────────────────────────────────────────┤
│  Bill of Materials (12 parts)          [Export BOM as CSV]  │
│  PN-001  Walnut top panel   Enclosure  1                    │
│  PN-002  M2.5 brass insert  Hardware   4                    │
│  ...                                                        │
├─────────────────────────────────────────────────────────────┤
│  Product Render  (if DALL-E 3 was run)                      │
│  [1792×1024 photorealistic render embedded as base64]       │
└─────────────────────────────────────────────────────────────┘
```

The report is a single `.html` file — no server needed, shareable by email or Slack.

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/config-collab/ai-product-agents.git
cd ai-product-agents
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env
```

Open `.env` and fill in:

| Variable | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com/keys](https://console.anthropic.com/keys) |
| `AIRTABLE_TOKEN` | [airtable.com/create/tokens](https://airtable.com/create/tokens) — scopes: `data.records:write`, `schema.bases:read` |
| `AIRTABLE_BASE_ID` | Your base URL: `airtable.com/<BASE_ID>/...` |
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) _(image generation only)_ |
| `ONSHAPE_ACCESS_KEY` / `ONSHAPE_SECRET_KEY` | [dev-portal.onshape.com/keys](https://dev-portal.onshape.com/keys) _(CAD only)_ |
| `ONSHAPE_DID` / `ONSHAPE_WID` / `ONSHAPE_EID` | Your Onshape document URL _(CAD only)_ |

Onshape and OpenAI keys are optional — skip those steps and everything else still works.

### 3. Airtable base structure

The `--setup` command creates all tables automatically. If you prefer to create them manually:

| Table | Fields |
|---|---|
| **Product Families** | Name, Product Type, Description |
| **Features** | Name, Type, Family |
| **Feature Options** | Feature, Value, Family |
| **Constraints** | Rule, Family |
| **Parts** | part_number, name, category, active |
| **BOM** | parent, part_number (linked), quantity, level, notes |

### 4. Verify setup

```bash
python plm_agents.py --setup
```

This checks your API keys and creates all required Airtable tables automatically.

### 5. Run

```bash
python plm_agents.py
```

Or skip the product idea prompt:

```bash
python plm_agents.py --idea "ergonomic standing desk"
```

---

## Models

| Agent | Model |
|---|---|
| Product Family, Competitive Analysis, Configurator, Evaluator, Optimizer | `claude-sonnet-4-6` |
| CAD planning | `claude-opus-4-6` with extended thinking |
| Image generation | DALL-E 3 (1792×1024 HD) |

---

## Notes

- **Product-agnostic** — scoring dimensions, features, and CAD geometry all come from the product family the system defines, not hardcoded rules.
- **Competitive analysis** — real competitors (from Claude's knowledge) identified before you pick your intent, shown as a table in the HTML report.
- **Session saved** after each run (`.last_session.json`, gitignored) — next run offers CAD-only or image-only from the last design, with full family context preserved.
- **Variant picker** — after the product family is defined, choose a predefined variant (entry-level / standard / pro) as your starting intent, or let the system recommend one automatically (option 0).
- **HTML report** auto-generated after each run — radar chart, optimization journey chart, competitive landscape, BOM table with CSV export, configuration, issues, and render image. Opens in your browser automatically.
- **`--setup` flag** — verifies keys and creates Airtable tables without running the full pipeline.
- **`--idea` flag** — skip the interactive prompt: `python plm_agents.py --idea "espresso machine"`.
- **Prompt caching** on evaluator/optimizer system prompts cuts API cost during optimization loops.

---

See [`.env.example`](.env.example) for the full environment variable reference.
