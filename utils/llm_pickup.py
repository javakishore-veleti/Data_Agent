from langchain_openai import ChatOpenAI

def pick_llm(level: str) -> ChatOpenAI:
    """
    Picks the appropriate LLM based on the level of the question.
    """
    if level == "low":
        llm = ChatOpenAI(model="gpt-5.6-luna", temperature=0.0)
    elif level == "medium":
        llm = ChatOpenAI(model="gpt-5.6-terra", temperature=0.0)
    elif level == "high":
        llm = ChatOpenAI(model="gpt-5.6-sol", temperature=0.0)
    else:
        raise ValueError(f"Unsupported level: {level}")

    return llm

if __name__ == "__main__":
    llm_obj = pick_llm("low")
    print(llm_obj.invoke("Hello, how are you?").content)
