from io import TextIOWrapper
from typing import Dict, Tuple
import yaml


"""
Format of the file:
1={
    position={
        3085.000 1723.000 3086.000 1730.000 3084.500 1729.000 3095.000 1724.500 3082.000 1730.000 3080.000 1736.000 0.000 0.000 
    }
    rotation={
        0.000 0.000 0.087 -0.698 0.000 0.000 0.000 
    }
    height={
        0.000 0.000 1.000 0.000 0.000 0.000 0.000 
    }
}

So we want the 3085.000 1723.000 from the 1={ because the first two are the location of the city in the province
"""


def readProvLocs(file: TextIOWrapper) -> Dict[int, Tuple[float, float]]:
    out: Dict[int, Tuple[float, float]] = {}

    id: int = None
    sub: str = ""
    for line in file:
        # Remove comments
        if "#" in line:
            line = line[:line.index("#")]

        # Handle stuff
        if "={" in line:
            key = line[:line.index("=")].strip()
            if key.isdigit():
                assert(id is None)
                id = int(key)
            else:
                assert(id is not None)
                sub = key
        elif "}" in line:
            assert(id)
            if not sub:
                id = None
            else:
                assert(sub)
                sub = ""
        elif id is not None and sub == "position" and line.strip() != "":
            # This is the line we want.
            items = line.split()
            out[id] = (float(items[0]), 2048-float(items[1]))
    return out


def saveProvLocs(file: TextIOWrapper, data: Dict[int, Tuple[float, float]]):
    yaml.dump(data, file)


if __name__ == "__main__":
    srcFile = input("Source file: ").strip('"& ')
    destFile = input("Target name: ").strip()
    destFile = f"resources/{destFile}/positions.yml"

    locs = readProvLocs(open(srcFile, "r"))
    dest = open(destFile, "w")
    saveProvLocs(dest, locs)
