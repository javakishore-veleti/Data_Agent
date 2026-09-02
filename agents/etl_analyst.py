import logging
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.logging_config import log_run_result
from utils.llm_pickup import pick_llm
from utils.etl_tools import ETLTools
from utils.safety import as_text, pandas_code_is_safe, validate_etl_tool
from Models.schema import ETLAgentSchema
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langchain.tools import tool
from langchain_anthropic import ChatAnthropic

logger = logging.getLogger(__name__)


#------------------------------------ AGENT TOOLS ------------------------------------#


@tool
def extract_load_tool(url:str, output_folder:str, format:str) -> str:
    """
    This tool extracts the data from the API (url) and loads it into the
    the desired location (output_folder).

    Args:
        url (str): The API endpoint from which to extract data.
        output_folder (str): The folder where the extracted data will be saved.
        format (str): The format in which to save the extracted data (csv, json, parquet).
    
    Returns:
        str: A message indicating the success or failure of the operation.

    """
    etl_tools = ETLTools()
    return etl_tools.extract_load(url, output_folder, format)


@tool
def transform_load_tool(input_file_path:str,output_folder:str,output_format:str, user_question:str) -> str:
    """
    This tool transforms the data from the specified file and loads it into the
    desired location (output_folder).

    Args:
        input_file_path (str): The path to the file containing the data to be transformed.
        output_folder (str): The folder where the transformed data will be saved.
        output_format (str): The format in which to save the transformed data (csv, json, parquet).
    
    Returns:
        str: A message indicating the success or failure of the operation.

    """
    etl_tools = ETLTools()

    top_3_rows = etl_tools.transform_load_context(input_file_path)

    llm = pick_llm("claude")

    prompt = f"""
            You are a Python Data Analyst who uses Pandas to analyze data. 
            You need to provide only the Pandas Code that will help to perform the right ETL operations on the data stored in the file : {input_file_path}
            as per the user's question. Do not provide any explanation or comments, only
            the code should be provided. The code should be in a format that can be executed 
            in a Python environment with Pandas installed. 
            Don't write anything else than Pandas Code. \n
            
            Create the Pandas Dataframe from the data stored in the file : {input_file_path} and then 
            write the code to transform and save the data at {output_folder}.
            Here's the user's question: {user_question}\n
            Here's the context of the data you will be analyzing: {top_3_rows}\n

        """

    response = llm.invoke(prompt).content 

    pandas_code = as_text(response).strip().strip('```').strip().lstrip('python').strip()

    ok, reason = pandas_code_is_safe(pandas_code)
    if not ok:
        return f"Transform blocked: {reason}\n\nPandas Code:\n{pandas_code}"

    results = etl_tools.execute_code(pandas_code)

    return f"The data is transformed and saved at {output_folder} in {output_format} format. \n\n Pandas Code Executed: \n {pandas_code} \n\n Execution Result: \n {results}"


# Toolkit 
tools = [extract_load_tool, transform_load_tool]

llm = pick_llm("claude")
llm_bind = llm.bind_tools(tools)


# ---------------------------------------- AGENT GRAPH ---------------------------------------- #

def llm_node(state:ETLAgentSchema):

    messages = state.messages

    prompt = f"""
            You are a Python Data Analyst who has access to tools that can extract and load, 
            transform and load data. You will be provided with a user's question 
            and you would need to perform the right ETL operations as per the user's question. 
            If the operation is performed then inform the user and end the coversation.
            Here's the chat history: {messages}\n
    """

    final_answer = llm_bind.invoke(prompt)

    state.messages = messages + [final_answer]

    return state


def _iter_tool_calls(message):
    calls = getattr(message, "tool_calls", None) or []
    for call in calls:
        if isinstance(call, dict):
            yield call.get("name"), call.get("args") or {}, call.get("id")
        else:
            yield call["name"], call.get("args") or {}, call["id"]


def etl_tool_safety_eval(state: ETLAgentSchema) -> dict:
    """Fail-closed: URL, format, and paths under data/extract or data/transform."""
    last = state.messages[-1]
    reasons: list[str] = []
    blocked_messages: list[ToolMessage] = []
    for name, args, call_id in _iter_tool_calls(last):
        ok, reason = validate_etl_tool(name, args)
        if not ok:
            reasons.append(reason)
            blocked_messages.append(
                ToolMessage(content=f"Blocked: {reason}", tool_call_id=call_id or "blocked")
            )
    if reasons:
        comments = "; ".join(reasons)
        logger.warning("ETL tool safety: blocked. %s", comments)
        return {
            "etl_safe": "No",
            "etl_safety_comments": comments,
            "messages": blocked_messages,
        }
    logger.debug("ETL tool safety: passed.")
    return {"etl_safe": "Yes", "etl_safety_comments": ""}


def tool_node(state:ETLAgentSchema):
    """
    This node is responsible for invoking the appropriate tool based on the user's question and the context provided by the LLM.
    """

    tools_results = []

    tools_by_name = {tool.name: tool for tool in tools}

    tool_calls = state.messages[-1].tool_calls

    for tool_call in tool_calls:

        tool = tools_by_name[tool_call['name']]
        observation = tool.invoke(tool_call['args'])

        tools_results.append(ToolMessage(content=observation, tool_call_id = tool_call['id']))

    state.messages = state.messages + tools_results

    return state   


# Nodes & Edges
etl_analyst_graph = StateGraph(ETLAgentSchema)
etl_analyst_graph.add_node("llm_node", llm_node)
etl_analyst_graph.add_node("etl_tool_safety_eval", etl_tool_safety_eval)
etl_analyst_graph.add_node("tool_node", tool_node)

etl_analyst_graph.add_edge(START, "llm_node")

def is_tool_call(state:ETLAgentSchema):
    tool_calls = getattr(state.messages[-1], "tool_calls", None)

    if tool_calls:
        return "etl_tool_safety_eval"
    else:
        return "end"

etl_analyst_graph.add_conditional_edges(
    "llm_node",is_tool_call,
    {
        "etl_tool_safety_eval": "etl_tool_safety_eval",
        "end": END
    }
)

def etl_safety_edge(state: ETLAgentSchema) -> str:
    if state.etl_safe == "Yes":
        return "tool_node"
    # ToolMessages with Blocked: already appended; send the model back without executing.
    return "llm_node"

etl_analyst_graph.add_conditional_edges(
    "etl_tool_safety_eval",
    etl_safety_edge,
    {
        "tool_node": "tool_node",
        "llm_node": "llm_node",
    },
)

etl_analyst_graph.add_edge("tool_node", "llm_node")

etl_analyst = etl_analyst_graph.compile()

if __name__ == "__main__":
    # Compile the Graph
    

    # Optional
    from IPython.display import display, Image
    img = Image(etl_analyst.get_graph().draw_mermaid_png())
    with open("etl_analyst_graph.png", "wb") as f:
        f.write(img.data)

    response = etl_analyst.invoke(
        ETLAgentSchema(
            messages=[HumanMessage(content="I want to extract the data from the API endpoint 'https://pokeapi.co/api/v2/pokemon' and save it to data/extract folder in the csv folder")],
        )
    )

#     response = etl_analyst.invoke(
#          {"messages":[HumanMessage(content=f"""
#             I want to transform the data stored in the 'c:\\Data_Agent\\data\\extract\\extracted_data.csv' file 
#             and save the transformed data in the 'c:\\Data_Agent\\data\\transform' folder in the csv format.
#             The transformation should filter the data to show bulbasaur pokemon only.
# """)]}
#     )    

    log_run_result(logger, response)