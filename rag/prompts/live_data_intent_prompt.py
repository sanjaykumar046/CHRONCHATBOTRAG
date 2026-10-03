"""
Stage 3 : Live Data Intent Prompt

The user's request has already been classified as:

    Category : on_talk
    Intent   : live_data

Your job is ONLY to identify the correct API intent from the
candidate list below.

You will receive:

1. User Question
2. Candidate API Registry Entries (already narrowed to the most
   relevant options)

Instructions

- Understand the user's request.
- Compare it with the candidate registry entries.
- Pay close attention to words that distinguish similar-sounding
  intents - e.g. "pending" vs "approved" vs "upcoming", "summary" vs
  "detailed", "my" vs "team" vs "department". Do not treat similar
  intents as interchangeable just because they cover the same topic.
- If two or more candidates seem similarly relevant, prefer the one
  whose Required Params are clearly present or reasonably implied by
  the user's question (e.g. a date, an employee, a department).
- Select the SINGLE best matching intent.
- Never invent a new intent.
- The returned intent MUST exactly match one of the
  "Intent Name" values in the candidates below, OR be the exact
  string "NO_MATCH" if none of them genuinely fit.
- Only return NO_MATCH if none of the candidates reasonably address
  the user's request - do not use it just because you are unsure
  between two plausible options. If a candidate is a plausible
  interpretation, prefer it over NO_MATCH.
- Do NOT answer the user's question.
- Do NOT explain application features.
- Do NOT repeat or list the registry entries.
- Return ONLY valid JSON in the exact format below. Nothing else.

Confidence guide - be honest about uncertainty, do not default to
high confidence:
- 0.90-1.00 = the question clearly and unambiguously maps to one
  intent, with no other candidate being a reasonable alternative.
- 0.60-0.89 = plausible best match, but another candidate could
  also reasonably fit, or the question is missing some detail.
- Below 0.60 = weak or uncertain match - multiple candidates seem
  equally valid, or the question does not clearly indicate which
  intent applies. If genuinely nothing fits, use NO_MATCH instead
  of forcing a low-confidence guess.

------------------------------------------------------------
User Question
------------------------------------------------------------

{question}

------------------------------------------------------------
Candidate API Registry Entries
------------------------------------------------------------

{registry}

------------------------------------------------------------

Now classify the User Question above. Respond with ONLY this JSON
object and nothing else - do not output the registry, do not add
extra keys. Write "reason" first, then "intent", then "confidence" -
reason through the decision before committing to the intent name:

{{
    "reason": "Short explanation of why this registry intent is the best match, or why NO_MATCH applies.",
    "intent": "<Intent Name or NO_MATCH>",
    "confidence": 0.98
}}
"""

LIVE_DATA_INTENT_PROMPT = __doc__