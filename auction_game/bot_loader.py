from __future__ import annotations

import importlib
import inspect
from pathlib import Path

from auction_game.interfaces import AuctionBot


def discover_bot_names(bots_dir: Path) -> list[str]:
    names = []
    for path in sorted(bots_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        names.append(path.stem)
    return names


def load_bot(package_prefix: str, bot_name: str) -> AuctionBot:
    module = importlib.import_module(f"{package_prefix}.{bot_name}")
    bot_class = getattr(module, "BOT_CLASS", None)

    if bot_class is None:
        for _, candidate in inspect.getmembers(module, inspect.isclass):
            if issubclass(candidate, AuctionBot) and candidate is not AuctionBot:
                bot_class = candidate
                break

    if bot_class is None:
        raise ValueError(f"Bot module {package_prefix}.{bot_name} does not define a bot class")
    if not issubclass(bot_class, AuctionBot):
        raise TypeError(f"BOT_CLASS for {package_prefix}.{bot_name} must inherit from AuctionBot")

    return bot_class()
