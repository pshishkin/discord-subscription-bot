import discord

class BotDiscordClient(discord.Client):

    async def on_ready():
        guild = discord.utils.get(client.guilds, name=GUILD)

        assert(guild)

        print(
            f'{client.user} is connected to the following guild:\n'
            f'{guild.name}(id: {guild.id})'
        )
    
