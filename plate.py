import re

def normalize_and_fix_plate(raw: str) -> str:
    if not raw:
        return ""
    s = raw.upper()
    s = re.sub(r"[\s\-\.\_]", "", s)          # bỏ khoảng trắng, '-', '.', '_'
    s = re.sub(r"[^A-Z0-9]", "", s)           # chỉ giữ A-Z0-9
    if len(s) < 3:
        return s

    # Heuristic fix ký tự thứ 3 (index=2) nếu nó là số (hay bị nhầm)
    ch3 = s[2]
    if ch3.isdigit():
        digit_to_letter = {
            "2": "Z",
            "0": "D",
            "5": "S",
            "8": "B",
            "1": "L",
            "4": "A",
            "6": "G",
        }
        if ch3 in digit_to_letter:
            s = s[:2] + digit_to_letter[ch3] + s[3:]
    return s

def format_plate_display(canon: str) -> str:
    if not canon:
        return ""
    s = re.sub(r"[^A-Z0-9]", "", canon.upper())

    m = re.match(r"^(\d{2})([A-Z])(\d)(\d{4})$", s)  # 29Z71140 -> 29Z7 1140
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)} {m.group(4)}"

    m = re.match(r"^(\d{2})([A-Z])(\d{4,5})$", s)    # 29A12345 -> 29A 12345
    if m:
        return f"{m.group(1)}{m.group(2)} {m.group(3)}"

    m = re.match(r"^(\d{2})([A-Z]{2})(\d{4,5})$", s) # 29AB12345 -> 29AB 12345
    if m:
        return f"{m.group(1)}{m.group(2)} {m.group(3)}"

    return s
