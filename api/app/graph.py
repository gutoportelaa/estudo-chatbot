"""Definição do grafo LangGraph: um nó que chama o LLM (Ollama).

O histórico é mantido pelo checkpointer (SqliteSaver), isolado por `thread_id`.
Cada `thread_id` corresponde ao `session_id` de um usuário, garantindo que
conversas de usuários diferentes nunca se misturem.
"""

from langchain_core.messages import SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import START, MessagesState, StateGraph

from .config import get_settings


def build_graph(checkpointer):
    """Compila o grafo usando o checkpointer fornecido (gerenciado no lifespan)."""
    settings = get_settings()

    llm = ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0.7,
    )
    system_message = SystemMessage(content=settings.system_prompt)

    async def call_model(state: MessagesState) -> dict:
        # Antepõe o system prompt sem persisti-lo no histórico.
        response = await llm.ainvoke([system_message, *state["messages"]])
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("model", call_model)
    builder.add_edge(START, "model")

    return builder.compile(checkpointer=checkpointer)
