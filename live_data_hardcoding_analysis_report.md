# Comprehensive Live Data Pipeline Audit Report: Hardcoding vs. JSON-Driven Architecture

## Executive Summary

The ChronRAG live data system is designed around an API Registry (`api_registry_Correct.json`), where an LLM dynamically classifies user questions into registered intents and extracts required parameters. 

However, across the end-to-end execution path—from intent classification down to frontend UI rendering—multiple layers of hardcoded rules, endpoint whitelists, parameter mappings, and UI shape extractors exist.

This document identifies every hardcoded element in the live data pipeline and presents the blueprint for a **100% JSON/Registry-driven system**.

---

## Complete Audit of Hardcoded Logic in the Pipeline

```
User Query
   │
   ▼
[1. Request Router & Intent Retrieval] ──► (Hardcoded classification prompts & registry caching)
   │
   ▼
[2. Parameter Resolution & Scope] ──────► (Hardcoded param casing sets, identity regex, broad date expansion)
   │
   ▼
[3. API Service Execution] ─────────────► (Hardcoded FORM_ENCODED_ENDPOINTS & date param popping)
   │
   ▼
[4. Response Service Shaping] ──────────► (Hardcoded profile/manager keywords & static response strings)
   │
   ▼
[5. Frontend Chatbot Rendering] ────────► (Hardcoded per-table shape extractors & fixed column lists)
```

---

### 1. API Execution Layer (`rag/services/api_service.py`)

#### A. Hardcoded Endpoint Whitelist for Form Encoding
* **Current Code:**
  ```python
  FORM_ENCODED_ENDPOINTS = {
      "/timelineapp.php",
      "/userusage.php",
      "/timeline.php",
  }
  ```
* **Issue:** Python hardcodes which URLs receive form-encoded POST requests vs JSON POST requests.
* **JSON-Driven Solution:** The registry's `"HTTP Method"` column already contains values like `"POST FORM"`, `"POST JSON"`, and `"GET"`. The code should inspect `registry.get("HTTP Method")` instead of checking a hardcoded URL set.

#### B. Hardcoded Date Parameter Stripping for Form Endpoints
* **Current Code:**
  ```python
  if endpoint in self.FORM_ENCODED_ENDPOINTS:
      for key in ("startDate", "endDate", "from_date", "to_date", "dateRange"):
          payload.pop(key, None)
  ```
* **Issue:** Explicitly hardcodes keys to remove based on URL matching.
* **JSON-Driven Solution:** Only parameters declared in `Required Params` and `Optional Params` for that specific intent should ever be passed to the payload.

#### C. Fallback Date Range Defaulting
* **Current Code:**
  ```python
  if not start and not end:
      today = date.today()
      start = today.replace(day=1).isoformat()
      end = ...
  ```
* **Issue:** Injects first-to-last day of the current month for any endpoint without dates.

---

### 2. Parameter Resolution Layer (`rag/services/parameter_service.py`)

#### A. Hardcoded Parameter Casing & Auto-Injection Sets
* **Current Code:**
  ```python
  AUTO_INJECTED = {"userid", "userId", "user_id", "action"}
  ```
  ```python
  if "userid" in required or "userid" in optional:
      parameters.setdefault("userid", user.get("userid"))
  if "userId" in required or "userId" in optional:
      parameters.setdefault("userId", user.get("userid"))
  if "user_id" in required or "user_id" in optional:
      parameters.setdefault("user_id", user.get("userid"))
  ```
* **Issue:** Hardcoded branching to handle inconsistent casing across PHP endpoints.
* **JSON-Driven Solution:** The parameter resolution can automatically map the authenticated user context to any parameter declared in the registry that matches identity/viewer semantics.

#### B. Over-Broad Date Parameter Expansion (7-Key Injection)
* **Current Code:**
  ```python
  parameters.setdefault("startDate", date_range["startDate"])
  parameters.setdefault("endDate", date_range["endDate"])
  parameters.setdefault("from_date", date_range["startDate"])
  parameters.setdefault("to_date", date_range["endDate"])
  parameters.setdefault("date", date_range["startDate"])
  parameters.setdefault("enddate", date_range["endDate"])
  parameters.setdefault("dateRange", {"start": ..., "end": ...})
  ```
* **Issue:** Regardless of what the registry declares, DateResolver injects all 7 date keys into the parameter dictionary.
* **JSON-Driven Solution:** Only populate the specific date keys declared in that intent's registry definition.

#### C. Hardcoded Regex Patterns for Identity Keys
* **Current Code:**
  ```python
  _IDENTITY_PARAM_PATTERNS = (
      r"^ids?$", r"^emp_?id$", r"^empId$", r"^EMPID$", 
      r"^employee_?id$", r"(^|_)user_?id(s)?$", r"^userId$"
  )
  ```
* **Issue:** Heuristically guesses which parameter represents employee identity using hardcoded regexes.

---

### 3. RBAC & Data Scope Layer (`rag/services/rbac_service.py`)

* **Hardcoded Endpoint for Hierarchy Lookup:**
  ```python
  url = f"{API_BASE_URL}/org_chart.php"
  ```
* **Hardcoded Role Hierarchy:**
  ```python
  ROLE_RANK = {
      "EXECUTIVE": 1,
      "LEADERSHIP": 2,
      "ADMIN": 3,
      "SUPER_ADMIN": 4,
  }
  ```

---

### 4. Response Generation Layer (`rag/services/response_service.py`)

#### A. Question Keyword Matching for Profile and Manager
* **Current Code:**
  ```python
  profile_keywords = ["my details", "my profile", "my emp id", "my name", "my department", ...]
  manager_keywords = ["my manager", "who is my manager", "reporting manager", ...]
  ```
* **Issue:** Instead of relying on the intent classified by the LLM (`user_profile_details`, `reporting_manager_view`), `ResponseService` inspects the raw question string with keyword lists.
* **JSON-Driven Solution:** Route response shaping based on the classified `intent` name or registry response metadata.

#### B. Static Non-LLM Text Replies
* **Current Code:**
  ```python
  "reply": "Here are the results:"
  ```
* **Issue:** The response generator does not use an LLM to formulate conversational answers based on the returned API data.

#### C. Hardcoded "No Data" Heuristics
* **Current Code:**
  ```python
  zero_totals = all(str(v) in ("00:00:00", "0", 0, 0.0) for v in totals.values())
  ```
* **Issue:** Hardcoded string checks specifically designed for `data1` and `totals` shapes.

---

### 5. Frontend Rendering Layer (`Chronaichatbot.jsx`)

#### A. Hardcoded Table Shape Extractors & Column Lists
`extractTableFromData` in `Chronaichatbot.jsx` contains multiple custom blocks:
* **Org Chart Reportees:** Hardcoded column list: `["EMPID", "EMPNAME", "DESIGNATION", "DEPARTMENT", "EMAIL"]`.
* **System Time:** Hardcoded extraction of `data.employees[].days` and columns: `["empid", "empname", "date", "hours", "status"]`.
* **Leave Applications:** Hardcoded check for `data.data[0]?.leaveType` and columns: `["empId", "empName", "leaveType", "fromDate", "toDate", "totalDays", "status"]`.
* **Website Usage:** Hardcoded checks for `data.userActivityData`, `data.topWebsitesData`, `data.topDomainsData`.
* **Activity:** Hardcoded check for `data.data1`.

* **Issue:** Whenever a new API endpoint with a new response format is added to the backend, the frontend fails to render a proper table unless a developer manually codes another `if (data.yourNewKey)` block in React.

---

## The Pure JSON-Driven Architecture Blueprint

To achieve a system where everything is controlled by `api_registry_Correct.json`, the registry schema can be slightly enriched to include explicit contract metadata:

### Proposed Registry Entry Structure:
```json
{
  "Intent Name": "employee_attendance_calendar",
  "Module": "Sense",
  "Page": "Calendar",
  "Description": "Attendance calendar showing daily attendance status for an employee.",
  "Example questions": "Show my attendance for January 2026",
  "API Endpoint": "/fetch_attendance_calendar.php",
  "HTTP Method": "GET",
  "Required Params": "from_date, to_date, empid",
  "Optional Params": "user_id, target_date",
  "Auto Injected": {
    "user_id": "viewer_id",
    "empid": "self_or_target_id"
  },
  "Date Mapping": {
    "from_date": "start_date",
    "to_date": "end_date"
  },
  "Response Config": {
    "data_path": "data",
    "table_title": "Attendance Calendar",
    "columns": ["DATE", "STATUS", "LOGGED_HOURS"]
  },
  "Roles": "ADMIN, LEADERSHIP, EXECUTIVE"
}
```

### Benefits:
1. **Zero Endpoint Hardcoding:** `APIService` reads `HTTP Method` (`GET`, `POST JSON`, `POST FORM`) directly from the registry entry.
2. **Zero Date Guessing:** Parameter resolution maps date ranges only to the exact keys defined in the registry.
3. **Zero Intent Hardcoding:** `ResponseService` routes based on `intent_name`, not raw question keywords.
4. **Universal Frontend Rendering:** The frontend renders dynamic columns derived either directly from the JSON metadata or generically from the first row of tabular results.

---

## Short Summary of Findings

| Component | What is Currently Hardcoded? | What Should Drive It? |
| :--- | :--- | :--- |
| **API Calling (`api_service.py`)** | Form-encoded URLs (`/timelineapp.php`, `/userusage.php`, `/timeline.php`) and date param stripping | Registry `"HTTP Method"` column (`GET`, `POST JSON`, `POST FORM`) |
| **Date Resolution (`parameter_service.py`)** | Injects 7 different date keys (`startDate`, `endDate`, `from_date`, `to_date`, `date`, `enddate`, `dateRange`) | Only the exact date parameters declared in the Registry |
| **User Identity (`parameter_service.py`)** | Regex patterns guessing `empid`, `ids`, `userId` | Declared parameter list in Registry |
| **Response Logic (`response_service.py`)** | Raw question keyword matching (`profile_keywords`, `manager_keywords`) | The classified `intent` from the Registry |
| **UI Table Rendering (`Chronaichatbot.jsx`)** | 8+ manual `if (data.xyz)` extractors with fixed column arrays | Dynamic generic row extraction or registry response metadata |
