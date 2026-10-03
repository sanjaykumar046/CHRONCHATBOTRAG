from rag.llm.classifier_llm import ClassifierLLM
from rag.prompts.parameter_extraction_prompt import PARAMETER_EXTRACTION_PROMPT
from rag.utils.date_resolver import DateResolver
import re


class ParameterService:
    """
    Stage 3 - Parameter Resolution
    Stage 4 - Parameter Validation

    Responsibilities
    ----------------
    - Extract parameter values the user explicitly mentioned in the question
    - Auto-inject parameters the system already knows (userid, action)
    - Resolve date-like parameters via DateResolver (never via LLM extraction -
      see DATE_PARAM_NAMES note below)
    - Validate that all "Required Params" from the registry are present
      after extraction + auto-injection
    - Report exactly which params are still missing, so the caller can
      ask the user for them

    Does NOT:
    - Call the API
    - Perform RBAC

    NOTE on key naming
    -------------------
    Earlier versions of the extraction prompt always asked the LLM to
    return generic "ids"/"names" keys, which then had to be remapped
    in Python onto whatever the registry's real Required/Optional
    Params happened to call that field (e.g. "empid", "employeeId").
    That remap relied on a hardcoded candidate list per naming style
    and silently failed to fill the *actual* required key whenever a
    registry entry used a name not already in the list - the reported
    symptom being "I already gave the employee ID but it keeps asking
    again", because extraction filled "ids" while validate() checked
    for e.g. "empid".

    The extraction prompt now receives the registry's real parameter
    names directly and is asked to pick which one (if any) is the
    employee-identifier field and which one (if any) is the
    employee-name field, then return values under those *real* keys.
    So this service no longer needs a hardcoded remap table - it only
    needs a generic "__SELF__" substitution (wherever it shows up) and
    a narrow last-resort fallback for when the LLM misses an explicit
    self-reference.

    NOTE on date naming
    --------------------
    Different PHP endpoints call the same "date range" concept by
    different literal keys:
        - startDate / endDate                  (most endpoints)
        - from_date / to_date                   (timeonsystem.php, etc)
        - date / enddate                        (timelineapp.php, userusage.php,
                                                   timeline.php - see APIService's
                                                   FORM_ENCODED_ENDPOINTS docstring)

    Bug this fixes: the date-filling block used to only trigger when the
    registry declared startDate/endDate/from_date/to_date/dateRange. For
    any endpoint whose registry entry instead declares "date, enddate"
    (matching its actual PHP $_POST keys), that check was False, so
    DateResolver never ran - the raw, unresolved LLM extraction (e.g.
    literally the string "yesterday") was sent straight to the PHP
    endpoint instead, causing a 500.

    Fix has two parts:
      1. All date-like param names (DATE_PARAM_NAMES) are excluded from
         the LLM extraction prompt entirely - the LLM should never be
         trusted to resolve relative dates ("yesterday", "last week")
         into real values, only DateResolver should.
      2. The date-filling block's trigger condition and its fill-in both
         cover every naming convention above, so whichever key names a
         given registry entry actually declares, DateResolver's output
         gets mapped onto it.
    """

    # Params that are never asked from the user - the system fills
    # these in automatically. Covers all casing variants used across
    # the PHP endpoints (userid, userId, user_id).
    AUTO_INJECTED = {
        "userid", "userId", "user_id", "action"
    }

    # Every literal key name any endpoint's registry entry uses for a
    # date range. Excluded from LLM extraction; filled exclusively by
    # DateResolver in resolve() below.
    DATE_PARAM_NAMES = {
        "startDate", "endDate",
        "from_date", "to_date",
        "date", "enddate",
        "dateRange",
    }

    _SELF_REFERENCE_WORDS = {"my", "me", "i", "mine", "myself"}
    _EMPLOYEE_ID_RE = re.compile(r"\b[A-Z]{2}\d{5}\b", re.IGNORECASE)

    def __init__(self):
        self.classifier = ClassifierLLM()
        self.date_resolver = DateResolver()

    def _parse_param_list(self, params_field: str) -> list:
        if not params_field:
            return []
        return [p.strip() for p in params_field.split(",") if p.strip()]

    def _has_self_reference(self, question: str) -> bool:
        return bool(re.search(
            r"\b(?:my|me|i|mine|myself)\b",
            question,
            re.IGNORECASE
        ))

    # Regex patterns, checked in order, each boundary-safe so a short
    # token like "id" matches "ids"/"empid"/"user_id" but does NOT
    # false-positive on unrelated params like "validity" or
    # "candidate" that merely contain the letters "id" mid-word.
    # underscore-or-start/end is treated as a word boundary since
    # param names are usually snake_case or a single bare word.
    _IDENTITY_PARAM_PATTERNS = (
        r"^ids?$",                      # "id", "ids"
        r"^emp_?id$",                   # "empid", "emp_id"
        r"^empId$",                     # camelCase "empId"
        r"^EMPID$",                     # uppercase "EMPID"
        r"^employee_?id$",              # "employeeid", "employee_id"
        r"(^|_)user_?id(s)?$",          # "userid", "user_id"
        r"^userId$",                    # camelCase "userId"  (attendance/leave)
        r"(^|_)employee_id(s)?$",
    )

    def _guess_identity_param(self, param_names: list) -> str | None:
        """
        Narrow last-resort fallback: if the LLM missed an explicit
        self-reference, try to spot the identity-like param name
        ourselves so we don't ask the user for something they've
        effectively already implied ("my attendance", "my productive
        hours"). Different registry entries use different literal
        param names for the same concept - "empid"/"user_id" on some
        intents, "ids" on others - so this has to check several known
        conventions rather than one fixed key.

        Matching uses whole-word/segment regex patterns rather than a
        raw substring check, so a short token like "id" matches "ids"
        or "user_id" but does NOT false-positive on unrelated params
        like "validity" or "candidate" that merely happen to contain
        the letters "id" mid-word. This is intentionally conservative
        - it returns None rather than guess wrong, in which case
        validate() correctly asks the user instead.
        """
        import re

        for p in param_names:
            p_lower = p.lower()
            if any(re.match(pattern, p) or re.match(pattern, p_lower)
                   for pattern in self._IDENTITY_PARAM_PATTERNS):
                return p
        return None

    def _extract_from_question(self, question: str, param_names: list, user: dict = None) -> dict:
        if not param_names:
            return {}

        prompt = PARAMETER_EXTRACTION_PROMPT.format(
            question=question,
            parameter_names=", ".join(param_names)
        )

        result = self.classifier.classify(prompt, fallback={})
        if not isinstance(result, dict):
            return {}

        # Replace __SELF__ with the actual logged-in userid, wherever
        # it shows up - the LLM now writes it under the real registry
        # key it chose as the identity param, not a fixed "ids" key.
        for key, value in list(result.items()):
            if value == "__SELF__":
                userid = (user or {}).get("userid")
                if userid:
                    result[key] = userid
                else:
                    # No logged-in userid available - drop rather than
                    # send a literal "__SELF__" to the API.
                    result.pop(key, None)

        # Remove empty string / null values the LLM sometimes returns
        # for unused params.
        result = {k: v for k, v in result.items() if v not in (None, "", [], {})}

        # Never trust a model-generated employee ID. The extraction prompt
        # includes sample IDs, which a small model can copy into its answer.
        # Keep only IDs actually present in the user's question; otherwise
        # use the authenticated user for self-references or omit the filter.
        identity_param = self._guess_identity_param(param_names)
        if identity_param:
            explicit_ids = list(dict.fromkeys(
                match.group(0)
                for match in self._EMPLOYEE_ID_RE.finditer(question)
            ))
            if explicit_ids:
                result[identity_param] = ", ".join(explicit_ids)
            elif self._has_self_reference(question):
                userid = (user or {}).get("userid")
                if userid:
                    result[identity_param] = userid
                else:
                    result.pop(identity_param, None)
            else:
                result.pop(identity_param, None)

        # Fallback: if the question has an explicit self-reference,
        # make sure the identity param specifically is filled - even
        # if OTHER params (dates, etc) were successfully extracted.
        #
        # Bug this fixes: checking "was anything at all extracted"
        # instead of "was the identity param specifically extracted"
        # let this fallback get silently skipped whenever unrelated
        # params (e.g. from_date/to_date) happened to extract fine
        # while the LLM missed the self-reference rule for the
        # identity field.
        #
        # identity_ids is always tried as a fallback target (in
        # addition to any registry-declared field _guess_identity_param
        # finds) since it's always in extractable_names_for_llm even
        # when the registry itself never declared an identity field -
        # see the comment in resolve() for why that safety net exists.
        if self._has_self_reference(question):
            userid = (user or {}).get("userid")
            if userid:
                identity_param = self._guess_identity_param(param_names)
                if identity_param and not self._EMPLOYEE_ID_RE.search(question):
                    result[identity_param] = userid

        return result

    def extract(self, question: str, parameter_names: list, user: dict = None) -> dict:
        """
        Public wrapper around _extract_from_question, for callers that
        already know which specific parameter names they need filled
        (e.g. re-extracting from a user's reply to an ask_user prompt).
        """
        return self._extract_from_question(question, parameter_names, user)

    def resolve(self, question: str, registry: dict, user: dict = None) -> dict:
        """
        Returns:
            {"status": "success", "parameters": {...}}
        """

        user = user or {}

        required = self._parse_param_list(registry.get("Required Params", ""))
        optional = self._parse_param_list(registry.get("Optional Params", ""))
        all_param_names = list(set(required + optional))

        # ---------------------------------------------------------
        # Extract explicitly-mentioned values from the question.
        # The prompt receives the registry's real param names directly
        # (exactly as declared in Required Params / Optional Params).
        # The LLM picks which one is the identity field and which one
        # is the name field from those real names, so no translation is
        # needed after extraction - output keys already match what the
        # PHP endpoint reads.
        #
        # Date-like params (DATE_PARAM_NAMES) are excluded here on
        # purpose - the LLM is not trusted to resolve relative dates
        # ("yesterday", "last week") into real values. Only
        # DateResolver (below) fills those.
        # ---------------------------------------------------------

        extractable_names = [
            p for p in all_param_names
            if p not in self.AUTO_INJECTED
            and p not in self.DATE_PARAM_NAMES
        ]
        extractable_names_for_llm = extractable_names

        extracted = self._extract_from_question(question, extractable_names_for_llm, user)

        # ---------------------------------------------------------
        # Auto-inject known system values
        # ---------------------------------------------------------

        parameters = dict(extracted)

        if "userid" in required or "userid" in optional:
            parameters.setdefault("userid", user.get("userid"))
        if "userId" in required or "userId" in optional:
            parameters.setdefault("userId", user.get("userid"))
        if "user_id" in required or "user_id" in optional:
            parameters.setdefault("user_id", user.get("userid"))
        if "EMPID" in required or "EMPID" in optional:
            parameters.setdefault("EMPID", user.get("userid"))

        # ---------------------------------------------------------
        # Resolve date params via DateResolver only.
        #
        # Only fill dates if the question actually contains a real date
        # reference (explicit date, "today", "this week", etc). If none
        # is found, leave date params unset so validate() reports them
        # as missing and the user gets asked explicitly - no silent
        # "today" default.
        #
        # Covers every naming convention any registry entry might use
        # (startDate/endDate, from_date/to_date, date/enddate) so the
        # resolved value lands under whichever literal key that
        # endpoint's PHP source actually reads - see DATE_PARAM_NAMES
        # docstring above for why this must be exhaustive.
        # ---------------------------------------------------------

        if any(p in required or p in optional for p in self.DATE_PARAM_NAMES):
            date_range = self.date_resolver.resolve(question, default_to_today=False)
            if date_range:
                parameters.setdefault("startDate", date_range["startDate"])
                parameters.setdefault("endDate", date_range["endDate"])
                parameters.setdefault("from_date", date_range["startDate"])
                parameters.setdefault("to_date", date_range["endDate"])
                parameters.setdefault("date", date_range["startDate"])
                parameters.setdefault("enddate", date_range["endDate"])
                parameters.setdefault("dateRange", {
                    "start": date_range["startDate"],
                    "end": date_range["endDate"]
                })

        if "action" in required or "action" in optional:
            # Registry-specific action value, if defined - adjust key
            # name below if your registry stores it differently.
            parameters.setdefault("action", registry.get("PHP Action") or registry.get("Intent Name"))

        return {
            "status": "success",
            "parameters": parameters
        }

    def validate(self, registry: dict, parameters: dict) -> dict:
        """
        Returns:
            {"status": "success"}
            or
            {"status": "missing_parameters", "missing": [...]}
        """

        required = self._parse_param_list(registry.get("Required Params", ""))

        verified_missing = []

        for p in required:
            # For auto-injected params, check they actually have a real value
            if p in self.AUTO_INJECTED:
                value = parameters.get(p)
                # If the param is None or empty string, it's effectively missing
                if value is None or value == "":
                    # Only report as missing if it's a critical param (userid/userId)
                    if p in ("userid", "userId"):
                        verified_missing.append(p)
            else:
                # For non-auto-injected params (including all date fields
                # now that they're not auto-injected), check presence
                if not parameters.get(p):
                    verified_missing.append(p)

        if verified_missing:
            return {
                "status": "missing_parameters",
                "missing": verified_missing
            }

        return {"status": "success"}
