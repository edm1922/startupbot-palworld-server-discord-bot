import asyncio
import struct
from typing import Optional, Tuple
from utils.config_manager import config


class RconUtility:
    """RCON utility for sending commands to PalGuard/PalDefender"""
    
    # RCON packet types
    SERVERDATA_AUTH = 3
    SERVERDATA_AUTH_RESPONSE = 2
    SERVERDATA_EXECCOMMAND = 2
    SERVERDATA_RESPONSE_VALUE = 0
    
    def __init__(self):
        self.request_id = 0
    
    def _pack_packet(self, packet_type: int, body: str) -> bytes:
        """Pack an RCON packet"""
        self.request_id += 1
        body_bytes = body.encode('utf-8')
        
        # Packet structure: size (4 bytes) + id (4 bytes) + type (4 bytes) + body + null terminators (2 bytes)
        packet_size = 4 + 4 + len(body_bytes) + 2
        
        packet = struct.pack('<i', packet_size)  # Size
        packet += struct.pack('<i', self.request_id)  # Request ID
        packet += struct.pack('<i', packet_type)  # Type
        packet += body_bytes  # Body
        packet += b'\x00\x00'  # Null terminators
        
        return packet
    
    def _unpack_packet(self, data: bytes) -> Tuple[int, int, str]:
        """Unpack an RCON packet"""
        if len(data) < 12:
            return 0, 0, ""
        
        size = struct.unpack('<i', data[:4])[0]
        request_id = struct.unpack('<i', data[4:8])[0]
        packet_type = struct.unpack('<i', data[8:12])[0]
        
        # Body is from byte 12 to end minus 2 null terminators
        body = data[12:-2].decode('utf-8', errors='ignore')
        
        return request_id, packet_type, body
    
    async def rcon_command(self, server_info: dict, command: str) -> Optional[str]:
        """
        Send an RCON command to the server
        
        Args:
            server_info: Dict with 'host', 'port', 'password'
            command: The RCON command to execute
            
        Returns:
            Response string or None if failed
        """
        host = server_info.get('host', '127.0.0.1')
        port = server_info.get('port', 25575)
        password = server_info.get('password', '')
        
        if not password:
            print("⚠️ RCON password not configured")
            return None
        
        try:
            # Connect to RCON server
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5.0
            )
            
            # Authenticate
            auth_packet = self._pack_packet(self.SERVERDATA_AUTH, password)
            writer.write(auth_packet)
            await writer.drain()
            
            # Read auth response
            auth_response = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            auth_id, auth_type, _ = self._unpack_packet(auth_response)
            
            if auth_id == -1:
                print("❌ RCON authentication failed - incorrect password")
                writer.close()
                await writer.wait_closed()
                return None
            
            # Send command
            cmd_packet = self._pack_packet(self.SERVERDATA_EXECCOMMAND, command)
            writer.write(cmd_packet)
            await writer.drain()
            
            # Read response
            response_data = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            _, _, response = self._unpack_packet(response_data)
            
            # Close connection
            writer.close()
            await writer.wait_closed()
            
            return response.strip()
            
        except asyncio.TimeoutError:
            print(f"❌ RCON timeout connecting to {host}:{port}")
            return None
        except ConnectionRefusedError:
            print(f"❌ RCON connection refused to {host}:{port} - Is RCON enabled?")
            return None
        except Exception as e:
            print(f"❌ RCON error: {e}")
            return None
    
    async def give_item(self, steam_id: str, item_id: str, amount: int) -> bool:
        """
        Give an item to a player
        
        Args:
            steam_id: Player's Steam ID (e.g., 'steam_76561198012345678')
            item_id: Item ID (e.g., 'Gold', 'PalSphere')
            amount: Amount to give
            
        Returns:
            True if successful, False otherwise
        """
        server_info = self._get_server_info()
        if not server_info:
            return False
        
        # Use the full steam_id (including 'steam_' prefix) as required by your server mod
        command = f"give {steam_id} {item_id} {amount}"
        response = await self.rcon_command(server_info, command)
        
        if response is not None:
            # Check for common failure messages in PalGuard/PalDefender
            lower_resp = response.lower()
            if "failed" in lower_resp or "invalid" in lower_resp or "not found" in lower_resp or "error" in lower_resp:
                print(f"❌ RCON ERROR: '{command}' returned: '{response}'")
                return False

            print(f"✅ RCON: Sent '{command}' - Response: '{response}'")
            return True
        else:
            print(f"❌ RCON: Failed to send '{command}' (No response or timeout)")
            return False
    
    async def give_exp(self, steam_id: str, amount: int) -> bool:
        """
        Give experience to a player
        
        Args:
            steam_id: Player's Steam ID
            amount: Amount of EXP to give
            
        Returns:
            True if successful, False otherwise
        """
        server_info = self._get_server_info()
        if not server_info:
            return False
            
        # Use the full steam_id (including 'steam_' prefix)
        command = f"give_exp {steam_id} {amount}"
        response = await self.rcon_command(server_info, command)
        
        if response is not None:
            lower_resp = response.lower()
            if "failed" in lower_resp or "invalid" in lower_resp or "not found" in lower_resp:
                print(f"❌ RCON ERROR: '{command}' returned: '{response}'")
                return False

            print(f"✅ RCON: Sent '{command}' - Response: '{response}'")
            return True
        else:
            print(f"❌ RCON: Failed to send '{command}' (No response or timeout)")
            return False
    
    def _get_server_info(self) -> Optional[dict]:
        """Get RCON server info from config"""
        host = config.get('rcon_host', '127.0.0.1')
        port = config.get('rcon_port', 25575)
        password = config.get('rcon_password', '')
        
        if not password:
            print("⚠️ RCON not configured. Use /config to set RCON settings.")
            return None
        
        return {
            'host': host,
            'port': port,
            'password': password
        }
    
    def is_configured(self) -> bool:
        """Check if RCON is configured"""
        return bool(config.get('rcon_password', ''))


# Global instance
rcon_util = RconUtility()
