"""ZAE-Eval v0 prompts (Grey, 2026-11-07): 36 general prompts, none about the owner. Four categories can be scored by a program
(`check` says how); two are judged side by side against a stronger model's answer. Add personal and file-grounded prompts later,
only from sources the owner approves."""

# check kinds: ("any", [accepted strings]) normalized contains-match; ("fn", name) a function in score.py
PASSAGE_1 = ("The design review was moved from Tuesday to Thursday at 3 pm. Priya owns the review notes. The budget for the work is $12,400, "
             "and the room is B-204.")
PASSAGE_2 = ("Maintenance on the file server starts at 11 pm on Saturday and should end by 2 am. Backups run first, taking about 40 minutes. "
             "Only the finance share will be offline the whole time; the others return after the backup.")
PASSAGE_3 = ("Mina's training plan has three runs a week: a 5 km easy run on Monday, intervals on Wednesday, and a 12 km long run on Saturday. "
             "She rests on Tuesday, Thursday and Sunday. Friday is for strength work.")

PROMPTS = [
  # A. reasoning and maths (exact answers)
  {"id": "m1", "cat": "reasoning", "q": "A train leaves at 9:40 and arrives at 13:05 the same day. How many minutes is the trip? Give the number first.", "check": ("any", ["205"])},
  {"id": "m2", "cat": "reasoning", "q": "What is 17% of 2,350? Give the number first.", "check": ("any", ["399.5"])},
  {"id": "m3", "cat": "reasoning", "q": "If 5 machines make 5 widgets in 5 minutes, how many minutes do 100 machines need to make 100 widgets? Give the number first.", "check": ("any", ["5 minutes", "five minutes", "5 min"])},
  {"id": "m4", "cat": "reasoning", "q": "A shirt costs $40 after a 20% discount. What was its original price? Give the number first.", "check": ("any", ["50"])},
  {"id": "m5", "cat": "reasoning", "q": "Alice is taller than Bob. Bob is taller than Cara. Dana is shorter than Cara. Who is second tallest? Give the name first.", "check": ("any", ["bob"])},
  {"id": "m6", "cat": "reasoning", "q": "In a year that is not a leap year, how many days pass from March 3 to April 18, not counting March 3 itself? Give the number first.", "check": ("any", ["46"])},
  {"id": "m7", "cat": "reasoning", "q": "A recipe uses 3/4 cup of sugar for 12 cookies. How many cups for 30 cookies? Give the answer first.", "check": ("any", ["1.875", "1 7/8", "15/8"])},
  {"id": "m8", "cat": "reasoning", "q": "What is the sum of all whole numbers from 1 to 100 that are multiples of 3? Give the number first.", "check": ("any", ["1683", "1,683"])},
  # B. questions about a passage (grounding; one answer is 'not stated')
  {"id": "p1", "cat": "passage", "q": f"{PASSAGE_1}\n\nWhen is the design review now?", "check": ("any", ["thursday"])},
  {"id": "p2", "cat": "passage", "q": f"{PASSAGE_1}\n\nWho owns the review notes?", "check": ("any", ["priya"])},
  {"id": "p3", "cat": "passage", "q": f"{PASSAGE_1}\n\nWho is attending the review?", "check": ("any", ["not stated", "does not specify", "doesn't specify", "not specify", "doesn't say", "does not say", "not mentioned", "isn't stated", "not specified", "no information", "doesn't mention", "does not mention", "not provided"])},
  {"id": "p4", "cat": "passage", "q": f"{PASSAGE_2}\n\nWhich share is offline for the whole maintenance window?", "check": ("any", ["finance"])},
  {"id": "p5", "cat": "passage", "q": f"{PASSAGE_3}\n\nOn which day does Mina do strength work?", "check": ("any", ["friday"])},
  {"id": "p6", "cat": "passage", "q": f"{PASSAGE_3}\n\nHow far is her long run?", "check": ("any", ["12 km", "12km", "12 kilometers", "12 kilometres"])},
  # C. instruction following (checked by a program)
  {"id": "i1", "cat": "instructions", "q": "Write exactly three bullet points about sleep. Each bullet starts with '- ', has at most 12 words and contains no commas. Output only the bullets.", "check": ("fn", "three_bullets")},
  {"id": "i2", "cat": "instructions", "q": "Reply with only a JSON object with the keys \"name\" and \"age\" for a made-up person. No other text.", "check": ("fn", "json_name_age")},
  {"id": "i3", "cat": "instructions", "q": "In one sentence of at most 15 words, say why exercise helps mood.", "check": ("fn", "one_sentence_15")},
  {"id": "i4", "cat": "instructions", "q": "List five fruits in alphabetical order, one per line, with no numbering and no other text.", "check": ("fn", "five_alpha_lines")},
  {"id": "i5", "cat": "instructions", "q": "Answer in all lowercase letters, in exactly two sentences: what is a habit?", "check": ("fn", "lower_two_sentences")},
  {"id": "i6", "cat": "instructions", "q": "In a reply of exactly two sentences, use the word 'orbit' exactly twice. Topic: the moon.", "check": ("fn", "orbit_twice_two_sentences")},
  # D. planning and advice (judged)
  {"id": "d1", "cat": "planning", "q": "Plan a 3-day beginner strength routine with 40-minute sessions and no equipment."},
  {"id": "d2", "cat": "planning", "q": "I have 90 minutes tonight and need to study for a chemistry exam, do laundry and cook dinner. Make me a schedule."},
  {"id": "d3", "cat": "planning", "q": "Give me a simple weekly meal plan for one person, about 2,000 calories a day, with a short shopping list."},
  {"id": "d4", "cat": "planning", "q": "I want to read more. Suggest a realistic daily routine that fits a busy week and explain why it would stick."},
  {"id": "d5", "cat": "planning", "q": "How should I prepare for a job interview tomorrow if I only have two hours?"},
  {"id": "d6", "cat": "planning", "q": "Plan a one-day trip to a nearby city on a $100 budget, with time blocks."},
  {"id": "d7", "cat": "planning", "q": "I keep missing my morning workouts. Diagnose likely reasons and give three changes to try this week."},
  {"id": "d8", "cat": "planning", "q": "Help me decide between renting and buying a car for three years. What should I compare?"},
  # E. writing and explaining (judged)
  {"id": "w1", "cat": "writing", "q": "Explain why the sky is blue to a 10-year-old in under 120 words."},
  {"id": "w2", "cat": "writing", "q": "Write a polite email asking a landlord to fix a leaking tap. Keep it under 120 words."},
  {"id": "w3", "cat": "writing", "q": "Explain the difference between a virus and a bacterium in plain language."},
  {"id": "w4", "cat": "writing", "q": "Summarize the idea of compound interest in three sentences."},
  {"id": "w5", "cat": "writing", "q": "Write a short, encouraging message for a friend who failed a driving test."},
  {"id": "w6", "cat": "writing", "q": "Explain what an API is to someone who has never programmed, using an everyday comparison."},
  {"id": "w7", "cat": "writing", "q": "Give pros and cons of working from home, in a balanced paragraph."},
  {"id": "w8", "cat": "writing", "q": "Describe how to make a good cup of tea, step by step, in under 100 words."},
]
