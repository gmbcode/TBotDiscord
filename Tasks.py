import json
import os
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dotenv import dotenv_values
config = dotenv_values(".env")

class GoogleTasksClient:
    """
    Google Tasks API client that handles authentication using stored OAuth tokens
    and provides comprehensive methods for Google Tasks operations.
    """

    def __init__(self, user_id: str, oauth_data_file: str = "udb.json"):
        """
        Initialize the Google Tasks client for a specific user.

        Args:
            user_id: The user ID to load OAuth data for
            oauth_data_file: Path to the JSON file containing OAuth data
        """
        self.user_id = user_id
        self.oauth_data_file = oauth_data_file
        self.base_url = "https://tasks.googleapis.com/tasks/v1"
        self.client_id = config["GOOGLE_CLIENT_ID"]
        self.client_secret = config["GOOGLE_CLIENT_SECRET"]
        self.token_url = "https://oauth2.googleapis.com/token"

        self.user_data = self._load_user_data()
        if not self.user_data:
            raise ValueError(f"No OAuth data found for user_id: {user_id}")

    def _load_user_data(self) -> Optional[Dict]:
        """Load user OAuth data from JSON file."""
        if not os.path.exists(self.oauth_data_file):
            return None

        try:
            with open(self.oauth_data_file, 'r') as f:
                data = json.load(f)
                return data.get(self.user_id)
        except (json.JSONDecodeError, FileNotFoundError):
            return None

    def _save_user_data(self):
        """Save updated user data back to JSON file."""
        try:
            # Load existing data
            existing_data = {}
            if os.path.exists(self.oauth_data_file):
                with open(self.oauth_data_file, 'r') as f:
                    existing_data = json.load(f)

            # Update user data
            existing_data[self.user_id] = self.user_data

            # Save back to file
            with open(self.oauth_data_file, 'w') as f:
                json.dump(existing_data, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving user data: {e}")

    def _is_token_expired(self) -> bool:
        """Check if the current access token is expired."""
        if not self.user_data.get('expires_at'):
            return True

        try:
            expires_at = datetime.fromisoformat(self.user_data['expires_at'].replace('Z', '+00:00'))
            return datetime.now() >= expires_at - timedelta(minutes=5)  # 5-minute buffer
        except (ValueError, TypeError):
            return True

    def _refresh_access_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        if not self.user_data.get('refresh_token'):
            raise ValueError("No refresh token available for token refresh")

        refresh_data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.user_data['refresh_token'],
            "grant_type": "refresh_token"
        }

        try:
            response = requests.post(self.token_url, data=refresh_data)
            print(f"Using client id : {self.client_id}")
            print(f"using refresh token {refresh_data['refresh_token']}")
            if response.status_code == 401:
                print("401 Unauthorized Error Details:")
                print(f"Response: {response.text}")
                print("Common causes:")
                print("1. Invalid client_id or client_secret")
                print("2. Refresh token has expired or been revoked")
                print("3. Client credentials don't match OAuth consent screen")
                print("4. OAuth consent screen is in testing mode with expired test users")
            response.raise_for_status()
            new_tokens = response.json()

            # Update stored data
            expires_in = new_tokens.get('expires_in', 3600)
            expires_at = datetime.now() + timedelta(seconds=expires_in)

            self.user_data.update({
                "access_token": new_tokens.get('access_token'),
                "expires_in": expires_in,
                "expires_at": expires_at.isoformat(),
                "refreshed_at": datetime.now().isoformat()
            })

            # Update refresh token if provided
            if 'refresh_token' in new_tokens:
                self.user_data['refresh_token'] = new_tokens['refresh_token']

            self._save_user_data()
            return True

        except requests.RequestException as e:
            print(f"Error refreshing token: {e}")
            return False

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with valid access token."""
        if self._is_token_expired():
            if not self._refresh_access_token():
                raise ValueError("Failed to refresh access token")

        return {
            "Authorization": f"Bearer {self.user_data['access_token']}",
            "Content-Type": "application/json"
        }

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None,
                      params: Optional[Dict] = None) -> Dict:
        """Make an authenticated request to the Google Tasks API."""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, params=params)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data, params=params)
            elif method.upper() == "PATCH":
                response = requests.patch(url, headers=headers, json=data, params=params)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()

            # Return empty dict for successful DELETE requests
            if method.upper() == "DELETE" and response.status_code == 204:
                return {}

            return response.json()

        except requests.RequestException as e:
            print(f"API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise

    # Task Lists Operations

    def get_task_lists(self) -> List[Dict]:
        """Get all task lists for the user."""
        response = self._make_request("GET", "/users/@me/lists")
        return response.get("items", [])

    def get_task_list(self, task_list_id: str) -> Dict:
        """Get a specific task list by ID."""
        return self._make_request("GET", f"/users/@me/lists/{task_list_id}")

    def create_task_list(self, title: str) -> Dict:
        """Create a new task list."""
        data = {"title": title}
        return self._make_request("POST", "/users/@me/lists", data=data)

    def update_task_list(self, task_list_id: str, title: str) -> Dict:
        """Update a task list title."""
        data = {"title": title}
        return self._make_request("PUT", f"/users/@me/lists/{task_list_id}", data=data)

    def delete_task_list(self, task_list_id: str) -> Dict:
        """Delete a task list."""
        return self._make_request("DELETE", f"/users/@me/lists/{task_list_id}")

    # Tasks Operations

    def get_tasks(self, task_list_id: str, show_completed: bool = True,
                  show_deleted: bool = False, show_hidden: bool = True,
                  max_results: Optional[int] = None, page_token: Optional[str] = None,
                  updated_min: Optional[str] = None, completed_min: Optional[str] = None,
                  completed_max: Optional[str] = None, due_min: Optional[str] = None,
                  due_max: Optional[str] = None) -> Dict:
        """
        Get tasks from a specific task list with various filtering options.

        Args:
            task_list_id: ID of the task list
            show_completed: Include completed tasks
            show_deleted: Include deleted tasks
            show_hidden: Include hidden tasks
            max_results: Maximum number of tasks to return
            page_token: Token for pagination
            updated_min: RFC 3339 timestamp, only tasks updated after this time
            completed_min: RFC 3339 timestamp, only tasks completed after this time
            completed_max: RFC 3339 timestamp, only tasks completed before this time
            due_min: RFC 3339 timestamp, only tasks due after this time
            due_max: RFC 3339 timestamp, only tasks due before this time
        """
        params = {}
        if show_completed:
            params["showCompleted"] = "true"
        if show_deleted:
            params["showDeleted"] = "true"
        if show_hidden:
            params["showHidden"] = "true"
        if max_results:
            params["maxResults"] = str(max_results)
        if page_token:
            params["pageToken"] = page_token
        if updated_min:
            params["updatedMin"] = updated_min
        if completed_min:
            params["completedMin"] = completed_min
        if completed_max:
            params["completedMax"] = completed_max
        if due_min:
            params["dueMin"] = due_min
        if due_max:
            params["dueMax"] = due_max

        return self._make_request("GET", f"/lists/{task_list_id}/tasks", params=params)

    def get_task(self, task_list_id: str, task_id: str) -> Dict:
        """Get a specific task by ID."""
        return self._make_request("GET", f"/lists/{task_list_id}/tasks/{task_id}")

    def create_task(self, task_list_id: str, title: str, notes: Optional[str] = None,
                    due: Optional[str] = None, parent: Optional[str] = None,
                    previous: Optional[str] = None) -> Dict:
        """
        Create a new task.

        Args:
            task_list_id: ID of the task list
            title: Title of the task
            notes: Notes/description for the task
            due: Due date in RFC 3339 format (e.g., "2023-12-31T23:59:59.000Z")
            parent: Parent task ID (for subtasks)
            previous: Previous sibling task ID (for ordering)
        """
        data = {"title": title}
        if notes:
            data["notes"] = notes
        if due:
            data["due"] = due

        params = {}
        if parent:
            params["parent"] = parent
        if previous:
            params["previous"] = previous

        return self._make_request("POST", f"/lists/{task_list_id}/tasks", data=data, params=params)

    def update_task(self, task_list_id: str, task_id: str, title: Optional[str] = None,
                    notes: Optional[str] = None, status: Optional[str] = None,
                    due: Optional[str] = None, completed: Optional[str] = None) -> Dict:
        """
        Update an existing task.

        Args:
            task_list_id: ID of the task list
            task_id: ID of the task to update
            title: New title for the task
            notes: New notes for the task
            status: Task status ("needsAction" or "completed")
            due: Due date in RFC 3339 format
            completed: Completion date in RFC 3339 format
        """
        data = {}
        if title is not None:
            data["title"] = title
        if notes is not None:
            data["notes"] = notes
        if status is not None:
            data["status"] = status
        if due is not None:
            data["due"] = due
        if completed is not None:
            data["completed"] = completed

        return self._make_request("PATCH", f"/lists/{task_list_id}/tasks/{task_id}", data=data)

    def delete_task(self, task_list_id: str, task_id: str) -> Dict:
        """Delete a task."""
        return self._make_request("DELETE", f"/lists/{task_list_id}/tasks/{task_id}")

    def move_task(self, task_list_id: str, task_id: str, parent: Optional[str] = None,
                  previous: Optional[str] = None) -> Dict:
        """
        Move a task to a different position.

        Args:
            task_list_id: ID of the task list
            task_id: ID of the task to move
            parent: New parent task ID (for subtasks)
            previous: Previous sibling task ID (for ordering)
        """
        params = {}
        if parent:
            params["parent"] = parent
        if previous:
            params["previous"] = previous

        return self._make_request("POST", f"/lists/{task_list_id}/tasks/{task_id}/move", params=params)

    def complete_task(self, task_list_id: str, task_id: str) -> Dict:
        """Mark a task as completed."""
        return self.update_task(task_list_id, task_id,
                                status="completed",
                                completed=datetime.utcnow().isoformat() + "Z")

    def uncomplete_task(self, task_list_id: str, task_id: str) -> Dict:
        """Mark a task as not completed."""
        return self.update_task(task_list_id, task_id,
                                status="needsAction",
                                completed=None)

    def clear_completed_tasks(self, task_list_id: str) -> Dict:
        """Clear all completed tasks from a task list."""
        return self._make_request("POST", f"/lists/{task_list_id}/clear")

    # Utility Methods

    def get_default_task_list(self) -> Optional[Dict]:
        """Get the default task list (usually the first one)."""
        task_lists = self.get_task_lists()
        return task_lists[0] if task_lists else None

    def search_tasks(self, task_list_id: str, query: str) -> List[Dict]:
        """
        Search for tasks containing the query string in title or notes.
        Note: This is a client-side search since Google Tasks API doesn't support server-side search.
        """
        tasks_response = self.get_tasks(task_list_id, show_completed=True)
        tasks = tasks_response.get("items", [])

        query_lower = query.lower()
        matching_tasks = []

        for task in tasks:
            title = task.get("title", "").lower()
            notes = task.get("notes", "").lower()

            if query_lower in title or query_lower in notes:
                matching_tasks.append(task)

        return matching_tasks

    def get_task_count(self, task_list_id: str, completed_only: bool = False) -> int:
        """Get the total number of tasks in a task list."""
        tasks_response = self.get_tasks(task_list_id, show_completed=True)
        tasks = tasks_response.get("items", [])

        if not completed_only:
            return len(tasks)

        return sum(1 for task in tasks if task.get("status") == "completed")

    def get_overdue_tasks(self, task_list_id: str) -> List[Dict]:
        """Get all overdue tasks from a task list."""
        tasks_response = self.get_tasks(task_list_id, show_completed=False)
        tasks = tasks_response.get("items", [])

        now = datetime.utcnow()
        overdue_tasks = []

        for task in tasks:
            due_date = task.get("due")
            if due_date:
                try:
                    due_datetime = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                    if due_datetime.replace(tzinfo=None) < now:
                        overdue_tasks.append(task)
                except (ValueError, TypeError):
                    continue

        return overdue_tasks


# Example usage and testing
if __name__ == "__main__":
    # Example usage
    try:
        # Initialize client for a specific user
        client = GoogleTasksClient(user_id="585767830247571476")

        # Get all task lists
        print("Task Lists:")
        task_lists = client.get_task_lists()
        for task_list in task_lists:
            print(f"- {task_list['title']} (ID: {task_list['id']})")

        if task_lists:
            task_list_id = task_lists[0]['id']

            # Create a new task
            print(f"\nCreating a new task in list: {task_lists[0]['title']}")
            new_task = client.create_task(
                task_list_id=task_list_id,
                title="Test Task from Python Client",
                notes="This task was created using the Python Google Tasks client",
                due="2024-12-31T23:59:59.000Z"
            )
            print(f"Created task: {new_task['title']} (ID: {new_task['id']})")

            # Get all tasks
            print(f"\nTasks in {task_lists[0]['title']}:")
            tasks_response = client.get_tasks(task_list_id)
            tasks = tasks_response.get("items", [])
            for task in tasks:
                status = "✓" if task.get("status") == "completed" else "○"
                print(f"{status} {task['title']}")

            # Update the task
            updated_task = client.update_task(
                task_list_id=task_list_id,
                task_id=new_task['id'],
                title="Updated Test Task",
                notes="This task was updated!"
            )
            print(f"\nUpdated task: {updated_task['title']}")

            # Complete the task
            client.complete_task(task_list_id, new_task['id'])
            print("Task marked as completed")

            # Get overdue tasks
            overdue = client.get_overdue_tasks(task_list_id)
            print(f"\nOverdue tasks: {len(overdue)}")

    except Exception as e:
        print(f"Error: {e}")
        print("Make sure you have valid OAuth data stored and the user_id exists.")