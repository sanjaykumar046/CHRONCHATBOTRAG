import requests

from rag.config import API_BASE_URL


class APIService:
    """
    Stage 4 - API Call

    Takes a matched registry entry and resolved parameters, builds the
    correctly-shaped request payload for that endpoint, and calls the
    real backend API.

    Does NOT:
    - Resolve or validate parameters (already done by ParameterService)
    - Interpret or summarize the response (that's ResponseService's job)

    PHP endpoint quirks handled here
    ---------------------------------
    The PHP backend is not uniform in how it reads request parameters -
    some endpoints do `json_decode(file_get_contents('php://input'))`
    (JSON body), some read `$_GET[...]` (query string only - a raw JSON
    POST body does NOT populate this), and a few read `$_POST[...]` /
    `parse_str(file_get_contents('php://input'))` only (both of which
    PHP populates from form-encoded bodies, not JSON ones).
    Sending only a JSON body, as this used to do unconditionally, left
    the `$_GET`-reading endpoints always falling back to their PHP-side
    defaults regardless of what the user asked, and left the
    form-encoded-only endpoints seeing no parameters at all.

    Fix: always send params as a query string too (`params=`, harmless
    for JSON-body endpoints, satisfies `$_GET` endpoints for free), and
    for the small, explicit set of form-encoded-only endpoints, send
    form-encoded instead of JSON.

    Each entry in FORM_ENCODED_ENDPOINTS was added only after reading
    that specific PHP file's source and confirming it parses the body
    with parse_str() or reads $_POST directly - never guessed. See the
    per-endpoint comments below for what was actually found in each
    file.

    PARAM NAME quirks handled here
    -------------------------------
    Endpoints also don't agree on what to CALL the same concept. Reading
    groupdata1.php's source directly, for example, showed it reads
    "ids" (not "userid"), "selectedDepartments" (not "department"),
    "roles" (not "role"), "EMPID" (not "userid" - and NOT the same
    field as "ids"), etc. Every other PHP file in this project likely
    has its own similar quirks.

    Rather than encode every endpoint's exact key names into the
    registry (error-prone, and has to be redone by hand for every new
    intent - see the group_productivity_report registry bug this was
    written to fix), the rest of the pipeline works with a small set of
    CANONICAL internal names:

        identity_ids    - list/CSV of specific employee IDs
        identity_names  - list/CSV of specific employee names

    ParameterService fills these generically (e.g. from a self-
    reference like "my" or an explicit ID/name in the question) without
    needing to know what any particular PHP file calls them.

    PARAM_ALIASES below is the ONLY place that translates a canonical
    name (or another common synonym like "userid"/"empid"/"id") into
    the literal key a specific endpoint's PHP source actually reads.
    Add an entry here - confirmed against the PHP source, not guessed -
    whenever a new endpoint is wired in. If an endpoint has no entry,
    canonical/common names are passed through unchanged, so endpoints
    that already use the "obvious" names keep working with zero config.
    """

    # Endpoints confirmed (by reading the PHP source) to read the body
    # as form-encoded only - no php://input JSON parsing. These get a
    # form-encoded body instead of a JSON one.
    #
    #   /timelineapp.php  - reads $_POST['date'], $_POST['EMPID'], $_POST['userid']
    #   /userusage.php    - same as timelineapp.php
    #   /timeline.php     - does parse_str(file_get_contents('php://input'), $parsedData);
    #                       parse_str() only understands a=b&c=d, not JSON, so a JSON
    #                       body silently fails to populate any of $parsedData's keys
    #                       (date, enddate, EMPID, EMPNAME, TEAMS, ROLE, DEPARTMENT,
    #                       PROJECTS, userid) - confirmed 2026-08-10 while debugging
    #                       PR_USER_TIMELINE always returning "No data found."
    FORM_ENCODED_ENDPOINTS = {
        "/timelineapp.php",
        "/userusage.php",
        "/timeline.php",
    }

    # Per-endpoint translation from canonical/common internal param
    # names to the literal key that endpoint's PHP source reads.
    # Keys on the left are what the rest of the pipeline uses
    # internally; values on the right are copied verbatim from the
    # PHP file's own isset($inputData['...']) checks.
    #
    # IMPORTANT: only add an endpoint here after reading its actual
    # PHP source - a guessed mapping just relocates the same bug this
    # table exists to fix. See groupdata1.php below for the confirmed
    # reference example.
    # PARAM_ALIASES is intentionally empty.
    # Parameter names are now passed directly from the registry to the
    # LLM extraction prompt (ParameterService.resolve), so the LLM
    # outputs keys that already match what each PHP endpoint reads.
    # No post-extraction translation is needed.
    PARAM_ALIASES = {}

    def execute(self, registry: dict, parameters: dict) -> dict:

        endpoint = registry.get("API Endpoint")

        if not endpoint:
            return {
                "status": "error",
                "message": f"No 'API Endpoint' defined for intent "
                           f"'{registry.get('Intent Name')}' in the registry."
            }

        # Some registry entries list more than one endpoint
        # (e.g. "/timelineapp.php, /userusage.php") for intents backed
        # by two calls. Only the first is actually callable here - a
        # comma-joined string is not a valid URL path. Using the first
        # one matches current behavior for those intents' primary data.
        first_endpoint = endpoint.split(",")[0].strip()

        url = f"{API_BASE_URL}{first_endpoint}"

        http_method = (registry.get("HTTP Method") or "").strip().upper()
        is_form_encoded = "FORM" in http_method or first_endpoint in self.FORM_ENCODED_ENDPOINTS

        payload = self._build_payload(
            parameters,
            first_endpoint,
            is_form_encoded=is_form_encoded,
            intent=registry.get("Intent Name"),
        )

        try:
            if is_form_encoded:
                response = requests.post(
                    url,
                    data=payload,
                    timeout=120
                )
            elif http_method == "GET":
                # For GET endpoints, send only scalar flat values as query params
                query_params = {k: v for k, v in payload.items() if not isinstance(v, (dict, list))}
                response = requests.get(
                    url,
                    params=query_params,
                    timeout=120
                )
            else:
                # For POST JSON, send pure JSON body (with scalar-only params as query string for PHP compatibility)
                query_params = {k: v for k, v in payload.items() if not isinstance(v, (dict, list))}
                response = requests.post(
                    url,
                    params=query_params,
                    json=payload,
                    timeout=120
                )
            response.raise_for_status()

        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": f"API call to '{first_endpoint}' failed: {e}"
            }

        try:
            data = response.json()
        except ValueError:
            return {
                "status": "error",
                "message": f"API '{first_endpoint}' returned a non-JSON response."
            }

        return {
            "status": "success",
            "data": data
        }

    def _apply_param_aliases(self, parameters: dict, endpoint: str) -> dict:
        """
        Renames canonical/common internal keys (identity_ids, userid,
        department, ...) to whatever this specific endpoint's PHP
        source actually reads, per PARAM_ALIASES.

        If two different internal keys alias to the same real PHP key
        for this endpoint (shouldn't normally happen, but registries
        evolve), the last one processed wins - dict iteration order
        follows `parameters`' own insertion order, so this is
        deterministic given a fixed input, but worth knowing if you
        see an unexpected value silently overwritten.

        Endpoints with no entry in PARAM_ALIASES pass every key
        through unchanged, so this is a no-op / safe default for
        endpoints that already use the "obvious" names.
        """
        aliases = self.PARAM_ALIASES.get(endpoint)
        if not aliases:
            return dict(parameters)

        translated = {}
        for key, value in parameters.items():
            real_key = aliases.get(key, key)
            translated[real_key] = value
        return translated

    def _build_payload(
        self,
        parameters: dict,
        endpoint: str = None,
        is_form_encoded: bool = False,
        intent: str = None,
    ) -> dict:
        """
        Builds the correctly-shaped payload for the given endpoint.

        - For form-encoded requests (HTTP Method: POST FORM):
          timelineapp.php / userusage.php read $_POST['date'],
          $_POST['EMPID'], $_POST['userid'] only - a single day, no
          range, no nested objects.
          timeline.php additionally reads $_POST['enddate'] (via
          parse_str) since PR_USER_TIMELINE takes a date range, not a
          single day - so enddate is mapped and kept for this endpoint
          specifically, alongside date. All other range/nested keys
          (startDate, endDate, from_date, to_date, dateRange) are
          stripped, since none of these three PHP files understand them
          and a nested dict would break form-encoding.

        - For all other endpoints:
          Add nested dateRange object alongside flat date keys.
          Some PHP files read dateRange['start'/'end'] (fetch_employee_activity1.php),
          others read flat from_date/to_date (timeonsystem.php).
          Sending both costs nothing.

        - Array normalization:
          PHP group endpoints (groupdata1.php, designation1.php) expect
          filter parameters (selectedTeams, selectedDepartments, selectedProjects,
          selectedShift, roles, ids, names) to be arrays. Strings are
          automatically converted to lists.

        - Date defaulting:
          If no date is present at all, default to the current month
          so endpoints that require a date don't receive NULL or 'ALL'.
        """
        from datetime import date
        import calendar

        payload = self._apply_param_aliases(parameters, endpoint) if endpoint else dict(parameters)

        # Ensure filter parameters expected as arrays by PHP are lists
        array_param_keys = {
            "selectedTeams", "selectedDepartments", "selectedProjects", "selectedShift",
            "roles", "ids", "names", "designations", "EMPID", "DEPARTMENT", "ROLE",
            "DESIGNATION", "PROJECT", "SHIFT", "TEAM"
        }
        for key in array_param_keys:
            if key in payload and isinstance(payload[key], str):
                val = payload[key].strip()
                if val:
                    payload[key] = [v.strip() for v in val.split(",") if v.strip()]

        # Form-encoded endpoints (POST FORM)
        # only read: date, enddate, EMPID, userid — no dateRange, no nested objects
        if is_form_encoded or (endpoint and endpoint in self.FORM_ENCODED_ENDPOINTS):
            # Map startDate → date (single day, or range start)
            if "date" not in payload:
                single_date = payload.get("startDate") or payload.get("from_date")
                if single_date:
                    payload["date"] = single_date
            # Map endDate → enddate (range end - only meaningful for
            # timeline.php, but harmless for timelineapp.php/userusage.php
            # since their PHP simply ignores any key it doesn't isset() check)
            if "enddate" not in payload:
                end_date = payload.get("endDate") or payload.get("to_date")
                if end_date:
                    payload["enddate"] = end_date
            # Remove all date range keys — PHP ignores them but nested
            # objects cause serialization errors in form-encoded requests
            for key in ("startDate", "endDate", "from_date", "to_date", "dateRange"):
                payload.pop(key, None)
            return payload

        # All other endpoints — build dateRange alongside flat keys
        start = payload.get("startDate") or payload.get("from_date")
        end = payload.get("endDate") or payload.get("to_date")

        # Most date-based endpoints default to the current month when no
        # range is supplied. The last-leave intent deliberately omits dates
        # so leave.php returns the employee's full history for latest-record
        # selection.
        if not start and not end and intent != "last_leave_taken":
            today = date.today()
            start = today.replace(day=1).isoformat()
            last_day = calendar.monthrange(today.year, today.month)[1]
            end = today.replace(day=last_day).isoformat()

        if start:
            payload.setdefault("startDate", start)
            payload.setdefault("from_date", start)
        if end:
            payload.setdefault("endDate", end)
            payload.setdefault("to_date", end)

        if start or end:
            payload["dateRange"] = {
                "start": start,
                "end": end
            }

        return payload
