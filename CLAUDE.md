# CLAUDE.md – Ironforge Exchange Commission (IFEC)

## What this project is

A portfolio project. It is an automated data platform that does market surveillance and post-mortem analytics on the **World of Warcraft: Forever** auction house. Forever is Blizzard's third permanent WoW version, alongside Retail and Classic. It launches on 2026-11-04 at 15:00 PST.

It is framed as a **securities regulator (SEC-style)**, not a trading tool and not a central bank:
- hourly capture of auction house snapshots
- nightly baselines (7-day and 30-day EMAs) plus anomaly detection (Z-scores, supply crashes, volume deltas)
- an anomaly log that is never changed (audit trail) and public Grafana dashboards for post-mortem review

**Why it exists:** a portfolio project. It must show two skill sets together:
1. **DevOps / platform skills:** Terraform, containers, Azure, scheduled pipelines, managed identity, cost control, CI/CD
2. **Risk and controls mindset:** surveillance, audit trail, data lineage, evidence-based findings, clear documentation

A second goal: let Claude architect the DevOps part. Code, docs and commit history are part of the showcase. Keep them clean and professional.

## Hard constraints

- **Cost:** **$15 per month hard cap for everything** (raised from $5–10 on 2026-11-02); the Azure budget is set as **€15/month** (billing currency). The chosen design costs about $1–2.
- **One location:** everything runs in **one Azure subscription**. Do not add external free-tier services (Supabase, Grafana Cloud, Databricks, MotherDuck, etc.).
- **CI/CD:** GitHub Actions (GitHub is allowed next to Azure; runtime stays in Azure). Container images in GHCR (free), not ACR (~$5).
- Raw data: the brief estimated about 4 GB per month uncompressed. **First measurement (2026-11-06): v1 scope (commodities of houses 111 + 114) is ~6.5 MB raw per snapshot, ~4.7 GB/month raw** – the estimate holds. **Second measurement (2026-11-13, live ingest test): house 114 alone 7.9 MB raw; both houses 1.6 MB gzipped per snapshot (~5x compression) → ~1.2 GB/month in Bronze, cents per month.** Storage must stay cheap for years.

## Architecture: decided (option C, "serverless, no VM") – 2026-11-02

```
Blizzard API ──hourly──▶ ingest job ──▶ Bronze (raw JSON, gzipped)
                                            │
                              nightly analyze job
                                            ▼
                          Silver (clean listings) ─▶ Gold (baselines, anomaly log, run log)
                                                          │
                                         small summary files (JSON/CSV)
                                                          ▼
                                  Grafana (Container App, scale to zero, Infinity plugin)
                                                          ▼
                                           public: ifec.<owner-domain>
```

| Area | Decision |
|---|---|
| Name | Ironforge Exchange Commission. Use **IFEC** as the short form, never "IEC" (clashes with the International Electrotechnical Commission, as in ISO/IEC 27001) |
| Cloud | **Azure, settled.** Region: **Sweden Central** (cheapest EU). AWS, Linode/Akamai and Hetzner considered and rejected (Hetzner re-checked: at ~$1–2/month it cannot be cheaper and has no managed identity / serverless / policy features): Azure fits the target skill set and the governance story (Entra ID, managed identity, OIDC, Key Vault, Policy, Budgets) |
| IaC | Terraform (state in Azure Storage), applied from GitHub Actions with **OIDC federation** – no Azure secrets in GitHub |
| Jobs | Python containers as **Azure Container Apps Jobs** (consumption plan): ingest hourly, analyze nightly. Fits in the monthly free grant |
| Lakehouse | **Single source of truth.** Open-source, **no Microsoft Fabric** (F2 ≈ $260/month). **Delta Lake** tables on **ADLS Gen2**, medallion layers Bronze (raw JSON as received, never changed) → Silver → Gold. Delta versioning = provable history ("what did the anomaly log look like on date X"). Fabric-compatible format (Fabric shortcuts could mount it later) |
| Engine | Polars + `deltalake` (delta-rs) in the analyze job (Claude's call, owner did not object). DuckDB for ad-hoc queries from a laptop |
| Dashboards | **Grafana as a Container App with scale to zero.** The owner accepts a 10–30 s cold start on first visit. **Stateless:** dashboards, data sources and settings are provisioned from git at startup (no database, changes go through PRs). Public read-only (anonymous viewer); owner logs in to edit |
| Grafana data | The analyze job writes small Gold summary files; Grafana reads them with the **Infinity** plugin (Grafana Labs). The community DuckDB plugin was considered and is riskier. Bake plugins into the image to keep cold start short |
| Monitoring | **No Prometheus, no VM, no Postgres** (owner accepted the trade-off). Every job run writes a row to a **run log** Delta table (start, end, rows, status). Azure Monitor alert e-mails the owner when a job fails (Grafana sleeps, so alerting must not live in Grafana) |
| Dashboards (2) | **Market dashboard** (the surveillance data) and **Platform / DevOps dashboard** (replaces Prometheus): run log, data freshness, job durations and failures, data volumes. Proposed sources: Gold run log + Grafana's built-in Azure Monitor data source (managed identity) + a nightly cost export vs. budget. Panels still to agree |
| Secrets | Key Vault + managed identities (Blizzard client ID/secret) |
| Scope | **EU region** servers |
| Public access | Container Apps ingress gives a free HTTPS endpoint + free managed certificate for the custom domain – **no paid public IP** |
| Addon | **Optional extra**, not the main point. The project started as an addon idea; the infra and data are now the core. Addons cannot use the network, so a desktop helper writes the addon's SavedVariables (the TSM pattern) |

## Surveillance scope v1 (proposed by Claude, accepted by the owner 2026-11-02)

- **Start with commodities = crafting materials only** (owner's choice). Expand later.
- Proposed starter detectors (thresholds kept in a config file in git, so every change is a reviewed PR):
  1. Price spike / crash – daily price vs. 7-day baseline, robust Z-score (median + MAD), flag |z| > 3
  2. Supply shock – listed quantity drops > 50 % ("supply crash") or more than doubles ("flood / dumping") vs. baseline
  3. Possible cornering / buyout – supply drop and price spike on the same item, same day
  4. Crafting Materials Price Index – a CPI-like basket index (the macro, Fed-like view)
- Warm-up: no flags until an item has 7 days of history (launch economy is wild).
- Limitation: the API has no seller identities, so surveillance is market-level only, not per-trader.
- Status: **accepted by the owner** (2026-11-02).

## Cost estimate (Azure Retail Prices API, Sweden Central, pay-as-you-go, checked 2026-11-02)

| Item | $/month |
|---|---|
| ADLS Gen2 LRS (hot 0.0184 / cool 0.010 / cold 0.0036 per GB) – lifecycle rule moves old Bronze to cool/cold | ~0.10–0.50 in year 1 |
| Container Apps Jobs (ingest + analyze) | 0 (free grant: 180k vCPU-s, 360k GiB-s per month) |
| Grafana Container App, scale to zero | ~0 (always-on would be ~$4.70) |
| Key Vault (operations) | ~0.01 |
| GHCR images | 0 |
| **Total** | **~$1–2** |

Watch: Container Apps logs to Log Analytics cost money above 5 GB/month – keep logging lean. Terraform creates an **Azure Budget alert** (e.g. at $10) as proof of cost control.

## Options considered and rejected (keep for the design doc and interviews)

- **A – VM (B2ats v2, 1 GB) + public IP**, Docker Compose with Postgres + Grafana + Prometheus + nginx: ~$13.50/month. Fine but runs a server (patching, tight RAM).
- **B – private VM behind Container Apps:** Container Apps with a custom VNet adds billed public IPs/load balancer; the VM needs outbound internet – new VNets are private by default since 2026-03-31, so it needs either a NAT Gateway (~$33/month) or the deprecated default outbound access (an audit finding). Bastion Developer would be free. Verdict: costs more than A and is the most complex.
- **Managed Azure PostgreSQL** (~$12/month) and **Azure Managed Grafana** ($6/user/month + nodes): over budget.

## Changed from the original brief

The original brief is in `docs/original-brief.md` (local only, `docs/` is gitignored).
- Supabase dropped (one Azure subscription only).
- Framing changed from "central bank" to "securities regulator (SEC)": the core output is market surveillance and an anomaly log. Blizzard is the "central bank" (it controls the gold supply). The 7/30-day baselines remain as the macro, Fed-like part. Real-world example of both roles in one institution: the Czech National Bank (ČNB).
- Pandas → Polars. Postgres and the VM dropped; the lakehouse serves Grafana directly via summary files.
- Grafana "local Docker" → Azure Container App, public, scale to zero.

## Other decisions (2026-11-02)

- **Repo: public since 2026-11-02** – https://github.com/ValentinHoracek/ironforge-exchange-commission. Every commit is visible immediately: no secrets, no personal data, no internal notes in git. Consequences: GHCR images are public packages (no pull credential needed, so images must never contain secrets); GitHub `prod` environment with required reviewers is free and is used for prod approvals; GitHub Actions minutes are free.
- **Security and quality checks in CI: yes** (e.g. checkov/tfsec for Terraform, Trivy for images, tests, linting). Exact tools are Claude's call.
- **Environments: dev + prod.** Same Terraform, two state files / resource groups; dev ingests less often or on demand. Prod deploys need approval in the GitHub `prod` environment (required reviewers).
- **Markets:** Forever has no realm list – one mega-server per region × ruleset, one auction house per region × ruleset × faction (pre-launch sources). **v1 = EU, Normal (PvE) ruleset, Alliance + Horde (2 markets).** `region`, `ruleset`, `faction` are dimensions from day one. **Verified 2026-11-06:** markets are auction house IDs – **EU Normal Alliance = house 111 (verified by marker listing)**, **EU Normal Horde = house 114 (inferred, still to verify)**. Commodities are per house, not region-wide. **v1 captures and analyses only houses 111 and 114** (owner, 2026-11-06); the other 13 houses are not captured yet. Blackwater = neutral NPC (goblin) auction house, a gold sink – out of scope. Details: design doc §5.1.1.
- **Retention:** move Bronze to a cheaper tier after **6 months**. Proposed (Claude): Bronze hot → cold at 180 days (still online, instant access, higher read cost); Silver/Gold stay hot; **no Archive tier** (offline, hours to restore – breaks "rebuild from raw").
- **Controls register:** wanted eventually, **not now**.
- **Addon and domain:** later.

- **Bootstrap:** documented manual bootstrap is the only allowed click-ops. Record: `bootstrap/README.md`.
- **Bronze immutability:** 1-year time-based retention (WORM), locked in prod at the "done" milestone (end of December 2026) – the original trigger ("before going public") no longer applies; owner to confirm. Prod Bronze storage in its own Terraform root.
- **Design document:** `docs/superpowers/specs/2026-11-02-ifec-design.md` (builder check done, owner answers applied).

## Domain – to discuss later

The owner already has a domain. Plan: `ifec.<owner-domain>` as a CNAME + TXT (domain validation) to the Container App. Open: which domain and registrar, and whether Terraform can manage the DNS record.

## Blizzard API for Forever – resolved 2026-11-06 (was the main known risk)

Forever auction data went live on 2026-11-06. Verified with IFEC's own API client (EU); undocumented by Blizzard, so it can change:
- Namespace `dynamic-forever-eu` (items: `static-forever-eu`), host `eu.api.blizzard.com`.
- House index `/data/wow/ruleset/{rs}/auctions/` (trailing slash required). Per house: `/data/wow/ruleset/{rs}/auctions/{house}` and `/.../{house}/commodities`. Retail's `/data/wow/auctions/commodities` returns 404.
- **The ruleset ID does not filter**: all rulesets return the same 15 houses (110–121, 123–125). The house ID is the market key.
- Dedup must hash the body: the same `Last-Modified` was once served with different content.
- **Latency about one hour:** each house is a snapshot refreshed roughly hourly (large houses at about :22–:24 past the hour). A marker listing took up to ~1 hour to appear in the API. Events are timed only to the snapshot (±1 h); listings that appear and vanish within the hour are invisible.
- Item names need the item API; community testers report many auctioned item IDs return 404, so names need a fallback.

History: on 2026-10-28 no Forever namespace existed (all guesses returned 403). Owner's decision then: assume it will be available and do not block the design. Reference: https://github.com/jkc-be/goldbook/issues/67

## Where we are in the process

- **Design approved by the owner on 2026-11-02**: `docs/superpowers/specs/2026-11-02-ifec-design.md` – read it first; it is the source of truth over this file where they differ.
- **Progress, next steps and to-dos live in `PROGRESS.local.md`** (gitignored, loaded via `CLAUDE.local.md`). The public record is the commits, pull requests and `bootstrap/README.md`. Keep status notes out of this file.
- **`docs/` is gitignored on purpose:** specs, plans and the original brief stay local. Do not commit them and do not remove the ignore rule.

## Working agreements

- Communicate in plain, concise English.
- Explain *why* behind choices. The owner values evidence-based decisions.
- Do not commit or push unless asked.
- **The owner does the infra steps hands-on, to learn** – learning is a main goal of the project. Claude explains each step (what, why, portal path, CLI command, how to verify, what the Activity log shows) and does not run commands that change Azure unless the owner asks for that specific step. "What's next" means a plan, not execution.
- **This repo is public.** Personal context about the owner lives in `CLAUDE.local.md` (gitignored). Never copy anything from it, or from files outside the repo, into tracked files.
