import requests
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class GitHubClient:
    """
    A client for interacting with the GitHub REST API.
    """
    def __init__(self):
        self.api_base = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def list_user_public_repositories(self, username: str) -> List[Dict[str, Any]]:
        """
        Lists public repositories for a given GitHub user.

        Args:
            username: The GitHub username.

        Returns:
            A list of dictionaries, each representing a public repository.
        """
        repos_url = f"{self.api_base}/users/{username}/repos"
        logger.info(f"Fetching public repositories for user: {username} from {repos_url}")

        try:
            response = requests.get(repos_url, headers=self.headers, timeout=10)
            response.raise_for_status()  # Raise an exception for HTTP errors

            repositories_data = response.json()
            public_repos = []
            for repo in repositories_data:
                if not repo.get('private', False):  # Ensure it's a public repository
                    public_repos.append({
                        "name": repo.get("name"),
                        "full_name": repo.get("full_name"),
                        "html_url": repo.get("html_url"),
                        "description": repo.get("description"),
                        "language": repo.get("language"),
                        "stargazers_count": repo.get("stargazers_count"),
                        "forks_count": repo.get("forks_count"),
                        "updated_at": repo.get("updated_at"),
                    })
            return public_repos
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.error(f"GitHub user '{username}' not found.")
            elif e.response.status_code == 403:
                logger.error(f"Rate limit exceeded or forbidden access for user '{username}'.")
            else:
                logger.error(f"HTTP error fetching repositories for '{username}': {e}")
            return []
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error fetching repositories for '{username}': {e}")
            return []
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout error fetching repositories for '{username}': {e}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return []

# Example usage:
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    github_client = GitHubClient()
    username = "MiaMiZ17"
    public_repositories = github_client.list_user_public_repositories(username)

    if public_repositories:
        print(f"\nPublic repositories for {username}:")
        for repo in public_repositories:
            print(f"  Name: {repo['name']}")
            print(f"  URL: {repo['html_url']}")
            print(f"  Description: {repo['description']}")
            print(f"  Language: {repo['language']}")
            print(f"  Stars: {repo['stargazers_count']}")
            print(f"  Last Updated: {repo['updated_at']}\n")
    else:
        print(f"No public repositories found for {username} or an error occurred.")
