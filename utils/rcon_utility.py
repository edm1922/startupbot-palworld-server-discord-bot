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
        self.lock = asyncio.Lock()
        self.tell_works = True # Track if 'tell' command is supported
    
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
        
        async with self.lock:
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
                
                # Mandatory delay to prevent server flooding (Palworld RCON is unstable)
                await asyncio.sleep(0.5)
                
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
    
    async def broadcast(self, message: str) -> bool:
        """
        Send a broadcast message to all players on the server.
        Tries REST API first (most reliable), then falls back to RCON.
        """
        # 1. Try REST API first (it handles characters like spaces/quotes better)
        from utils.rest_api import rest_api
        if rest_api.is_configured():
            try:
                success = await rest_api.broadcast_message(message)
                if success:
                    return True
            except:
                pass

        # 2. Fallback to RCON
        server_info = self._get_server_info()
        if not server_info:
            return False
            
        # Many RCON implementations prefer NO quotes, or handle them weirdly.
        command = f"Broadcast {message}"
        response = await self.rcon_command(server_info, command)
        
        return response is not None

    async def send_private_message(self, steam_id: str, message: str) -> bool:
        """
        Send a private message to a specific player via PalGuard/PalDefender 'tell' command.
        """
        if not self.tell_works:
            # Fallback to broadcast if private messaging isn't possible
            # We prefix with [PRIVATE-MSG] so players know it was meant for them
            await self.broadcast(f"[MSG] @{steam_id}: {message}")
            return False

        server_info = self._get_server_info()
        if not server_info: return False

        # Strip/Add prefix to ensure we have both formats
        id_no_prefix = steam_id.replace("steam_", "")
        id_with_prefix = f"steam_{id_no_prefix}"

        # Try with raw ID first as it's most common for tell
        cmd = f'tell {id_no_prefix} "{message}"'
        resp = await self.rcon_command(server_info, cmd)
        
        # Fallback for PalGuard: some versions use 'pg tell'
        if resp == "Unknown command":
            cmd = f'pg tell {id_no_prefix} "{message}"'
            resp = await self.rcon_command(server_info, cmd)
            if resp != "Unknown command":
                # It worked with pg! We can continue.
                return resp is not None
        
        # If still unknown or server doesn't support messaging at all
        if resp == "Unknown command":
            print(f"⚠️ Server RCON does not support 'tell' or 'pg tell'. Disabling private messages.")
            self.tell_works = False
            return False

        # Legacy prefix fallbacks
        if resp is None or "not found" in resp.lower() or "error" in resp.lower():
            cmd = f'tell {id_with_prefix} "{message}"'
            resp = await self.rcon_command(server_info, cmd)

        if resp is not None:
            print(f"📡 [TELL] Sent to {id_no_prefix}: {message} (Resp: {resp})")
            return True
        return False

    async def give_item(self, steam_id: str, item_id: str, amount: int) -> Tuple[bool, str]:
        """
        Give an item to a player
        """
        server_info = self._get_server_info()
        if not server_info:
            return False, "RCON not configured"
        
        command = f"give {steam_id} {item_id} {amount}"
        response = await self.rcon_command(server_info, command)
        
        if response is not None:
            lower_resp = response.lower()
            if "failed" in lower_resp or "invalid" in lower_resp or "not found" in lower_resp or "error" in lower_resp:
                return False, response
            return True, response
        return False, "RCON Timeout/No Response"
    
    async def give_exp(self, steam_id: str, amount: int) -> Tuple[bool, str]:
        """
        Give experience to a player
        """
        server_info = self._get_server_info()
        if not server_info:
            return False, "RCON not configured"
            
        command = f"give_exp {steam_id} {amount}"
        response = await self.rcon_command(server_info, command)
        
        if response is not None:
            lower_resp = response.lower()
            if "failed" in lower_resp or "invalid" in lower_resp or "not found" in lower_resp:
                return False, response
            return True, response
        return False, "RCON Timeout/No Response"

    async def give_pal_standard(self, steam_id: str, pal_id: str, level: int = 1) -> Tuple[bool, str]:
        """
        Give a base game Pal using PalGuard/PalDefender 'givepal' command.
        Includes a fallback to givepal_j if file-not-found error occurs.
        """
        server_info = self._get_server_info()
        if not server_info: return False, "RCON not configured"

        # Try givepal first
        cmd = f"givepal {steam_id} {pal_id} {level}"
        resp = await self.rcon_command(server_info, cmd)
        
        success = resp is not None and (resp == "" or any(x in resp.lower() for x in ["success", "spawned", "sent", "ok", "added", "given", "granted", "active"]))
        
        if not success and resp and ("could not import" in resp.lower() or "not found" in resp.lower()):
            # Fallback: maybe it's a template?
            return await self.give_pal_template(steam_id, pal_id)
            
        return success, resp

    async def give_pal_template(self, steam_id: str, template_name: str) -> Tuple[bool, str]:
        """
        Give a custom Pal using 'givepal_j' command.
        Includes a lowercase fallback for case-sensitive filenames.
        """
        server_info = self._get_server_info()
        if not server_info: return False, "RCON not configured"

        cmd = f"givepal_j {steam_id} {template_name}"
        resp = await self.rcon_command(server_info, cmd)
        
        success = resp is not None and (resp == "" or any(x in resp.lower() for x in ["success", "spawned", "sent", "ok", "added", "given", "granted", "active"]))
        
        # Lowercase fallback
        if not success and resp and "could not import" in resp.lower() and template_name != template_name.lower():
            # Try lowercase
            cmd = f"givepal_j {steam_id} {template_name.lower()}"
            resp = await self.rcon_command(server_info, cmd)
            success = resp is not None and (resp == "" or any(x in resp.lower() for x in ["success", "spawned", "sent", "ok", "added", "given", "granted", "active"]))
            
        return success, resp
    
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
