"""
Stage 3 : Parameter Extraction Prompt

The intent has already been matched. Your job is ONLY to extract
parameter values that the user has explicitly mentioned in their
question - nothing else.

Instructions

- Look at the Parameter Names list below. These are the EXACT keys
  you must use in your output - never invent a different key name,
  and never use a generic placeholder like "ids" or "names" unless
  that literal string is itself one of the Parameter Names.
- For each one, check if the user's question mentions a value for it.
- If mentioned, extract the value exactly as stated (e.g. an employee
  ID, a date, a name, a number).
- If NOT mentioned, do not include that key at all in your output.
- Never guess or invent a value that isn't actually in the question.
- Do NOT extract values for dates like "today", "this week", "this
  month", "last month", "January 2026", "January", "February" etc.
  — those are ALL handled separately by the date resolver. Only extract
  EXPLICIT full dates in formats like "2026-01-15", "01-01-2026",
  "from 1st to 15th Jan".
- Return ONLY valid JSON - a flat object of extracted key/value pairs.
  If nothing is found, return an empty JSON object: {{}}

IMPORTANT - Scope Detection (ALWAYS apply these rules first):

Step 1 - Identify the relevant fields.
Look at the Parameter Names list and decide:
- IDENTITY_PARAM: the single parameter name (if any) that represents
  an employee identifier - a field used to say WHICH employee's data
  is being requested. Common names: ids, id, empid, emp_id, empId,
  EMPID, employee_id, userid, user_id — or anything that looks like
  an employee ID field. If none of the Parameter Names look like an
  identity field, IDENTITY_PARAM is null.
- NAME_PARAM: the single parameter name (if any) that represents an
  employee's NAME. Common names: names, name, empname, EMPNAME,
  employee_name, empNames. If none match, NAME_PARAM is null.
Only choose from the literal strings given in Parameter Names. Do not
invent a key that isn't in that list.

Step 2 - Apply these rules using the fields you identified:

RULE 1 - Self reference:
If the question contains any of these words: "my", "me", "I", "mine",
"myself" AND an IDENTITY_PARAM was identified → set that parameter's
value to "__SELF__". This takes priority over everything else.

RULE 2 - Specific employee ID:
If the question mentions an employee ID (2 letters + 5 digits,
e.g. CL00262, CM21021, CN19075) AND an IDENTITY_PARAM was identified
→ set that parameter to the ID value.

RULE 3 - Specific employee name:
If the question mentions a person's name AND a NAME_PARAM was
identified → set that parameter to the name value.

RULE 4 - Whole team or all employees:
If the question is about the whole team, all employees, or no
specific person → do NOT set IDENTITY_PARAM or NAME_PARAM at all.

If IDENTITY_PARAM or NAME_PARAM is null, do not output any key for
that concept, even if the question seems to reference a person -
there is nowhere valid to put that value for this intent.

------------------------------------------------------------
Parameter Names
------------------------------------------------------------

{parameter_names}

------------------------------------------------------------
User Question
------------------------------------------------------------

{question}

------------------------------------------------------------

Return ONLY the JSON object of extracted parameters, using the exact
key names from Parameter Names above. Nothing else - no explanation,
no markdown, no extra keys.
"""

PARAMETER_EXTRACTION_PROMPT = __doc__