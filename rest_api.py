import aiohttp
import asyncio
from typing import Optional, Dict, Any
from config_manager import config


class RestApiHandler:
    """Handles communication with the Palworld server REST API"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_url = config.get('rest_api_endpoint', '')
        self.api_key = config.get('rest_api_key', '')
        self.last_error = None
        
    async def initialize(self):
        """Initialize the HTTP session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    def is_configured(self) -> bool:
        """Check if REST API is configured"""
        base_url = config.get('rest_api_endpoint', '')
        api_key = config.get('rest_api_key', '')
        return bool(base_url and api_key)
    
    async def _make_request(self, endpoint: str, method: str = "GET", data: Optional[Dict] = None) -> Optional[Dict[Any, Any]]:
        """Make a request to the REST API using live configuration"""
        # Fetch live config
        base_url = config.get('rest_api_endpoint', '').strip()
        api_key = config.get('rest_api_key', '').strip()
        
        if not base_url or not api_key:
            print("⚠️ REST API not fully configured (Endpoint or Key missing)")
            return None
            
        # 1. Auto-add http:// if missing
        if not base_url.startswith(('http://', 'https://')):
            base_url = f"http://{base_url}"
            
        await self.initialize()
        
        # 2. Use Standard Palworld Basic Auth (admin:password)
        auth = aiohttp.BasicAuth("admin", api_key)
        
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            async with self.session.request(method, url, auth=auth, json=data, timeout=5) as response:
                if response.status == 200:
                    self.last_error = None
                    return await response.json()
                elif response.status == 401:
                    self.last_error = "Unauthorized (401): Your API Key (Admin Password) is likely incorrect."
                elif response.status == 404:
                    self.last_error = "Not Found (404): The REST API endpoint or version is incorrect."
                else:
                    error_text = await response.text()
                    self.last_error = f"Server Error ({response.status}): {error_text[:100]}"
                
                print(f"❌ REST API Error: {self.last_error} at {url}")
                return None
        except asyncio.TimeoutError:
            self.last_error = "Timeout: The server did not respond in time. Check if the port is open."
            print(f"❌ REST API Error: {self.last_error} at {url}")
            return None
        except aiohttp.ClientConnectorError:
            self.last_error = "Connection Failed: Could not connect to the server. Is the IP/Port correct? Is the server running?"
            print(f"❌ REST API Error: {self.last_error} at {url}")
            return None
        except Exception as e:
            self.last_error = f"Unexpected Error: {str(e)}"
            print(f"❌ REST API Error connecting to {url}: {e}")
            return None
    
    def get_last_error(self) -> str:
        """Get the last error message"""
        return self.last_error or "Unknown Error"
    
    async def get_player_list(self) -> Optional[Dict]:
        """Get the current list of players from the server"""
        # Standard Palworld Endpoint is /v1/api/players
        return await self._make_request("/v1/api/players")
    
    async def get_server_info(self) -> Optional[Dict]:
        """Get general server information"""
        return await self._make_request("/v1/api/info")
    
    async def get_server_status(self) -> Optional[Dict]:
        """Get server status"""
        return await self._make_request("/v1/api/status")
    
    async def broadcast_message(self, message: str) -> bool:
        """Send a broadcast message (Announcement) to the server"""
        data = {"message": message}
        # Official Palworld REST API uses /v1/api/announce
        result = await self._make_request("/v1/api/announce", "POST", data)
        return result is not None
    
    async def shutdown_server_gracefully(self, seconds: int = 60, message: str = "Server shutting down") -> bool:
        """Gracefully shut down the server after a delay"""
        data = {
            "waittime": seconds,
            "message": message
        }
        result = await self._make_request("/v1/api/shutdown", "POST", data)
        return result is not None
    
    async def save_world(self) -> bool:
        """Save the current world state"""
        result = await self._make_request("/v1/api/save", "POST")
        return result is not None


# Global instance
rest_api = RestApiHandler()