from auction_game.bots.andre_team._strategy import SpecialistConfig, build_specialist_bot


BOT_CLASS = build_specialist_bot(SpecialistConfig(bot_name="BrandSpecialistBot", category="brand"))
