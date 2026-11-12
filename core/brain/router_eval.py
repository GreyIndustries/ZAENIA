"""The fixed set of labelled messages the router is measured against (SE improvements, 2026-11-08)."""
from __future__ import annotations

CASES: tuple[tuple[str, str], ...] = (
    # chat: stays on the PC with Talk
    ("good morning", "chat"), ("how are you doing today", "chat"), ("what should I focus on first today?", "chat"),
    ("tell me a joke", "chat"), ("explain how a transformer works", "chat"), ("what is photosynthesis", "chat"),
    ("help me write a text to my brother", "chat"), ("what's on my calendar this week", "chat"), ("what do I have today", "chat"),
    ("should I work out today or rest", "chat"), ("can you help me plan my week", "chat"), ("I'm tired, keep it short", "chat"),
    ("what's the capital of France", "chat"), ("how do plants grow", "chat"), ("write a poem about rain", "chat"),
    ("why is the sky blue", "chat"), ("give me a recipe idea for dinner", "chat"), ("what did I eat today", "chat"),
    ("summarize what we just talked about", "chat"), ("do you have a hydroponics tab", "chat"), ("which tab has my reminders", "chat"),
    ("what's my current weight goal", "chat"), ("remind me what my latest task was", "chat"), ("how's my training going this week", "chat"),
    ("explain that again more simply", "chat"), ("what do you think about that song", "chat"), ("is it better to lift in the morning", "chat"),
    ("teach me about aquaponics", "chat"), ("what's a good name for my project", "chat"), ("translate hello to Spanish", "chat"),
    # web: he asked for online or current information
    ("search the web for the best budget gpu", "web"), ("look online for hydroponic nutrient prices", "web"),
    ("what's the latest news on nvidia", "web"), ("what's the current price of bitcoin", "web"), ("check online if the new Python is out", "web"),
    ("what's happening in the world right now", "web"), ("web search aquaponics kits", "web"), ("look up online how much tilapia costs", "web"),
    ("latest tesla stock news", "web"), ("what's the news this week about AI", "web"), ("search online for lettuce pH levels", "web"),
    ("is there any news about the election today", "web"), ("find on the internet a good grow light", "web"),
    ("search for reviews of the RTX 5080", "web"), ("what is the current weather in Tokyo", "web"), ("check online what time the game starts", "web"),
    ("look up online whether creatine is safe", "web"), ("current interest rates", "web"), ("latest version of Node", "web"),
    ("search the web for aeroponic misting pressure", "web"),
    # deep: online and thorough
    ("do a deep dive online into hydroponic nutrient ratios", "deep"), ("search online for a comprehensive overview of aquaponics", "deep"),
    ("look online and give me a thorough answer on creatine", "deep"), ("search the web, use multiple sources, on solar batteries", "deep"),
    ("find on the internet everything you can find about aeroponics", "deep"), ("web search a full report on home fusion projects", "deep"),
    ("research the literature review on sleep and muscle growth online", "deep"), ("look online and compare the studies on intermittent fasting", "deep"),
    ("search for an in-depth guide on aquaponic fish stocking", "deep"), ("online, a detailed report on grow lights", "deep"),
    # local: what he saved or she researched
    ("what did you find about creatine", "local"), ("what did we research on hydroponics", "local"), ("check my notes on the arc reactor", "local"),
    ("search my research about aquaponics", "local"), ("look through my notebook for the pump idea", "local"), ("did we already research grow lights", "local"),
    ("what do my notes say about the pump", "local"), ("in my notes, what was the fish ratio", "local"), ("your earlier research on lettuce said what", "local"),
    ("from my saved notes, what's the plan for the tower", "local"),
)
