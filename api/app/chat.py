"""Lógica de streaming de respostas via SSE e leitura de histórico."""

from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage


def _sse(data: str) -> str:
    """Formata uma linha de Server-Sent Events."""
    return f"data: {data}\n\n"


async def stream_chat(graph, session_id: str, message: str) -> AsyncIterator[str]:
    """Gera eventos SSE com os tokens da resposta para uma sessão específica.

    `thread_id = session_id` isola o histórico desta conversa.
    """
    config = {"configurable": {"thread_id": session_id}}
    inputs = {"messages": [HumanMessage(content=message)]}

    async for chunk, _meta in graph.astream(
        inputs, config=config, stream_mode="messages"
    ):
        # No stream_mode="messages", `chunk` é um AIMessageChunk com os tokens.
        if isinstance(chunk, AIMessage) and chunk.content:
            # Escapa quebras de linha para não quebrar o protocolo SSE.
            yield _sse(chunk.content.replace("\n", "\\n"))

    yield _sse("[DONE]")


async def get_history(graph, session_id: str) -> list[dict]:
    """Retorna o histórico (user/assistant) persistido para a sessão."""
    config = {"configurable": {"thread_id": session_id}}
    state = await graph.aget_state(config)
    messages = state.values.get("messages", []) if state and state.values else []

    history: list[dict] = []
    for m in messages:
        if isinstance(m, HumanMessage):
            history.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            history.append({"role": "assistant", "content": m.content})
    return history
