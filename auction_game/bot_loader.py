from __future__ import annotations

import inspect
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

from auction_game.interfaces import AuctionBot


@dataclass(frozen=True, slots=True)
class BotSpec:
    user_name: str
    bot_name: str
    file_path: Path

    @property
    def bot_id(self) -> str:
        return f"{self.user_name}/{self.bot_name}"


def discover_bots(bots_dir: Path) -> list[BotSpec]:
    bots: list[BotSpec] = []
    for path in sorted(bots_dir.glob("*/*.py")):
        if path.name.startswith("_") or path.parent.name.startswith("_"):
            continue
        bots.append(
            BotSpec(
                user_name=path.parent.name,
                bot_name=path.stem,
                file_path=path,
            )
        )
    return bots


def load_bot(bot_spec: BotSpec) -> AuctionBot:
    module_name = (
        "auction_game_dynamic_bots."
        f"{bot_spec.user_name.replace('-', '_')}.{bot_spec.bot_name}"
    )
    spec = importlib.util.spec_from_file_location(module_name, bot_spec.file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load bot module from {bot_spec.file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    bot_class = getattr(module, "BOT_CLASS", None)

    if bot_class is None:
        for _, candidate in inspect.getmembers(module, inspect.isclass):
            if issubclass(candidate, AuctionBot) and candidate is not AuctionBot:
                bot_class = candidate
                break

    if bot_class is None:
        raise ValueError(f"Bot module {bot_spec.bot_id} does not define a bot class")
    if not issubclass(bot_class, AuctionBot):
        raise TypeError(f"BOT_CLASS for {bot_spec.bot_id} must inherit from AuctionBot")

    return bot_class()
