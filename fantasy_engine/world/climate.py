from __future__ import annotations

from dataclasses import dataclass

from fantasy_engine.core.engine import Phase, TickContext


@dataclass(slots=True)
class SeasonalOutlook:
    rainfall_modifier: float
    harvest_modifier: float
    spoilage_modifier: float
    consumption_modifier: float


class ClimateSystem:
    phase = Phase.CLIMATE

    def update(self, world: "World", context: TickContext) -> None:
        for civilization in world.civilizations:
            region = civilization.region
            weather_shift = world.rng.uniform(0.88, 1.12)
            rainfall_modifier = region.rainfall * weather_shift
            harvest_modifier = rainfall_modifier * region.fertility
            spoilage_modifier = 1.0 + (region.route_cost - 1.0) * 0.12
            consumption_modifier = 1.0

            if context.season == "winter":
                harvest_modifier *= 0.25
                consumption_modifier += region.winter_severity * 0.18
                spoilage_modifier += region.winter_severity * 0.08
            elif context.season == "autumn":
                harvest_modifier *= 1.35
            elif context.season == "spring":
                harvest_modifier *= 0.65

            civilization.outlook = SeasonalOutlook(
                rainfall_modifier=rainfall_modifier,
                harvest_modifier=harvest_modifier,
                spoilage_modifier=spoilage_modifier,
                consumption_modifier=consumption_modifier,
            )