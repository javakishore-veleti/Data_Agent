import logging
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.logging_config import log_run_result
from utils.llm_pickup import pick_llm
from utils.etl_tools import ETLTools
from Models.schema import RouterSchema, DataAgentSchema, ETLAgentSchema, AgentSchema
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langchain.tools import tool
from langchain_anthropic import ChatAnthropic
from agents.etl_analyst import etl_analyst
from agents.sql_analyst import sql_analyst

logger = logging.getLogger(__name__)

llm = pick_llm("claude")

# Force the LLM to return RouterSchema (answer: "sql" | "etl") instead of free-form text.
llm_router = llm.with_structured_output(RouterSchema)


# ---------------------------- DATA AGENT GRAPH ---------------------------- #


def router_node(state:DataAgentSchema):
    """Classify the latest user message as SQL or ETL and store the route on state."""

    message = state.messages[-1].content

    # Structured output may be a Pydantic model or a dict depending on the LLM wrapper.
    route_result = llm_router.invoke(message)
    if isinstance(route_result, RouterSchema):
        route_response = route_result.answer
    elif isinstance(route_result, dict):
        route_response = route_result["answer"]
    else:
        raise TypeError(f"Unexpected router output type: {type(route_result)}")

    state.route_response = route_response
    logger.debug("Route response: %s", state.route_response)

    return state


def route_safety_eval(state: DataAgentSchema) -> dict:
    """Fail-closed: only sql or etl may continue."""
    if state.route_response in ("sql", "etl"):
        logger.debug("Route safety: passed.")
        return {"route_safe": "Yes", "route_safety_comments": ""}
    comments = f"Invalid route {state.route_response!r}; expected sql or etl."
    logger.warning("Route safety: blocked. %s", comments)
    return {"route_safe": "No", "route_safety_comments": comments}


def route_rejected_node(state: DataAgentSchema) -> dict:
    content = state.route_safety_comments or "Request was not routed to SQL or ETL."
    return {"messages": [AIMessage(content=content)]}


def etl_node(state:DataAgentSchema):
    """Hand the user question to the ETL subgraph."""

    message = state.messages[-1].content

    response = etl_analyst.invoke(
        ETLAgentSchema(messages=[HumanMessage(content=f"""
            {message}
    """)])
        ) 
    state.messages = state.messages + [response]

    return state

def sql_node(state:DataAgentSchema):
    """Hand the user question to the SQL subgraph."""

    message = state.messages[-1].content

    input_schema = AgentSchema(
        messages=[],
        user_question=f"{message}",
        curated_question="",
        prompt_query_context="",
        is_safe="No",
        generated_sql_query="",
        sql_execution_result="",
        final_answer="",
    )

    response = sql_analyst.invoke(input_schema)

    state.messages = state.messages + [response]

    return state

# Empty LangGraph: nodes/edges come next. DataAgentSchema is the shared state
# (messages + route_response) that every node receives and returns.
data_agent_graph = StateGraph(DataAgentSchema)

data_agent_graph.add_node("router_node", router_node)
data_agent_graph.add_node("route_safety_eval", route_safety_eval)
data_agent_graph.add_node("route_rejected_node", route_rejected_node)
data_agent_graph.add_node("etl_node", etl_node)
data_agent_graph.add_node("sql_node", sql_node)

# Every run starts at the classifier, then a fail-closed route eval.
data_agent_graph.add_edge(START, "router_node")
data_agent_graph.add_edge("router_node", "route_safety_eval")

def route_edge(state: DataAgentSchema) -> str:
    """Map the router classification to the next graph node."""
    if state.route_safe != "Yes":
        return "route_rejected_node"
    if state.route_response == "sql":
        return "sql_node"
    elif state.route_response == "etl":
        return "etl_node"
    else:
        return "route_rejected_node"


# After route_safety_eval, branch on route_edge's return value.
data_agent_graph.add_conditional_edges("route_safety_eval", route_edge,
                                      {
                                          "sql_node": "sql_node",
                                          "etl_node": "etl_node",
                                          "route_rejected_node": "route_rejected_node",
                                      })
data_agent_graph.add_edge("route_rejected_node", END)

# one data_agent for the whole app; 
# per-user state only if you add persistence + thread_id; 
# compaction only once you keep a long message history.
data_agent = data_agent_graph.compile()

# Optional graph image; skip if mermaid.ink is unreachable.
try:
    graph_png = data_agent.get_graph().draw_mermaid_png()
    with open("data_agent_graph.png", "wb") as f:
        f.write(graph_png)
except Exception as exc:
    logger.warning("Could not render data_agent_graph.png: %s", exc)

if __name__ == "__main__":

    response = data_agent.invoke(
        DataAgentSchema(
            messages=[HumanMessage(content="I want to extract the data from the API endpoint 'https://pokeapi.co/api/v2/pokemon' and save it to data/extract folder in the csv folder")],
            route_response="",
        )
    )

    log_run_result(logger, response)