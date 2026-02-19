"""Audience simulator LangGraph runner."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from app.core.logging import get_logger
from app.simulator.nodes import SimulationGraphNodes
from app.simulator.state import SimulationState

logger = get_logger("simulator.graph")


class SimulationGraphRunner:
    def __init__(
        self,
        nodes: SimulationGraphNodes,
        emit_event: Callable[[str, str, dict[str, Any]], Awaitable[None]],
    ):
        self.nodes = nodes
        self.emit_event = emit_event
        self.graph = self._build_graph()

    def _build_graph(self):
        try:
            from langgraph.graph import END, StateGraph
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("langgraph is not installed. Please add dependencies and rebuild backend image.") from exc

        builder = StateGraph(dict)
        builder.add_node("load_policy_profile", self._wrap_node("load_policy_profile", self.nodes.load_policy_profile))
        builder.add_node("sanitize_input", self._wrap_node("sanitize_input", self.nodes.sanitize_input))
        builder.add_node("run_persona_simulation", self._wrap_node("run_persona_simulation", self.nodes.run_persona_simulation))
        builder.add_node("compute_scores", self._wrap_node("compute_scores", self.nodes.compute_scores))
        builder.add_node("generate_editor_advice", self._wrap_node("generate_editor_advice", self.nodes.generate_editor_advice))
        builder.add_node("persist_and_return", self._wrap_node("persist_and_return", self.nodes.persist_and_return))

        builder.set_entry_point("load_policy_profile")
        builder.add_edge("load_policy_profile", "sanitize_input")
        builder.add_edge("sanitize_input", "run_persona_simulation")
        builder.add_edge("run_persona_simulation", "compute_scores")
        builder.add_edge("compute_scores", "generate_editor_advice")
        builder.add_edge("generate_editor_advice", "persist_and_return")
        builder.add_edge("persist_and_return", END)
        return builder.compile()

    def _wrap_node(self, node_name: str, handler):
        async def _wrapped(state: dict[str, Any]) -> dict[str, Any]:
            await self.emit_event(node_name, "started", {"node": node_name})
            try:
                update = await handler(state)
                await self.emit_event(node_name, "finished", {"keys": list((update or {}).keys())})
                return {**state, **(update or {})}
            except Exception as exc:  # noqa: BLE001
                await self.emit_event(node_name, "failed", {"error": str(exc)})
                logger.error("simulator_node_failed", node=node_name, error=str(exc))
                raise

        return _wrapped

    async def run(self, initial_state: SimulationState) -> SimulationState:
        result = await self.graph.ainvoke(initial_state.model_dump(mode="json"))
        return SimulationState.model_validate(result)
