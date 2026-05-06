from auction_game.bots.andre_optimizer.optimizer import AndreOptimizerBot


class HighOpenerOptimizerBot(AndreOptimizerBot):
    def _opening_ratio(self, state):
        if self._opponent_chase_events >= 2:
            return 0.82
        if self._opponent_overpay_events:
            return 0.78
        if state.round_index <= 2:
            return 0.92
        return 0.88


BOT_CLASS = HighOpenerOptimizerBot
