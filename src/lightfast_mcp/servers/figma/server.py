"""
Figma MCP Server for web design and collaborative design workflows.
Implements comprehensive Figma automation through the Figma Web API.
"""

import json
from typing import ClassVar, Dict, Optional

import aiohttp

from ...core.base_server import BaseServer, ServerConfig
from ...utils.logging_utils import get_logger

logger = get_logger("FigmaMCPServer")


class FigmaAPIError(Exception):
    """Base exception for Figma API errors."""

    pass


class FigmaConnectionError(FigmaAPIError):
    """Exception raised when connection to Figma API fails."""

    pass


class FigmaResponseError(FigmaAPIError):
    """Exception raised when Figma API returns an error response."""

    pass


class FigmaMCPServer(BaseServer):
    """Figma MCP server for web design and collaborative design workflows."""

    # Server metadata
    SERVER_TYPE: ClassVar[str] = "figma"
    SERVER_VERSION: ClassVar[str] = "1.0.0"
    REQUIRED_DEPENDENCIES: ClassVar[list[str]] = ["aiohttp"]
    REQUIRED_APPS: ClassVar[list[str]] = ["Figma"]

    def __init__(self, config: ServerConfig):
        """Initialize the Figma server."""
        super().__init__(config)

        # Figma-specific configuration
        self.api_token = config.config.get("api_token")
        self.base_url = "https://api.figma.com/v1"
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = config.config.get("timeout", 30)

        if not self.api_token:
            raise ValueError("Figma API token is required in config.api_token")

        logger.info("Figma server configured with API access")

    async def _setup_session(self):
        """Setup HTTP session with authentication."""
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers={
                    "X-Figma-Token": self.api_token,
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )
            logger.info("Figma API session initialized")

    def _register_tools(self):
        """Register Figma server tools."""
        if not self.mcp:
            return

        # Register core tools
        self.mcp.tool()(self.get_file_info)
        self.mcp.tool()(self.export_node)
        self.mcp.tool()(self.add_comment)
        self.mcp.tool()(self.get_team_projects)
        self.mcp.tool()(self.get_file_versions)
        self.mcp.tool()(self.get_file_components)
        self.mcp.tool()(self.get_user_info)
        self.mcp.tool()(self.search_files)

        # Update available tools list
        self.info.tools = [
            "get_file_info",
            "export_node",
            "add_comment",
            "get_team_projects",
            "get_file_versions",
            "get_file_components",
            "get_user_info",
            "search_files",
        ]
        logger.info(f"Registered {len(self.info.tools)} tools: {self.info.tools}")

    async def _check_application(self, app: str) -> bool:
        """Check if Figma API is available."""
        if app.lower() == "figma":
            return await self._check_figma_connection()
        return True

    async def _check_figma_connection(self) -> bool:
        """Check if Figma API is accessible."""
        try:
            await self._setup_session()
            if not self.session:
                return False

            async with self.session.get(f"{self.base_url}/me") as response:
                return response.status == 200
        except Exception as e:
            logger.warning(f"Figma API connection check failed: {e}")
            return False

    async def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict] = None
    ) -> Dict:
        """Make HTTP request to Figma API."""
        await self._setup_session()

        if not self.session:
            raise FigmaConnectionError("Failed to setup HTTP session")

        url = f"{self.base_url}/{endpoint}"

        try:
            if method.upper() == "GET":
                async with self.session.get(url) as response:
                    response.raise_for_status()
                    return await response.json()
            elif method.upper() == "POST":
                async with self.session.post(url, json=data) as response:
                    response.raise_for_status()
                    return await response.json()
            elif method.upper() == "PUT":
                async with self.session.put(url, json=data) as response:
                    response.raise_for_status()
                    return await response.json()
            elif method.upper() == "DELETE":
                async with self.session.delete(url) as response:
                    response.raise_for_status()
                    return await response.json()
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except aiohttp.ClientError as e:
            logger.error(f"Figma API request failed: {e}")
            raise FigmaResponseError(f"API request failed: {e}") from e

    async def get_file_info(self, file_key: str) -> str:
        """Get information about a Figma file.

        Args:
            file_key: The Figma file key (from file URL)

        Returns:
            JSON string with file information including name, version, and document structure
        """
        try:
            response = await self._make_request("GET", f"files/{file_key}")

            file_info = {
                "name": response.get("name", "Unknown"),
                "lastModified": response.get("lastModified"),
                "version": response.get("version"),
                "thumbnailUrl": response.get("thumbnailUrl"),
                "role": response.get("role"),
                "editorType": response.get("editorType"),
                "document": {
                    "id": response["document"]["id"],
                    "name": response["document"]["name"],
                    "type": response["document"]["type"],
                }
                if "document" in response
                else None,
            }

            return json.dumps(file_info, indent=2)

        except Exception as e:
            logger.error(f"Error getting file info for {file_key}: {e}")
            return f"Error getting file info: {str(e)}"

    async def export_node(
        self, file_key: str, node_id: str, format: str = "png", scale: float = 1.0
    ) -> str:
        """Export a node as image.

        Args:
            file_key: The Figma file key
            node_id: The node ID to export
            format: Export format (png, jpg, svg, pdf)
            scale: Export scale factor (1.0 = 100%)

        Returns:
            JSON string with export URL or error message
        """
        try:
            # Validate format
            valid_formats = ["png", "jpg", "svg", "pdf"]
            if format.lower() not in valid_formats:
                return f"Error: Invalid format '{format}'. Valid formats: {', '.join(valid_formats)}"

            # Validate scale
            if not (0.01 <= scale <= 4.0):
                return "Error: Scale must be between 0.01 and 4.0"

            params = {"ids": node_id, "format": format.lower(), "scale": scale}

            # Build query string
            query_params = "&".join([f"{k}={v}" for k, v in params.items()])
            endpoint = f"images/{file_key}?{query_params}"

            response = await self._make_request("GET", endpoint)

            if "images" in response and node_id in response["images"]:
                image_url = response["images"][node_id]
                result = {
                    "success": True,
                    "download_url": image_url,
                    "format": format,
                    "scale": scale,
                    "node_id": node_id,
                }
                return json.dumps(result, indent=2)
            else:
                return json.dumps({"success": False, "error": "No image URL returned"})

        except Exception as e:
            logger.error(f"Error exporting node {node_id}: {e}")
            return json.dumps({"success": False, "error": str(e)})

    async def add_comment(self, file_key: str, x: float, y: float, message: str) -> str:
        """Add a comment to the file.

        Args:
            file_key: The Figma file key
            x: X coordinate for comment position
            y: Y coordinate for comment position
            message: Comment text

        Returns:
            JSON string with comment ID or error message
        """
        try:
            if not message or not message.strip():
                return json.dumps(
                    {"success": False, "error": "Comment message cannot be empty"}
                )

            comment_data = {"message": message.strip(), "client_meta": {"x": x, "y": y}}

            response = await self._make_request(
                "POST", f"files/{file_key}/comments", comment_data
            )

            if "id" in response:
                result = {
                    "success": True,
                    "comment_id": response["id"],
                    "message": message,
                    "position": {"x": x, "y": y},
                    "created_at": response.get("created_at"),
                }
                return json.dumps(result, indent=2)
            else:
                return json.dumps({"success": False, "error": "Failed to add comment"})

        except Exception as e:
            logger.error(f"Error adding comment to {file_key}: {e}")
            return json.dumps({"success": False, "error": str(e)})

    async def get_team_projects(self, team_id: str) -> str:
        """Get projects for a team.

        Args:
            team_id: The team ID

        Returns:
            JSON string with list of team projects
        """
        try:
            response = await self._make_request("GET", f"teams/{team_id}/projects")

            projects = []
            for project in response.get("projects", []):
                projects.append({"id": project["id"], "name": project["name"]})

            return json.dumps({"projects": projects}, indent=2)

        except Exception as e:
            logger.error(f"Error getting team projects for {team_id}: {e}")
            return json.dumps({"success": False, "error": str(e)})

    async def get_file_versions(self, file_key: str) -> str:
        """Get version history of a file.

        Args:
            file_key: The Figma file key

        Returns:
            JSON string with version history
        """
        try:
            response = await self._make_request("GET", f"files/{file_key}/versions")

            versions = []
            for version in response.get("versions", []):
                versions.append(
                    {
                        "id": version["id"],
                        "created_at": version["created_at"],
                        "label": version.get("label", ""),
                        "description": version.get("description", ""),
                        "user": version.get("user", {}).get("handle", "Unknown"),
                    }
                )

            return json.dumps({"versions": versions}, indent=2)

        except Exception as e:
            logger.error(f"Error getting file versions for {file_key}: {e}")
            return json.dumps({"success": False, "error": str(e)})

    async def get_file_components(self, file_key: str) -> str:
        """Get components from a Figma file.

        Args:
            file_key: The Figma file key

        Returns:
            JSON string with components information
        """
        try:
            response = await self._make_request("GET", f"files/{file_key}/components")

            components = []
            for comp_id, component in (
                response.get("meta", {}).get("components", {}).items()
            ):
                components.append(
                    {
                        "id": comp_id,
                        "name": component.get("name", "Unnamed"),
                        "description": component.get("description", ""),
                        "created_at": component.get("created_at"),
                        "updated_at": component.get("updated_at"),
                        "user": component.get("user", {}).get("handle", "Unknown"),
                    }
                )

            return json.dumps({"components": components}, indent=2)

        except Exception as e:
            logger.error(f"Error getting file components for {file_key}: {e}")
            return json.dumps({"success": False, "error": str(e)})

    async def get_user_info(self) -> str:
        """Get information about the authenticated user.

        Returns:
            JSON string with user information
        """
        try:
            response = await self._make_request("GET", "me")

            user_info = {
                "id": response.get("id"),
                "email": response.get("email"),
                "handle": response.get("handle"),
                "img_url": response.get("img_url"),
            }

            return json.dumps(user_info, indent=2)

        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return json.dumps({"success": False, "error": str(e)})

    async def search_files(self, team_id: str, query: str) -> str:
        """Search for files in a team.

        Args:
            team_id: The team ID to search in
            query: Search query string

        Returns:
            JSON string with search results
        """
        try:
            if not query or not query.strip():
                return json.dumps(
                    {"success": False, "error": "Search query cannot be empty"}
                )

            # Note: This is a simplified search - Figma API has limited search capabilities
            # In practice, you might need to get all files and filter client-side
            projects_response = await self._make_request(
                "GET", f"teams/{team_id}/projects"
            )

            files = []
            for project in projects_response.get("projects", []):
                project_files = await self._make_request(
                    "GET", f"projects/{project['id']}/files"
                )
                for file in project_files.get("files", []):
                    if query.lower() in file.get("name", "").lower():
                        files.append(
                            {
                                "key": file.get("key"),
                                "name": file.get("name"),
                                "thumbnail_url": file.get("thumbnail_url"),
                                "last_modified": file.get("last_modified"),
                                "project": project["name"],
                            }
                        )

            return json.dumps({"files": files, "query": query}, indent=2)

        except Exception as e:
            logger.error(f"Error searching files: {e}")
            return json.dumps({"success": False, "error": str(e)})

    async def cleanup(self):
        """Cleanup resources."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("Figma API session closed")

    async def __aenter__(self):
        """Async context manager entry."""
        await self._setup_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()


def main():
    """Run the Figma MCP server directly."""
    # Create a default configuration for standalone running
    config = ServerConfig(
        name="FigmaMCP",
        description="Figma MCP Server for web design and collaborative design workflows",
        config={
            "type": "figma",
            "api_token": None,  # Must be provided via environment or config
            "timeout": 30,
        },
    )

    # Create and run the server
    server = FigmaMCPServer(config)
    logger.info(f"Starting standalone Figma server: {config.name}")
    server.run()


if __name__ == "__main__":
    main()
