# AI Product Agents

A multi-agent system that takes a product idea and a design intent, then configures, evaluates, and builds it — automatically. Works for any product.

---

## How it works

```
  You type: "modular home energy storage system"
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  PRODUCT FAMILY AGENT                                           │
│  Generates the product's feature model from scratch             │
│                                                                 │
│  → Features: cell_chemistry, capacity_kwh, inverter_type, ...  │
│  → Options:  LFP | NMC | LTO  /  5kWh | 10kWh | 15kWh  / ...  │
│  → Constraints: "LTO requires active cooling"                   │
│  → Variants: entry-level / standard / pro                       │
│  → Scoring: usable_capacity, efficiency, install_cost           │
│                                                                 │
│  Writes family to Airtable                                      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  COMPETITIVE ANALYSIS AGENT                                     │
│  Identifies real market competitors using Claude's knowledge    │
│                                                                 │
│  → Tesla Powerwall 3   [€9,500]  — best ecosystem integration   │
│  → Sonnen Eco          [€12,000] — premium, long warranty       │
│  → BYD Battery-Box     [€5,800]  — value, modular expansion     │
│  → Enphase IQ Battery  [€7,200]  — AC-coupled, easy retrofit    │
│                                                                 │
│  Market gap: nothing strong at €4k–6k with open protocols       │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  YOU  — define your intent                                      │
│                                                                 │
│  Option 0: Auto (Claude recommends based on market gap)         │
│    → Goal: "best value at under €5,000 with open BMS"           │
│    → Constraints: ["grid-tie capable", "IP55 outdoor rating"]   │
│    → Context: "residential installer, EU market"                │
│                                                                 │
│  Or pick a variant, or type your own goal                       │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  CONFIGURATOR AGENT                                             │
│  Selects valid options, builds initial BOM                      │
│                                                                 │
│  Configuration:  LFP cells / 10kWh / hybrid inverter / IP55    │
│  BOM: 14 parts — cell modules, BMS, inverter, enclosure, ...    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
              ┌────────────────┘
              │   up to 5 iterations
              ▼
┌─────────────────────────────────────────────────────────────────┐
│  EVALUATOR AGENT              →    OPTIMIZER AGENT              │
│                                                                 │
│  Scores each dimension:            Fixes critical issues first  │
│  usable_capacity  7/10             then improves scores         │
│  efficiency       6/10      →                                   │
│  install_cost     8/10             Adjusts config + BOM         │
│                                    and loops back               │
│  Issues:                                                        │
│  ⚠ BMS lacks CAN bus (critical)                                 │
│  ⚠ no surge protection (critical)                               │
└──────────────────────────────┬──────────────────────────────────┘
                               │  scores ≥ 8, no critical issues
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  BUILDER AGENT (Airtable)                                       │
│  Writes final parts + BOM to your Airtable base                 │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
             ┌─────────────────┴─────────────────┐
             │                                   │
             ▼                                   ▼
┌────────────────────────┐          ┌────────────────────────────┐
│  CAD AGENT (optional)  │          │  IMAGE AGENT (optional)    │
│  Onshape parametric    │          │  DALL-E 3 product render   │
│  3D model via API      │          │  1792×1024 HD image        │
└────────────┬───────────┘          └─────────────┬──────────────┘
             └─────────────────┬─────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  HTML REPORT  (auto-opens in browser)                           │
│  Radar chart · Optimization journey · Competitive landscape     │
│  BOM table · Configuration · Issues · Render image             │
│                                                                 │
│  → example_report.html                                          │
└─────────────────────────────────────────────────────────────────┘
```

See **[example_report.html](example_report.html)** for a full sample output.

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

### 3. First-time setup

```bash
python plm_agents.py --setup
```

Creates all required Airtable tables automatically and verifies your API keys.

### 4. Run

```bash
python plm_agents.py
```

Or skip the product idea prompt:

```bash
python plm_agents.py --idea "modular home energy storage system"
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
- **Competitive analysis** — real competitors identified before you set your intent; auto-intent uses the market gap to recommend differentiated goals.
- **Session saved** after each run (`.last_session.json`, gitignored) — next run offers CAD-only or image-only from the last design.
- **Variant picker** — choose a predefined variant as your starting intent, or pick option 0 to let the system recommend one based on the competitive landscape.
- **HTML report** auto-generated after each run — radar chart, optimization journey, competitive landscape table, BOM with CSV export. Opens automatically.
- **`--setup` flag** — verifies keys and creates Airtable tables without running the full pipeline.
- **`--idea` flag** — skip the interactive prompt: `python plm_agents.py --idea "espresso machine"`.

---

See [`.env.example`](.env.example) for the full environment variable reference.
