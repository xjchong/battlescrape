import battlescrape
import itertools
import pyperclip
import sys
import threading
import time


def get_test_string(test_name, board_string, frame_string, player_name, expected_moves, board_width, board_height):
    return f"""{board_string}
@Test
fun {test_name}() {{
    val frameString = {frame_string}
    assertMove(frameString, "{player_name}", listOf({', '.join(expected_moves)}), boardWidth = {board_width}, boardHeight = {board_height})
}}

"""


def display_loading(message):
    for indicator in ["", ".", "..", "...", "   "]:
        sys.stdout.write("\r" + message + indicator)
        time.sleep(0.3)
        sys.stdout.flush()
    


def build_test(test_name, game_url, turn, player_name, raw_moves, result_buffer):
    formatted_moves = [f"\"{formatted_move}\"" for formatted_move in raw_moves.split(",")]
    game_id = game_url[31:-1]
    game_json = battlescrape.scrape_game(game_id)
    board_string = battlescrape.get_board_string(game_id, turn, format_option="java")
    frame_string = battlescrape.get_frame_string(game_id, turn)
    result_buffer[0] = get_test_string(
        test_name=test_name, 
        board_string=board_string, 
        frame_string=frame_string, 
        player_name=player_name, 
        expected_moves=formatted_moves, 
        board_width=game_json["Width"], 
        board_height=game_json["Height"]
    )

def load_test():
    time.sleep(2)

def main():
    filename = sys.argv[1]
    output = ""

    with open(filename) as file:
        for line in file:
            if not line or line[0] == "#":
                continue

            test_name, game_url, _, _, _ = line.split()

            result_buffer = [None]
            args = line.split()
            args.append(result_buffer)

            build_thread = threading.Thread(name='build', target=build_test, args=args)
            build_thread.daemon = True # Allow keyboard to interrupt.
            build_thread.start()

            loading_message = f"Preparing test \"{test_name}\" with {game_url} "

            while build_thread.is_alive():
                display_loading(loading_message)

            output = output + result_buffer[0]
            print()

    print()
    print(output)
    pyperclip.copy(output)
    print("Tests copied to clipboard!")


if __name__ == "__main__":
    main()