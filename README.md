# Data Agent

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-agent-1C3C3C)](https://github.com/langchain-ai/langgraph)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

![Data Agent banner](docs/banner.png)

A LangGraph data agent that classifies a natural-language request as **SQL** or **ETL**, then runs the matching subgraph.

- **SQL** — curate the question, generate a Postgres query from live schema, judge it for read-only safety, execute it, and answer in plain language.
- **ETL** — extract JSON from an HTTP API (or transform a local file with generated Pandas) and save CSV / JSON / Parquet.

The router and ETL path use Claude. The SQL path uses OpenAI models of increasing size for curation, generation, and the safety judge.

## Architecture

```text
START
  → router_node          # structured output: "sql" | "etl"
       ├─ sql_node  → SQL analyst subgraph
       └─ etl_node  → ETL analyst subgraph
```

**SQL analyst**

```text
curate_ques → prompt_query_context → generate_sql → is_safe_sql
                                                 ├─ Yes → execute_sql → represent_final_answer → END
                                                 └─ No  → canceled_sql → END
```

**ETL analyst**

```text
START → llm_node → (tool calls?) → tool_node → llm_node → END
```

ETL tools:

| Tool | Role |
| --- | --- |
| `extract_load_tool` | `GET` an API, flatten `results` with Pandas, write `extracted_data.{csv\|json\|parquet}` |
| `transform_load_tool` | Sample the file, generate Pandas, `exec` it, write into the transform folder |

## Repository layout

```text
main.py                 # invoke the compiled data agent
agents/
  data_agent.py         # router + SQL/ETL dispatch
  sql_analyst.py        # SQL subgraph
  etl_analyst.py        # ETL subgraph (tool-calling loop)
Models/schema.py        # Pydantic graph state and structured outputs
utils/
  llm_pickup.py         # pick_llm("low"|"medium"|"high"|"claude")
  database.py           # Postgres connect, schema dump, execute
  etl_tools.py          # extract / preview / execute generated Pandas
data/
  users.csv, rides.csv, vehicles.csv, payments.csv, ratings.csv
  extract/              # ETL extract output
  transform/            # ETL transform output
.env.template           # Postgres settings to copy into .env
```

Sample CSVs are a rideshare-style dataset (users, rides, vehicles, payments, ratings) intended for the SQL path once loaded into Postgres.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- API keys for the models you use (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)
- Postgres, if you run the SQL path

## Setup

```bash
uv sync
cp .env.template .env
```

Fill `.env`. `utils/database.py` reads:

```text
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=
POSTGRES_DB=postgres
```

`sql_analyst.py` currently reads `host`, `port`, `user`, `password`, and `database` from the environment when it builds a connection. Set those as well (same values as the `POSTGRES_*` keys) until both paths share one config.

Also set:

```text
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
```

Load the sample CSVs into the `public` schema of `POSTGRES_DB` before asking SQL questions.

## Run

From the repo root (so `agents` and `Models` import cleanly):

```bash
uv run python main.py
```

`main.py` asks the agent to extract [PokeAPI](https://pokeapi.co/api/v2/pokemon) into `data/extract` as CSV. That should route to ETL.

Run a subgraph directly:

```bash
uv run python agents/etl_analyst.py
uv run python agents/sql_analyst.py
```

The SQL `__main__` example asks which payment methods exist in the database.

Importing `agents/data_agent.py` also writes `data_agent_graph.png` (Mermaid render of the compiled graph).

## Models

`utils/llm_pickup.py` maps a level to a chat model:

| Level | Model |
| --- | --- |
| `low` | `gpt-5.6-luna` |
| `medium` | `gpt-5.6-terra` |
| `high` | `gpt-5.6-sol` |
| `claude` | `claude-sonnet-5` |

The data-agent router and ETL analyst use `claude`. SQL curation and the final answer use `low`; SQL generation and the safety judge use `medium`.

## License

Apache License 2.0. See [LICENSE](LICENSE).
