from auction_game.bots.andre_optimizer.optimizer import AndreOptimizerBot


class LowOpenerOptimizerBot(AndreOptimizerBot):
    def _opening_ratio(self, state):
        if self._opponent_chase_events >= 2:
            return 0.68
        if self._opponent_overpay_events:
            return 0.66
        if state.round_index <= 2:
            return 0.74
        return 0.71


BOT_CLASS = LowOpenerOptimizerBot
