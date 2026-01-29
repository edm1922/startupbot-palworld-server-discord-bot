import re

chat_patterns = [
    re.compile(r"\[Chat::Global\]\['(?P<author>.+?)'\s*\(UserId=.*?\)\].*?:\s*(?P<content>.*)"),
    re.compile(r"\[Chat::(?:Global)\]\['(?P<author>[^']+)'.*\].*?:\s*(?P<content>.*)"),
    re.compile(r"\[Chat::Global\]\s*\[?(?P<author>[^'\[]+?)[\s'\]]*\(UserId=.*?\)\].*?:\s*(?P<content>.*)"),
    re.compile(r"\[.*?\]\[info\] \[Chat::Global\]\['(?P<author>.+?)' \(UserId=steam_\d+, IP=.+?\)\](?:\[.*?\])*:\s*(?P<content>.+)")
]

lines = [
    "[12:38:28][info] [Chat::Global]['Your Mom' (UserId=steam_76561198105952390, IP=216.247.24.233)]: eee",
    "[12:43:35][info] [Chat::Global]['kaonbylat192' (UserId=steam_76561198339426085, IP=180.194.20.83)][Admin]: test",
]

for line in lines:
    print(f"Testing line: {line}")
    matched = False
    for i, p in enumerate(chat_patterns):
        match = p.search(line)
        if match:
            print(f"  Matched Pattern {i}: author={match.group('author')}, content={match.group('content')}")
            matched = True
            break
    if not matched:
        print("  NO MATCH")
