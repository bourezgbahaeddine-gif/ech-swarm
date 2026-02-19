"""MSI LangGraph runner."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from app.core.logging import get_logger
from app.msi.nodes import MsiGraphNodes
from app.msi.state import MSIState

logger = get_logger("msi.graph")


class MsiGraphRunner:
    def __init__(
        self,
        nodes: MsiGraphNodes,
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

        builder.add_node("load_profile", self._wrap_node("load_profile", self.nodes.load_profile))
        builder.add_node("build_queries", self._wrap_node("build_queries", self.nodes.build_queries))
        builder.add_node("collect_articles", self._wrap_node("collect_articles", self.nodes.collect_articles))
        builder.add_node("dedupe_and_normalize", self._wrap_node("dedupe_and_normalize", self.nodes.dedupe_and_normalize))
        builder.add_node("analyze_items", self._wrap_node("analyze_items", self.nodes.analyze_items))
        builder.add_node("aggregate_metrics", self._wrap_node("aggregate_metrics", self.nodes.aggregate_metrics))
        builder.add_node("compute_msi", self._wrap_node("compute_msi", self.nodes.compute_msi))
        builder.add_node("generate_report", self._wrap_node("generate_report", self.nodes.generate_report))

        builder.set_entry_point("load_profile")
        builder.add_edge("load_profile", "build_queries")
        builder.add_edge("build_queries", "collect_articles")
        builder.add_edge("collect_articles", "dedupe_and_normalize")
        builder.add_edge("dedupe_and_normalize", "analyze_items")
        builder.add_edge("analyze_items", "aggregate_metrics")
        builder.add_edge("aggregate_metrics", "compute_msi")
        builder.add_edge("compute_msi", "generate_report")
        builder.add_edge("generate_report", END)
        return builder.compile()

    def _wrap_node(self, node_name: str, handler):
        async def _wrapped(state: dict[str, Any]) -> dict[str, Any]:
            await self.emit_event(node_name, "started", {"node": node_name})
            try:
                update = await handler(state)
                merged_state = {**state, **(update or {})}
                await self.emit_event(node_name, "finished", {"keys": list((update or {}).keys())})
                return merged_state
            except Exception as exc:  # noqa: BLE001
                await self.emit_event(node_name, "failed", {"error": str(exc)})
                logger.error("msi_node_failed", node=node_name, error=str(exc))
                raise

        return _wrapped

    async def run(self, initial_state: MSIState) -> MSIState:
        result = await self.graph.ainvoke(initial_state.model_dump())
        return MSIState.model_validate(result)
