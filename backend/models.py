"""Typed data contracts used across the application."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Sequence


@dataclass(slots=True)
class Team:
    id: str
    league_id: str
    name: str
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float
    playoff_odds: float


@dataclass(slots=True)
class Player:
    id: str
    name: str
    position: str
    team: str
    bye_week: int
    injury_status: str


@dataclass(slots=True)
class Projection:
    player_id: str
    week: int
    source: str
    projected_points: float
    floor: float
    ceiling: float


@dataclass(slots=True)
class RosterSpot:
    player: Player
    slot: str
    status: Literal["start", "bench", "ir"]
    projected_points: float
    opponent: str
    notes: str


@dataclass(slots=True)
class League:
    id: str
    name: str
    season: int
    scoring_type: str
    is_active: bool


@dataclass(slots=True)
class Matchup:
    league_id: str
    week: int
    home_team_id: str
    away_team_id: str
    home_score: float
    away_score: float
    kickoff: datetime


@dataclass(slots=True)
class WaiverCandidate:
    player: Player
    ros_value: float
    scarcity_score: float
    team_fit_score: float
    bye_coverage_score: float
    schedule_score: float
    total_score: float
    explanation: str


@dataclass(slots=True)
class TradeProposal:
    offer_players: Sequence[Player]
    request_players: Sequence[Player]
    offer_value: float
    request_value: float
    lineup_delta: float
    playoff_odds_delta: float
    notes: str


@dataclass(slots=True)
class SimulationResult:
    league_id: str
    week: int
    runs: int
    win_probability: float
    playoff_odds: float
    median_score: float
    percentiles: dict[str, float]


@dataclass(slots=True)
class Notification:
    id: str
    user_id: str
    league_id: str | None
    type: str
    message: str
    delivered: bool
    created_at: datetime
