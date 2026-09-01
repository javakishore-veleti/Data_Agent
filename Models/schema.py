from pydantic import BaseModel, Field
from typing import Annotated, Literal
from operator import add

class AgentState(BaseModel):
    """
    Represents the state of an agent.
    """
    messages:Annotated[list,add] = Field(..., description="The messages of the agent." )
    curated_ques : str = Field(..., description="The curated question of the agent." )
    prompt_query_context: str = Field(..., description="The prompt query context of the agent." )
    is_safe: Literal["Yes", "No"] = Field(..., description="Whether the agent is safe." )
    generated_sql_query: str = Field(..., description="The generated SQL query of the agent." )
    sql_execution_result: str = Field(..., description="The SQL execution result of the agent." )
    final_answer: str = Field(..., description="The final answer of the agent." )

    