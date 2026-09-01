import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Models.schema import AgentSchema
from utils.llm_pickup import pick_llm


def curate_question(state: AgentSchema) -> AgentSchema:

    user_question = state.user_question

    llm = pick_llm("low")
    response = llm.invoke(f"Curate the following question: {user_question}")
    curated_question = response.text
    state.curated_question = curated_question

    return state

def prompt_query_context(state: AgentSchema) -> AgentSchema:
    curated_question = state.curated_question

    return state


