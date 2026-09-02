from pydantic import BaseModel, Field
from typing import Annotated, Literal
from operator import add

class AgentSchema(BaseModel):
    """
    Represents the state of an agent.
    """
    messages:Annotated[list,add] = Field(..., description="The messages of the agent." )
    user_question: str = Field(..., description="The user question of the agent." )
    curated_question : str = Field(..., description="The curated question of the agent." )
    prompt_query_context: str = Field(..., description="The prompt query context of the agent." )
    is_safe: Literal["Yes", "No"] = Field(..., description="Whether the LLM judge considers the SQL safe." )
    generated_sql_query: str = Field(..., description="The generated SQL query of the agent." )
    sql_execution_result: str = Field(..., description="The SQL execution result of the agent." )
    final_answer: str = Field(..., description="The final answer of the agent." )
    comments: str = Field(default="", description="LLM judge comments on SQL safety." )
    keyword_safe: Literal["Yes", "No"] = Field(default="No", description="Fail-closed SQL keyword eval." )
    keyword_comments: str = Field(default="", description="Why the keyword eval passed or failed." )
    sql_result_safe: Literal["Yes", "No"] = Field(default="No", description="Fail-closed eval after SQL execute." )
    sql_result_comments: str = Field(default="", description="Why the SQL result eval passed or failed." )


class JudgeSchema(BaseModel):
    answer : Literal["Yes","No"] = Field(..., description="Indicates whether the generated SQL query is safe to execute or not")
    comments : str = Field(..., description="Additional comments or feedback from the judge regarding the SQL query")


class ETLAgentSchema(BaseModel):
    messages : Annotated[list,add] = Field(..., description="List of messages to be processed by the ETL agent")
    etl_safe: Literal["Yes", "No"] = Field(default="No", description="Fail-closed ETL tool-arg eval." )
    etl_safety_comments: str = Field(default="", description="Why the ETL tool call was allowed or blocked." )
    etl_result_safe: Literal["Yes", "No"] = Field(default="No", description="Fail-closed eval after ETL tools run." )
    etl_result_comments: str = Field(default="", description="Why the ETL result eval passed or failed." )

class RouterSchema(BaseModel):
    """Structured classifier output used by llm_router to pick SQL vs ETL."""
    answer: Literal["sql","etl"] = Field(..., description="Indicates whether the user's question is related to SQL or ETL operations")
    comments: str = Field(..., description="Additional comments or feedback regarding the classification of the user's question")

class DataAgentSchema(BaseModel):
    messages : Annotated[list,add] = Field(..., description="List of messages to be processed by the Data agent")
    route_response : str = Field(..., description="The response from the router indicating whether to route to SQL or ETL operations")
    route_safe: Literal["Yes", "No"] = Field(default="No", description="Fail-closed router eval: sql or etl only." )
    route_safety_comments: str = Field(default="", description="Why the route was allowed or rejected." ) 