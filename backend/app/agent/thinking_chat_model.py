from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_openai import ChatOpenAI


def _reasoning_content_from_message(message: BaseMessage) -> str | None:
    if not isinstance(message, AIMessage):
        return None
    value = message.additional_kwargs.get("reasoning_content")
    return value if isinstance(value, str) else None


def _attach_reasoning_content(message: AIMessage, reasoning_content: str) -> AIMessage:
    additional_kwargs = dict(message.additional_kwargs)
    additional_kwargs["reasoning_content"] = reasoning_content
    return message.model_copy(update={"additional_kwargs": additional_kwargs})


def _inject_reasoning_content(payload: dict[str, Any], source_messages: list[BaseMessage]) -> None:
    outbound_messages = payload.get("messages")
    if not isinstance(outbound_messages, list):
        return

    for source, outbound in zip(source_messages, outbound_messages, strict=False):
        if outbound.get("role") != "assistant" or not isinstance(source, AIMessage):
            continue
        reasoning = _reasoning_content_from_message(source)
        if reasoning is not None:
            outbound["reasoning_content"] = reasoning
        elif source.tool_calls:
            outbound["reasoning_content"] = ""


class ThinkingCompatibleChatOpenAI(ChatOpenAI):
    """Round-trip reasoning_content for OpenAI-compatible thinking-mode models."""

    def _get_request_payload(
        self,
        input_: Any,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        if self._use_responses_api(payload):
            return payload
        source_messages = self._convert_input(input_).to_messages()
        _inject_reasoning_content(payload, source_messages)
        return payload

    def _create_chat_result(
        self,
        response: dict | Any,
        generation_info: dict | None = None,
    ) -> ChatResult:
        result = super()._create_chat_result(response, generation_info=generation_info)
        response_dict = (
            response
            if isinstance(response, dict)
            else response.model_dump(exclude={"choices": {"__all__": {"message": {"parsed"}}}})
        )
        choices = response_dict.get("choices") or []
        for generation, choice in zip(result.generations, choices, strict=False):
            message_dict = choice.get("message") or {}
            reasoning = message_dict.get("reasoning_content")
            if isinstance(reasoning, str) and isinstance(generation.message, AIMessage):
                generation.message = _attach_reasoning_content(generation.message, reasoning)
        return result

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk,
            default_chunk_class,
            base_generation_info,
        )
        if generation_chunk is None:
            return None

        choices = chunk.get("choices", []) or chunk.get("chunk", {}).get("choices", [])
        if not choices:
            return generation_chunk

        delta = choices[0].get("delta") or {}
        reasoning = delta.get("reasoning_content")
        if not isinstance(reasoning, str):
            return generation_chunk

        message = generation_chunk.message
        if not isinstance(message, AIMessageChunk):
            return generation_chunk

        additional_kwargs = dict(message.additional_kwargs)
        previous = additional_kwargs.get("reasoning_content")
        merged = f"{previous}{reasoning}" if isinstance(previous, str) else reasoning
        additional_kwargs["reasoning_content"] = merged
        generation_chunk.message = message.model_copy(update={"additional_kwargs": additional_kwargs})
        return generation_chunk
