import discord
import requests
import random
import string
import json
import os
import asyncio
import datetime
import sqlite3
import pytz
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from discord.ext import tasks, commands
from datetime import datetime, timedelta, time
from discord import app_commands  # , Activity, ActivityType
from discord.utils import get

intents = discord.Intents.all()
bot = discord.Client(command_prefix="!", HelpCommand=False, self_bot=False, intents=intents)
tree = app_commands.CommandTree(bot)

last_bot_message = {} #review
allowed_users = [884497527158755328] # Do0ks UserID


def is_allowed_user(ctx):
    return ctx.author.id in allowed_users
    
# Twitch API configuration
TWITCH_CLIENT_ID = ''
TWITCH_CLIENT_SECRET = ''
TWITCH_TOKEN_URL = ''
TWITCH_STREAMS_URL = ''
WORDPRESS_API_URL = ''

# Dictionary to keep track of live status
live_status = {}
twitch_usernames = []

# Function to get an OAuth token from Twitch
def get_twitch_token():
    payload = {
        'client_id': TWITCH_CLIENT_ID,
        'client_secret': TWITCH_CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }
    
    try:
        response = requests.post(TWITCH_TOKEN_URL, data=payload)
        response.raise_for_status()
        token = response.json()['access_token']
        return token
    except requests.exceptions.HTTPError as e:
        print(f"HTTPError while obtaining Twitch token: {e}")
        print(f"Response content: {response.text}")  # Log the response to help debug
    except Exception as e:
        print(f"An error occurred while obtaining Twitch token: {e}")
    return None

# Function to fetch Twitch usernames from the WordPress REST API
def fetch_twitch_usernames():
    url = WORDPRESS_API_URL
    retries = 3
    backoff_factor = 2

    for i in range(retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            usernames = response.json()
            return usernames
        except requests.exceptions.HTTPError as e:
            print(f"HTTPError: {e}")
            if e.response.status_code == 503 and i < retries - 1:
                sleep_time = backoff_factor ** i
                print(f"Retrying in {sleep_time} seconds...")
                sleep(sleep_time)
            else:
                print("Failed to fetch usernames after retries.")
                return []
        except Exception as e:
            print(f"An error occurred: {e}")
            return []
    return []

def get_live_streams(usernames):
    access_token = get_twitch_token()
    if not access_token:
        print("Failed to obtain Twitch OAuth token.")
        return []

    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {access_token}'
    }

    # Send a single bulk request for all usernames
    params = [('user_login', username) for username in usernames]  # Multiple user_login parameters
    try:
        response = requests.get(TWITCH_STREAMS_URL, headers=headers, params=params)
        response.raise_for_status()
        streams = response.json().get('data', [])
        return streams
    except requests.exceptions.HTTPError as e:
        print(f"HTTPError while checking live streams: {e}")
    except Exception as e:
        print(f"An error occurred while checking live streams: {e}")

    return []
    
def create_stream_embed(stream_info):
    embed = discord.Embed(
        title=f"{stream_info['user_name']} is live on Twitch!",
        url=f"https://twitch.tv/{stream_info['user_name']}",
        description=stream_info['title'],
        color=0x9146FF  # Twitch color
    )
    thumbnail_url = stream_info['thumbnail_url'].replace('{width}', '440').replace('{height}', '248')
    embed.set_thumbnail(url=thumbnail_url)
    embed.set_image(url=thumbnail_url)  # Set the stream preview image
    embed.add_field(name="Game", value=stream_info['game_name'], inline=True)
    embed.add_field(name="Viewers", value=str(stream_info['viewer_count']), inline=True)
    embed.set_footer(text="Click the title to watch the stream!", icon_url="https://static.twitchcdn.net/assets/favicon-32-e29e246c157142c94346.png")
    
    return embed
    
async def send_live_notifications(live_users, channel):
    for username, stream_info in live_users.items():
        embed = create_stream_embed(stream_info)
        await channel.send(embed=embed)
        print(f"Posted live status for {username}")
        live_status[username] = True  # Mark as posted
        
        # Sleep for 1 second to avoid hitting rate limits
        await asyncio.sleep(1)
    
@tree.command(guild=discord.Object(id=1268334937489014847), name="help", description="List All Available Commands And Prefixes")
async def help(ctx: commands.Context):  
    AdminChannel = ctx.guild.get_channel(1272054467205927017)
    # Define the required role names or role IDs in a list
    required_roles = ["Admin", "*"]  # Replace with the actual role names or role IDs

    # Check if the user has any of the required roles
    has_required_role = any(role.name in required_roles for role in ctx.user.roles)
    embed = discord.Embed(title="__ParleyBee__", description="_List of Available Commands_", color=0x00ff00)
    
    # User commands section
    user_commands = [
        ("", "▬▬▬▬▬▬▬𝐋𝐎𝐓𝐓𝐄𝐑𝐘 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒▬▬▬▬▬▬▬"),
        ("", f">>> **/lottery**\n`Play the Lottery Giveaway Game for a chance to win prizes.🎉`"),
        ("", "▬▬▬▬▬▬▬𝐈𝐃 𝐂𝐀𝐑𝐃 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒▬▬▬▬▬▬▬▬"),
        ("", f">>> **/info**\n`Pull a info card for yourself or any member, anytime, anywhere.`"),
        ("", f">>> **/url**\n`Personalize your info by adding a website.`"),
        ("", f">>> **/description**\n`Personalize your info by adding your personal description.`"),
        ("", f">>> **/upvote**\n`Increase a members reputation by one.`"),
        ("", f">>> **/downvote**\n`Decrease a members reputation by one.`"),
        ("", "▬▬▬▬▬▬▬𝐆𝐄𝐌 𝐁𝐀𝐆 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒▬▬▬▬▬▬▬"),
        ("", f">>> **/gembag**\n`Opens your Gem bag.`"),
    ]

    # Admin commands section (only if the user has the required roles)
    admin_commands = [
        ("", "▬▬▬▬▬▬▬𝐀𝐃𝐌𝐈𝐍 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒▬▬▬▬▬▬▬▬"),
        ("", f">>> **/warn**\n`Warn a member₁ with a reason₂`"),
        ("", f">>> **!warnings**\n`View the mentioned members warnings.`"),
        ("", f">>> **/ban**\n`Ban a member₁ with a reason₂`"),
        ("", f">>> **!ab**\n`Add a user ID₁ to a auto-ban list.`"),
        ("", f">>> **!bw**\n`Add a word or phrase₁ to a auto-ban list.`"),
        ("", f">>> **/purge**\n`Deletes the giving number₁ of messages.`"),
        ("", "▬▬▬▬▬▬▬𝐎𝐖𝐍𝐄𝐑 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒▬▬▬▬▬▬▬"),
        ("", f">>> **!dmu**\n`Send a DM to Unverified asking them to verify.`"),
        ("", f">>> **!ag**\n`Add gems₁ to a members₂ balance.`"),
        ("", f">>> **!sg**\n`Sub gems₁ and clusters₂ from a members₃ balance.`"),
        ("", f">>> **!pga**\n`Post Gems₁ in the Announcements`"),
        ("", f">>> **!uds**\n`Push the updated Gem Store.`"),
        ("", f">>> **!udr**\n`Push the updated Rules.`"),
    ]

    # Add user commands
    for name, description in user_commands:
        embed.add_field(name=name, value=description, inline=False)
    
    # Add admin commands if the user has the required roles
    if has_required_role and ctx.channel == AdminChannel:
        for name, description in admin_commands:
            embed.add_field(name=name, value=description, inline=False)

    await ctx.response.send_message(embed=embed)
    
    
@app_commands.checks.cooldown(1, 7200, key=lambda i: (i.guild_id, i.user.id))
@tree.command(guild=discord.Object(id=1268334937489014847), name="lottery", description="Win Sponsored Prizes!")
async def lottery(interaction: discord.Interaction):
    prize = '[Prize Info](https://discord.com/channels/1268334937489014847/1276674695843811378/1276675999811112990)' #prize info message link
    winners = '[Winners](https://discord.com/channels/1268334937489014847/1276674695843811378/1276676051816419348)' #current winners message link
    #if the command isn't ran in the correct channel;
    if interaction.channel.id != 1276674695843811378: 
        embed = discord.Embed(title="**Ops!!**", description=f"The lottery can only be played in <#1276674695843811378>!", color=0x00ff00)
        await interaction.response.send_message(embed=embed)
    else:
        LotteryFacts = open('/home/container/LotteryFacts.txt').read().splitlines()  # Local text file with facts location. 
        rand1 = random.randint(1, 300) #adjust min/max random numbers
        rand2 = random.randint(1, 300) #adjust min/max random numbers
        if rand1 != rand2:
            choice = random.choice(LotteryFacts)
            embed = discord.Embed(title="**ParleyBee Lottery!**", description=f"Good Luck, <@{interaction.user.id}>!")
            embed.set_image(url="https://i.imgur.com/RTGmwRz.png")
            embed.add_field(name="Status: You didn't win the lottery.", value=f"\nWinning Numbers: **{rand1}**\nYour Numbers: **{rand2}**", inline=False)
            embed.add_field(name="Random Lottery Fact:", value=choice, inline=False)
            embed.add_field(name="__**Would you like to play? Just type**__: `/lottery`", value=f"(*{prize} | {winners}*) <-- _Clickable Links_", inline=False)
            await interaction.response.send_message(embed=embed)
        elif rand1 == rand2:
            choice = random.choice(LotteryFacts)
            embed = discord.Embed(title="**ParleyBee Lottery!**", description=f"Good Luck, <@{interaction.user.id}>!")
            embed.set_image(url="https://i.imgur.com/RTGmwRz.png")
            embed.add_field(name="Status: You won the lottery! 🏆💰.", value=f"\nWinning Numbers: **{rand1}**\nYour Numbers: **{rand2}**", inline=False)
            embed.add_field(name="Random Lottery Fact:", value=choice, inline=False)
            embed.add_field(name="__**Would you like to play? Just type**__: `/lottery`", value=f"*({prize} | {winners})* <-- _Clickable Links_ ~ <@884497527158755328>", inline=False)
            await interaction.response.send_message(embed=embed)
@lottery.error
async def on_test_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        raw = str(timedelta(seconds=error.retry_after))
        stripms = len(raw)
        timeleft = raw[:stripms -7]
        await interaction.response.send_message(str(f"You can only play once every 2 hours. Try again in {timeleft}, <@{interaction.user.id}>!"), ephemeral=True)


@tasks.loop(hours=12)
async def meme():
    memechat = bot.get_channel(1276679255438397440)
    dir_path = "/home/container/memes"
    choice = random.choice(os.listdir(dir_path))
    link = os.path.join(dir_path, choice)
    await memechat.send(file=discord.File(link))
    

@bot.event
async def on_raw_reaction_add(payload):
    msgid = payload.message_id
    # Seller/Buyer Status
    if msgid == 1276887642834735198:
        gld = bot.get_guild(1268334937489014847)
        if payload.emoji.name == 'twitch':
            role = discord.utils.get(gld.roles, name="Twitch")
            await payload.member.add_roles(role)
        elif payload.emoji.name == 'kick':
            role = discord.utils.get(gld.roles, name="Kick")
            await payload.member.add_roles(role)
        elif payload.emoji.name == 'youtube':
            role = discord.utils.get(gld.roles, name="YouTube")
            await payload.member.add_roles(role)
        elif payload.emoji.name == 'tiktok':
            role = discord.utils.get(gld.roles, name="TikTok")
            await payload.member.add_roles(role)
        elif payload.emoji.name == 'trovo':
            role = discord.utils.get(gld.roles, name="Trovo")
            await payload.member.add_roles(role)
        elif payload.emoji.name == 'facebook':
            role = discord.utils.get(gld.roles, name="Facebook")
            await payload.member.add_roles(role)
        elif payload.emoji.name == 'discord':
            role = discord.utils.get(gld.roles, name="Discord")
            await payload.member.add_roles(role)
        elif payload.emoji.name == 'instagram':
            role = discord.utils.get(gld.roles, name="Instagram")
            await payload.member.add_roles(role)
        elif payload.emoji.name == 'Bee5':
            role = discord.utils.get(gld.roles, name="Giveaways")
            await payload.member.add_roles(role)
    # DMs
    if msgid == 1276890266988580864:
        gld = bot.get_guild(1268334937489014847)
        if payload.emoji.name == 'DMYes':
            role = discord.utils.get(gld.roles, name="DMs")
            await payload.member.add_roles(role)
        elif payload.emoji.name == 'DMNo':
            role = discord.utils.get(gld.roles, name="No-DMs")
            await payload.member.add_roles(role)
    # Timezone
    if msgid == 1276892389147017308:
        gld = bot.get_guild(1268334937489014847)
        if payload.emoji.name == 'EST':
            role = discord.utils.get(gld.roles, name="EST")
            await payload.member.add_roles(role)
        elif payload.emoji.name == 'CST':
            role = discord.utils.get(gld.roles, name="CST")
            await payload.member.add_roles(role)
        elif payload.emoji.name == 'MST':
            role = discord.utils.get(gld.roles, name="MST")
            await payload.member.add_roles(role)
        elif payload.emoji.name == 'PST':
            role = discord.utils.get(gld.roles, name="PST")
            await payload.member.add_roles(role)
        elif payload.emoji.name == 'Other':
            role = discord.utils.get(gld.roles, name="Other Time Zone")
            await payload.member.add_roles(role)
    # Pronouns
    if msgid == 1276894578020057129:
        gld = bot.get_guild(1268334937489014847)
        if payload.emoji.name == 'He_Him':
            role = discord.utils.get(gld.roles, name="He/Him")
            await payload.member.add_roles(role)
        elif payload.emoji.name == 'She_Her':
            role = discord.utils.get(gld.roles, name="She/Her")
            await payload.member.add_roles(role)
        elif payload.emoji.name == 'They_Them':
            role = discord.utils.get(gld.roles, name="They/Them")
            await payload.member.add_roles(role)
        elif payload.emoji.name == 'Ask':
            role = discord.utils.get(gld.roles, name="Ask My Pronoun")
            await payload.member.add_roles(role)
            
    # Giveaways
    if msgid == 1297007092246249526:
        gld = bot.get_guild(1268334937489014847)
        if payload.emoji.name == 'Bee5':
            role = discord.utils.get(gld.roles, name="Giveaways")
            await payload.member.add_roles(role)
        
        
    # Verification
    if msgid == 1280192663978512447:
        guild = bot.get_guild(1268334937489014847)
        if payload.emoji.name == '✅':
            user = bot.get_user(payload.user_id)
            member = guild.get_member(payload.user_id)
            role = discord.utils.get(guild.roles, name="Bzzz...")
            removerole = discord.utils.get(guild.roles, name="Unverified") 
            
            await payload.member.add_roles(role)
            await member.remove_roles(removerole)           
            
            channel = bot.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            await message.remove_reaction('✅', user)
            
            try:
                embed = discord.Embed(title="**Verification Successful!**", description=f"You have confirmed your understanding and agreement with the ParleyBee [Rules](https://discord.com/channels/1268334937489014847/1268344260831481988/1271925513417523332) and [Privacy Policy](https://parleybee.com/privacy-policy/).", color=0x586edd)
                embed.set_image(url="https://i.imgur.com/O3rYw4O.png")
                await user.send(embed=embed)
                bot.db = sqlite3.connect('bee.db')
                cursor = bot.db.cursor()
                cursor.execute('UPDATE BeeData SET member_unverify = ? WHERE member_id = ?', (0, member.id))
                bot.db.commit()           
                bot.db.close()
            except discord.errors.Forbidden:
                print(f"Couldn't send a direct message to {user.name}. They might have DMs closed.")
                
            log_channel = bot.get_channel(1272010238639345756)  # Assuming this is a logging channel
            await log_channel.send(f"<@{payload.member.id}> Just Verified.")            


@bot.event
async def on_raw_reaction_remove(payload):
    msgid = payload.message_id
    # Programming Status
    if msgid == 1276887642834735198:
        gld = bot.get_guild(1268334937489014847)
        member = gld.get_member(payload.user_id)
        if payload.emoji.name == 'twitch':
            role = discord.utils.get(gld.roles, name="Twitch")
            await member.remove_roles(role)
        elif payload.emoji.name == 'kick':
            role = discord.utils.get(gld.roles, name="Kick")
            await member.remove_roles(role)
        elif payload.emoji.name == 'youtube':
            role = discord.utils.get(gld.roles, name="YouTube")
            await member.remove_roles(role)
        elif payload.emoji.name == 'tiktok':
            role = discord.utils.get(gld.roles, name="TikTok")
            await member.remove_roles(role)
        elif payload.emoji.name == 'trovo':
            role = discord.utils.get(gld.roles, name="Trovo")
            await member.remove_roles(role)
        elif payload.emoji.name == 'facebook':
            role = discord.utils.get(gld.roles, name="Facebook")
            await member.remove_roles(role)
        elif payload.emoji.name == 'discord':
            role = discord.utils.get(gld.roles, name="Discord")
            await member.remove_roles(role)
        elif payload.emoji.name == 'instagram':
            role = discord.utils.get(gld.roles, name="Instagram")
            await member.remove_roles(role)
    # DMs
    if msgid == 1276890266988580864:
        gld = bot.get_guild(1268334937489014847)
        member = gld.get_member(payload.user_id)
        if payload.emoji.name == 'DMYes':
            role = discord.utils.get(gld.roles, name="DMs")
            await member.remove_roles(role)
        elif payload.emoji.name == 'DMNo':
            role = discord.utils.get(gld.roles, name="No-DMs")
            await member.remove_roles(role)
    # Timezone
    if msgid == 1276892389147017308:
        gld = bot.get_guild(1268334937489014847)
        member = gld.get_member(payload.user_id)
        if payload.emoji.name == 'EST':
            role = discord.utils.get(gld.roles, name="EST")
            await member.remove_roles(role)
        elif payload.emoji.name == 'CST':
            role = discord.utils.get(gld.roles, name="CST")
            await member.remove_roles(role)
        elif payload.emoji.name == 'MST':
            role = discord.utils.get(gld.roles, name="MST")
            await member.remove_roles(role)
        elif payload.emoji.name == 'PST':
            role = discord.utils.get(gld.roles, name="PST")
            await member.remove_roles(role)
        elif payload.emoji.name == 'Other':
            role = discord.utils.get(gld.roles, name="Other Time Zone")
            await member.remove_roles(role)
    # Pronouns
    if msgid == 1276894578020057129:
        gld = bot.get_guild(1268334937489014847)
        member = gld.get_member(payload.user_id)
        if payload.emoji.name == 'He_Him':
            role = discord.utils.get(gld.roles, name="He/Him")
            await member.remove_roles(role)
        elif payload.emoji.name == 'She_Her':
            role = discord.utils.get(gld.roles, name="She/Her")
            await member.remove_roles(role)
        elif payload.emoji.name == 'They_Them':
            role = discord.utils.get(gld.roles, name="They/Them")
            await member.remove_roles(role)
        elif payload.emoji.name == 'Ask':
            role = discord.utils.get(gld.roles, name="Ask My Pronoun")
            await member.remove_roles(role)
            
    #Giveaways        
    if msgid == 1297007092246249526:
        gld = bot.get_guild(1268334937489014847)
        member = gld.get_member(payload.user_id)
        if payload.emoji.name == 'Bee5':
            role = discord.utils.get(gld.roles, name="Giveaways")
            await member.remove_roles(role)


@bot.event
async def on_member_join(member):
    await asyncio.sleep(1)
    guild_id = 1268334937489014847
    voice_channel_id = 1276725755317059614
    unverified = member.guild.get_role(1276680358078976061)
    
    invites_before = bot.invites
    invites_after = await member.guild.invites()
    
    emojis = [
        '<:Bee1:1283215352586829925>',
        '<:Bee2:1283215354222612520>',
        '<:Bee3:1283215355258339428>',
        '<:Bee4:1283215356336410646>',
        '<:Bee5:1283215357460484176>',
        '<:Bee6:1283215358882222154>',
        '<:Bee7:1283215360241438791>',
        '<:Bee8:1283215361612972105>',
        '<:Bee9:1283215394777333850>'
    ]
    
    random_emoji = random.choice(emojis)

    # Compare invites before and after to find the one that was used
    for invite in invites_before:
        updated_invite = next((inv for inv in invites_after if inv.code == invite.code), None)
        if updated_invite and updated_invite.uses > invite.uses:
            await update_invite_data(str(member.id), str(updated_invite.inviter.id))
            channel = bot.get_channel(1272012055464906753)
            await channel.send(f"{member.mention} was invited by {updated_invite.inviter.mention}")
            break

    bot.invites = invites_after
    

    if unverified is not None:
        await member.add_roles(unverified)
    
    bot.db = sqlite3.connect('bee.db')
    cursor = bot.db.cursor()
    iconn = sqlite3.connect('invite_tracker.db')
    icursor = iconn.cursor()
    
    with open('/home/container/members/autoban/pending.txt', 'r') as file:
        auto_ban_list = file.read().splitlines()

    if str(member.id) in auto_ban_list:
        # Message the User.
        embed = discord.Embed(
            title=f"**Hi, ParleyBee Here!**",
            description=f"**Error Joining ParleyBee!**\nWe regret to inform you that you have been automatically banned from ParleyBee Discord server due to observed violations of community rules/TOS and/or Discord's Terms of Service and Community Guidelines. If you believe this ban is in error and would like to appeal it, please follow these steps:\n\nSend an email to __**support@parleybee.com**__. In the subject line, please use the following format:\n\n**Discord Ban Appeal - [Your Discord Username]**.\nIn the body of the email, provide a brief explanation of why you believe the ban should be lifted. Be concise and respectful in your message. Our team will review your appeal as soon as possible. Please allow some time for us to investigate and respond to your request.\n\nWe take all Communities and Discords rules seriously and appreciate your understanding and cooperation in maintaining a positive and respectful environment for all members.\n\nBest regards,\nParleyBee Support Team.",
            color=0xFF0000,  # RED color
        )
        embed.set_image(url="https://i.imgur.com/O3rYw4O.png")
        await member.send(embed=embed)

        # Ban the user
        await member.ban(reason="Auto-banned on join")

        # Remove the user ID from the auto-ban list
        auto_ban_list.remove(str(member.id))

        # Write the updated auto-ban list back to the file
        with open('/home/container/members/autoban/pending.txt', 'w') as file:
            file.write('\n'.join(auto_ban_list))

        # Send a message to the specified channel
        channel = bot.get_channel(1272010238639345756)
        await channel.send(f"{member.mention} was auto-banned.")
        cursor.execute("DELETE FROM BeeData WHERE member_id = ?", (member.id,))
    else:
        icursor.execute('SELECT COUNT(*) FROM invites WHERE inviter_id = ?', (str(member.id),))
        total_invites = icursor.fetchone()[0]

        cursor.execute("SELECT * FROM BeeData WHERE member_id=?", (member.id,))
        existing_member = cursor.fetchone()

        if existing_member is None:
            # If the member doesn't exist, add them to the BeeData table
            cursor.execute("INSERT INTO BeeData (member_id, username, member_message_count, member_vote_count, member_warning, member_ad_count, member_url, member_description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (member.id, member.name, 0, 0, 0, 0, 'Use `/url` to update your Website URL.', 'Use `/description` to add your own description.'))
            bot.db.commit()
            channel = bot.get_channel(1272019629102989413)
            welcome = f"Welcome to ParleyBee, {member.mention}!\n"
        
            # Fetch member data from the database
            cursor.execute("SELECT member_message_count, member_vote_count, member_warning, member_ad_count, member_url, member_description FROM BeeData WHERE member_id=?", (member.id,))
            member_data = cursor.fetchone()
            
            if member_data is not None:
                message_count, vote_count, warning_count, ad_count, website_url, description = member_data
                embed = discord.Embed(
                    title="ParleyBee Info Card",
                    description=f"Please Review:\n <#1268344260831481988>, <#1269494120972423259>, <#1276679967605915678>",
                    color=0x00ff00)
                embed.set_thumbnail(url=member.avatar)
                embed.add_field(name="Username:", value=member.mention, inline=True)
                embed.add_field(name="Messages:", value=message_count, inline=True)
                embed.add_field(name="Promos:", value=ad_count, inline=True)
                embed.add_field(name="Invites:", value=str(total_invites), inline=True)
                embed.add_field(name="Reputation:", value=vote_count, inline=True)
                embed.add_field(name="Warnings:", value=warning_count, inline=True)
                embed.add_field(name="Website URL:", value=f"_{website_url}_", inline=False)
                embed.add_field(name="Description:", value=f"_{description}_\n\n**Invited By:** {updated_invite.inviter.mention}\n\n", inline=False)
            
                account_created = member.created_at  # This is an offset-aware datetime
                joined_server = member.joined_at  # This is an offset-aware datetime
                today = datetime.now(pytz.utc)  # Make sure it's offset-aware using UTC timezone

                account_age = today - account_created
                joined_age = today - joined_server

                months_account = account_age.days // 30
                days_account = account_age.days % 30

                months_joined = joined_age.days // 30
                days_joined = joined_age.days % 30

                account_age_str = f"Account created: {months_account} months, {days_account} days ago"
                joined_age_str = f"Joined Server: {months_joined} months, {days_joined} days ago"

                if account_age.days < 1:
                    account_age_str = "Account created: Today"
                elif months_account == 0:
                    account_age_str = f"Account created: {days_account} days ago"

                if joined_age.days < 1:
                    joined_age_str = "Joined Server: Today"
                elif months_joined == 0:
                    joined_age_str = f"Joined Server: {days_joined} days ago"
                    
                footer_text = f"{account_age_str}\n{joined_age_str}"
                embed.set_footer(text=footer_text)

                msg = await channel.send(f"{welcome}\n", embed=embed)
                await msg.add_reaction(random_emoji)
        else:
            # If the member's data exists, fetch their stats from the database         
            message_count, vote_count, warning_count, ad_count, website_url, description = existing_member[2:8]
            
            welcome = f"Welcome back to ParleyBee, {member.mention}!\n"
            
            channel = bot.get_channel(1272019629102989413)
            
            embed = discord.Embed(
                title="ParleyBee Info Card",
                description=f"Please Review:\n <#1268344260831481988>, <#1269494120972423259>, <#1276679967605915678>",
                color=0x00ff00)
            embed.set_thumbnail(url=member.avatar)
            embed.add_field(name="Username:", value=member.mention, inline=True)
            embed.add_field(name="Messages:", value=message_count, inline=True)
            embed.add_field(name="Promos:", value=ad_count, inline=True)
            embed.add_field(name="Invites:", value=str(total_invites), inline=True)
            embed.add_field(name="Reputation:", value=vote_count, inline=True)
            embed.add_field(name="Warnings:", value=warning_count, inline=True)
            embed.add_field(name="Website URL:", value=f"_{website_url}_", inline=False)
            embed.add_field(name="Description:", value=f"_{description}_\n\n**Invited By:** {updated_invite.inviter.mention}\n\n", inline=False)
            
            account_created = member.created_at  # This is an offset-aware datetime
            joined_server = member.joined_at  # This is an offset-aware datetime
            today = datetime.now(pytz.utc)  # Make sure it's offset-aware using UTC timezone

            account_age = today - account_created
            joined_age = today - joined_server

            months_account = account_age.days // 30
            days_account = account_age.days % 30

            months_joined = joined_age.days // 30
            days_joined = joined_age.days % 30

            account_age_str = f"Account created: {months_account} months, {days_account} days ago"
            joined_age_str = f"Rejoined Server: {months_joined} months, {days_joined} days ago"

            if account_age.days < 1:
                account_age_str = "Account created: Today"
            elif months_account == 0:
                account_age_str = f"Account created: {days_account} days ago"

            if joined_age.days < 1:
                joined_age_str = "Rejoined Server: Today"
            elif months_joined == 0:
                joined_age_str = f"Rejoined Server: {days_joined} days ago"
                
            footer_text = f"{account_age_str}\n{joined_age_str}"
            embed.set_footer(text=footer_text)

            msg = await channel.send(f"{welcome}\n", embed=embed)
            await msg.add_reaction(random_emoji)
    
    iconn.close()
    bot.db.close()
    
    guild = bot.get_guild(guild_id)
    voice_channel = guild.get_channel(voice_channel_id)

    if guild and voice_channel:
        member_count = guild.member_count
        await voice_channel.edit(name=f'Members: {member_count}')
    

@bot.event
async def on_member_remove(member):
    guild_id = 1268334937489014847
    voice_channel_id = 1276725755317059614
    eastern_timezone = pytz.timezone('US/Eastern')
    current_time_edt = datetime.now(eastern_timezone)
    seven_days_ago = current_time_edt - timedelta(days=7)
    
    iconn = sqlite3.connect('invite_tracker.db')
    icursor = iconn.cursor()
    icursor.execute('SELECT inviter_id FROM invites WHERE user_id = ?', (str(member.id),))
    result = icursor.fetchone()
    channel = bot.get_channel(1272012055464906753)
    if result:
        inviter_id = result[0]
        inviter = await bot.fetch_user(inviter_id)
        await channel.send(f"{member.mention} left the server, they were invited by {inviter.mention}")
    else:
        await channel.send(f"{member.mention} left the server, inviter unknown")
    
    icursor.execute('SELECT * FROM invites WHERE user_id = ?', (str(member.id),))
    result = icursor.fetchone()

    if result:
        # Member exists in the database, delete their entry
        icursor.execute('DELETE FROM invites WHERE user_id = ?', (str(member.id),))
        iconn.commit()
    
    
    db = sqlite3.connect('bee.db')
    cursor = db.cursor()
    
    try:
        was_banned = False
        async for entry in member.guild.audit_logs(action=discord.AuditLogAction.ban, limit=1):
            if entry.target.id == member.id:
                was_banned = True
                break
    
        cursor.execute("SELECT member_warning, member_vote_count FROM BeeData WHERE member_id = ?", (member.id,))
        row = cursor.fetchone()
        
        if row and all(value == 0 for value in row):
            cursor.execute("DELETE FROM BeeData WHERE member_id = ?", (member.id,))
            db.commit()
        
        if not was_banned:
            for channel in member.guild.text_channels:
                try:
                    messages_to_delete = []
                    async for message in channel.history(limit=100):
                        if message.author == member and message.created_at > seven_days_ago:
                            messages_to_delete.append(message)
                    
                    if messages_to_delete:
                        await channel.delete_messages(messages_to_delete)
                except Exception as e:
                    print(f"Error while deleting messages in {channel.name}: {e}")

    except Exception as e:
        print(f"An error occurred: {e}")        
        
        
    finally:
        cursor.close()  # Close the cursor
        db.close()  # Close the database connection
        icursor.close() # Close the cursor
        iconn.close() # Close the invite connection
        
    guild = bot.get_guild(guild_id)
    voice_channel = guild.get_channel(voice_channel_id)

    if guild and voice_channel:
        member_count = guild.member_count
        await voice_channel.edit(name=f'Members: {member_count}')
        
        
        

@bot.event
async def on_member_update(before, after):
    # Fetch the "Nitro Booster" role (replace ROLE_ID with your Nitro Booster role's ID)
    nitro_booster_role = after.guild.get_role(1272015580488007771)  # Replace ROLE_ID with the actual role ID for Nitro Boosters
    channel = bot.get_channel(1272019769679155233)  # Replace with your channel ID

    # Check if the "Nitro Booster" role was added
    if nitro_booster_role not in before.roles and nitro_booster_role in after.roles:
        embed = discord.Embed(
            title="🚀 Thank You for Boosting the Server!",
            description=f"Wow, {after.mention} is absolutely amazing for boosting the server! \n✨❗**I'll process your Pro Membership now!**❗✨",
            color=0xffbf00
        )
        await channel.send(embed=embed)

 
'''
-----------------------------ADMIN COMMANDS-----------------------------
''' 

async def cmd_bw(message, has_required_role):
    phrase = message.content[len('!bw '):].strip()
    with open("/home/container/members/autoban/wordlist.txt", "a") as f:
        f.write(f"{phrase}\n")
    await message.channel.send(f"'{phrase}' has been added to the banned words list.")
    return


async def cmd_ab(message, has_required_role):
    args = message.content.split(' ')
    if len(args) >= 2:
        user_id = args[1]
        
        # Check if the user ID is already in the file
        with open('/home/container/members/autoban/pending.txt', 'r') as file:
            existing_ids = file.read().splitlines()
        
        if user_id in existing_ids:
            await message.channel.send(f'User ID {user_id} is already added to the auto-ban list.')
        else:
            # Save the user ID to the file
            with open('/home/container/members/autoban/pending.txt', 'a') as file:
                file.write(user_id + '\n')
            
            await message.channel.send(f'User ID {user_id} has been added to the auto-ban list.') 
                

async def cmd_warnings(message, has_required_role):
    if len(message.mentions) == 1:
        mentioned_user = message.mentions[0]
        users_id = mentioned_user.id
        
        # Construct the path to the warning file
        warning_file_path = f"/home/container/members/warnings/{users_id}.txt"

        try:
            # Read the content of the warning file
            with open(warning_file_path, 'r') as file:
                warnings = file.read().splitlines()
            
            # Get the most recent 10 warnings (or less if there are fewer than 10)
            recent_warnings = warnings[-10:]

            # Create an embed to display the warnings
            embed = discord.Embed(title=f"Warnings for {mentioned_user.display_name}", color=discord.Color.red())
            
            for idx, warning in enumerate(recent_warnings, start=1):
                embed.add_field(name=f"Warning {idx}:", value=warning, inline=False)
            
            await message.channel.send(embed=embed)
        
        except FileNotFoundError:
            await message.channel.send("No warnings found for this user.")
    
    else:
        await message.channel.send("Please mention a user to check their warnings.")
            
            
'''
-----------------------------OWNER COMMANDS-----------------------------
'''                          


async def cmd_dmu(message):
    channel = bot.get_channel(1272054467205927017)
    tut = '[Here](<https://discord.com/channels/1268334937489014847/1276698226703208520/1276698259934679073>)'
    invite = '[Click Here To Rejoin](<https://discord.gg/EcXMx7JQPB>)'
    role_name = "Unverified" 
    role = discord.utils.get(channel.guild.roles, name=role_name)
    
    if not role:
        await channel.send(f"Role '{role_name}' not found.")
        return
        
    members_with_role = role.members

    # Connect to SQLite database
    try:
        with sqlite3.connect('bee.db') as db:
            cursor = db.cursor()
            
            for member in members_with_role:
                try:
                    # Retry mechanism for locked database
                    retries = 3
                    while retries > 0:
                        try:
                            cursor.execute('SELECT member_unverify FROM BeeData WHERE member_id = ?', (member.id,))
                            row = cursor.fetchone()
                            
                            if row is None:
                                cursor.execute('INSERT INTO BeeData (member_id, member_unverify) VALUES (?, 1)', (member.id,))
                                count = 1
                            else:
                                count = row[0]
                            
                            if count < 3:
                                cursor.execute('UPDATE BeeData SET member_unverify = ? WHERE member_id = ?', (count + 1, member.id))
                                db.commit()
                                
                                embed = discord.Embed(
                                    title=f"**Hi, ParleyBee Here!**",
                                    description=f"We've noticed that you've recently joined ParleyBee Discord server, which is fantastic news! However, it seems that you haven't completed the verification process yet. Whenever it's convenient for you, we kindly request that you take a moment to navigate through the straightforward verification process {tut}.\n\nYour presence in the ParleyBee Discord server is greatly appreciated, and we are eager to welcome you fully into our community. We look forward to your successful verification and hope to see you actively engaging with us soon!\n\nThank you for choosing ParleyBee!",
                                    color=0x00ff00,  # Green color
                                )
                                embed.set_image(url="https://i.imgur.com/O3rYw4O.png")
                                embed.set_footer(text=f"Attempt: {count + 1}/3")
                                await member.send(embed=embed)
                            else:
                                embed = discord.Embed(
                                    title=f"**Hi, ParleyBee Here!**",
                                    description=f"**We Are Sorry To See You Go!**\nWe noticed that you haven't verified your account and have been inactive in ParleyBee Discord server for some time. Verification is essential to ensure the safety and integrity of our community.\n\nDon't worry, you are always welcome back! If you would like to try again, please {invite}.\n\nIf you have any questions or need assistance, don't hesitate to reach out to our staff. We are always happy to help!\n\nBest regards,\nParleyBee Support Team.\nsupport@parleybee.com",
                                    color=0xFF0000,  # RED color
                                )
                                embed.set_image(url="https://i.imgur.com/O3rYw4O.png")
                                await member.send(embed=embed)
                                await member.kick(reason='Inactive Unverified User')
                                cursor.execute("DELETE FROM BeeData WHERE member_id = ?", (member.id,))
                                db.commit()
                            break
                        except sqlite3.OperationalError as e:
                            if 'database is locked' in str(e):
                                await asyncio.sleep(1)  # Wait and retry
                                retries -= 1
                            else:
                                raise
                except discord.Forbidden:
                    await channel.send(f"Could not send a message to {member.mention}.")
                except Exception as e:
                    print(f"Error processing {member.mention}: {e}")
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

        
async def cmd_udr(message):
    channel = message.guild.get_channel(1280191581697216622)

    #ParleyBee Rules
    nmrheader = f"**ParleyBee Rules**"
    embed = discord.Embed(
        title="",
        description=f"__**Rule1**__:\n***Every Member Should Be Respected.***\nAt the heart of our community, respect is paramount. Every individual, regardless of religious belief, ethnicity, or views, deserves respect. Acts of racism, sexism, or discrimination against the LGBTQIA+ community are inexcusable. Consider this your sole warning.\n\n"
                    f"__**Rule2**__:\n***Abusive Language is Unacceptable.***\nIn any language, please choose words that respect and uplift fellow members, avoiding those that might cause harm or offense.\n\n"
                    f"__**Rule3**__:\n***Refrain From Spamming.***\nBe it messages, pictures or emojis, send everything in moderation and do not bombard the chat with unnecessary things that will make members miss out on important messages. This includes Mass Mentions. Using `@everyone` or `@here` will result in an **automatic** ban by Bee Bot.\n\n"
                    f"__**Rule4**__:\n***Sexual Content is Prohibited.***\nSexual content is strictly prohibited. We have a zero-tolerance policy on this matter to ensure the comfort and enjoyment of all members in this server.\n\n"
                    f"__**Rule5**__:\n***Self Promotion is Prohibited.***\nPlease refrain from self-promotion outside of allocated areas. All promotional content should be confined to designated channels. Be advised: warnings will be issued publicly in main chats for violations.\n\n"
                    f"__**Rule6**__:\n***Membes Wishes.***\nBefore sending mass DMs promoting your services or products, please pay attention to your fellow members wishes. If you DM ads to someone with the role `@No DMs`, that member can wish for your removal, and staff will support it.\n\n",
        color=0x586edd  # Use a color of your choice here
    )
    
    if channel:
        await channel.send(f"{nmrheader}\n", embed=embed)
        await asyncio.sleep(1)
    else:
        # Optional: Send an error message or log it if the channel is not found
        print(f"Channel not found in guild {message.guild.name}")     

    #Verification
    vheader = f"**Acceptance Into The Server**"
    embed = discord.Embed(
        title="",
        description=f"By reacting to this message, you gain access to the server. Your reaction signifies that you have read and understood the server's rules and ParleyBee [Privacy Policy](https://parleybee.com/privacy-policy/). Reacting is a commitment to abide by these terms. If you agree, please react to this message.",
        color=0x586edd  # Use a color of your choice here
    )
    embed.set_image(url="https://i.imgur.com/O3rYw4O.png")
    
    if channel:
        sent_message = await channel.send(f"{vheader}\n", embed=embed)
        await sent_message.add_reaction('✅')
    else:
        # Optional: Send an error message or log it if the channel is not found
        print(f"Channel not found in guild {message.guild.name}")

    

'''
-----------------------------COMMAND TABLE-----------------------------
''' 

ADMINCOMMANDS = {
    "!bw": cmd_bw,
    "!ab": cmd_ab,
    "!warnings": cmd_warnings,
}

OWNERCOMMANDS = {
    "!dmu": cmd_dmu,
    "!udr": cmd_udr,
}

'''
------------------------------------------------------------------------
'''

def load_banned_phrases():
    with open("/home/container/members/autoban/wordlist.txt", "r") as f:
        return [line.strip() for line in f.readlines()]
        
banned_users_cooldown = {}
        
def remove_cooldown(user_phrase_key):
    banned_users_cooldown.pop(user_phrase_key, None)

@bot.event
async def on_message(message):
    bot.db = sqlite3.connect('bee.db')
    cursor = bot.db.cursor()
    global banned_users_cooldown
    
    channels_to_skip = {1268341191779549315, 1272002088116817941, 1272004162619707392, 1272011667688919071, 1272011703932026910, 1272010238639345756, 1272009729110966337, 1272009761868615784, 1272009977330012200, 1272010530726609028, 1272011856617406557, 1272012055464906753, 1272012243529367653, 1272012650376728607, 1281661279886381178}
    
    if message.author == bot.user or message.channel.id in channels_to_skip:
        return
        
    required_roles = {"Admin", "Worker Bees", "*"}
    has_required_role = isinstance(message.author, discord.Member) and \
                        any(role.name in required_roles for role in message.author.roles)
        
    if not has_required_role:
        matched_phrase = next((phrase for phrase in load_banned_phrases() if phrase in message.content.lower()), None)
        
        user_phrase_key = f"{message.author.id}-{matched_phrase}"

        if matched_phrase and user_phrase_key not in banned_users_cooldown:
            case_number = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            
            cembed = discord.Embed(
                title="__Member Banned__",
                color=0xFF0800,  # You can set the color to your preference
            )
            cembed.add_field(name="Member: ", value=message.author.mention, inline=False)  # Use message.author.mention here
            cembed.add_field(name="Reason: ", value=f"Using a forbidden phrase: `{matched_phrase}`", inline=False)  # Use matched_phrase here
            cembed.set_thumbnail(url="https://i.imgur.com/M0RjN63.png")
            cembed.set_footer(text=f"Case Number: {case_number}")
            
            try:
                await message.guild.get_channel(1276703619629977651).send(f"<@{message.author.id}> - Case Number: {case_number}\n", embed=cembed)
            except discord.Forbidden:
                pass
            
            
            embed = discord.Embed(
                title=f"**Hi, ParleyBee Here!**",
                description=(
                    f"**You've been banned from ParleyBee Discord Server!**\n"
                    f"We regret to inform you that you have been automatically banned from ParleyBee Discord server for the use of a forbidden phrase.\n\n"
                    f"**__Phrase__:** {matched_phrase}\n"
                    f"**__Case Number__:** {case_number}\n\n"
                    f"If you believe this ban is in error and would like to appeal it, please follow these steps:\n\n"
                    f"Send an email to __**support@parleybee.com**__. In the subject line, please use the following format:\n\n"
                    f"**Discord Ban Appeal - {message.author} - {case_number}**.\n\n"
                    f"In the body of the email, provide a brief explanation of why you believe the ban should be lifted. "
                    f"Be concise and respectful in your message. Our team will review your appeal as soon as possible. "
                    f"Please allow some time for us to investigate and respond to your request.\n\n"
                    f"We take all Communities and Discords rules seriously and appreciate your understanding and cooperation "
                    f"in maintaining a positive and respectful environment for all members.\n\n"
                    f"Best regards,\nParleyBee Support Team."
                ),
                color=0xFF0000,  # RED color
            )
            embed.set_image(url="https://i.imgur.com/O3rYw4O.png")
            try:
                await message.author.send(embed=embed)
            except discord.Forbidden:
                # This will occur if the user has blocked the bot or has DMs disabled for this server.
                pass
                
            try:
                await message.author.ban(reason=f"Used forbidden phrase: {matched_phrase}.", delete_message_days=7)
                banned_users_cooldown[user_phrase_key] = True
                bot.loop.call_later(10, remove_cooldown, user_phrase_key) 
                
            except discord.Forbidden:
                print("The bot doesn't have the required permissions to ban users.")

            try:
                notification_channel = message.guild.get_channel(1272010238639345756)
                if notification_channel:
                    await notification_channel.send(f"{message.author.mention} has been auto-banned for using the forbidden phrase: `{matched_phrase}`.")
                else:
                    print(f"Notification channel not found in guild.")
            except discord.Forbidden:
                print("The bot doesn't have the required permissions to send messages in the notification channel.")
      

    try:
        cursor.execute("SELECT * FROM BeeData WHERE member_id=?", (message.author.id,))
        existing_user = cursor.fetchone()

        if existing_user is None:
            print(f"User with ID {message.author.id} is not in the database.")
        else:
            cursor.execute("UPDATE BeeData SET member_message_count = member_message_count + 1 WHERE member_id=?", (message.author.id,))
            bot.db.commit()
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        
        
    ad_channels = [1271919100465123328, 1271919249585340579, 1271919425267699763, 1271921573347070004, 1271919441570959562]
    if message.channel.id in ad_channels:
        if message.author.bot:
            return 

        try:
            cursor.execute("SELECT * FROM BeeData WHERE member_id=?", (message.author.id,))
            existing_user = cursor.fetchone()

            if existing_user is None:
                print(f"User with ID {message.author.id} is not in the database.")
            else:
                cursor.execute("UPDATE BeeData SET member_ad_count = member_ad_count + 1 WHERE member_id=?", (message.author.id,))
                bot.db.commit()
            
        except sqlite3.Error as e:
            print(f"SQLite error: {e}")

    if message.author.id in allowed_users:               
        if message.channel.id == 1272054467205927017:
            for cmd, func in OWNERCOMMANDS.items():
                if message.content.startswith(cmd):
                    await func(message)
                    return
          
    for cmd, func in ADMINCOMMANDS.items():
        if message.content.startswith(cmd) and has_required_role:
            await func(message, has_required_role)
            break
    
    cursor.close()
    bot.db.close()
                               
            
@bot.event
async def on_message_edit(before, after):
    if before.content == after.content:
        return
    
    channels_to_skip = {1268341191779549315, 1272002088116817941, 1272004162619707392, 1272011667688919071, 1272011703932026910, 1272010238639345756, 1272009729110966337, 1272009761868615784, 1272009977330012200, 1272010530726609028, 1272011856617406557, 1272012055464906753, 1272012243529367653, 1272012650376728607, 1281661279886381178}    
    if after.channel.id in channels_to_skip:
        return

    
    if after.author == bot.user:
        return
        
    required_roles = {"Admin", "Worker Bees", "*"}

    # Check if the author is a Member
    if isinstance(after.author, discord.Member):
        has_required_role = any(role.name in required_roles for role in after.author.roles)
    else:
        has_required_role = False
        
    def load_banned_phrases():
        with open("/home/container/members/autoban/wordlist.txt", "r") as f:
            return [line.strip() for line in f.readlines()]
        
    if not has_required_role:
        banned_phrases = load_banned_phrases()
        # Identify the specific banned phrase
        matched_phrase = next((phrase for phrase in banned_phrases if phrase in after.content), None)
        if matched_phrase:
            case_number = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            
            cembed = discord.Embed(
                title="__Member Banned__",
                color=0xFF0800,  # You can set the color to your preference
            )
            cembed.add_field(name="Member: ", value=after.author.mention, inline=False)  
            cembed.add_field(name="Reason: ", value=f"Using a forbidden phrase: `{matched_phrase}`", inline=False)  # Use matched_phrase here
            cembed.set_thumbnail(url="https://i.imgur.com/M0RjN63.png")
            cembed.set_footer(text=f"Case Number: {case_number}")
            
            try:
                await after.guild.get_channel(1276703619629977651).send(f"<@{after.author.id}> - Case Number: {case_number}\n", embed=cembed)
            except discord.Forbidden:
                # This will occur if the user has blocked the bot or has DMs disabled for this server.
                pass
            
            embed = discord.Embed(
                title=f"**Hi, ParleyBee Here!**",
                description=(
                    f"**You've been banned from ParleyBee Discord server!**\n"
                    f"We regret to inform you that you have been automatically banned from ParleyBee Discord server for the use of a forbidden phrase.\n\n"
                    f"**__Phrase__:** {matched_phrase}\n"
                    f"**__Case Number__:** {case_number}\n\n"
                    f"If you believe this ban is in error and would like to appeal it, please follow these steps:\n\n"
                    f"Send an email to __**support@parleybee.com**__. In the subject line, please use the following format:\n\n"
                    f"**Discord Ban Appeal - {after.author} - {case_number}**.\n\n"
                    f"In the body of the email, provide a brief explanation of why you believe the ban should be lifted. "
                    f"Be concise and respectful in your message. Our team will review your appeal as soon as possible. "
                    f"Please allow some time for us to investigate and respond to your request.\n\n"
                    f"We take all Communities and Discords rules seriously and appreciate your understanding and cooperation "
                    f"in maintaining a positive and respectful environment for all members.\n\n"
                    f"Best regards,\nParleyBee Support Team."
                ),
                color=0xFF0000,  # RED color
            )
            embed.set_image(url="https://i.imgur.com/O3rYw4O.png")
            try:
                await after.author.send(embed=embed)
            except discord.Forbidden:
                # This will occur if the user has blocked the bot or has DMs disabled for this server.
                pass

            # Ban the user
            await after.author.ban(reason=f"Used forbidden phrase: {matched_phrase}.", delete_message_days=7)

            # Send a notification to the specific channel
            ServerUpdates = bot.get_channel(1272010238639345756)
            if ServerUpdates:  # Check to ensure the channel was found
                await ServerUpdates.send(f"{after.author.mention} has been auto-banned for using the forbidden phrase: `{matched_phrase}`.")
            return
                            
                      
@tree.command(guild=discord.Object(id=1268334937489014847), name="info", description="Pull a members Info card")
async def info(ctx: commands.Context, member: discord.Member):
    bot.db = sqlite3.connect('bee.db')
    cursor = bot.db.cursor()
    cursor.execute("SELECT member_message_count, member_vote_count, member_warning, member_ad_count, member_url, member_description FROM BeeData WHERE member_id=?", (member.id,))
    member_data = cursor.fetchone()
    message_count, vote_count, warning_count, ad_count, website_url, description = member_data
    iconn = sqlite3.connect('invite_tracker.db')
    icursor = iconn.cursor()
    icursor.execute('SELECT COUNT(*) FROM invites WHERE inviter_id = ?', (str(member.id),))
    total_invites = icursor.fetchone()[0]
    iconn.close()
    embed = discord.Embed(
        title="ParleyBee Info Card",
        description="",
        color=0x00ff00)
    embed.set_thumbnail(url=member.avatar)

    embed.add_field(name="Username:", value=member.mention, inline=True)
    embed.add_field(name="Messages:", value=message_count, inline=True)
    embed.add_field(name="Promos:", value=ad_count, inline=True)
    embed.add_field(name="Invites:", value=str(total_invites), inline=True)
    embed.add_field(name="Reputation:", value=vote_count, inline=True)
    embed.add_field(name="Warnings:", value=warning_count, inline=True)
    embed.add_field(name="Website URL:", value=f"_{website_url}_", inline=False)
    embed.add_field(name=f"Description:", value=f"_{description}_\n", inline=False)

    account_created = member.created_at  # This is an offset-aware datetime
    joined_server = member.joined_at  # This is an offset-aware datetime
    today = datetime.now(pytz.utc)  # Make sure it's offset-aware using UTC timezone

    account_age = today - account_created
    joined_age = today - joined_server

    months_account = account_age.days // 30
    days_account = account_age.days % 30

    months_joined = joined_age.days // 30
    days_joined = joined_age.days % 30

    account_age_str = f"Account created: {months_account} months, {days_account} days ago"
    joined_age_str = f"Joined Server: {months_joined} months, {days_joined} days ago"

    if account_age.days < 1:
        account_age_str = "Account created: Today"
    elif months_account == 0:
        account_age_str = f"Account created: {days_account} days ago"

    if joined_age.days < 1:
        joined_age_str = "Joined Server: Today"
    elif months_joined == 0:
        joined_age_str = f"Joined Server: {days_joined} days ago"
        
    footer_text = f"{account_age_str}\n{joined_age_str}"
    embed.set_footer(text=footer_text)
    await ctx.response.send_message(embed=embed)
    
    
@tree.command(guild=discord.Object(id=1268334937489014847), name="upvote", description="Give a member reputation")
async def upvote(ctx: commands.Context, member: discord.Member):
    bot.db = sqlite3.connect("bee.db")
    cursor = bot.db.cursor()
    upvote_file_path = f"/home/container/members/upvote/{member.id}.txt"
    unverified_role = discord.utils.get(ctx.user.roles, name="Unverified")
    
    if unverified_role:
        # The member has the "Unverified" role, send a message
        embed = discord.Embed(
            title="Error:",
            description="You must verify your account to use the voting system.",
            color=0xFF0000  # Red color for error
        )
        embed.set_thumbnail(url="https://i.imgur.com/xSd8IRi.png")
        await ctx.response.send_message(embed=embed)
        return
    
    if os.path.exists(upvote_file_path):
        with open(upvote_file_path, "r") as file:
            upvoters = file.read().splitlines()
            if str(ctx.user.id) in upvoters:
                embed = discord.Embed(
                    title="Error:",
                    description=f"You have already upvoted {member.mention}.",
                    color=0xFF0000  # Green color for success
                )
                embed.set_thumbnail(url="https://i.imgur.com/xSd8IRi.png")
                await ctx.response.send_message(embed=embed)
                return
                
    downvote_file_path = f"/home/container/members/downvote/{member.id}.txt"
    if os.path.exists(downvote_file_path):
        with open(downvote_file_path, "r") as file:
            downvoters = file.read().splitlines()
            if str(ctx.user.id) in downvoters:
                downvoters.remove(str(ctx.user.id))
        # Overwrite the downvote file with the updated list
        with open(downvote_file_path, "w") as file:
            file.write("\n".join(downvoters))

    # Find the user in the database
    cursor.execute("SELECT member_vote_count FROM BeeData WHERE member_id = ?", (member.id,))
    result = cursor.fetchone()

    if result is None:
        # User not found in the database, insert a new row
        cursor.execute("INSERT INTO BeeData (member_id, member_vote_count) VALUES (?, 1)", (member.id,))
    else:
        # User found, update the vote count
        cursor.execute("UPDATE BeeData SET member_vote_count = member_vote_count + 1 WHERE member_id = ?", (member.id,))
    
    # Commit the changes and close the database connection
    bot.db.commit()
    bot.db.close()
    
    embed = discord.Embed(
        title="Upvote Successful",
        description=f"Upvoted {member.mention}! They now have {result[0] + 1} reputation.",
        color=0x00FF00  # Green color for success
    )
    embed.set_thumbnail(url="https://i.imgur.com/22vd1zW.png")
    await ctx.response.send_message(embed=embed)

    # Check if the text file exists, and either create or append to it
    if not os.path.exists(upvote_file_path):
        with open(upvote_file_path, "w") as file:
            file.write(str(ctx.user.id))
    else:
        with open(upvote_file_path, "a") as file:
            file.write("\n" + str(ctx.user.id))


@tree.command(guild=discord.Object(id=1268334937489014847), name="downvote", description="Remove reputation from a member")
async def downvote(ctx: commands.Context, member: discord.Member):
    bot.db = sqlite3.connect("bee.db")
    cursor = bot.db.cursor()
    downvote_file_path = f"/home/container/members/downvote/{member.id}.txt"
    unverified_role = discord.utils.get(ctx.user.roles, name="Unverified")
    
    if unverified_role:
        # The member has the "Unverified" role, send a message
        embed = discord.Embed(
            title="Error:",
            description="You must verify your account to use the voting system.",
            color=0xFF0000  # Red color for error
        )
        embed.set_thumbnail(url="https://i.imgur.com/xSd8IRi.png")
        await ctx.response.send_message(embed=embed)
        return
    
    if os.path.exists(downvote_file_path):
        with open(downvote_file_path, "r") as file:
            downvoters = file.read().splitlines()
            if str(ctx.user.id) in downvoters:
                embed = discord.Embed(
                    title="Error:",
                    description=f"You have already upvoted {member.mention}.",
                    color=0xFF0000  # RED color for success
                )
                embed.set_thumbnail(url="https://i.imgur.com/xSd8IRi.png")
                await ctx.response.send_message(embed=embed)
                return
           
    upvote_file_path = f"/home/container/members/upvote/{member.id}.txt"
    if os.path.exists(upvote_file_path):
        with open(upvote_file_path, "r") as file:
            upvoters = file.read().splitlines()
            if str(ctx.user.id) in upvoters:
                upvoters.remove(str(ctx.user.id))
        # Overwrite the downvote file with the updated list
        with open(upvote_file_path, "w") as file:
            file.write("\n".join(upvoters))

    # Find the user in the database
    cursor.execute("SELECT member_vote_count FROM BeeData WHERE member_id = ?", (member.id,))
    result = cursor.fetchone()

    if result is None:
        # User not found in the database, insert a new row
        cursor.execute("INSERT INTO BeeData (member_id, member_vote_count) VALUES (?, -1)", (member.id,))
    else:
        # User found, update the vote count
        cursor.execute("UPDATE BeeData SET member_vote_count = member_vote_count - 1 WHERE member_id = ?", (member.id,))
        
    # Commit the changes and close the database connection
    bot.db.commit()
    bot.db.close()
    
    embed = discord.Embed(
        title="Downvote Successful",
        description=f"Downvoted {member.mention}! They now have {result[0] - 1} reputation.",
        color=0xFF0000  # RED color for success
    )
    embed.set_thumbnail(url="https://i.imgur.com/jWAQYm8.png")
    await ctx.response.send_message(embed=embed)

    # Check if the text file exists, and either create or append to it
    if not os.path.exists(downvote_file_path):
        with open(downvote_file_path, "w") as file:
            file.write(str(ctx.user.id))
    else:
        with open(downvote_file_path, "a") as file:
            file.write("\n" + str(ctx.user.id))   


@tree.command(guild=discord.Object(id=1268334937489014847), name="warn", description="Issue a warning to a member")
async def warn(ctx: commands.Context, user: discord.Member, *, description: str):
    # Define the required role names or role IDs in a list
    required_roles = ["Admin", "Worker Bees", "*"]  # Replace with the actual role names or role IDs

    # Check if the user has any of the required roles
    has_required_role = any(role.name in required_roles for role in ctx.user.roles)

    if has_required_role:
        bot.db = sqlite3.connect('bee.db')
        cursor = bot.db.cursor()
    
        cursor.execute("UPDATE BeeData SET member_warning = member_warning + 1 WHERE member_id = ?", (user.id,))
        bot.db.commit()
        
        cursor.execute("SELECT member_warning FROM BeeData WHERE member_id = ?", (user.id,))
        total_warnings = cursor.fetchone()[0]
        
        bot.db.close()
    
        users_id = user.id
        username = user.name
        warning_file_path = f"/home/container/members/warnings/{users_id}.txt"
    
        with open(warning_file_path, "a") as file:
            file.write(f"{description}\n")
    
        try:
            case_number = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            if total_warnings < 5:
                embed = discord.Embed(
                    title="__Warning Issued__",
                    color=0xFF0800,
                )
                embed.add_field(name="Member: ", value=f"_<@{users_id}>_", inline=False)
                embed.add_field(name="Description: ", value=f"_{description}_", inline=False)
                embed.set_thumbnail(url="https://i.imgur.com/lVO5vz5.png")
                embed.set_footer(text=f"Total Warnings: {total_warnings}/5")
                await ctx.guild.get_channel(1276703619629977651).send(f"<@{users_id}> - Case Number: {case_number}\n",embed=embed)
                await ctx.response.send_message(f"<@{users_id}>\n",embed=embed)
                
                dm_title = "You've been warned!"
                dm_description = f"**You have received a warning for**:\n> {description}\n\n**Please review the server rules to avoid further penalties.**"

                dm_embed = discord.Embed(
                    title=dm_title,
                    description=dm_description,
                    color=0xFF0800  # Set color as preferred
                )
                dm_embed.set_footer(text=f"Total Warnings: {total_warnings}/5")
                dm_embed.set_image(url="https://i.imgur.com/O3rYw4O.png")
                await user.send(embed=dm_embed)
            else:
                embed = discord.Embed(
                    title="__Warnings Exceeded__",
                    color=0xFF0800,
                )
                embed.add_field(name="Member: ", value=f"_<@{users_id}>_", inline=False)
                embed.add_field(name="Description: ", value=f"_{description}_", inline=False)
                embed.set_thumbnail(url="https://i.imgur.com/lVO5vz5.png")
                embed.set_footer(text=f"Total Warnings: {total_warnings}/5\nStatus: Banned")
                await ctx.guild.get_channel(1276703619629977651).send(f"<@{users_id}> - Case Number: {case_number}\n",embed=embed)
                await ctx.response.send_message(f"<@{users_id}>\n",embed=embed)
                member = ctx.guild.get_member(users_id)
                if member:
                    await member.ban(reason="Exceeded warnings")               
        except Exception as e:
            print(f"Error sending message: {e}")
    else:
        # Create an embed message for permission denied
        embed = discord.Embed(
            title="Permission Denied",
            description=f"You do not have permission to use this command.\n_All unauthorized attempts are logged._",
            color=0xFF0800,  # You can set the color to your preference
        )
        embed.set_thumbnail(url="https://i.imgur.com/WCkJXsN.png")

        try:
            # Send the embed message for permission denied
            await ctx.response.send_message(embed=embed)
        except Exception as e:
            print(f"Error sending message: {e}")


@tree.command(guild=discord.Object(id=1268334937489014847), name="ban", description="Ban a member")
async def ban(ctx: commands.Context, user: discord.Member, *, reason: str = "No reason provided"):
    # Define the required role names or role IDs in a list
    required_roles = ["Admin", "*"]  # Replace with the actual role names or role IDs

    # Check if the user has any of the required roles
    has_required_role = any(role.name in required_roles for role in ctx.user.roles)

    if has_required_role:
        users_id = user.id
        try:
            # Generate a random case number with letters and numbers
            case_number = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            
            # Create an embed for the ban
            embed = discord.Embed(
                title="__Member Banned__",
                color=0xFF0800,  # You can set the color to your preference
            )
            embed.add_field(name="Member: ", value=f"{user.mention}", inline=False)
            embed.add_field(name="Reason: ", value=f"{reason}", inline=False)
            embed.set_thumbnail(url="https://i.imgur.com/M0RjN63.png")
            embed.set_footer(text=f"Case Number: {case_number}")
            
            # Send the ban message to the specified channel
            await ctx.guild.get_channel(1276703619629977651).send(f"<@{users_id}> - Case Number: {case_number}\n", embed=embed)
            await ctx.response.send_message(f"<@{users_id}>\n",embed=embed)
            
            # Send a DM to the user
            dm_embed = discord.Embed(
                title="You've been banned from ParleyBee Discord server!",
                description=f"We regret to inform you that you have been banned from ParleyBee Discord server for the following reason:\n\n"
                            f"**__Reason__:** {reason}\n"
                            f"**__Case Number__:** {case_number}\n\n"
                            f"If you believe this ban is in error and would like to appeal it, please follow these steps:\n\n"
                            f"Send an email to **support@parleybee.com**. In the subject line, please use the following format:\n\n"
                            f"**Discord Ban Appeal - {user.name} - {case_number}**.\n\n"
                            f"In the body of the email, provide a brief explanation of why you believe the ban should be lifted. "
                            f"Be concise and respectful in your message. Our team will review your appeal as soon as possible. "
                            f"Please allow some time for us to investigate and respond to your request.\n\n"
                            f"We take all Communities and Discords rules seriously and appreciate your understanding and cooperation "
                            f"in maintaining a positive and respectful environment for all members.\n\n"
                            f"Best regards,\nParleyBee Support Team.",
                color=0xFF0800  # You can set the color to your preference
            )
            dm_embed.set_image(url="https://i.imgur.com/O3rYw4O.png")
            
            # Send the DM message as an embed
            await user.send(embed=dm_embed)
            
            # Ban the member
            await user.ban(reason=reason)
        except Exception as e:
            print(f"Error banning member: {e}")
    else:
        # Create an embed message for permission denied
        embed = discord.Embed(
            title="Permission Denied",
            description=f"You do not have permission to use this command.\n_All unauthorized attempts are logged._",
            color=0xFF0800,  # You can set the color to your preference
        )
        embed.set_thumbnail(url="https://i.imgur.com/WCkJXsN.png")

        try:
            # Send the embed message for permission denied
            await ctx.response.send_message(embed=embed)
        except Exception as e:
            print(f"Error sending message: {e}")
            
            
@tree.command(guild=discord.Object(id=1268334937489014847), name="url", description="Add your website to your ID card")
async def add_url_to_database(ctx, url: str):
    member_id = ctx.user.id  # Use ctx.user.id to get the member's ID
    unverified_role = discord.utils.get(ctx.user.roles, name="Unverified")
    
    if unverified_role:
        # The member has the "Unverified" role, send a message
        embed = discord.Embed(
            title="Error:",
            description="You must verify your account to update your IDs URL.",
            color=0xFF0000  # Red color for error
        )
        embed.set_thumbnail(url="https://i.imgur.com/xSd8IRi.png")
        await ctx.response.send_message(embed=embed)
        return

    # Check if the URL starts with "http://" or "https://"
    if not url.startswith(("http://", "https://")):
        url = "https://" + url  # Automatically add "https://" if missing

    # Check if "www." is present, and add it if not
    if not url.startswith("https://www.") and not url.startswith("http://www."):
        url = url.replace("https://", "https://www.").replace("http://", "http://www.")

    bot.db = sqlite3.connect('bee.db')
    cursor = bot.db.cursor()

    # Check if a record with the same member_id already exists
    cursor.execute("SELECT COUNT(*) FROM BeeData WHERE member_id = ?", (member_id,))
    existing_record = cursor.fetchone()[0]

    if existing_record > 0:
        # If a record exists, update the member_url
        cursor.execute("UPDATE BeeData SET member_url = ? WHERE member_id = ?", (url, member_id))
    else:
        # If no record exists, insert a new one
        cursor.execute("INSERT INTO BeeData (member_id, member_url, username) VALUES (?, ?, ?)", (member_id, url, ctx.user.name))

    bot.db.commit()
    bot.db.close()

    # Create an embed message for successful URL update
    embed = discord.Embed(
        title="URL Update Successful",
        description=f"The URL has been added to your ID card.",
        color=0x00FF00  # Green color for success
    )
    embed.set_thumbnail(url="https://i.imgur.com/sN60QqB.png")  # Replace with the actual URL of the thumbnail

    try:
        # Send the embed message for URL update success
        await ctx.response.send_message(embed=embed)
        channel_id = 1272010238639345756  # Replace with the actual channel ID
        channel = ctx.guild.get_channel(channel_id)
        if channel:
            await channel.send(f"User <@{ctx.user.id}> has updated their URL to: \n{url}")    
    except Exception as e:
        print(f"Error sending message: {e}")
        
        
@tree.command(guild=discord.Object(id=1268334937489014847), name="description", description="Add a description to your ID card")
async def add_description_to_database(ctx, description: str):
    member_id = ctx.user.id  # Use ctx.user.id to get the member's ID
    unverified_role = discord.utils.get(ctx.user.roles, name="Unverified")
    
    if unverified_role:
        # The member has the "Unverified" role, send a message
        embed = discord.Embed(
            title="Error:",
            description="You must verify your account to update your IDs description.",
            color=0xFF0000  # Red color for error
        )
        embed.set_thumbnail(url="https://i.imgur.com/xSd8IRi.png")
        await ctx.response.send_message(embed=embed)
        return

    bot.db = sqlite3.connect('bee.db')
    cursor = bot.db.cursor()

    # Check if a record with the same member_id already exists
    cursor.execute("SELECT COUNT(*) FROM BeeData WHERE member_id = ?", (member_id,))
    existing_record = cursor.fetchone()[0]

    if existing_record > 0:
        # If a record exists, update the member_description
        cursor.execute("UPDATE BeeData SET member_description = ? WHERE member_id = ?", (description, member_id))
    else:
        # If no record exists, insert a new one
        cursor.execute("INSERT INTO BeeData (member_id, member_description, username) VALUES (?, ?, ?)", (member_id, description, ctx.author.name))

    bot.db.commit()
    bot.db.close()

    # Create an embed message for successful description update
    embed = discord.Embed(
        title="Description Update Successful",
        description=f"The description has been added to your ID card.",
        color=0x00FF00  # Green color for success
    )
    embed.set_thumbnail(url="https://i.imgur.com/sN60QqB.png")  # Replace with the actual URL of the thumbnail

    try:
        # Send the embed message for description update success
        await ctx.response.send_message(embed=embed)
        channel_id = 1272010238639345756  # Replace with the actual channel ID
        channel = ctx.guild.get_channel(channel_id)
        if channel:
            await channel.send(f"User <@{ctx.user.id}> has updated their description to: \n{description}")    
    except Exception as e:
        print(f"Error sending message: {e}")


@tree.command(guild=discord.Object(id=1268334937489014847), name="purge", description="Purge a number of messages")
async def purge(interaction: discord.Interaction, amount: int):
    required_roles = ["Admin", "*"]
    has_required_role = any(role.name in required_roles for role in interaction.user.roles)
    
    if not has_required_role:
        embed = discord.Embed(
            title="Permission Denied",
            description=f"You do not have permission to use this command.\n_All unauthorized attempts are logged._",
            color=0xFF0800,  # You can set the color to your preference
        )
        embed.set_thumbnail(url="https://i.imgur.com/WCkJXsN.png")
        await interaction.response.send_message(embed=embed)
        return

    if amount <= 0:
        await interaction.response.send_message("Please specify the number of messages to delete.", ephemeral=True)
        return
        
    await interaction.response.defer()
    await interaction.channel.purge(limit=amount + 1)
                
            
async def daily_purge():
    pinged_role = 'Unverified'
    while True:
        now = datetime.now()
        purge_time = time(17, 0)  # 5:00 PM
        
        delta = datetime.combine(datetime.today().date(), purge_time) - now
        if delta.total_seconds() < 0:
            delta += timedelta(days=1)
        await asyncio.sleep(delta.total_seconds())
        channel = bot.get_channel(1276698226703208520)
        if channel and isinstance(channel, discord.TextChannel):
            async for message in channel.history(limit=None):
                if not message.pinned:
                    try:
                        await message.delete() #carry old code
                    except discord.errors.HTTPException as e:
                        if e.status == 429:
                            # Rate limited, wait for X seconds specified in the headers
                            await asyncio.sleep(e.retry_after)
                        else:
                            # Handle other exceptions
                            pass
            role = discord.utils.get(channel.guild.roles, name=pinged_role)
            if role:
                await channel.send(f"Hello {role.mention} and a warm welcome to the ParleyBee Discord server!!\n\nTo ensure a seamless and enjoyable experience free from spam bots, we require a quick verification process for all members. It's simple: navigate to <#1280191581697216622>, take a moment to read through them, and then click the ✅ at the bottom to verify your account. Should you encounter any issues with verification, don't hesitate to drop a message here, and I'll assist you with manual verification. Let's keep our community safe and fun for everyone!\n\n<@1276623984598847488> will attemp to send you a reminder by DMs 3 times over 3 days. If you fail to verify after, you will be kicked from the server.\n\n_This message is scheduled to post once every 24 hours._")

async def scan_and_update_members():
    try:
        bot.db = sqlite3.connect('bee.db')
        cursor = bot.db.cursor()
        
        cursor.execute('SELECT member_id FROM BeeData')
        existing_member_ids = set(row[0] for row in cursor.fetchall())
        
        guild = bot.get_guild(1268334937489014847)
                
        for member in guild.members:
            if member.id not in existing_member_ids:
                cursor.execute("INSERT INTO BeeData (member_id, username, member_message_count, member_vote_count, member_warning, member_ad_count, member_unverify, member_url, member_description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (member.id, member.name, 0, 0, 0, 0, 0, 'Use `/url` to update your Websites URL.', 'Use `/description` to add your own description.'))
                bot.db.commit()
                print(f'Recovered member: {member.name}. Added to the database.')
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    
    finally:
        if hasattr(bot, 'db'):
            bot.db.close()
    

async def update_invite_data(user_id, inviter_id):
    iconn = sqlite3.connect('invite_tracker.db')
    icursor = iconn.cursor()
    icursor.execute('SELECT * FROM invites WHERE user_id = ?', (user_id,))
    result = icursor.fetchone()
    if result:
        # Update existing entry
        icursor.execute('UPDATE invites SET invites = invites + 1 WHERE user_id = ?', (user_id,))
    else:
        # Create new entry
        icursor.execute('INSERT INTO invites (user_id, invites, inviter_id) VALUES (?, 1, ?)', (user_id, inviter_id))
    iconn.commit()
  
  
@bot.event
async def on_invite_create(invite):
    bot.invites = await invite.guild.invites()

@bot.event
async def on_invite_delete(invite):
    bot.invites = await invite.guild.invites()

@bot.event
async def on_guild_join(guild):
    bot.invites = await guild.invites()

@bot.event
async def on_guild_available(guild):
    bot.invites = await guild.invites()

async def setup():
    bot.invites = {}
    for guild in bot.guilds:
        bot.invites[guild.id] = await guild.invites()

async def setup_hook():
    await setup()

# Function to check streamers periodically
async def check_streamers():
    global twitch_usernames, live_status

    while True:
        if not twitch_usernames:
            print("No usernames found.")
        else:
            try:
                # Fetch live streams for the given usernames in bulk
                live_streams = get_live_streams(twitch_usernames)
                live_users = {stream['user_name'].lower(): stream for stream in live_streams}

                channel = bot.get_channel(1271919100465123328)  # Update with your actual channel ID
                if not channel:
                    print("Announcement channel not found.")
                else:
                    # Filter only those who are live and haven't been posted yet
                    new_live_users = {
                        username: stream_info 
                        for username, stream_info in live_users.items() 
                        if not live_status.get(username, False)
                    }

                    # Remove users from live_status who are no longer live
                    offline_users = set(live_status.keys()) - set(live_users.keys())
                    for offline_user in offline_users:
                        live_status.pop(offline_user, None)

                    if new_live_users:
                        await send_live_notifications(new_live_users, channel)

            except Exception as e:
                print(f"An error occurred: {e}")

        await asyncio.sleep(300)  # Wait for 5 minutes before the next check
    
@bot.event
async def on_ready():
    global twitch_usernames
    guild_id = 1268334937489014847
    voice_channel_id = 1276725755317059614

    bot.db = sqlite3.connect('bee.db')
    cursor = bot.db.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS BeeData (
                    member_id INTEGER PRIMARY KEY NOT NULL,
                    username TEXT NOT NULL,
                    member_message_count INTEGER NOT NULL DEFAULT 0,
                    member_vote_count INTEGER NOT NULL DEFAULT 0,
                    member_warning INTEGER NOT NULL DEFAULT 0,
                    member_ad_count INTEGER NOT NULL DEFAULT 0,
                    member_unverify INTEGER NOT NULL DEFAULT 0,
                    member_url TEXT NOT NULL DEFAULT '',
                    member_description TEXT NOT NULL DEFAULT ''
                        )''')
    bot.db.commit()
    bot.db.close()
    
    iconn = sqlite3.connect('invite_tracker.db')
    icursor = iconn.cursor()
    icursor.execute('''CREATE TABLE IF NOT EXISTS invites
                  (user_id TEXT PRIMARY KEY, invites INTEGER, inviter_id TEXT)''')
    iconn.commit()
    iconn.close()
    
    await bot.wait_until_ready()
    print(bot.user, 'is online. ✔️')
    print(discord.__version__)
    await tree.sync(guild=discord.Object(id=1268334937489014847))
    await scan_and_update_members()
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Messages In ParleyBee."))
    meme.start()  # 12 hour memes
    if not twitch_usernames:
        twitch_usernames = fetch_twitch_usernames()  # Fetch once on startup
    bot.loop.create_task(check_streamers())  # Start the manual timer loop

    await daily_purge() #Unverified purge/ping
    await asyncio.sleep(2)
    
    guild = bot.get_guild(guild_id)
    voice_channel = guild.get_channel(voice_channel_id)

    if guild and voice_channel:
        member_count = guild.member_count
        try:
            await voice_channel.edit(name=f'Members: {member_count}')
        except Exception as e:
            print(f"Failed to update voice channel name: {e}")

bot.setup_hook = setup_hook

bot.run("", reconnect=True)
# Official
