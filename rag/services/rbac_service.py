import requests
import re

from rag.config import API_BASE_URL


class RbacService:
    """
    Stage 2 (of LiveDataPipeline) - RBAC Check + Data Scope Enforcement

    check()         — can this role use this intent at all?
    enforce_scope() — after params are resolved, enforce what data
                      this user is allowed to see:

        SUPER_ADMIN / ADMIN  → see everyone, no restriction
        LEADERSHIP           → can see themselves OR any employee
                               whose REPORTING_1 = this user's ID.
                               Any other ID is rejected.
        EXECUTIVE            → can only see themselves. Any identity
                               param that isn't their own ID is
                               replaced with their own ID (not an
                               error — just silently scoped down,
                               matching typical app behaviour).

    Role hierarchy (matches PHP normalizeAccessRole in apiMain.php):
        SUPER_ADMIN > ADMIN > LEADERSHIP > EXECUTIVE
    """

    ROLE_RANK = {
        "EXECUTIVE": 1,
        "LEADERSHIP": 2,
        "ADMIN": 3,
        "SUPER_ADMIN": 4,
    }

    # Regex patterns that identify an "employee identity" parameter
    # by name — same list as ParameterService._IDENTITY_PARAM_PATTERNS.
    _IDENTITY_PARAM_PATTERNS = (
        r"^ids?$",
        r"^emp_?id$",
        r"^empId$",
        r"^EMPID$",
        r"^employee_?id$",
        r"(^|_)user_?id(s)?$",
        r"^userId$",
        r"(^|_)employee_id(s)?$",
    )

    def _normalize(self, role: str) -> str:
        return (role or "").strip().upper()

    def _parse_allowed_roles(self, roles_field: str) -> list:
        if not roles_field:
            return []
        return [
            self._normalize(r)
            for r in roles_field.split(",")
            if r.strip()
        ]

    def _find_identity_params(self, parameters: dict) -> list:
        """Return all keys in parameters that look like identity fields."""
        found = []
        for key in parameters:
            key_lower = key.lower()
            if any(re.match(pat, key) or re.match(pat, key_lower)
                   for pat in self._IDENTITY_PARAM_PATTERNS):
                found.append(key)
        return found

    def _is_reportee(self, candidate_id: str, manager_id: str) -> bool:
        """
        Check whether candidate_id has manager_id as their REPORTING_1.
        Calls the lightweight org_chart reportee-check mode, which performs a
        single-row lookup instead of loading the manager's full org chart.
        Returns False on any error so the pipeline fails safe.
        """
        try:
            url = f"{API_BASE_URL}/org_chart.php"
            response = requests.get(
                url,
                params={"userid": manager_id, "candidate_id": candidate_id},
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "success":
                raise ValueError("Reportee check endpoint returned an unsuccessful response")
            return bool(data.get("is_reportee"))
        except Exception as exc:
            print(
                f"[RBAC] Reportee lookup failed for candidate={candidate_id!r}, "
                f"manager={manager_id!r}, url={API_BASE_URL!r}: {exc}"
            )
            return False

    def check(self, user: dict, registry: dict) -> dict:
        """
        Returns:
            {"status": "success"} if allowed
            {"status": "error", "message": "..."} if denied
        """

        user = user or {}
        user_role = self._normalize(user.get("access_role"))
        intent_name = registry.get("Intent Name", "unknown")

        if not user_role:
            return {
                "status": "error",
                "message": "Access denied: no role found for this user.",
                "intent": intent_name
            }

        if user_role == "SUPER_ADMIN":
            return {"status": "success"}

        allowed_roles = self._parse_allowed_roles(registry.get("Roles", ""))

        if not allowed_roles:
            return {"status": "success"}

        user_rank = self.ROLE_RANK.get(user_role, 0)
        required_rank = min(
            (self.ROLE_RANK.get(role, 0) for role in allowed_roles),
            default=0
        )

        if user_role in allowed_roles or user_rank >= required_rank:
            return {"status": "success"}

        return {
            "status": "error",
            "message": (
                f"Access denied: '{user_role}' is not permitted to use "
                f"'{intent_name}'. Requires one of: {', '.join(allowed_roles)}."
            ),
            "intent": intent_name,
            "user_role": user_role,
            "allowed_roles": allowed_roles
        }

    def enforce_scope(self, user: dict, parameters: dict) -> dict:
        """
        Enforce data scope rules on the resolved parameters.

        Returns:
            {"status": "success", "parameters": {...}}  — scoped params
            {"status": "error",   "message": "..."}     — access denied
        """
        user = user or {}
        user_role = self._normalize(user.get("access_role"))
        user_id = (user.get("userid") or "").strip()

        # ADMIN / SUPER_ADMIN — unrestricted
        if user_role in ("ADMIN", "SUPER_ADMIN"):
            return {"status": "success", "parameters": parameters}

        identity_keys = self._find_identity_params(parameters)

        # No identity param in this request — nothing to scope
        if not identity_keys:
            return {"status": "success", "parameters": parameters}

        scoped = dict(parameters)

        for key in identity_keys:
            requested_id = (parameters.get(key) or "").strip()

            # Empty / ALL — means "show everyone". Scope it down.
            if not requested_id or requested_id.upper() == "ALL":
                if user_role == "EXECUTIVE":
                    # EXECUTIVE sees only themselves
                    scoped[key] = user_id
                # LEADERSHIP with no specific ID → leave as-is,
                # PHP will return their team via userid/EMPID viewer param
                continue

            # Specific ID requested
            if user_role == "EXECUTIVE":
                if requested_id.upper() != user_id.upper():
                    # EXECUTIVE tried to look up someone else — silently
                    # scope back to themselves
                    scoped[key] = user_id
                # else: they asked for themselves, allow

            elif user_role == "LEADERSHIP":
                if requested_id.upper() == user_id.upper():
                    pass  # self-lookup always allowed
                elif self._is_reportee(requested_id, user_id):
                    pass  # direct reportee — allowed
                else:
                    return {
                        "status": "error",
                        "message": (
                            f"Access denied: you can only view data for yourself "
                            f"or your direct reportees. '{requested_id}' is not "
                            f"in your team."
                        )
                    }

        return {"status": "success", "parameters": scoped}
