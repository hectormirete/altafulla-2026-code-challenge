from auction_game.bots.andre_optimizer.optimizer import AndreOptimizerBot


class BalancedOpenerOptimizerBot(AndreOptimizerBot):
    def _opening_ratio(self, state):
        if self._opponent_chase_events >= 2:
            return 0.72
        if self._opponent_overpay_events:
            return 0.70
        if state.round_index <= 2:
            return 0.79
        return 0.76


BOT_CLASS = BalancedOpenerOptimizerBot
