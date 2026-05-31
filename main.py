import discord
from discord.ext import commands
import os
import random
from flask import Flask
from threading import Thread
import logging
import asyncio
import time
import json 
from discord.ui import View, Button # Required for interactable Blackjack

BOT_NAME = "Zylo"
# Set Flask logging to ERROR only to keep the console clean
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# --- GLOBAL ECONOMY SETUP (IN-MEMORY DATABASE) ---
USER_ECONOMY_DB = {}
STARTING_BALANCE = 500
DATA_FILE = 'economy_data.json'
# Removed the global lottery_jackpot variable as it's no longer a jackpot system
COOLDOWN_GROUP_GAMBLING = 5 # 5 seconds cooldown for gambling commands (roll, flip, bj, slots, lotto)
# Stores {user_id + channel_id: {msg_id: int, ...}} to prevent multiple simultaneous games
ACTIVE_BLACKJACK_GAMES = {} 

# --- CONFIGURATION (Customize these variables) ---
# IMPORTANT: REPLACE 'YOUR_ADMIN_USER_ID' with the actual Discord User ID(s)
ADMIN_IDS = ['123456789012345678', '1419323306192142407'] # Placeholder and Example ID

# --- POKE DATA DEFINITION (Truncated for space) ---

POKE_TYPES = {
    'Normal': '⚪', 'Fire': '🔥', 'Water': '💧', 'Grass': '🌿',
    'Electric': '⚡', 'Ice': '❄️', 'Fighting': '👊', 'Poison': '🧪',
    'Ground': '⛰️', 'Flying': '🦅', 'Psychic': '✨', 'Bug': '🐛',
    'Rock': '🗿', 'Ghost': '👻', 'Dragon': '🐲', 'Steel': '⚙️',
    'Dark': '🌑', 'Fairy': '🧚'
}

RARITY_WEIGHTS = {
    'C': {'name': 'Common', 'weight': 8450, 'color': discord.Color.light_grey()},
    'R': {'name': 'Rare', 'weight': 1500, 'color': discord.Color.blue()},
    'L': {'name': 'Legendary', 'weight': 49, 'color': discord.Color.gold()},
    'A': {'name': 'Arceus', 'weight': 1, 'color': discord.Color.purple()},
}
TOTAL_WEIGHT = sum(r['weight'] for r in RARITY_WEIGHTS.values())

POKE_DATA = [
    {'name': 'Eveejoy', 'r': 'C', 'type': 'Normal'}, {'name': 'Snorlaxle', 'r': 'C', 'type': 'Normal'},
    {'name': 'Jigglepuff', 'r': 'C', 'type': 'Normal'}, {'name': 'Chanheal', 'r': 'C', 'type': 'Normal'},
    {'name': 'Cinderrace', 'r': 'R', 'type': 'Normal'},
    {'name': 'Charflame', 'r': 'C', 'type': 'Fire'}, {'name': 'Vulpixie', 'r': 'C', 'type': 'Fire'},
    {'name': 'Squirtleto', 'r': 'C', 'type': 'Water'}, {'name': 'Waple', 'r': 'C', 'type': 'Water'},
    {'name': 'Bulbabud', 'r': 'C', 'type': 'Grass'}, {'name': 'Leafeonix', 'r': 'C', 'type': 'Grass'},
    {'name': 'Pikaboom', 'r': 'C', 'type': 'Electric'}, {'name': 'Jolteon', 'r': 'C', 'type': 'Electric'},
    {'name': 'Laprasaur', 'r': 'C', 'type': 'Ice'}, {'name': 'Snoverice', 'r': 'C', 'type': 'Ice'},
    {'name': 'Machoke', 'r': 'C', 'type': 'Fighting'}, {'name': 'Hitmonlee', 'r': 'C', 'type': 'Fighting'},
    {'name': 'Ekanserpent', 'r': 'C', 'type': 'Poison'}, {'name': 'Koffingas', 'r': 'C', 'type': 'Poison'},
    {'name': 'Diglett', 'r': 'C', 'type': 'Ground'}, {'name': 'Sandshrew', 'r': 'C', 'type': 'Ground'},
    {'name': 'Pidgeon', 'r': 'C', 'type': 'Flying'}, {'name': 'Hoothoot', 'r': 'C', 'type': 'Flying'},
    {'name': 'Abrakadabra', 'r': 'C', 'type': 'Psychic'}, {'name': 'Drowzee', 'r': 'C', 'type': 'Psychic'},
    {'name': 'Caterbee', 'r': 'C', 'type': 'Bug'}, {'name': 'Weedle', 'r': 'C', 'type': 'Bug'},
    {'name': 'Geodude', 'r': 'C', 'type': 'Rock'}, {'name': 'Onixhard', 'r': 'C', 'type': 'Rock'},
    {'name': 'Gastly', 'r': 'C', 'type': 'Ghost'}, {'name': 'Phantump', 'r': 'C', 'type': 'Ghost'},
    {'name': 'Dratini', 'r': 'C', 'type': 'Dragon'}, {'name': 'Bagon', 'r': 'C', 'type': 'Dragon'},
    {'name': 'Magnemite', 'r': 'C', 'type': 'Steel'}, {'name': 'Beldum', 'r': 'C', 'type': 'Steel'},
    {'name': 'Umbreonix', 'r': 'C', 'type': 'Dark'}, {'name': 'Poochyena', 'r': 'C', 'type': 'Dark'},
    {'name': 'Clefairy', 'r': 'C', 'type': 'Fairy'}, {'name': 'Togepi', 'r': 'C', 'type': 'Fairy'},
    {'name': 'Alphamon', 'r': 'A', 'type': 'Normal'}, # Arceus
    # ... (rest of 250 species data)
] 

# --- DATA PERSISTENCE FUNCTIONS ---

def load_data():
    """Loads user data from the JSON file."""
    global USER_ECONOMY_DB
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                USER_ECONOMY_DB = data.get('users', {})
                # Removed jackpot loading
        except json.JSONDecodeError:
            print(f"Warning: Failed to decode JSON from {DATA_FILE}. Starting with empty data.")
            USER_ECONOMY_DB = {}
    else:
        USER_ECONOMY_DB = {}

def save_data():
    """Saves user data to the JSON file."""
    global USER_ECONOMY_DB
    data_to_save = {
        'users': USER_ECONOMY_DB,
        # Removed jackpot saving
    }
    with open(DATA_FILE, 'w') as f:
        json.dump(data_to_save, f, indent=4)

# --- HELPER FUNCTIONS ---

def get_profile(user_id: str) -> dict:
    """Retrieves or creates a user's profile from the in-memory database."""
    if user_id not in USER_ECONOMY_DB:
        USER_ECONOMY_DB[user_id] = {
            'coins': STARTING_BALANCE,
            'poke_inventory': {}, 
            'last_daily': 0, 
            'last_weekly': 0, 
            'last_hunt': 0, 
        }
    
    # Ensure all required keys exist (for older profiles)
    profile = USER_ECONOMY_DB[user_id]
    if 'last_daily' not in profile: profile['last_daily'] = 0
    if 'last_weekly' not in profile: profile['last_weekly'] = 0
    if 'last_hunt' not in profile: profile['last_hunt'] = 0
    if 'poke_inventory' not in profile: profile['poke_inventory'] = {}

    return profile

def update_coins(user_id: str, amount: int) -> bool:
    """Adds or subtracts coins. Returns True if successful, False if insufficient funds."""
    profile = get_profile(user_id)
    new_balance = profile['coins'] + amount

    if new_balance < 0:
        if abs(amount) > profile['coins']:
            return False
    
    profile['coins'] = new_balance
    return True

def format_time(seconds: int) -> str:
    """Converts seconds into a human-readable H/M/S string."""
    if seconds >= 86400: 
        days = seconds // 86400
        return f"{days} day{'s' if days != 1 else ''}"
    if seconds >= 3600: 
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"
    if seconds >= 60: 
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    return f"{seconds} second{'s' if seconds != 1 else ''}"

def add_custom_footer(embed: discord.Embed):
    """Adds the required custom footer."""
    if embed.fields:
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        embed.add_field(name="\u200b", value="\u200b", inline=False)
    embed.set_footer(text="Made By xpheonixx_", icon_url=None)

def get_random_poke():
    """Selects a random Poke based on rarity weights."""
    rarity_pool = [(data['weight'], code) for code, data in RARITY_WEIGHTS.items()]
    chosen_rarity_code = random.choices(
        population=[code for weight, code in rarity_pool],
        weights=[weight for weight, code in rarity_pool],
        k=1
    )[0]
    available_poke = [p for p in POKE_DATA if p['r'] == chosen_rarity_code]
    return random.choice(available_poke) if available_poke else random.choice(POKE_DATA)

# --- BLACKJACK HELPER FUNCTIONS ---

def create_deck():
    """Creates and shuffles a standard deck of 52 cards."""
    # Format: (Rank, Value, Suit)
    SUITS = ['♠️', '♥️', '♦️', '♣️']
    RANKS = [('A', 11), ('2', 2), ('3', 3), ('4', 4), ('5', 5), ('6', 6), ('7', 7), ('8', 8), ('9', 9), ('10', 10), ('J', 10), ('Q', 10), ('K', 10)]
    deck = [(rank, value, suit) for rank, value in RANKS for suit in SUITS]
    random.shuffle(deck)
    return deck

def calculate_hand_value(hand):
    """Calculates the total value of a hand, handling Aces (11 or 1)."""
    value = sum(card[1] for card in hand)
    num_aces = sum(1 for card in hand if card[0] == 'A')

    while value > 21 and num_aces > 0:
        value -= 10 # Convert an Ace from 11 to 1
        num_aces -= 1
    return value

def hand_to_string(hand, hide_dealer_card=False):
    """Formats the hand for display."""
    display = []
    
    if hide_dealer_card and len(hand) > 1:
        # Hide the dealer's second card
        display.append(f"`{hand[0][0]}{hand[0][2]}`")
        display.append("`❓`")
        remaining_cards = hand[2:]
    else:
        remaining_cards = hand
    
    for card in remaining_cards:
        display.append(f"`{card[0]}{card[2]}`")
        
    return ' '.join(display)


# --- CUSTOM DECORATOR: Check if user is an Admin ---
def is_admin():
    """A command check that verifies the user's ID is in the ADMIN_IDS list."""
    async def predicate(ctx):
        if str(ctx.author.id) not in ADMIN_IDS:
            await ctx.send("❌ **Access Denied:** This command requires administrator privileges.")
            return False
        return True
    return commands.check(predicate)

# --- BLACKJACK VIEW CLASS (NEW) ---

class BlackjackView(discord.ui.View):
    def __init__(self, user_id, bet, deck, player_hand, dealer_hand, embed_msg, game_id, timeout=180):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.bet = bet
        self.deck = deck
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.embed_msg = embed_msg
        self.game_id = game_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the player who started the game to interact."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your game! Start your own with `!bj <bet>`.", ephemeral=True)
            return False
        return True

    async def _update_message(self, status_msg, game_over=False, color=discord.Color.blue()):
        """Helper to update the game message embed."""
        embed = self.embed_msg.embeds[0]
        player_value = calculate_hand_value(self.player_hand)
        dealer_value = calculate_hand_value(self.dealer_hand)
        
        # Update fields
        embed.set_field_at(0, name="Your Hand", value=f"{hand_to_string(self.player_hand)} (Value: {player_value})", inline=False)
        # Dealer's hand display must be correct based on game state
        dealer_display = f"{hand_to_string(self.dealer_hand)} (Value: {dealer_value})" if game_over else f"{hand_to_string(self.dealer_hand, hide_dealer_card=True)} (Value: {self.dealer_hand[0][1]})"
        embed.set_field_at(1, name="Dealer's Hand", value=dealer_display, inline=False)
        embed.set_field_at(2, name="Status", value=status_msg, inline=False)
        embed.color = color

        if game_over:
            # Add final balance
            new_balance = get_profile(str(self.user_id))['coins']
            embed.add_field(name="Final Balance", value=f"**{new_balance:,}** points", inline=False)
            
            self.stop()
            self.clear_items()
            
            # Clean up the global game state
            if self.game_id in ACTIVE_BLACKJACK_GAMES:
                del ACTIVE_BLACKJACK_GAMES[self.game_id]

        await self.embed_msg.edit(embed=embed, view=self if not game_over else None)
        
    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # interaction_check handles user validation
            
        await interaction.response.defer()

        # Deal a card
        self.player_hand.append(self.deck.pop())
        player_value = calculate_hand_value(self.player_hand)
        
        if player_value > 21:
            # Player BUST
            update_coins(str(self.user_id), 0) # Already deducted the bet, so no change
            status_msg = f"💥 **BUST!** You went over 21. You lose **{self.bet:,}** points."
            await self._update_message(status_msg, game_over=True, color=discord.Color.red())
        else:
            # Continue game
            await self._update_message("You chose to Hit. Dealer awaits your next move.", color=discord.Color.blue())

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # interaction_check handles user validation
            
        await interaction.response.defer()
        
        # Dealer's turn
        dealer_value = calculate_hand_value(self.dealer_hand)
        player_value = calculate_hand_value(self.player_hand)
        
        # Update message to show dealer is starting to draw
        await self._update_message(f"You Stand. Dealer reveals hand and draws cards...", color=discord.Color.dark_grey())
        
        while dealer_value < 17:
            # Dealer must hit on < 17
            self.dealer_hand.append(self.deck.pop())
            dealer_value = calculate_hand_value(self.dealer_hand)
            await asyncio.sleep(0.5) 
            # Re-update to show the latest state of the dealer's hand
            await self._update_message(f"Dealer draws another card...", color=discord.Color.dark_grey())


        # Determine Winner
        winnings = 0
        status_msg = ""
        color = discord.Color.gold()
        
        if dealer_value > 21:
            # Dealer BUST
            winnings = self.bet * 2 # Bet + 1x winnings
            update_coins(str(self.user_id), winnings)
            status_msg = f"🎉 **DEALER BUSTS!** You win **{self.bet:,}** points (1:1 payout)."
            color = discord.Color.green()
        elif dealer_value > player_value:
            # Dealer Wins
            status_msg = f"❌ **DEALER WINS!** ({dealer_value} vs {player_value}). You lose **{self.bet:,}** points."
            color = discord.Color.red()
        elif player_value > dealer_value:
            # Player Wins
            winnings = self.bet * 2 # Bet + 1x winnings
            update_coins(str(self.user_id), winnings)
            status_msg = f"🎉 **YOU WIN!** ({player_value} vs {dealer_value}). You win **{self.bet:,}** points (1:1 payout)."
            color = discord.Color.green()
        elif player_value == dealer_value:
            # Push (Tie) - Return bet
            winnings = self.bet
            update_coins(str(self.user_id), winnings) # Return the bet
            status_msg = f"🤝 **PUSH!** ({player_value} vs {dealer_value}). Your bet of **{self.bet:,}** points is returned."
            color = discord.Color.dark_teal()
            
        # Update final message
        await self._update_message(status_msg, game_over=True, color=color)

    async def on_timeout(self):
        """Called when the view times out."""
        game_id = self.game_id
        # Check if the game is still active globally
        if game_id in ACTIVE_BLACKJACK_GAMES:
            # Refund the bet to the user
            update_coins(str(self.user_id), self.bet) 
            
            # Create a final embed
            embed = self.embed_msg.embeds[0]
            embed.set_field_at(2, name="Status", value=f"⏰ **Game Timed Out!** Your bet of **{self.bet:,}** points was refunded.", inline=False)
            embed.color = discord.Color.dark_grey()
            
            # Remove buttons and show timeout result
            self.clear_items()
            await self.embed_msg.edit(embed=embed, view=None)
            del ACTIVE_BLACKJACK_GAMES[game_id]


# --- BOT INITIALIZATION ---

intents = discord.Intents.default()
# CRITICAL: message_content is needed for prefix commands like !help
intents.message_content = True 
intents.members = True 

# Initialize the bot client using commands.Bot
bot = commands.Bot(command_prefix='!', intents=intents) 

async def save_data_loop():
    """Periodically saves the economy data to the file."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(60) # Save every 60 seconds
        save_data()
        print("Data saved automatically.")

@bot.event
async def on_ready():
    # Load data and start background loop
    load_data() 
    bot.loop.create_task(save_data_loop()) # Start the save loop
    
    activity_message = f"Playing with {BOT_NAME} | !help" 
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(
            name=activity_message, 
            type=discord.ActivityType.playing
        )
    )
    print(f"Bot {BOT_NAME} is online and ready.")

# --- COMMANDS ---

# --- Admin Commands ---

@bot.command(name='givecoins', help='[ADMIN] Add points to a user. Usage: !givecoins @user <amount>')
@is_admin()
async def admin_give(ctx, member: discord.Member, amount: int):
    user_id = str(member.id)
    if amount <= 0:
        return await ctx.send("Admin: Amount must be positive.")
    update_coins(user_id, amount)
    new_balance = get_profile(user_id)['coins']
    embed = discord.Embed(
        title="🛠️ Admin: Points Granted",
        description=f"**{amount:,}** points manually added to {member.mention}.",
        color=discord.Color.dark_green()
    )
    embed.add_field(name="New Balance", value=f"**{new_balance:,}** points", inline=False)
    add_custom_footer(embed)
    await ctx.send(embed=embed)

@bot.command(name='takecoins', help='[ADMIN] Remove points from a user. Usage: !takecoins @user <amount>')
@is_admin()
async def admin_take(ctx, member: discord.Member, amount: int):
    user_id = str(member.id)
    if amount <= 0:
        return await ctx.send("Admin: Amount must be positive.")
    
    if not update_coins(user_id, -amount):
        return await ctx.send(f"Admin: Could not remove **{amount:,}** points. {member.mention}'s balance would go negative.")
        
    new_balance = get_profile(user_id)['coins']
    embed = discord.Embed(
        title="🛠️ Admin: Points Removed",
        description=f"**{amount:,}** points manually removed from {member.mention}.",
        color=discord.Color.dark_red()
    )
    embed.add_field(name="New Balance", value=f"**{new_balance:,}** points", inline=False)
    add_custom_footer(embed)
    await ctx.send(embed=embed)

# --- Economy Commands ---

@bot.command(name='balance', aliases=['bal'], help='Checks your current coin balance.')
async def balance(ctx):
    profile = get_profile(str(ctx.author.id))
    embed = discord.Embed(
        title="💰 Current Balance",
        description=f"{ctx.author.mention}, you currently have **{profile['coins']:,} points**.",
        color=discord.Color.gold()
    )
    add_custom_footer(embed)
    await ctx.send(embed=embed)

@bot.command(name='give', help='Transfer points to another user. Usage: !give @user <amount>')
async def give(ctx, member: discord.Member, amount: int):
    sender_id = str(ctx.author.id)
    recipient_id = str(member.id)
    if ctx.author.id == member.id:
        return await ctx.send("You cannot give points to yourself!")
    if amount <= 0:
        return await ctx.send("You must give a positive amount!")
    if not update_coins(sender_id, -amount):
        return await ctx.send(f"{ctx.author.mention}, you don't have enough points! Your balance is {get_profile(sender_id)['coins']:,}.")
    update_coins(recipient_id, amount)
    sender_balance = get_profile(sender_id)['coins']
    recipient_balance = get_profile(recipient_id)['coins']
    embed = discord.Embed(
        title="💸 Points Transfer Successful",
        description=f"{ctx.author.mention} transferred **{amount:,}** points to {member.mention}.",
        color=discord.Color.teal()
    )
    embed.add_field(name=f"{ctx.author.display_name}'s New Balance", value=f"{sender_balance:,} points", inline=False)
    embed.add_field(name=f"{member.display_name}'s New Balance", value=f"{recipient_balance:,} points", inline=False)
    add_custom_footer(embed)
    await ctx.send(embed=embed)

@bot.command(name='roll', aliases=['r'], help='Bet on a specific number (1-6). Usage: !r <number> <bet>')
@commands.cooldown(1, COOLDOWN_GROUP_GAMBLING, commands.BucketType.user)
async def roll(ctx, guess: int, bet: int):
    user_id = str(ctx.author.id)
    if not 1 <= guess <= 6:
        return await ctx.send("You must bet on a number between 1 and 6!")
    if bet <= 0:
        return await ctx.send("You must bet a positive amount!")
    if not update_coins(user_id, -bet):
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(f"{ctx.author.mention}, you don't have enough points! Your balance is {get_profile(user_id)['coins']:,}.")

    roll_result = random.randint(1, 6) 
    if roll_result == guess:
        winnings = bet * 8
        update_coins(user_id, winnings)
        status = f"🎉 WIN! It landed on your guess, **{roll_result}**. Payout: 8x!"
        net_change = winnings - bet
        color = discord.Color.green()
    else:
        status = f"❌ LOSS! It landed on **{roll_result}**."
        net_change = -bet
        color = discord.Color.red()

    new_balance = get_profile(user_id)['coins']
    embed = discord.Embed(
        title="🎲 Dice Roll Bet (8x Payout)",
        description=f"{ctx.author.mention} bet **{bet:,}** points on the number **{guess}**.",
        color=color
    )
    embed.add_field(name="Roll Result", value=status, inline=False)
    embed.add_field(name="Net Change", value=f"**{net_change:,}** points", inline=True)
    embed.add_field(name="New Balance", value=f"**{new_balance:,}** points", inline=True)
    add_custom_footer(embed)
    await ctx.send(embed=embed)

@bot.command(name='flip', aliases=['cf'], help='Bet on Heads or Tails. Usage: !flip <H/T> <bet>')
@commands.cooldown(1, COOLDOWN_GROUP_GAMBLING, commands.BucketType.user)
async def coin_flip(ctx, side: str, bet: int):
    user_id = str(ctx.author.id)
    side = side.lower()
    if side not in ['h', 'heads', 't', 'tails']:
        return await ctx.send("Invalid guess. Please use 'H' or 'T'.")
    side = 'heads' if side.startswith('h') else 'tails'

    if bet <= 0:
        return await ctx.send("You must bet a positive amount!")
    if not update_coins(user_id, -bet):
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(f"{ctx.author.mention}, you don't have enough points! Your balance is {get_profile(user_id)['coins']:,}.")

    result = random.choice(['heads', 'tails'])
    if result == side:
        winnings = bet * 2
        update_coins(user_id, winnings)
        status = f"🎉 WIN! The coin landed on **{result.capitalize()}**."
        color = discord.Color.green()
    else:
        winnings = 0
        status = f"❌ LOSS! The coin landed on **{result.capitalize()}**."
        color = discord.Color.red()
    
    new_balance = get_profile(user_id)['coins']
    net_change = winnings - bet
    embed = discord.Embed(
        title="🪙 Coin Flip Bet (1:1 Payout)",
        description=f"{ctx.author.mention} bet **{bet:,}** on **{side.capitalize()}**.",
        color=color
    )
    embed.add_field(name="Result", value=status, inline=False)
    embed.add_field(name="Net Change", value=f"**{net_change:,}** points", inline=True)
    embed.add_field(name="New Balance", value=f"**{new_balance:,}** points", inline=True)
    add_custom_footer(embed)
    await ctx.send(embed=embed)
    
# --- REVISED LOTTERY COMMAND (NOW A SIMPLE GAMBLE) ---
@bot.command(name='lottery', aliases=['lotto', 'l'], help='A 50/50 gamble with a 2x payout (max bet 1M). Usage: !lotto <bet>')
@commands.cooldown(1, COOLDOWN_GROUP_GAMBLING, commands.BucketType.user) 
async def lottery(ctx, bet: int):
    user_id = str(ctx.author.id)
    MAX_BET = 1000000 
    
    if bet <= 0:
        return await ctx.send(f"{ctx.author.mention}, you must bet a positive amount!")
        
    if bet > MAX_BET:
        return await ctx.send(f"{ctx.author.mention}, the maximum bet is **{MAX_BET:,}** points.")
        
    if not update_coins(user_id, -bet):
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(f"{ctx.author.mention}, you don't have enough points! Your balance is {get_profile(user_id)['coins']:,}.")

    # --- Instant Winning System (50/50 Chance) ---
    # Roll a number 1-100. Win if roll >= 51 (50% chance).
    roll_result = random.randint(1, 100) 
    
    if roll_result >= 51:
        winnings = bet * 2
        update_coins(user_id, winnings) # Return bet + 1x profit
        status = f"🎉 **WON!** (Rolled {roll_result}/100)"
        net_change = winnings - bet # Profit is 1x bet
        color = discord.Color.green()
    else:
        winnings = 0
        status = f"❌ **LOST!** (Rolled {roll_result}/100)"
        net_change = -bet # Loss is -1x bet
        color = discord.Color.red()
        
    new_balance = get_profile(user_id)['coins']
    
    embed = discord.Embed(
        title="🎰 Lottery Gamble (50/50 Payout)",
        description=f"{ctx.author.mention} placed a bet on the instant lottery!",
        color=color
    )
    # Changed output fields as requested: SPEND, WON/LOSS, BALANCE
    embed.add_field(name="Amount Spent/Bet", value=f"**{bet:,}** points", inline=True)
    embed.add_field(name="Won/Loss Status", value=status, inline=True)
    embed.add_field(name="Net Change", value=f"**{net_change:,}** points", inline=False)
    embed.add_field(name="New Balance", value=f"**{new_balance:,}** points", inline=True)
    add_custom_footer(embed)
    await ctx.send(embed=embed)

@lottery.error
async def lottery_error(ctx, error):
    # This handles the cooldown error
    if isinstance(error, commands.CommandOnCooldown):
        wait_time = format_time(int(error.retry_after))
        embed = discord.Embed(
            title="⏱️ Cooldown Active",
            description=f"{ctx.author.mention}, you are on a **{COOLDOWN_GROUP_GAMBLING} second** cooldown for gambling commands. Please wait **{wait_time}** before playing again.",
            color=discord.Color.orange()
        )
        add_custom_footer(embed)
        await ctx.send(embed=embed)
    elif isinstance(error, commands.MissingRequiredArgument) or isinstance(error, commands.BadArgument):
        # If bet amount is missing or invalid
        await ctx.send(f"{ctx.author.mention}, invalid usage. Usage: `!lotto <bet>`. The bet must be a whole number up to 1,000,000.")
    else:
        # Catch all other errors
        print(f"An unexpected error occurred in !lottery: {error}")
        await ctx.send(f"An unexpected error occurred while running the gamble: `{error}`. Please try again.")

# --- Interactable Blackjack (`!blackjack` / `!bj`) ---
@bot.command(name='blackjack', aliases=['bj'], help='Play a game of Blackjack against the dealer! Usage: !bj <bet>')
@commands.cooldown(1, COOLDOWN_GROUP_GAMBLING, commands.BucketType.user)
async def blackjack(ctx, bet: int):
    user_id = str(ctx.author.id)

    # Use a combined ID to track active games per user per channel
    game_id = f"{user_id}-{ctx.channel.id}" 
    if game_id in ACTIVE_BLACKJACK_GAMES:
        game_info = ACTIVE_BLACKJACK_GAMES[game_id]
        return await ctx.send(f"{ctx.author.mention}, you already have an active Blackjack game in this channel! Please finish the game or wait for the timeout (Message ID: {game_info['msg_id']}).")

    if bet <= 0:
        return await ctx.send("You must bet a positive amount!")
    if not update_coins(user_id, -bet):
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(f"{ctx.author.mention}, you don't have enough points! Your balance is {get_profile(user_id)['coins']:,}.")

    # Game Setup
    deck = create_deck()
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]
    player_value = calculate_hand_value(player_hand)
    dealer_value = calculate_hand_value(dealer_hand)

    # --- Instant Blackjack Check ---
    if player_value == 21:
        if dealer_value == 21:
            # Push/Tie (both BlackJack)
            winnings = bet 
            update_coins(user_id, winnings)
            net_change = 0
            status_msg = f"🤝 **PUSH!** Both you and the dealer hit Blackjack. Your bet of **{bet:,}** points is returned."
            color = discord.Color.dark_teal()
        else:
            # Player BlackJack (1.5x payout)
            winnings = int(bet * 2.5) # Bet + 1.5x winnings
            update_coins(user_id, winnings)
            net_change = winnings - bet
            status_msg = f"🎉 **BLACKJACK!** You win **{int(bet * 1.5):,}** points (1.5x payout)! Total return: {winnings:,}."
            color = discord.Color.gold()
        
        new_balance = get_profile(user_id)['coins']
        
        # Send instant result message
        embed = discord.Embed(
            title="♦️ Blackjack Game (Instant Result)",
            description=f"{ctx.author.mention} bet **{bet:,}** points.",
            color=color
        )
        embed.add_field(name="Your Hand", value=f"{hand_to_string(player_hand)} (Value: {player_value})", inline=False)
        embed.add_field(name="Dealer's Hand", value=f"{hand_to_string(dealer_hand)} (Value: {dealer_value})", inline=False)
        embed.add_field(name="Status", value=status_msg, inline=False)
        embed.add_field(name="New Balance", value=f"**{new_balance:,}** points", inline=False)
        add_custom_footer(embed)
        return await ctx.send(embed=embed)
        
    # --- Start the interactive game ---
    
    embed = discord.Embed(
        title="♦️ Blackjack Game (Hit/Stand)",
        description=f"{ctx.author.mention} bet **{bet:,}** points. Choose your next move!",
        color=discord.Color.blue()
    )
    embed.add_field(name="Your Hand", value=f"{hand_to_string(player_hand)} (Value: {player_value})", inline=False)
    # Dealer's second card is hidden initially
    embed.add_field(name="Dealer's Hand", value=f"{hand_to_string(dealer_hand, hide_dealer_card=True)} (Value: {dealer_hand[0][1]})", inline=False)
    embed.add_field(name="Status", value="Awaiting your move...", inline=False)
    add_custom_footer(embed)

    msg = await ctx.send(embed=embed)
    view = BlackjackView(ctx.author.id, bet, deck, player_hand, dealer_hand, msg, game_id)
    
    # Store Game State
    ACTIVE_BLACKJACK_GAMES[game_id] = {
        'msg_id': msg.id,
        'user_id': ctx.author.id,
        'channel_id': ctx.channel.id,
        'bet': bet
    }
    
    # Update the view's embed_msg reference and send it
    view.embed_msg = msg 
    await msg.edit(view=view)

    # Wait for the game to finish
    await view.wait()
    
    # Ensure game state is removed even if view.wait() completes normally but cleanup was missed (unlikely)
    if game_id in ACTIVE_BLACKJACK_GAMES:
        del ACTIVE_BLACKJACK_GAMES[game_id]


@blackjack.error
async def blackjack_error(ctx, error):
    # Ensure cooldown is reset if the error happened before the game started properly
    ctx.command.reset_cooldown(ctx) 
    
    if isinstance(error, commands.CommandOnCooldown):
        wait_time = format_time(int(error.retry_after))
        embed = discord.Embed(
            title="⏱️ Cooldown Active",
            description=f"{ctx.author.mention}, you are on a **{COOLDOWN_GROUP_GAMBLING} second** cooldown for gambling commands. Please wait **{wait_time}** before playing again.",
            color=discord.Color.orange()
        )
        add_custom_footer(embed)
        await ctx.send(embed=embed)
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"{ctx.author.mention}, invalid usage. Usage: `!bj <bet>`. Please ensure the bet is a whole number.")
    else:
        # If an unexpected error occurs, manually clean the game lock (if it was created)
        game_id = f"{ctx.author.id}-{ctx.channel.id}"
        if game_id in ACTIVE_BLACKJACK_GAMES:
            # Refund the bet if we can determine it from the game state before deletion
            if 'bet' in ACTIVE_BLACKJACK_GAMES[game_id]:
                update_coins(str(ctx.author.id), ACTIVE_BLACKJACK_GAMES[game_id]['bet'])
                await ctx.send(f"An unexpected error occurred and the game had to be cancelled. Your bet of **{ACTIVE_BLACKJACK_GAMES[game_id]['bet']:,}** points has been refunded.")
            del ACTIVE_BLACKJACK_GAMES[game_id]
        
        print(f"An unexpected error occurred in !blackjack: {error}")
        await ctx.send(f"An unexpected error occurred while running the game: `{error}`. Please try again.")

# --- Slot Machine (`!slots`) ---
@bot.command(name='slots', aliases=['s'], help='Spin the slot machine! Payouts up to 10x. Usage: !s <bet>')
@commands.cooldown(1, COOLDOWN_GROUP_GAMBLING, commands.BucketType.user)
async def slots(ctx, bet: int):
    user_id = str(ctx.author.id)

    if bet <= 0:
        return await ctx.send("You must bet a positive amount!")
    if not update_coins(user_id, -bet):
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(f"{ctx.author.mention}, you don't have enough points! Your balance is {get_profile(user_id)['coins']:,}.")

    SYMBOLS = [
        {'emoji': '💎', 'name': 'Diamond', 'weight': 5},
        {'emoji': '🔔', 'name': 'Bell', 'weight': 10},
        {'emoji': '🍋', 'name': 'Lemon', 'weight': 25},
        {'emoji': '🍒', 'name': 'Cherry', 'weight': 60},
    ]
    population = [s['emoji'] for s in SYMBOLS]
    weights = [s['weight'] for s in SYMBOLS]
    spin = random.choices(population, weights, k=3)
    result_display = f"| **{' | '.join(spin)}** |"
    counts = {symbol: spin.count(symbol) for symbol in population}
    payout = 0
    status = "❌ LOSS! No winning combination."
    color = discord.Color.red()

    if counts['💎'] == 3:
        payout = 10.0
        status = "🎉 **JACKPOT!** Three Diamonds (10x Payout)!"
        color = discord.Color.gold()
    elif counts['🔔'] == 3:
        payout = 5.0
        status = "🥳 **BIG WIN!** Three Bells (5x Payout)!"
        color = discord.Color.green()
    elif counts['🍋'] == 3:
        payout = 2.0
        status = "✨ WIN! Three Lemons (2x Payout)!"
        color = discord.Color.green()
    elif counts['🍒'] == 3:
        payout = 1.0
        status = "✅ WIN! Three Cherries (1x Payout)!"
        color = discord.Color.green()
    elif counts['🍒'] == 2:
        payout = 0.5 
        status = "🤏 SMALL WIN! Two Cherries (0.5x Payout)!"
        color = discord.Color.light_grey()

    winnings = int(bet * payout) + (bet if payout > 0 else 0)
    if winnings > 0:
        update_coins(user_id, winnings)

    new_balance = get_profile(user_id)['coins']
    net_change = winnings - bet

    embed = discord.Embed(
        title="🎰 Slot Machine Fun",
        description=f"{ctx.author.mention} bet **{bet:,}** points.",
        color=color
    )
    embed.add_field(name="Result", value=result_display, inline=False)
    embed.add_field(name="Status", value=status, inline=False)
    embed.add_field(name="Net Change", value=f"**{net_change:,}** points", inline=True)
    embed.add_field(name="New Balance", value=f"**{new_balance:,}** points", inline=True)
    add_custom_footer(embed)
    await ctx.send(embed=embed)


# --- Cooldown Rewards ---

@bot.command(name='daily', help='Claim your daily point reward (500-1000 points).')
async def daily(ctx):
    user_id = str(ctx.author.id)
    profile = get_profile(user_id)
    COOLDOWN = 86400 # 24 hours
    current_time = time.time()
    time_elapsed = current_time - profile.get('last_daily', 0)

    if time_elapsed < COOLDOWN:
        remaining_seconds = int(COOLDOWN - time_elapsed)
        wait_time = format_time(remaining_seconds)
        embed = discord.Embed(
            title="⏱️ Daily Cooldown",
            description=f"{ctx.author.mention}, you must wait **{wait_time}** before claiming your daily reward again.",
            color=discord.Color.orange()
        )
        add_custom_footer(embed)
        return await ctx.send(embed=embed)

    reward_amount = random.randint(500, 1000)
    update_coins(user_id, reward_amount)
    profile['last_daily'] = current_time
    new_balance = profile['coins']
    
    embed = discord.Embed(
        title="☀️ Daily Reward Claimed!",
        description=f"{ctx.author.mention}, you successfully claimed **{reward_amount:,}** points!",
        color=discord.Color.gold()
    )
    embed.add_field(name="New Balance", value=f"**{new_balance:,}** points", inline=False)
    add_custom_footer(embed)
    await ctx.send(embed=embed)

@bot.command(name='weekly', help='Claim your weekly point reward (5000-10000 points).')
async def weekly(ctx):
    user_id = str(ctx.author.id)
    profile = get_profile(user_id)
    COOLDOWN = 604800 # 7 days
    current_time = time.time()
    time_elapsed = current_time - profile.get('last_weekly', 0)

    if time_elapsed < COOLDOWN:
        remaining_seconds = int(COOLDOWN - time_elapsed)
        wait_time = format_time(remaining_seconds)
        embed = discord.Embed(
            title="⏱️ Weekly Cooldown",
            description=f"{ctx.author.mention}, you must wait **{wait_time}** before claiming your weekly reward again.",
            color=discord.Color.orange()
        )
        add_custom_footer(embed)
        return await ctx.send(embed=embed)

    reward_amount = random.randint(5000, 10000)
    update_coins(user_id, reward_amount)
    profile['last_weekly'] = current_time
    new_balance = profile['coins']

    embed = discord.Embed(
        title="💎 Weekly Mega Reward Claimed!",
        description=f"{ctx.author.mention}, you successfully claimed a massive **{reward_amount:,}** points!",
        color=discord.Color.fuchsia()
    )
    embed.add_field(name="New Balance", value=f"**{new_balance:,}** points", inline=False)
    add_custom_footer(embed)
    await ctx.send(embed=embed)


# --- Poke Commands ---

@bot.command(name='hunt', help='Go out and catch a random Poke! (60s cooldown)')
async def hunt(ctx):
    user_id = str(ctx.author.id)
    profile = get_profile(user_id)
    COOLDOWN = 60 # 60 seconds
    current_time = time.time()
    time_elapsed = current_time - profile.get('last_hunt', 0)

    if time_elapsed < COOLDOWN:
        remaining_seconds = int(COOLDOWN - time_elapsed)
        wait_time = format_time(remaining_seconds)
        embed = discord.Embed(
            title="⏱️ Hunt Cooldown",
            description=f"{ctx.author.mention}, you must wait **{wait_time}** before hunting again.",
            color=discord.Color.red()
        )
        add_custom_footer(embed)
        return await ctx.send(embed=embed)

    caught_poke = get_random_poke()
    poke_name = caught_poke['name']
    poke_type = caught_poke['type']
    rarity_code = caught_poke['r']
    rarity_info = RARITY_WEIGHTS[rarity_code]

    profile['poke_inventory'][poke_name] = profile['poke_inventory'].get(poke_name, 0) + 1
    profile['last_hunt'] = current_time
    emoji = POKE_TYPES.get(poke_type, '❓')

    embed = discord.Embed(
        title="🎉 Wild Poke Caught!",
        description=f"Congratulations, {ctx.author.mention}! You successfully caught a **{poke_name}**!",
        color=rarity_info['color']
    )
    embed.add_field(name="Details", value=f"**Rarity:** {rarity_info['name']}\n**Type:** {emoji} {poke_type}", inline=False)
    embed.set_thumbnail(url="https://placehold.co/100x100/3e7d4a/ffffff?text=Poke")
    add_custom_footer(embed)
    await ctx.send(embed=embed)

@bot.command(name='zoo', aliases=['z', 'inv', 'inventory'], help='View all the Poke you have collected. (250+ species!)')
async def zoo(ctx):
    user_id = str(ctx.author.id)
    profile = get_profile(user_id)
    inventory = profile['poke_inventory']

    if not inventory:
        embed = discord.Embed(
            title="🐾 Your Poke Zoo (Inventory)",
            description=f"{ctx.author.mention}, your Poke zoo is empty! Go out and `!hunt` to catch some!",
            color=discord.Color.greyple()
        )
        add_custom_footer(embed)
        return await ctx.send(embed=embed)

    unique_count = len(inventory)
    total_count = sum(inventory.values())
    grouped_inventory = {t: [] for t in POKE_TYPES.keys()}
    poke_map = {p['name']: p for p in POKE_DATA}

    for name, count in sorted(inventory.items()):
        poke_info = poke_map.get(name)
        if poke_info:
            rarity_name = RARITY_WEIGHTS[poke_info['r']]['name']
            entry = f"**{name}** ({rarity_name}) [x{count:,}]"
            grouped_inventory[poke_info['type']].append(entry)

    embed = discord.Embed(
        title="🐾 Your Poke Zoo (Inventory)",
        description=f"**Total Species:** {unique_count}/{len(POKE_DATA)} (Catch 'em all!)\n**Total Count:** {total_count:,} Poke collected.",
        color=discord.Color.dark_blue()
    )
    
    # Construct fields for the inventory
    for type_name, poke_list in grouped_inventory.items():
        if poke_list:
            emoji = POKE_TYPES.get(type_name, '❓')
            field_name = f"{emoji} {type_name} ({len(poke_list)} Collected)"
            field_value = "\n".join(poke_list)
            if len(field_value) > 1024: 
                field_value = field_value[:1000] + "..."
            embed.add_field(name=field_name, value=field_value, inline=False)

    add_custom_footer(embed)
    await ctx.send(embed=embed)

@bot.command(name='rarity', help='Shows the catch probability for each Poke rarity level.')
async def rarity(ctx):
    rarity_list = []
    for code, data in RARITY_WEIGHTS.items():
        percent = (data['weight'] / TOTAL_WEIGHT) * 100
        odds = f"1 in {int(TOTAL_WEIGHT / data['weight']):,}" if data['weight'] > 0 else "Extremely Rare"
        poke_count = len([p for p in POKE_DATA if p['r'] == code])
        rarity_list.append(f"**{data['name']}**: ({poke_count} species)\n\tChance: **{percent:.2f}%** ({odds})\n")

    embed = discord.Embed(
        title="✨ Poke Rarity Breakdown (250 Species)",
        description="The chance of catching a Poke depends on its rarity level when you `!hunt`.",
        color=discord.Color.from_rgb(173, 216, 230)
    )
    embed.add_field(name="Catch Probabilities", value="\n".join(rarity_list), inline=False)
    add_custom_footer(embed)
    await ctx.send(embed=embed)


# --- Utility Commands ---

@bot.command(name='hug', help='Hug another user! Usage: !hug @user')
async def hug(ctx, member: discord.Member):
    if member.id == ctx.author.id:
        return await ctx.send(f"Aww, {ctx.author.mention} attempts to hug themselves! You need a friend for that.")

    embed = discord.Embed(
        description=f"🤗 **{ctx.author.display_name}** gives **{member.display_name}** a warm hug!",
        color=discord.Color.from_rgb(255, 192, 203) # Pink
    )
    add_custom_footer(embed)
    await ctx.send(embed=embed)

@bot.command(name='8ball', aliases=['8b'], help='Ask the Magic 8-Ball a yes/no question. Usage: !8b [question]')
async def eight_ball(ctx, *, question: str):
    responses = [
        "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes definitely.", 
        "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.", 
        "Yes.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.", 
        "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.", 
        "Don't count on it.", "My reply is no.", "My sources say no.", 
        "Outlook not so good.", "Very doubtful."
    ]
    response = random.choice(responses)
    embed = discord.Embed(
        title="🎱 The Magic 8-Ball Answers",
        description=f"**Question:** {question}\n\n**Answer:** {response}",
        color=discord.Color.dark_purple()
    )
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    add_custom_footer(embed)
    await ctx.send(embed=embed)

@bot.command(name='choose', aliases=['pick'], help='Choose one option from a list. Usage: !choose option1, option2, option3')
async def choose(ctx, *, choices: str):
    option_list = [c.strip() for c in choices.split(',') if c.strip()]
    
    if len(option_list) < 2:
        return await ctx.send("Please provide at least two options separated by commas (e.g., `!choose red, blue, green`).")

    chosen = random.choice(option_list)
    embed = discord.Embed(
        title="🤔 The Decision Has Been Made",
        description=f"Out of your options, I choose... **{chosen}**!",
        color=discord.Color.orange()
    )
    embed.add_field(name="Your Options", value=", ".join(option_list), inline=False)
    add_custom_footer(embed)
    await ctx.send(embed=embed)

# --- Leaderboard (`!leaderboard`) ---
@bot.command(name='leaderboard', aliases=['lbd'], help='Shows the top users by total coin balance.')
async def leaderboard(ctx):
    leader_data = []
    # Filter out users who haven't interacted much or have 0 coins
    for user_id, profile in USER_ECONOMY_DB.items():
        if profile.get('coins', 0) > 0:
            leader_data.append((user_id, profile['coins']))

    leader_data.sort(key=lambda item: item[1], reverse=True)
    top_10 = leader_data[:10]
    
    if not top_10:
        embed = discord.Embed(
            title="🏆 Leaderboard",
            description="The leaderboard is currently empty. Start earning some points!",
            color=discord.Color.dark_grey()
        )
        add_custom_footer(embed)
        return await ctx.send(embed=embed)

    leaderboard_text = ""
    rank = 1
    for user_id, coins in top_10:
        user = bot.get_user(int(user_id))
        display_name = user.display_name if user else f"User ID: {user_id}"
        
        if str(ctx.author.id) == user_id:
            leaderboard_text += f"**#{rank}. {display_name}: {coins:,} points** 👑\n"
        else:
            leaderboard_text += f"#{rank}. {display_name}: {coins:,} points\n"
        rank += 1

    embed = discord.Embed(
        title="👑 Global Points Leaderboard (Top 10)",
        description=leaderboard_text,
        color=discord.Color.from_rgb(255, 215, 0) # Gold color
    )
    
    # Show user's own rank if not in the top 10
    author_rank = next(((i + 1, coins) for i, (uid, coins) in enumerate(leader_data) if uid == str(ctx.author.id)), None)
    if author_rank and author_rank[0] > 10:
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        embed.add_field(name="Your Rank", value=f"**#{author_rank[0]}.** {ctx.author.display_name}: {author_rank[1]:,} points", inline=False)
    
    add_custom_footer(embed)
    await ctx.send(embed=embed)

# --- Custom Help Command (Updated Format) ---

bot.remove_command('help')

def format_commands(cmd_list):
    """Formats command list to show !name, !alias1, !alias2: Description (No verbose aliases)"""
    command_list = []
    for command in cmd_list:
        # Get all names/aliases as a list of strings starting with '!'
        name_and_aliases = [f"!{command.name}"] + [f"!{a}" for a in command.aliases]
        # Join them with a comma and space: !name, !alias1, !alias2
        command_line = f"`{', '.join(name_and_aliases)}`: {command.help.split('. Usage:')[0]}"
        command_list.append(command_line)
    return "\n".join(command_list) or "No commands in this category."

@bot.command(name='help', help='Shows this categorized command list.')
async def help_command(ctx):
    embed = discord.Embed(
        title="📚 Bot Command List",
        description="Here are all the commands you can use. The prefix is `!`.",
        color=discord.Color.dark_teal()
    )

    all_commands = bot.commands
    
    # Note: Updated help for 'lottery'
    categories = {
        "🛡️ Admin Commands": [],
        "💰 Economy & Gambling": [],
        "🐾 Poke Collection": [],
        "🛠️ Utility & Fun": []
    }

    # Group commands manually since we aren't using Cogs
    for command in all_commands:
        if command.name == 'help':
            continue
        
        if command.name in ['givecoins', 'takecoins']:
            categories["🛡️ Admin Commands"].append(command)
        elif command.name in ['balance', 'give', 'roll', 'flip', 'blackjack', 'slots', 'daily', 'weekly', 'leaderboard', 'lottery']:
            categories["💰 Economy & Gambling"].append(command)
        elif command.name in ['hunt', 'zoo', 'rarity']:
            categories["🐾 Poke Collection"].append(command)
        elif command.name in ['8ball', 'choose', 'hug']: 
            categories["🛠️ Utility & Fun"].append(command)

    for name, cmd_list in categories.items():
        if cmd_list:
            embed.add_field(name=name, value=format_commands(cmd_list), inline=False)

    add_custom_footer(embed)
    await ctx.send(embed=embed)


# --- 4. Setup for 24/7 Uptime ---
app = Flask(__name__)

@app.route('/')
def home():
    """Endpoint for the external monitoring service (e.g., Uptime Robot) to ping."""
    return "Bot is alive! 🤖"

def run_flask_server():
    """Function to run the Flask server in a separate thread."""
    print("Starting web server thread...")
    # Set Flask logging to ERROR only to keep the console clean
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    try:
        app.run(host='0.0.0.0', port=os.getenv('PORT', 8080))
    except Exception as e:
        print(f"Flask server failed to start: {e}")


# --- 5. Running the Bot ---

async def main():
    """ Handles setup and running the bot and web server. """
    t = Thread(target=run_flask_server)
    t.daemon = True
    t.start()
    
    BOT_TOKEN = os.getenv('DISCORD_TOKEN')

    if BOT_TOKEN is None:
        print("FATAL ERROR: DISCORD_TOKEN environment variable is not set.")
        save_data() 
        exit(1)

    # Start the Discord bot
    await bot.start(BOT_TOKEN)

if __name__ == '__main__':
    # Load data before running the loop
    load_data()
    # Run the main async function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot shutting down. Saving final data...")
        save_data()
        print("Data saved. Goodbye.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        save_data()
