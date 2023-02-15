import traceback
from typing import Tuple


def stringifyTrbk(e: BaseException) -> str:
    return "\n".join(traceback.format_exception(e))


def armyDisplay(army: int) -> str:
    """
    Makes the army display text

    Under 100,000: "12.3k" or "12k" when 12,000
    Under 1,000,000: "123k" rounded
    Above 1,000,000: "1.23M" rounded
    """
    if army < 1000000:
        armydisplay = str(round(army/1000, 1))
        if armydisplay.endswith(".0") or ("." in armydisplay and len(armydisplay) > 4):
            armydisplay = armydisplay[:-2]
        return f"{armydisplay}k"
    else:  # army >= 1M
        armydisplay = str(round(army/1000000, 2))
        if armydisplay.endswith(".0"):
            armydisplay = armydisplay[:-2]
        elif armydisplay.endswith("0"):
            # This is the hundredth place. If the tenth place is 0, then floats will not include the hundredth place in a string and the previous if will catch it.
            armydisplay = armydisplay[:-1]
        return f"{armydisplay}M"


def invertColor(color: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """
    Inverts a color for the player border.
    """
    return (255 - color[0], 255 - color[1], 255 - color[2])
