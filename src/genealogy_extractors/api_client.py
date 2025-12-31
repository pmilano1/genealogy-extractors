"""
GraphQL API Client for Genealogy Research Tasks
Connects extractors to the Kindred API
"""

import json
import subprocess
from typing import List, Dict, Any, Optional

from .config import get_api_config


def _get_api_settings():
    """Get API endpoint and key from config."""
    config = get_api_config()
    endpoint = config.get('endpoint', '')
    key = config.get('key', '')
    if not endpoint or not key:
        raise ValueError(
            "API not configured. Please add 'api.endpoint' and 'api.key' to "
            "~/.genealogy-extractors/config.json"
        )
    return endpoint, key


def _execute_query(query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
    """Execute a GraphQL query using curl subprocess"""
    endpoint, key = _get_api_settings()

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    cmd = [
        'curl', '-s', '-X', 'POST', endpoint,
        '-H', 'Content-Type: application/json',
        '-H', f'X-API-Key: {key}',
        '-d', json.dumps(payload)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"API call failed: {result.stderr}")

    return json.loads(result.stdout)


def get_research_tasks(
    first: int = 10,
    gap_types: Optional[List[str]] = None,
    researchable_only: bool = True,
    region: Optional[str] = None,
    access_methods: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Fetch research tasks from the API.
    
    Args:
        first: Number of tasks to fetch (max 100)
        gap_types: Filter by gap types (END_OF_LINE, MISSING_FATHER, MISSING_MOTHER)
        researchable_only: Only return researchable tasks (1700-1950 era)
        region: Filter by region/country
        access_methods: Filter by source access methods (API, WEB_FETCH, CDP_BROWSER)
    
    Returns:
        List of research task dictionaries
    """
    query = """
    query GetResearchTasks($filter: ResearchTaskFilter, $first: Int) {
      researchTasks(filter: $filter, first: $first) {
        edges {
          node {
            person_id
            gap_type
            search_target
            surname
            given_name
            location
            country
            year_min
            year_max
            priority_score
            sources {
              name
              access_method
              url_pattern
            }
            previous_searches {
              source_name
              result
            }
            person {
              id
              name_full
              birth_year
              estimated_birth_year
              birth_place
            }
          }
        }
        pageInfo {
          hasNextPage
          totalCount
        }
        researchable_count
      }
    }
    """
    
    filter_input = {"researchable_only": researchable_only}
    if gap_types:
        filter_input["gap_types"] = gap_types
    if region:
        filter_input["region"] = region
    if access_methods:
        filter_input["access_methods"] = access_methods
    
    variables = {"filter": filter_input, "first": first}
    
    response = _execute_query(query, variables)
    
    if "errors" in response:
        raise Exception(f"GraphQL errors: {response['errors']}")
    
    edges = response.get("data", {}).get("researchTasks", {}).get("edges", [])
    return [edge["node"] for edge in edges]


def log_search_attempt(
    person_id: str,
    source_name: str,
    result: str,
    notes: Optional[str] = None,
    agent_id: str = "genealogy-extractors"
) -> Dict[str, Any]:
    """
    Log a search attempt to prevent duplicate searches.
    
    Args:
        person_id: ID of the person being researched
        source_name: Name of the source searched (e.g., "Geneanet", "FamilySearch")
        result: NO_MATCH, POSSIBLE_MATCH, CONFIRMED_MATCH, or SOURCE_UNAVAILABLE
        notes: Optional notes about the search
        agent_id: Identifier for the agent doing the search
    
    Returns:
        The created search attempt record
    """
    mutation = """
    mutation LogSearchAttempt($input: SearchAttemptInput!) {
      logSearchAttempt(input: $input) {
        id
        source_name
        searched_at
        result
        notes
      }
    }
    """
    
    variables = {
        "input": {
            "person_id": person_id,
            "source_name": source_name,
            "result": result,
            "notes": notes,
            "agent_id": agent_id
        }
    }
    
    response = _execute_query(mutation, variables)
    
    if "errors" in response:
        raise Exception(f"GraphQL errors: {response['errors']}")
    
    return response.get("data", {}).get("logSearchAttempt", {})


def get_all_people(
    first: int = 100,
    after: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch all people from the database with pagination.

    Args:
        first: Number of people per page (max 100)
        after: Cursor for pagination

    Returns:
        Dict with 'people' list and 'pageInfo' for pagination
    """
    query = """
    query GetAllPeople($first: Int, $after: String) {
      people(first: $first, after: $after) {
        edges {
          node {
            id
            name_full
            name_given
            name_surname
            birth_year
            estimated_birth_year
            birth_place
            death_year
            death_place
            sex
          }
        }
        pageInfo {
          hasNextPage
          endCursor
          totalCount
        }
      }
    }
    """

    variables = {"first": first}
    if after:
        variables["after"] = after

    response = _execute_query(query, variables)

    if "errors" in response:
        raise Exception(f"GraphQL errors: {response['errors']}")

    data = response.get("data", {}).get("people", {})
    people = [edge["node"] for edge in data.get("edges", [])]

    return {
        "people": people,
        "pageInfo": data.get("pageInfo", {})
    }


def get_all_people_iterator(batch_size: int = 100):
    """
    Generator that yields all people, handling pagination automatically.

    Usage:
        for person in get_all_people_iterator():
            print(person['name_full'])
    """
    cursor = None
    while True:
        result = get_all_people(first=batch_size, after=cursor)
        for person in result["people"]:
            yield person

        if not result["pageInfo"].get("hasNextPage"):
            break
        cursor = result["pageInfo"].get("endCursor")


def person_to_search_params(person: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a person record to search parameters for extractors.

    Uses birth_year if available, falls back to estimated_birth_year.
    """
    # Use actual birth_year, fall back to estimated_birth_year
    birth_year = person.get("birth_year") or person.get("estimated_birth_year")

    return {
        "surname": person.get("name_surname", ""),
        "given_name": person.get("name_given", ""),
        "year_min": birth_year - 5 if birth_year else None,
        "year_max": birth_year + 5 if birth_year else None,
        "location": person.get("birth_place", ""),
        "is_estimated_year": person.get("birth_year") is None and birth_year is not None,
    }


def submit_research(
    person_id: str,
    source: Dict[str, str],
    confidence: str,
    findings: Optional[Dict[str, Any]] = None,
    new_father: Optional[Dict[str, Any]] = None,
    new_mother: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None,
    agent_id: str = "genealogy-extractors"
) -> Dict[str, Any]:
    """
    Submit research findings to create/update family records.

    Args:
        person_id: ID of the person being researched
        source: Source documentation {source_type, source_name, source_url, action, content}
        confidence: Confidence level (HIGH, MEDIUM, LOW)
        findings: Updates to the person's record
        new_father: New father to create and link
        new_mother: New mother to create and link
        notes: Optional notes about the research
        agent_id: Identifier for the agent

    Returns:
        Result with changes_made, gaps_resolved, etc.
    """
    mutation = """
    mutation SubmitResearch($input: ResearchFindingsInput!) {
      submitResearch(input: $input) {
        success
        person { id name_full }
        changes_made
        gaps_resolved
        source_id
      }
    }
    """

    input_data = {
        "person_id": person_id,
        "source": source,
        "confidence": confidence,
        "agent_id": agent_id
    }

    if findings:
        input_data["findings"] = findings
    if new_father:
        input_data["new_father"] = new_father
    if new_mother:
        input_data["new_mother"] = new_mother
    if notes:
        input_data["notes"] = notes

    response = _execute_query(mutation, {"input": input_data})

    if "errors" in response:
        raise Exception(f"GraphQL errors: {response['errors']}")

    return response.get("data", {}).get("submitResearch", {})


def task_to_search_params(task: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a research task to search parameters for extractors."""
    return {
        "surname": task.get("surname", ""),
        "given_name": task.get("given_name", ""),
        "year_min": task.get("year_min"),
        "year_max": task.get("year_max"),
        "location": task.get("location", ""),
        "country": task.get("country", "")
    }


def get_unsearched_sources(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get sources that haven't been searched yet for a task."""
    searched = {s["source_name"] for s in task.get("previous_searches", [])}
    return [s for s in task.get("sources", []) if s["name"] not in searched]

