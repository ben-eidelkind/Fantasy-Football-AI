"""Analytics and recommendation engines."""
from __future__ import annotations

import itertools
import json
import math
import random
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Iterable

from . import db
from .models import Player, Projection, SimulationResult, TradeProposal, WaiverCandidate

CURRENT_WEEK = 8


@dataclass(slots=True)
class OptimizedLineup:
    lineup: list[dict]
    total_projection: float
    delta: float
    rationale: str


POSITION_REPLACEMENT = {
    "QB": 18.0,
    "RB": 12.0,
    "WR": 11.0,
    "TE": 8.0,
    "FLEX": 10.5,
}


def _player_from_row(row) -> Player:
    return Player(
        id=row["id"],
        name=row["name"],
        position=row["position"],
        team=row["team"],
        bye_week=row["bye_week"] or 0,
        injury_status=row["injury_status"] or "ACTIVE",
    )


def blend_projections(player_id: str, week: int = CURRENT_WEEK) -> Projection:
    rows = db.query_all(
        "SELECT source, projected_points, floor, ceiling FROM projections WHERE player_id = ? AND week = ?",
        (player_id, week),
    )
    if not rows:
        return Projection(player_id, week, "demo", 0.0, 0.0, 0.0)
    weights = {
        "fantasycalc": 0.6,
        "nfldata": 0.3,
        "mock-blend": 0.1,
    }
    total_weight = 0.0
    blended = {"points": 0.0, "floor": 0.0, "ceiling": 0.0}
    for row in rows:
        w = weights.get(row["source"], 0.2)
        total_weight += w
        blended["points"] += row["projected_points"] * w
        blended["floor"] += row["floor"] * w
        blended["ceiling"] += row["ceiling"] * w
    scale = 1 / total_weight if total_weight else 1.0
    return Projection(
        player_id=player_id,
        week=week,
        source="blended",
        projected_points=round(blended["points"] * scale, 2),
        floor=round(blended["floor"] * scale, 2),
        ceiling=round(blended["ceiling"] * scale, 2),
    )


def start_sit_for_roster(roster_id: str) -> OptimizedLineup:
    spots = db.query_all(
        """
        SELECT roster_spots.*, players.name, players.position, players.team, players.bye_week, players.injury_status
        FROM roster_spots
        JOIN players ON players.id = roster_spots.player_id
        WHERE roster_id = ?
        """,
        (roster_id,),
    )
    lineup = []
    baseline = 0.0
    optimized_total = 0.0
    rationale_lines = []
    for spot in spots:
        projection = blend_projections(spot["player_id"])
        replacement = POSITION_REPLACEMENT.get(spot["slot"], POSITION_REPLACEMENT.get(spot["status"].upper(), 9.5))
        start_score = projection.projected_points + (projection.projected_points - replacement) * 0.35
        risk_modifier = 0.0 if spot["status"] == "start" else -1.5
        recommendation = "start" if start_score + risk_modifier >= replacement else "bench"
        lineup.append(
            {
                "player_id": spot["player_id"],
                "name": spot["name"],
                "slot": spot["slot"],
                "status": spot["status"],
                "projected_points": projection.projected_points,
                "recommendation": recommendation,
                "rationale": f"Proj {projection.projected_points} vs replacement {replacement}",
            }
        )
        if spot["status"] == "start":
            baseline += spot["projected_points"]
        if recommendation == "start":
            optimized_total += max(projection.projected_points, replacement)
        else:
            optimized_total += replacement
        rationale_lines.append(
            f"{spot['name']}: {recommendation.upper()} (blend {projection.projected_points} / floor {projection.floor})"
        )
    delta = round(optimized_total - baseline, 2)
    return OptimizedLineup(
        lineup=lineup,
        total_projection=round(optimized_total, 2),
        delta=delta,
        rationale="; ".join(rationale_lines),
    )


def _league_players_not_on_team(league_id: str, team_id: str) -> list[Player]:
    rows = db.query_all(
        """
        SELECT DISTINCT players.*
        FROM players
        LEFT JOIN roster_spots ON roster_spots.player_id = players.id
        LEFT JOIN rosters ON rosters.id = roster_spots.roster_id
        WHERE (rosters.league_id != ? OR rosters.team_id != ? OR rosters.team_id IS NULL)
        """,
        (league_id, team_id),
    )
    return [_player_from_row(row) for row in rows]


def waiver_recommendations(league_id: str, team_id: str, limit: int = 5) -> list[WaiverCandidate]:
    candidates: list[WaiverCandidate] = []
    for player in _league_players_not_on_team(league_id, team_id):
        projection = blend_projections(player.id)
        ros_value = projection.projected_points * 0.9 + projection.ceiling * 0.1
        scarcity = 1.2 if player.position in {"RB", "WR"} else 1.0
        bye_bonus = 1.1 if player.bye_week not in {5, 9} else 0.9
        schedule = 1.0
        total = round(ros_value * scarcity * bye_bonus * schedule, 2)
        candidates.append(
            WaiverCandidate(
                player=player,
                ros_value=round(ros_value, 2),
                scarcity_score=scarcity,
                team_fit_score=round(bye_bonus, 2),
                bye_coverage_score=round(bye_bonus, 2),
                schedule_score=round(schedule, 2),
                total_score=total,
                explanation=f"Blended proj {projection.projected_points}, scarcity {scarcity}",
            )
        )
    candidates.sort(key=lambda c: c.total_score, reverse=True)
    return candidates[:limit]


def _team_players(team_id: str) -> list[Player]:
    rows = db.query_all(
        """
        SELECT players.*
        FROM roster_spots
        JOIN rosters ON rosters.id = roster_spots.roster_id
        JOIN players ON players.id = roster_spots.player_id
        WHERE rosters.team_id = ?
        """,
        (team_id,),
    )
    return [_player_from_row(row) for row in rows]


def trade_ideas(league_id: str, team_id: str) -> list[TradeProposal]:
    team_players = _team_players(team_id)
    other_team_rows = db.query_all(
        "SELECT id FROM teams WHERE league_id = ? AND id != ?",
        (league_id, team_id),
    )
    proposals: list[TradeProposal] = []
    for other in other_team_rows:
        other_players = _team_players(other["id"])
        for give_count in (1, 2):
            for receive_count in (1, 2):
                for give in itertools.combinations(team_players, give_count):
                    for receive in itertools.combinations(other_players, receive_count):
                        give_value = sum(blend_projections(p.id).projected_points for p in give)
                        receive_value = sum(blend_projections(p.id).projected_points for p in receive)
                        lineup_delta = round(receive_value - give_value, 2)
                        playoff_delta = round(lineup_delta * 0.02, 3)
                        if lineup_delta <= 0:
                            continue
                        proposals.append(
                            TradeProposal(
                                offer_players=give,
                                request_players=receive,
                                offer_value=round(give_value, 2),
                                request_value=round(receive_value, 2),
                                lineup_delta=lineup_delta,
                                playoff_odds_delta=playoff_delta,
                                notes="Improves starting lineup with higher floor",
                            )
                        )
    proposals.sort(key=lambda p: p.lineup_delta, reverse=True)
    return proposals[:3]


def simulate_matchup(league_id: str, team_id: str, opponent_team_id: str, runs: int = 500) -> SimulationResult:
    rng = random.Random(f"{league_id}-{team_id}-{opponent_team_id}")
    team_players = _team_players(team_id)
    opponent_players = _team_players(opponent_team_id)
    team_scores = []
    opponent_scores = []
    for _ in range(runs):
        team_scores.append(_simulate_team_score(rng, team_players))
        opponent_scores.append(_simulate_team_score(rng, opponent_players))
    wins = sum(1 for a, b in zip(team_scores, opponent_scores) if a > b)
    win_probability = wins / runs
    playoff_odds = min(0.99, 0.5 + (win_probability - 0.5) * 1.5)
    percentiles = {
        "p10": round(_percentile(team_scores, 10), 2),
        "p50": round(_percentile(team_scores, 50), 2),
        "p90": round(_percentile(team_scores, 90), 2),
    }
    summary = SimulationResult(
        league_id=league_id,
        week=CURRENT_WEEK,
        runs=runs,
        win_probability=round(win_probability, 3),
        playoff_odds=round(playoff_odds, 3),
        median_score=percentiles["p50"],
        percentiles=percentiles,
    )
    db.execute(
        """
        INSERT OR REPLACE INTO simulation_results (id, league_id, week, summary)
        VALUES (?, ?, ?, ?)
        """,
        (
            f"sim-{league_id}-{team_id}-{opponent_team_id}",
            league_id,
            CURRENT_WEEK,
            json.dumps(asdict(summary)),
        ),
    )
    return summary


def _simulate_team_score(rng: random.Random, players: Iterable[Player]) -> float:
    total = 0.0
    for player in players:
        projection = blend_projections(player.id)
        if projection.projected_points == 0:
            continue
        std_dev = max(2.5, (projection.ceiling - projection.floor) / 3)
        score = rng.gauss(projection.projected_points, std_dev)
        score = max(0.0, score)
        total += score
    return round(total, 2)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = (len(values) - 1) * percentile / 100
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values[int(k)]
    return values[f] * (c - k) + values[c] * (k - f)


def schedule_heatmap(league_id: str) -> list[dict[str, float]]:
    rows = db.query_all(
        "SELECT week, home_score, away_score FROM matchups WHERE league_id = ?",
        (league_id,),
    )
    heatmap: defaultdict[int, float] = defaultdict(float)
    for row in rows:
        heatmap[row["week"]] += float(row["home_score"]) + float(row["away_score"])
    return [
        {"week": week, "pace": round(score, 2)} for week, score in sorted(heatmap.items())
    ]
