import logging

from utils.logging_config import log_run_result
from agents.data_agent import data_agent
from langchain_core.messages import HumanMessage
from Models.schema import DataAgentSchema

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # one data_agent for the whole app; 
    # per-user state only if you add persistence + thread_id; 
    # compaction only once you keep a long message history.
    response = data_agent.invoke(
        DataAgentSchema(
            messages=[HumanMessage(content="I want to extract the data from the API endpoint 'https://pokeapi.co/api/v2/pokemon' and save it to data/extract folder in the csv folder")],
            route_response="",
        )
    )

    log_run_result(logger, response)