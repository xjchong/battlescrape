import argparse
import json
import pyperclip
import re
import urllib.request


"""
Setup command line arguments.
"""
arg_parser = argparse.ArgumentParser(description="Scrapes frame data from a battlesnake game url. Supports copying output to the clipboard, and formatting the output in various styles. Requires pyperclip to be installed.")
arg_parser.add_argument(
    "game_url",
    help="url for the game, of the format: https://play.battlesnake.com/g/<game_id>/"
)
arg_parser.add_argument(
    "turn",
    help="which turn of the game to find a frame for"
)
arg_parser.add_argument(
    "-d", "--display",
    dest="display_option",
    default="board",
    choices=["board", "frame", "all", "none"],
    help="which information to display"
)
arg_parser.add_argument(
    "-c", "--copy",
    dest="copy_option",
    default="frame",
    choices=["frame", "board", "all", "none"],
    help="copy output to clipboard"
)
arg_parser.add_argument(
    "-f", "--format", 
    dest="format_option",
    default="none",
    choices=["none", "java", "python"],
    help="format for the board"
)
args = arg_parser.parse_args()

def get_frame_string(frame_json):
    """
    Example:
        frame_json: { Turn, [Snakes], [Food], [Hazards] }
        -> frame_json in escaped string representation
    """
    frame_string = json.dumps(frame_json)
    frame_string_escaped = re.sub(r'([\"])', r'\\\1', frame_string)

    return f"\"{frame_string_escaped}\""


def scrape_frame(game_id, turn):
    """
    Example:
        game_id: 746f9c99-1360-45da-878c-2ee0b6bc435a
        turn: 60
        -> Frame object { Turn, [Snakes], [Food], [Hazards] }

    """
    frames_url = "https://engine.battlesnake.com/games/" + game_id + "/frames?offset=" + turn + "&limit=1"
    response = urllib.request.urlopen(frames_url)
    frames_json = json.loads(response.read().decode(response.info().get_param('charset') or 'utf-8'))
    return frames_json["Frames"][0]


def scrape_game(game_id):
    """
    Example:
        game_id: 746f9c99-1360-45da-878c-2ee0b6bc435a
        -> Game object { ID, Width, Height }
    """
    engine_url = "https://engine.battlesnake.com/games/" + game_id
    response = urllib.request.urlopen(engine_url)
    game_json = json.loads(response.read().decode(response.info().get_param('charset') or 'utf-8'))

    return game_json["Game"]


def get_body_char(body, index):
    """
    Example:
        body: [{ X: 0, Y: 0 }, { X: 0, Y: 1 }, { X: 1, Y: 1 }]
        index: 1
        -> '╔'
    """
    prev_body_pos, target_body_pos, next_body_pos = body[index - 1], body[index], body[index + 1]
    prev_x, prev_y = prev_body_pos["X"], prev_body_pos["Y"]
    target_x, target_y = target_body_pos["X"], target_body_pos["Y"]
    next_x, next_y = next_body_pos["X"], next_body_pos["Y"]

    # Check if vertical or horizontal body segment.
    if prev_x == next_x:
        # Vertical body segment.
        return '║ '
    elif prev_y == next_y:
        # Horizontal body segment.
        return '══'
    else:
        # Other body segment.
        # Get the midpoint between the prev and next body positions.
        # Comparing this relative to the target position will indicate 
        # which L-junction to use.
        prev_next_x, prev_next_y = (prev_x + next_x) / 2, (prev_y + next_y) / 2

        if target_x < prev_next_x and target_y < prev_next_y:
            return '╚═'
        elif target_x < prev_next_x:
            return '╔═'
        elif target_y > prev_next_y:
            return '╗ '
        else:
            return '╝ '


def validate_snake_names(snakes):
    """
    If any of the snakes do not have a valid name, i.e., a blank name, 
    then set the snake's name as "UNKNOWN"
    """
    for snake in snakes:
        if not snake["Name"]:
            snake["Name"] = "UNKNOWN"


def set_snake_chars(snakes):
    """
    Each snake needs to be represented by a unique alphabet.
    By default this would be the first letter of the snake's name.
    However, if there are multiple snakes with the same first letter,
    use the next letter in their name, or if they have identical names,
    start going through the alphabet for any unused letters.
    """
    used_chars = []
    conflict_snakes = []

    # First handle snakes that do not have any conflict. 
    # Letters are first-come, first-served, but there is a preference
    # for allowing snakes to use their first letter, so we go through
    # all the snakes' first letters to begin with.
    for snake in snakes:
        char = snake["Name"][0].upper()

        if char in used_chars:
            conflict_snakes.append(snake)
        else:
            snake["Char"] = char
            used_chars.append(char)
    
    # Any snakes remaining had some conflict with another snake
    # for using their first letter. Deal with them now.
    for snake in conflict_snakes:
        name = snake["Name"]
        char_index = 0
        char = name[char_index].upper()

        while char in used_chars:
            char_index = char_index + 1

            if char_index >= len(name):
                # If we have run out of characters to try in the name,
                # go through the alphabet.
                alphabet_index = 97 # 'a' starts from 97.

                while char in used_chars:
                    char = chr(alphabet_index)
                    alphabet_index = alphabet_index + 1
            else:
                char = name[char_index].upper()

        snake["Char"] = char
        used_chars.append(char)

    
def concat(string, added_string, end="\n"):
    """
    Example:
        string: "Hello"
        added_string: " world"
        end: "!"
        -> string := "Hello world!"
    """
    return string + added_string + end


def get_board_string(game_id, turn):
    """
    Output:
        https://board.battlesnake.com/?engine=https%3A//engine.battlesnake.com&game=12345-abcde&turn=5
        . . . .  Turn 5
        * ╔ a B 
        b A . ║  [A] Alice (100) <3>
        ╚═════╝  [B] Bob (85) <4> "I'm here to win!"
    """
    board_string = ""
    game = scrape_game(game_id)
    frame = scrape_frame(game_id, turn)
    width = game["Width"]
    height = game["Height"]
    foods = [food for food in frame["Food"]]
    snakes = [snake for snake in frame["Snakes"] if snake["Death"] is None]

    # We need to ensure that there is a name assigned to each snake.
    validate_snake_names(snakes)

    # Add a field to each snake for the character that will represent them.
    set_snake_chars(snakes)

    # This 'bucket' will store the characters that should be printed out at each position of the board.
    board_bucket = [[". "] * width for _ in range(height)]

    # Add food to the board.
    for food in foods:
        board_bucket[food["Y"]][food["X"]] = "% "

    # Add snakes to the board.
    for snake in snakes:
        char, body, length = snake["Char"], snake["Body"], len(snake["Body"])

        for index, body_pos in enumerate(body):
            x, y = body_pos["X"], body_pos["Y"]

            if index == 0:
                # Head position.
                head_char = char.upper()

                if length > 2 and body[index + 1]["X"] == x + 1:
                    board_bucket[y][x] = f"{head_char}═"
                else:
                    board_bucket[y][x] = f"{head_char} "
            elif index == length - 1:
                # Tail position.
                tail_char = char.lower()

                if length > 2 and body[index - 1]["X"] == x + 1:
                    board_bucket[y][x] = f"{tail_char}═"
                else:
                    board_bucket[y][x] = f"{tail_char} "
            else:
                # Other body position.
                board_bucket[y][x] = get_body_char(body, index)

    # Set the format for the board.
    comment_frame_start, comment_frame_edge, comment_frame_end = "", "", ""

    if args.format_option == "java":
        comment_frame_start = "\n/**"
        comment_frame_edge = " * "
        comment_frame_end = " */\n"
    elif args.format_option == "python":
        comment_frame_start = "\n\"\"\""
        comment_frame_edge = ""
        comment_frame_end = "\"\"\"\n"

    # Start a comment frame.
    board_string = concat(board_string, comment_frame_start)

    # Add the url of the game as a header.
    board_string = concat(board_string, f"{comment_frame_edge}https://board.battlesnake.com/?engine=https%3A//engine.battlesnake.com&game={game_id}&turn={turn}")

    # Layout the board.
    for row in range(height):
        # Add comment frame edge.
        board_string = concat(board_string, comment_frame_edge, end="")

        # Layout the board row.
        for col in range(width):
            board_string = concat(board_string, board_bucket[height - row - 1][col], end="")
        
        if row == 0:
            # Add the turn of the game.
            board_string = concat(board_string, f" Turn {turn}", end="")
        elif 2 <= row < 2 + len(snakes):
            # Add information about each live snake.
            snake = snakes[row - 2]
            # If there exist multiple snakes with the same name, append the snake's ID to the name.
            name = snake['Name']
            display_name = name if all(other["Name"] != name or other["ID"] == snake["ID"] for other in snakes) else f"{name}/{snake['ID'][-6:]}"
            # If the snake has a shout for this turn, display it, otherwise omit.
            shout = f"\"{snake['Shout']}\"" if snake['Shout'] else ""
            board_string = concat(board_string, f" {snake['Char'].upper()}: {display_name} ({snake['Health']}) <{len(snake['Body'])}> {shout}", end = "")
        
        board_string = concat(board_string, "")
    
    # Finish the comment frame.
    board_string = concat(board_string, comment_frame_end, end="")

    return board_string


def main():
    game_id = args.game_url[31:-1]
    frame = scrape_frame(game_id, args.turn)
    board_string = get_board_string(game_id, args.turn)
    frame_string = get_frame_string(frame)


    # Print out the requested information.
    if args.display_option == "board":
        print(board_string)
    elif args.display_option == "frame":
        print("\n" + frame_string, end="\n\n")
    elif args.display_option == "all":
        print(board_string)
        print(frame_string, end="\n\n")

    # Copy the requested information to the clipboard.
    if args.copy_option == "board":
        pyperclip.copy(board_string)
        print("Board copied to clipboard!")
    elif args.copy_option == "frame":
        pyperclip.copy(frame_string)
        print("Frame copied to clipboard!")
    elif args.copy_option == "all":
        pyperclip.copy(board_string + "\n" + frame_string)
        print("Board and frame copied to clipboard!")


if __name__ == "__main__":
    main()