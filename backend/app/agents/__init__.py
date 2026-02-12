"""Agents package — The Digital Swarm."""
from app.agents.scout import scout_agent
from app.agents.router import router_agent
from app.agents.scribe import scribe_agent
from app.agents.trend_radar import trend_radar_agent
from app.agents.audio_agent import audio_agent

__all__ = [
    "scout_agent",
    "router_agent",
    "scribe_agent",
    "trend_radar_agent",
    "audio_agent",
]
