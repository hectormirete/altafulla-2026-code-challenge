"""Low-risk shadow variant of meta_strategist.

This portfolio bot keeps the tuned strategy but makes passive-opponent typing
reversible. It is meant as a defensive hedge against opponents that open low
for a few rounds and then switch to high pressure.
"""

from __future__ import annotations

from auction_game.bots.pablogomis.meta_strategist import PabloMetaBot


class MetaDenierBot(PabloMetaBot):
    def _is_passive(self) -> bool:
        return self._low_open_samples >= 3 and self._high_open_samples == 0 and not self._mirror_flag


BOT_CLASS = MetaDenierBot
