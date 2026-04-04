# AI Product PLM Agent

A multi-agent system for AI-driven product configuration, bill of materials generation, and CAD model creation.

**Pipeline:**
```
Product Idea
  → Product Family Agent   — defines features, options, constraints, variants
  → Configurator Agent     — selects a valid configuration and builds a BOM
  → Evaluator Agent        — scores the design across product-specific dimensions
  → Optimizer Agent        — fixes issues and improves scores iteratively
  → PLM Agent              — persists BOM to Airtable
  → CAD Agent (optional)   — generates a parametric 3D model in Onshape
```

Works for any product type — drones, bicycles, espresso machines, robots, etc.

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
pip install -r requirements.txt
```

### 2. Configure API keys

Copy the example file and fill in your keys:

```bash
cp .env.example .env
```

Open `.env` and set:

| Variable | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com/keys](https://console.anthropic.com/keys) |
| `AIRTABLE_TOKEN` | [airtable.com/create/tokens](https://airtable.com/create/tokens) — scopes: `data.records:write`, `schema.bases:read` |
| `AIRTABLE_BASE_ID` | Your base URL: `airtable.com/<BASE_ID>/...` |
| `ONSHAPE_ACCESS_KEY` / `ONSHAPE_SECRET_KEY` | [dev-portal.onshape.com/keys](https://dev-portal.onshape.com/keys) _(CAD only)_ |
| `ONSHAPE_DID` / `ONSHAPE_WID` / `ONSHAPE_EID` | Your Onshape document URL _(CAD only)_ |

Onshape keys are optional — the system works without them if you skip the CAD step.

### 3. Airtable setup

Create a base with these tables:

| Table | Fields |
|---|---|
| **Product Families** | Name, Product Type, Description |
| **Features** | Name, Type, Family |
| **Feature Options** | Feature, Value, Family |
| **Constraints** | Rule, Family |
| **Parts** | part_number, name, category, active |
| **BOM** | parent, part_number (linked), quantity, level, notes |

### 4. Run

```bash
python drone_plm_agents.py
```

You will be prompted for:
1. **Product idea** — e.g. `electric mountain bike`, `inspection drone`, `espresso machine`
2. **Design intent** — goal, constraints, and context (shown after the product family is defined)

---

## Models used

| Agent | Model | Reason |
|---|---|---|
| Product Family, Configurator, Evaluator, Optimizer, PLM | `claude-sonnet-4-6` | Fast, cost-efficient |
| CAD reasoning | `claude-opus-4-6` with extended thinking | Complex spatial planning |

---

## Architecture notes

- **Product-agnostic:** the evaluator and optimizer derive scoring dimensions from the product family, not hardcoded drone metrics.
- **CAD is drone-specific:** the CAD agent generates drone geometry. Extending it to other products requires a new geometry planner.
- **Last design is cached** in `.last_bom.json` (gitignored). On next run you can skip straight to CAD.
- **Prompt caching** is used on the evaluator and optimizer system prompts to reduce API costs in long optimization loops.

---

## Environment variables reference

See [`.env.example`](.env.example) for the full list with descriptions.
