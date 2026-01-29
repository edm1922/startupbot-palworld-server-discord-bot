import nextcord
import json
import os
from nextcord.ext import commands
from utils.config_manager import config
from utils.rcon_utility import rcon_util
from utils.database import db
from cogs.pal_system import pal_system

class PalCageManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_admin(self, interaction: nextcord.Interaction):
        admin_id = config.get('admin_user_id', 0)
        return interaction.user.id == admin_id or (hasattr(interaction.user, 'guild_permissions') and interaction.user.guild_permissions.administrator)

    @nextcord.slash_command(name="pal_cage")
    async def pal_cage_group(self, interaction: nextcord.Interaction):
        """Parent command for Custom Pal (Pal Cage) management"""
        pass

    @pal_cage_group.subcommand(name="add", description="Add a custom Pal definition (JSON)")
    async def add_custom_pal(
        self,
        interaction: nextcord.Interaction,
        name: str = nextcord.SlashOption(description="Name for this custom Pal"),
        pal_json: str = nextcord.SlashOption(description="The Pal JSON data"),
        description: str = nextcord.SlashOption(required=False, description="Brief description")
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return
            
        # Basic JSON validation
        try:
            json.loads(pal_json)
        except json.JSONDecodeError:
            await interaction.response.send_message("❌ Invalid JSON format. Please provide a valid Pal JSON string.", ephemeral=True)
            return

        template_dir = config.get('pal_template_dir')
        msg = pal_system.add_pal(name, pal_json, description, export_dir=template_dir)
        await interaction.response.send_message(f"✅ {msg}.", ephemeral=True)

    @pal_cage_group.subcommand(name="view", description="Show a custom Pal's data")
    async def view_pal(self, interaction: nextcord.Interaction, name: str = nextcord.SlashOption(required=False, autocomplete=True)):
        if name:
            pal = pal_system.get_pal(name)
            if not pal:
                await interaction.response.send_message("❌ Custom Pal not found.", ephemeral=True)
                return
            
            # Format the JSON for readability
            try:
                formatted_json = json.dumps(json.loads(pal['json']), indent=2)
                if len(formatted_json) > 1000:
                    formatted_json = formatted_json[:997] + "..."
            except:
                formatted_json = pal['json']

            embed = nextcord.Embed(title=f"🐾 Custom Pal: {name}", description=pal.get('description', 'No description'), color=0x00FF88)
            embed.add_field(name="JSON Data", value=f"```json\n{formatted_json}\n```")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            names = pal_system.get_all_pal_names()
            if not names:
                await interaction.response.send_message("📭 The Pal Cage is empty.", ephemeral=True)
                return
            
            embed = nextcord.Embed(title="🐾 Pal Cage Database", color=0x00FF88)
            for n in names:
                info = pal_system.get_pal(n)
                embed.add_field(name=n.title(), value=info.get('description', 'No description'), inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)


    @pal_cage_group.subcommand(name="delete", description="Permanently delete a custom Pal")
    async def delete_pal(self, interaction: nextcord.Interaction, name: str):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return
        
        template_dir = config.get('pal_template_dir')
        if pal_system.delete_pal(name):
            file_deleted = pal_system.delete_pal_file(name, export_dir=template_dir)
            msg = f"🗑️ Deleted custom Pal **{name}** from the cage."
            if file_deleted:
                msg += f" (Also removed `{name.lower()}.json` from template folder)"
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.response.send_message("❌ Custom Pal not found.", ephemeral=True)

    @pal_cage_group.subcommand(name="import_folder", description="Import all .json files from a directory")
    async def import_pals_folder(
        self, 
        interaction: nextcord.Interaction,
        directory_path: str = nextcord.SlashOption(description="Full path to the folder (e.g. D:\\Pals). Defaults to data/pals", required=False)
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return
        
        if directory_path:
            pals_dir = directory_path
        else:
            # Try to use configured template dir, fallback to data/pals
            pals_dir = config.get('pal_template_dir')
            if not pals_dir:
                root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                pals_dir = os.path.join(root_dir, "data", "pals")
        
        if not os.path.exists(pals_dir):
            if not directory_path:
                os.makedirs(pals_dir)
                await interaction.response.send_message(f"📁 Created default folder `{pals_dir}`. Please put your Pal JSON files there and run this command again.", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ The directory `{pals_dir}` does not exist. Please check the path.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        template_dir = config.get('pal_template_dir')
        imported_count = 0
        errors = []
        files_found = 0
        
        try:
            for filename in os.listdir(pals_dir):
                if filename.endswith(".json"):
                    files_found += 1
                    path = os.path.join(pals_dir, filename)
                    name = filename[:-5].lower()
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Validate JSON
                            json.loads(content)
                            # Pass template_dir if we're importing from somewhere else into the template dir
                            pal_system.add_pal(name, content, f"Imported from {filename}", export_dir=template_dir)
                            imported_count += 1
                    except Exception as e:
                        errors.append(f"❌ Error importing `{filename}`: {str(e)}")
        except Exception as e:
            await interaction.followup.send(f"❌ Error reading directory: {str(e)}", ephemeral=True)
            return
        
        if files_found == 0:
            await interaction.followup.send(f"ℹ️ No `.json` files were found in `{pals_dir}`.", ephemeral=True)
            return

        report = f"✅ Success! Imported **{imported_count}** custom Pals from `{pals_dir}`."
        if errors:
            report += "\n\n**Errors:**\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                report += f"\n...and {len(errors)-5} more errors encountered."
        
        await interaction.followup.send(report, ephemeral=True)

    @pal_cage_group.subcommand(name="config_templates", description="Set the PalGuard PalTemplates directory path")
    async def set_template_dir(self, interaction: nextcord.Interaction, directory_path: str):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return
        
        if not os.path.exists(directory_path):
            await interaction.response.send_message(f"❌ Directory `{directory_path}` does not exist.", ephemeral=True)
            return
            
        config.set('pal_template_dir', directory_path)
        await interaction.response.send_message(f"✅ PalGuard template directory set to: `{directory_path}`. Future adds/imports will sync to this folder.", ephemeral=True)

    @pal_cage_group.subcommand(name="sync_all", description="Push all database Pals as JSON files to the template folder")
    async def sync_all_pals(self, interaction: nextcord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return
            
        template_dir = config.get('pal_template_dir')
        if not template_dir:
            await interaction.response.send_message("❌ Template directory not set. Use `/pal_cage config_templates` first.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        success_count = 0
        for name in pal_system.get_all_pal_names():
            pal = pal_system.get_pal(name)
            try:
                file_path = os.path.join(template_dir, f"{name}.json")
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(json.loads(pal['json']), f, indent=4)
                success_count += 1
            except:
                pass
                
        await interaction.followup.send(f"✅ Synced **{success_count}** Pals to `{template_dir}`.", ephemeral=True)

    @pal_cage_group.subcommand(name="give", description="Give a custom Pal to a player")
    async def give_custom_pal(
        self,
        interaction: nextcord.Interaction,
        player_name: str = nextcord.SlashOption(description="Player name", autocomplete=True),
        pal_name: str = nextcord.SlashOption(description="Custom Pal name", autocomplete=True)
    ):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
            return
            
        if not rcon_util.is_configured():
            await interaction.response.send_message("❌ RCON not configured.", ephemeral=True)
            return

        pal = pal_system.get_pal(pal_name)
        if not pal:
            await interaction.response.send_message(f"❌ Custom Pal '{pal_name}' not found.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # Get SteamID
        stats = await db.get_player_stats_by_name(player_name.strip())
        if not stats:
            # Fallback to direct steam ID if input is digits
            if player_name.isdigit() and len(player_name) >= 15:
                steam_id = f"steam_{player_name}"
            else:
                await interaction.followup.send(f"❌ Player '{player_name}' not found in database and is not a valid SteamID.")
                return
        else:
            steam_id = stats['steam_id']

        # Based on your research, embedded JSON is no longer supported via RCON.
        # We must use 'givepal_j' which expects a filename (without .json) 
        # that already exists in the server's PalTemplates folder.
        
        # The 'pal_name' used here is the key in our database, which matches 
        # the filename (without .json) from the import.
        cmd = f'givepal_j {steam_id} {pal_name}'
        
        print(f"📡 Sending Custom Pal Template command via RCON: {cmd}")
        
        server_info = rcon_util._get_server_info()
        resp = await rcon_util.rcon_command(server_info, cmd)
        
        # Success check for givepal_j usually looks for 'added', 'success', or 'sent'
        if resp and ("success" in resp.lower() or "spawned" in resp.lower() or "sent" in resp.lower() or "ok" in resp.lower() or "added" in resp.lower() or "given" in resp.lower()):
            await interaction.followup.send(f"✅ Successfully sent command to give template **{pal_name}** to `{player_name}`.")
        else:
            if resp == "" or resp is None:
                await interaction.followup.send(f"✅ Command `{cmd}` sent to server. (Check in-game)")
            else:
                await interaction.followup.send(f"❌ Server returned: {resp}\n*Note: Ensure the file `{pal_name}.json` exists in your server's PalTemplates folder.*")

    @give_custom_pal.on_autocomplete("player_name")
    async def give_pal_player_autocomplete(self, interaction: nextcord.Interaction, current: str):
        choices = await db.get_player_names_autocomplete(current)
        await interaction.response.send_autocomplete(choices)

    @view_pal.on_autocomplete("name")
    @delete_pal.on_autocomplete("name")
    @give_custom_pal.on_autocomplete("pal_name")
    async def pal_name_autocomplete(self, interaction: nextcord.Interaction, current: str):
        choices = [n for n in pal_system.get_all_pal_names() if current.lower() in n.lower()]
        await interaction.response.send_autocomplete(choices[:25])

def setup(bot):
    bot.add_cog(PalCageManagement(bot))
    print(f"✅ PalCageManagement Cog LOADED")
