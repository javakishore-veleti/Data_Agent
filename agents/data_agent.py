import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents import sql_analyst
from utils.llm_pickup import pick_llm
from utils.etl_tools import ETLTools
from Models.schema import RouterSchema, DataAgentSchema, ETLAgentSchema, AgentSchema
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langchain.tools import tool
from langchain_anthropic import ChatAnthropic
from agents.etl_analyst import etl_analyst
from agents.sql_analyst import sql_analyst


llm = pick_llm("claude")

llm_router = llm.with_structured_output(RouterSchema)


# ---------------------------- DATA AGENT GRAPH ---------------------------- #


def router_node(state:DataAgentSchema):

    message = state.messages[-1].content

    route_result = llm_router.invoke(message)
    if isinstance(route_result, RouterSchema):
        route_response = route_result.answer
    elif isinstance(route_result, dict):
        route_response = route_result["answer"]
    else:
        raise TypeError(f"Unexpected router output type: {type(route_result)}")

    state.route_response = route_response

    return state

def etl_node(state:DataAgentSchema):

    message = state.messages[-1].content

    response = etl_analyst.invoke(
        ETLAgentSchema(messages=[HumanMessage(content=f"""
            {message}
    """)])
        ) 
    state.messages = state.messages + [response]

    return state

def sql_node(state:DataAgentSchema):

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

data_agent_graph = StateGraph(DataAgentSchema)

data_agent_graph.add_node("router_node", router_node)
data_agent_graph.add_node("etl_node", etl_node)
data_agent_graph.add_node("sql_node", sql_node)

data_agent_graph.add_edge(START, "router_node")

def route_edge(state: DataAgentSchema) -> str:
    if state.route_response == "sql":
        return "sql_node"
    elif state.route_response == "etl":
        return "etl_node"
    else:
        raise ValueError(f"Invalid route response: {state.route_response}")


data_agent_graph.add_conditional_edges("router_node", route_edge,
                                      {
                                          "sql_node": "sql_node",
                                          "etl_node": "etl_node"
                                      })

data_agent = data_agent_graph.compile()

# Optional
graph_png = data_agent.get_graph().draw_mermaid_png()
with open("data_agent_graph.png", "wb") as f:
    f.write(graph_png)

if __name__ == "__main__":

    response = data_agent.invoke(
        DataAgentSchema(
            messages=[HumanMessage(content="I want to extract the data from the API endpoint 'https://pokeapi.co/api/v2/pokemon' and save it to data/extract folder in the csv folder")],
            route_response="",
        )
    )

    print(response)