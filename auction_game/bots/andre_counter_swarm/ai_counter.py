from auction_game.bots.andre_counter_swarm._strategy import CounterConfig, build_counter_bot


BOT_CLASS = build_counter_bot(CounterConfig(bot_name="AiCounterBot", category="ai"))
