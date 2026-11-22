#Coded by Jarren E. Auditor
#ADMIN PASSWORD: 12345
import base64
import itertools
import math
import os
import random
import struct
import sys
import time
import tkinter as tk
import tkinter.font as tkfont
import zlib
from datetime import datetime

IS_WINDOWS = sys.platform.startswith("win")
if IS_WINDOWS:
    import ctypes

HERE = os.path.dirname(os.path.abspath(__file__))
MASTER_FILE = os.path.join(HERE, "master_list.txt")
CARD_FILE = "atm_card.txt"
ADMIN_PASSWORD = "12345"
MAX_AMOUNT = 1_000_000_000


class Account:
    def __init__(self, account_no="", account_name="", birthday="",
                 contact_number="", balance=0.0, encrypted_pin=""):
        self.account_no = account_no
        self.account_name = account_name
        self.birthday = birthday
        self.contact_number = contact_number
        self.balance = balance
        self.encrypted_pin = encrypted_pin


class Node:
    def __init__(self, data):
        self.data = data
        self.next = None


class ATMSystem:
    def __init__(self, master_file=MASTER_FILE):
        self.head = None
        self.master_file = master_file
        random.seed(time.time())
        self.retrieve()

    def locate(self, acc_no):
        p = self.head
        while p is not None:
            if p.data.account_no == acc_no:
                return p
            p = p.next
        return None

    def all_accounts(self):
        out, p = [], self.head
        while p is not None:
            out.append(p.data)
            p = p.next
        return out

    def generate_account_no(self):
        while True:
            acc_no = str(random.randint(1000, 9999))
            if self.locate(acc_no) is None:
                return acc_no

    @staticmethod
    def encrypt_pin(pin):
        return "".join(str((int(c) + 3) % 10) for c in pin)

    @staticmethod
    def is_valid_birthday(bday):
        try:
            datetime.strptime(bday, "%m/%d/%Y")
        except ValueError:
            return False
        return len(bday) == 10

    @staticmethod
    def is_valid_contact(contact):
        return len(contact) == 11 and contact.isdigit()

    @staticmethod
    def is_valid_pin(pin):
        return len(pin) == 4 and pin.isdigit()

    @staticmethod
    def is_valid_amount(amount):
        return math.isfinite(amount) and 0 < amount <= MAX_AMOUNT

    def drives(self):
        """Paths of every inserted flash drive."""
        found = []
        if IS_WINDOWS:
            mask = ctypes.windll.kernel32.GetLogicalDrives()
            for i in range(26):
                if mask & (1 << i):
                    path = chr(ord("A") + i) + ":\\"
                    if ctypes.windll.kernel32.GetDriveTypeW(path) == 2:
                        found.append(path)
        return found

    def card_text(self, drive):
        try:
            with open(os.path.join(drive, CARD_FILE), "r") as f:
                return f.read()
        except OSError:
            return None

    def read_card(self, drive):
        text = self.card_text(drive)
        parts = text.split() if text else []
        if len(parts) != 2:
            return None
        acc_no, pin = parts
        if len(acc_no) == 4 and acc_no.isdigit() and len(pin) == 4 and pin.isdigit():
            return acc_no, pin
        return None

    def write_card(self, drive, acc_no, encrypted_pin):
        try:
            with open(os.path.join(drive, CARD_FILE), "w") as f:
                f.write(f"{acc_no} {encrypted_pin}\n")
            return True
        except OSError:
            return False

    def restore_card(self, drive, old_text):
        path = os.path.join(drive, CARD_FILE)
        try:
            if old_text is None:
                os.remove(path)
            else:
                with open(path, "w") as f:
                    f.write(old_text)
        except OSError:
            pass

    def card_drive(self):
        for d in self.drives():
            if self.read_card(d):
                return d
        return ""

    def blank_drive(self):
        for drive in self.drives():
            card_path = os.path.join(drive, CARD_FILE)

        # Only allow USB drives without an existing card file
        if not os.path.exists(card_path):
            return drive

        return ""

    def card_state(self):
        d = self.card_drive()
        if d:
            return "card", d
        found = self.drives()
        return ("blank", found[0]) if found else ("none", "")

    def card_matches(self, acc_no):
        d = self.card_drive()
        card = self.read_card(d) if d else None
        return bool(card and card[0] == acc_no)

    def create_account(self, name, birthday, contact, deposit, pin):
        name = name.strip()
        if not name or "," in name:
            return False, "Account name cannot be empty or contain commas.", None
        if not self.is_valid_birthday(birthday):
            return False, "Invalid birthday! Use a real date as MM/DD/YYYY (e.g., 07/16/2006).", None
        if not self.is_valid_contact(contact):
            return False, "Invalid contact number! Must be exactly 11 digits (numbers only).", None
        if not math.isfinite(deposit) or deposit < 5000 or deposit > MAX_AMOUNT:
            return False, "Initial deposit must be \u20b15,000.", None
        if not self.drives():
            return False, "No flash drive detected. Please insert a USB card.", None

        drive = self.blank_drive()

        if not drive:
            return False, "This USB card is already assigned to an account. Please insert an unregistered USB card.", None
        drive = self.blank_drive()
        if not drive:
            return False, "No flash drive detected. Registration cannot be completed without a card.", None

        old_card = self.card_text(drive)
        acc = Account(self.generate_account_no(), name, birthday, contact,
                      round(deposit, 2), self.encrypt_pin(pin))
        if not self.write_card(drive, acc.account_no, acc.encrypted_pin):
            return False, "Could not write the card file to " + drive + "\nRegistration was not completed.", None

        node = Node(acc)
        node.next = self.head
        self.head = node
        if not self.save():
            self.head = node.next
            self.restore_card(drive, old_card)
            return False, "Could not save the account to disk, so registration was cancelled.", None
        return True, "", acc.account_no

    def load_card_account(self):
        if not self.drives():
            return None, "No card detected. Please insert your flash drive to continue."
        drive = self.card_drive()
        if not drive:
            return None, "No valid card was found on the inserted drive."
        acc_no, card_pin = self.read_card(drive)
        acc = self.locate(acc_no)
        if acc is None:
            return None, "No matching account found in the system."
        if acc.data.encrypted_pin != card_pin:
            return None, "PIN mismatch between card and record. Access denied."
        return acc_no, None

    def verify_pin(self, acc_no, pin):
        acc = self.locate(acc_no)
        return (acc is not None and self.is_valid_pin(pin)
                and self.encrypt_pin(pin) == acc.data.encrypted_pin)

    def withdraw(self, acc_no, amount):
        acc = self.locate(acc_no)
        if acc is None:
            return False, "Account not found."
        if not self.is_valid_amount(amount):
            return False, "Invalid amount. Please enter a number greater than zero."
        if amount < 100:
            return False, "Minimum withdrawal amount is \u20b1100."
        if amount % 100 != 0:
            return False, "Withdrawal amount must be in multiples of 100 (no change allowed)."
        if amount > acc.data.balance:
            return False, "Insufficient funds!"
        old = acc.data.balance
        acc.data.balance = round(old - amount, 2)
        if not self.save():
            acc.data.balance = old
            return False, "Could not save the transaction. Withdrawal cancelled."
        return True, f"Withdrawal successful!\nNew balance: \u20b1{acc.data.balance:,.2f}"

    def deposit(self, acc_no, amount):
        acc = self.locate(acc_no)
        if acc is None:
            return False, "Account not found."
        if not self.is_valid_amount(amount):
            return False, "Invalid amount. Please enter a number greater than zero."
        amount = round(amount, 2)
        if amount < 100:
            return False, "Minimum deposit amount is \u20b1100."
        old = acc.data.balance
        acc.data.balance = round(old + amount, 2)
        if not self.save():
            acc.data.balance = old
            return False, "Could not save the transaction. Deposit cancelled."
        return True, f"Deposit successful!\nNew balance: \u20b1{acc.data.balance:,.2f}"

    def fund_transfer(self, from_acc, to_acc, amount):
        sender = self.locate(from_acc)
        receiver = self.locate(to_acc.strip())
        if sender is None:
            return False, "Sender account not found."
        if receiver is None:
            return False, "Receiver account not found."
        if sender is receiver:
            return False, "Cannot transfer funds to your own account."
        if not self.is_valid_amount(amount):
            return False, "Invalid amount. Please enter a number greater than zero."
        amount = round(amount, 2)
        if amount > sender.data.balance:
            return False, "Insufficient balance to perform this transfer."
        old_s, old_r = sender.data.balance, receiver.data.balance
        sender.data.balance = round(old_s - amount, 2)
        receiver.data.balance = round(old_r + amount, 2)
        if not self.save():
            sender.data.balance, receiver.data.balance = old_s, old_r
            return False, "Could not save the transaction. Transfer cancelled."
        return True, (f"Transfer successful!\n\u20b1{amount:,.2f} sent to account {receiver.data.account_no}\n"
                      f"Your balance: \u20b1{sender.data.balance:,.2f}")

    def change_pin(self, acc_no, new_pin):
        acc = self.locate(acc_no)
        if acc is None:
            return False, "Account not found."
        if not self.is_valid_pin(new_pin):
            return False, "PIN must be exactly 4 digits (numbers only). PIN not changed."
        if not self.card_matches(acc_no):
            return False, "Insert the card that belongs to this account to change its PIN."

        drive = self.card_drive()
        old_pin, old_card = acc.data.encrypted_pin, self.card_text(drive)
        new_enc = self.encrypt_pin(new_pin)
        if not self.write_card(drive, acc_no, new_enc):
            return False, "Could not write the new PIN to your card. PIN not changed."
        acc.data.encrypted_pin = new_enc
        if not self.save():
            acc.data.encrypted_pin = old_pin
            self.restore_card(drive, old_card)
            return False, "Could not save the new PIN. PIN not changed."
        return True, "PIN successfully updated in the system and on your card!"

    def delete_account(self, acc_no):
        prev, node = None, self.head
        while node is not None and node.data.account_no != acc_no:
            prev, node = node, node.next
        if node is None:
            return False, "Account number not found."

        if prev is None:
            self.head = node.next
        else:
            prev.next = node.next
        if not self.save():
            if prev is None:
                self.head = node
            else:
                prev.next = node
            return False, "Could not save the change, so nothing was deleted."

        lines = [f"Account {acc_no} successfully deleted!"]
        drive = self.card_drive()
        card = self.read_card(drive) if drive else None
        if card and card[0] == acc_no:
            try:
                os.remove(os.path.join(drive, CARD_FILE))
                lines.append("Card file removed from the flash drive.")
            except OSError:
                lines.append("Warning: could not remove the card file from the flash drive.")
        return True, "\n".join(lines)

    def save(self):
        tmp = self.master_file + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                for d in self.all_accounts():
                    f.write(",".join([d.account_no, d.account_name, d.birthday,
                                      d.contact_number, str(d.balance), d.encrypted_pin]) + "\n")
            os.replace(tmp, self.master_file)
            return True
        except OSError:
            return False

    def retrieve(self):
        try:
            with open(self.master_file, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            return
        for line in lines:
            parts = line.split(",")
            if len(parts) != 6:
                continue
            acc_no, name, bday, contact, bal, enc = parts
            try:
                balance = float(bal)
            except ValueError:
                continue
            if not math.isfinite(balance):
                continue
            node = Node(Account(acc_no, name, bday, contact, balance, enc))
            node.next = self.head
            self.head = node

#GUI LAYOUT
W, H = 960, 720

BG = "#E9E9E9"
BLACK = "#000000"
SUB = "#333333"
GRAY = "#979797"
KEY_TXT = "#595959"
GREEN = "#2BAE66"
RED = "#E8514A"
BLUE = "#5B8DFF"
BLUE_SHADOW = "#A3B1C6"
AMBER = "#E0A100"

LEVELS = {"xl": (9, 18), "l": (6, 12), "m": (5, 9), "s": (3, 6)}


def _rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def mix(c1, c2, t):
    t = max(0.0, min(1.0, t))
    a, b = _rgb(c1), _rgb(c2)
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def short_path(p, n=30):
    return p if len(p) <= n else "\u2026" + p[-(n - 1):]


def parse_amount(text):
    try:
        value = float(text.replace(",", ""))
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _sd(px, py, hw, hh, r):
    qx, qy = abs(px) - hw + r, abs(py) - hh + r
    return min(max(qx, qy), 0.0) + math.hypot(max(qx, 0.0), max(qy, 0.0)) - r


def _zone(n, z):
    z = max(0, min(z, n // 2))
    reps = list(range(z)) + ([z] if n - 2 * z > 0 else []) + list(range(n - z, n))
    idx = []
    for i in range(n):
        if i < z:
            idx.append(i)
        elif i >= n - z:
            idx.append(len(reps) - (n - i))
        else:
            idx.append(z)
    return reps, idx


def _png(W, H, zx, zy, f, rgb, amax):
    xr, xi = _zone(W, zx)
    yr, yi = _zone(H, zy)
    rows = []
    for jj in yr:
        a = [f(ii, jj) for ii in xr]
        al = bytes(min(255, max(0, int(a[k] * amax * 255 + 0.5))) for k in xi)
        row = bytearray(4 * W)
        row[0::4] = bytes([rgb[0]]) * W
        row[1::4] = bytes([rgb[1]]) * W
        row[2::4] = bytes([rgb[2]]) * W
        row[3::4] = al
        rows.append(b"\x00" + bytes(row))
    raw = b"".join(rows[k] for k in yi)

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b""))
    return base64.b64encode(png).decode("ascii")


class NeuCanvas(tk.Canvas):
    def __init__(self, master):
        super().__init__(master, width=W, height=H, bg=BG, highlightthickness=0, bd=0)
        self._cache = {}

    def _photo(self, key, make):
        img = self._cache.get(key)
        if img is None:
            img = tk.PhotoImage(master=self, data=make())
            self._cache[key] = img
        return img

    @staticmethod
    def _size(x1, y1, x2, y2, r):
        wb, hb = int(round(x2 - x1)), int(round(y2 - y1))
        return wb, hb, max(0, min(r, wb / 2, hb / 2))

    def body(self, x1, y1, x2, y2, r, color=BG, tags=()):
        wb, hb, r = self._size(x1, y1, x2, y2, r)

        def make():
            hw, hh = wb / 2, hb / 2
            return _png(wb, hb, int(r) + 3, int(r) + 3,
                        lambda i, j: max(0.0, min(1.0, 0.5 - _sd(i + .5 - hw, j + .5 - hh, hw, hh, r))),
                        _rgb(color), 1.0)
        img = self._photo(("body", wb, hb, r, color), make)
        return self.create_image(int(round(x1)), int(round(y1)), image=img, anchor="nw", tags=tags)

    def neu_shadow(self, x1, y1, x2, y2, r, lvl="m", tags=()):
        d, blur = LEVELS[lvl]
        wb, hb, r = self._size(x1, y1, x2, y2, r)
        m = int(blur * 1.5) + 2
        sigma = blur / 2.0
        W2, H2 = wb + 2 * m, hb + 2 * m

        def maker(rgb, amax):
            def make():
                hw, hh = wb / 2, hb / 2

                def f(i, j):
                    sd = _sd(i + .5 - W2 / 2, j + .5 - H2 / 2, hw, hh, r)
                    return 0.5 * (1 - math.erf(sd / (sigma * 1.4142135)))
                z = m + int(r) + 2
                return _png(W2, H2, z, z, f, rgb, amax)
            return make
        dark = self._photo(("sh", wb, hb, r, lvl, 0), maker(_rgb(BLUE_SHADOW), 0.65))
        light = self._photo(("sh", wb, hb, r, lvl, 1), maker((255, 255, 255), 0.95))
        ix, iy = int(round(x1)) - m, int(round(y1)) - m
        self.create_image(ix + d, iy + d, image=dark, anchor="nw", tags=tags)
        self.create_image(ix - d, iy - d, image=light, anchor="nw", tags=tags)

    def panel(self, x1, y1, x2, y2, r=20, lvl="m", tags=()):
        self.neu_shadow(x1, y1, x2, y2, r, lvl, tags)
        self.body(x1, y1, x2, y2, r, BG, tags)

    def inset(self, x1, y1, x2, y2, r=15, tags=()):
        wb, hb, r = self._size(x1, y1, x2, y2, r)
        self.body(x1, y1, x2, y2, r, BG, tags)
        d, blur = 3, 7
        sigma = blur / 2.0
        for sign, rgb, amax in ((1, _rgb(BLUE_SHADOW), 0.55), (-1, (255, 255, 255), 0.95)):
            def make(sign=sign, rgb=rgb, amax=amax):
                hw, hh = wb / 2, hb / 2

                def f(i, j):
                    px, py = i + .5 - hw, j + .5 - hh
                    cov = max(0.0, min(1.0, 0.5 - _sd(px, py, hw, hh, r)))
                    if cov <= 0:
                        return 0.0
                    s = 0.5 * (1 - math.erf(_sd(px - sign * d, py - sign * d, hw, hh, r) / (sigma * 1.4142135)))
                    return cov * (1 - s)
                z = int(r) + int(1.5 * blur) + d + 3
                return _png(wb, hb, z, z, f, rgb, amax)
            img = self._photo(("in", wb, hb, r, sign), make)
            self.create_image(int(round(x1)), int(round(y1)), image=img, anchor="nw", tags=tags)

    def glyph(self, name, cx, cy, tags=()):
        if name == "back":
            self.create_line(cx + 5, cy - 12, cx - 5, cy, cx + 5, cy + 12, fill="#8C8C8C",
                             width=3, capstyle="round", joinstyle="round", tags=tags)
        elif name == "close":
            s = 4.5
            kw = dict(fill=RED, width=2, capstyle="round", tags=tags)
            self.create_line(cx - s, cy - s, cx + s, cy + s, **kw)
            self.create_line(cx + s, cy - s, cx - s, cy + s, **kw)


class App:
    PAGE_SIZE = 6

    def __init__(self):
        self.atm = ATMSystem()

        self.root = tk.Tk()
        self.root.title("ATM System")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{max(0, (sw - W) // 2)}+{max(0, (sh - H) // 2 - 20)}")

        fams = set(tkfont.families(self.root))
        self.fam = next((f for f in ("Inter", "Segoe UI", "SF Pro Display", "Helvetica Neue",
                                     "Arial") if f in fams), "Helvetica")

        self.cv = NeuCanvas(self.root)
        self.cv.pack()

        self.ids = itertools.count()
        self.btns, self.entries, self.dlg_btns = {}, {}, []
        self.modal = False
        self.page = ""
        self.session = None
        self.pin_acc, self.pin_buf, self.attempts = None, "", 0
        self.admin_page = 0

        self.root.bind("<Key>", self.on_key)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.show_home()
        self.poll_card()

    def run(self):
        self.root.mainloop()

    def quit(self):
        self.atm.save()
        self.root.destroy()

    def F(self, size, bold=False):
        return (self.fam, -size, "bold" if bold else "normal")

    def t(self, x, y, s, size=14, bold=False, fill=BLACK, anchor="nw", tags=(), width=None):
        kw = dict(text=s, font=self.F(size, bold), fill=fill, anchor=anchor, tags=tags)
        if width:
            kw["width"] = width
        return self.cv.create_text(x, y, **kw)

    def clear(self, page):
        self.cv.delete("all")
        for e, _ in self.entries.values():
            e.destroy()
        self.entries, self.btns, self.dlg_btns = {}, {}, []
        self.modal = False
        self.page = page
        self.cv.configure(cursor="")

    def card(self):
        self.cv.panel(74, 144, 869, 686, r=20, lvl="xl")

    CARD_STATES = {"card": (GREEN, "Card Detected"),
                   "blank": (AMBER, "Blank Drive Detected"),
                   "none": (RED, "No Card Detected")}

    def refresh_card_status(self):
        state, path = self.atm.card_state()
        color, title = self.CARD_STATES[state]
        self.cv.itemconfigure("card_dot", fill=color)
        self.cv.itemconfigure("card_text", text=title)
        self.cv.itemconfigure("card_path", text=short_path(path) if path else "Insert a flash drive")

    def poll_card(self):
        try:
            self.refresh_card_status()
            if self.session and not self.modal and not self.atm.card_matches(self.session):
                self.session = None
                self.dialog("Card removed", "Your card was removed or changed, so the session was ended.",
                            "error", [("OK", self.show_home)])
        finally:
            self.root.after(1000, self.poll_card)

    def status_pill(self):
        self.cv.panel(653, 34, 916, 104, r=20, lvl="l")
        self.cv.create_oval(669, 61, 686, 78, fill=RED, outline="", tags="card_dot")
        self.t(698, 46, "", 15, True, tags="card_text")
        self.t(698, 69, "", 12, False, SUB, tags="card_path")
        self.refresh_card_status()

    def header(self, title, back=None):
        if back:
            self.button(74, 40, 166, 104, cmd=back, r=20, style="l",
                        decor=lambda dx, dy, tg: self.cv.glyph("back", 120 + dx, 72 + dy, tg))
            self.t(185, 55, title, 32, True)
        else:
            self.t(44, 54, title, 32, True)
        self.status_pill()

    def button(self, x1, y1, x2, y2, text=None, cmd=None, r=20, style="l",
               decor=None, size=16, bold=True, fg=BLACK, modal=False, tags=()):
        bid = "b%d" % next(self.ids)
        self.btns[bid] = dict(box=(x1, y1, x2, y2), text=text, cmd=cmd, r=r, style=style,
                              decor=decor, size=size, bold=bold, fg=fg, modal=modal,
                              tags=tuple(tags))
        self._paint(bid, False, (bid,) + tuple(tags))
        cv = self.cv
        cv.tag_bind(bid, "<ButtonPress-1>", lambda e, b=bid: self._press(b))
        cv.tag_bind(bid, "<ButtonRelease-1>", lambda e, b=bid: self._release(b, e))
        cv.tag_bind(bid, "<Enter>", lambda e: cv.configure(cursor="hand2"))
        cv.tag_bind(bid, "<Leave>", lambda e: cv.configure(cursor=""))
        return bid

    def _paint(self, bid, pressed, tags):
        b = self.btns[bid]
        x1, y1, x2, y2 = b["box"]
        if pressed:
            self.cv.body(x1, y1, x2, y2, b["r"], mix(BG, "#000000", 0.07), tags)
        elif b["style"] == "flat": 
            self.cv.body(x1, y1, x2, y2, b["r"], BG, tags)
        else:
            self.cv.panel(x1, y1, x2, y2, b["r"], b["style"], tags)
        d = 1 if pressed else 0
        if b["text"]:
            self.t((x1 + x2) / 2 + d, (y1 + y2) / 2 + d, b["text"], b["size"], b["bold"],
                   b["fg"], "center", tags)
        if b["decor"]:
            b["decor"](d, d, tags)

    def _press(self, bid):
        b = self.btns.get(bid)
        if not b or (self.modal and not b["modal"]):
            return
        self._paint(bid, True, (bid, "ov" + bid) + b["tags"])

    def _release(self, bid, ev):
        b = self.btns.get(bid)
        if not b:
            return
        self.cv.delete("ov" + bid)
        if self.modal and not b["modal"]:
            return
        x1, y1, x2, y2 = b["box"]
        if x1 <= ev.x <= x2 and y1 <= ev.y <= y2 and b["cmd"]:
            b["cmd"]()

    def list_row(self, x1, y1, x2, y2, title, sub, cmd, color=BLACK):
        def decor(dx, dy, tags):
            self.t(x1 + 38 + dx, y1 + 19 + dy, title, 24, True, color, tags=tags)
            self.t(x1 + 38 + dx, y1 + 53 + dy, sub, 12, False, SUB, tags=tags)
        self.button(x1, y1, x2, y2, cmd=cmd, decor=decor, r=20, style="l")

    def tile(self, x1, y1, title, sub, cmd, color=BLACK):
        def decor(dx, dy, tags):
            self.t(x1 + 34 + dx, y1 + 38 + dy, title, 21, True, color, tags=tags)
            self.t(x1 + 34 + dx, y1 + 70 + dy, sub, 14, False, SUB, tags=tags)
        self.button(x1, y1, x1 + 333, y1 + 124, cmd=cmd, decor=decor, r=19, style="m")

    def _begin_modal(self):
        self.modal = True
        for _, win in self.entries.values():
            self.cv.itemconfigure(win, state="hidden")
        self.cv.delete("dlg")
        for bid in self.dlg_btns:
            self.btns.pop(bid, None)
        self.dlg_btns = []
        self.cv.create_rectangle(0, 0, W, H, fill=BG, outline="", tags="dlg")
        self.cv.focus_set()

    def dialog(self, title, msg, kind="info", buttons=None):
        buttons = buttons or [("OK", None)]
        self._begin_modal()
        lines = sum(max(1, -(-len(ln) // 46)) for ln in msg.split("\n"))
        bw, bh = 560, max(250, 175 + 22 * lines)
        x1, y1 = (W - bw) // 2, (H - bh) // 2
        x2, y2 = x1 + bw, y1 + bh
        self.cv.panel(x1, y1, x2, y2, r=20, lvl="xl", tags="dlg")
        col = {"success": GREEN, "error": RED}.get(kind, BLUE)
        self.cv.create_oval(x1 + 36, y1 + 38, x1 + 52, y1 + 54, fill=col, outline="", tags="dlg")
        self.t(x1 + 64, y1 + 32, title, 22, True, tags="dlg")
        self.t(x1 + 36, y1 + 80, msg, 15, False, SUB, tags="dlg", width=bw - 72)
        n, gap = len(buttons), 30
        bwid = 150 if n > 1 else 180
        bx = (x1 + x2 - (n * bwid + (n - 1) * gap)) / 2
        for label, cb in buttons:
            bid = self.button(bx, y2 - 82, bx + bwid, y2 - 28, label,
                              lambda cb=cb: self._close_dialog(cb), size=16,
                              modal=True, style="m", tags=("dlg",))
            self.dlg_btns.append(bid)
            bx += bwid + gap

    def _close_dialog(self, cb=None):
        if not self.modal:
            return
        self.cv.delete("dlg")
        for bid in self.dlg_btns:
            self.btns.pop(bid, None)
        self.dlg_btns = []
        self.modal = False
        for _, win in self.entries.values():
            self.cv.itemconfigure(win, state="normal")
        if cb:
            cb()
        else:
            self.focus_first()

    def balance_card(self, acc):
        self._begin_modal()
        bw, bh = 644, 350
        x1, y1 = (W - bw) // 2, (H - bh) // 2
        x2, y2 = x1 + bw, y1 + bh
        self.cv.panel(x1, y1, x2, y2, r=20, lvl="xl", tags="dlg")
        mut, ink = "#8794A8", "#3B4252"
        self.t(x1 + 44, y1 + 46, "AVAILABLE BALANCE", 14, True, mut, tags="dlg")
        self.t(x1 + 44, y1 + 78, f"{acc.balance:,.2f}", 62, True, ink, tags="dlg")
        self.cv.create_line(x1 + 44, y1 + 172, x2 - 44, y1 + 172, fill="#C9CFDA", width=2, tags="dlg")
        self.t(x1 + 44, y1 + 196, acc.account_name[:26], 26, True, ink, tags="dlg")
        self.t(x1 + 44, y1 + 232, "Account holder", 16, False, mut, tags="dlg")
        self.t(x1 + 44, y1 + 276, "Contact  " + acc.contact_number, 16, False, mut, tags="dlg")
        bid = self.button(x2 - 184, y2 - 78, x2 - 36, y2 - 28, "Close",
                          lambda: self._close_dialog(None), size=16, modal=True,
                          style="m", tags=("dlg",))
        self.dlg_btns.append(bid)

    def field(self, name, label, x, y, w, h=60, show=None, prefix=None):
        self.t(x + 1, y - 19, label, 12, True, GRAY)
        self.cv.inset(x, y, x + w, y + h, r=15)
        off = 22
        if prefix:
            self.t(x + 19, y + h / 2, prefix, 20, True, anchor="w")
            off = 48
        e = tk.Entry(self.cv, bd=0, relief="flat", highlightthickness=0, bg=BG, fg=BLACK,
                     insertbackground=BLACK, font=self.F(17), show=show or "")
        win = self.cv.create_window(x + off, y + h / 2, window=e, anchor="w",
                                    width=w - off - 20, height=h - 24)
        self.entries[name] = (e, win)

    def focus_first(self):
        if not self.entries:
            return
        first = next(iter(self.entries.values()))[0]

        def focus():
            try:
                if not self.modal:
                    first.focus_set()
            except tk.TclError:
                pass
        self.root.after(60, focus)

    def bind_enter(self, cmd):
        def handler(ev):
            if not self.modal:
                cmd()
            return "break"
        for e, _ in self.entries.values():
            e.bind("<Return>", handler)
        self.focus_first()

    def val(self, name):
        return self.entries[name][0].get().strip()

    def show_home(self):
        self.session = None
        self.clear("home")
        self.header("ATM SYSTEM")
        self.card()
        self.t(119, 169, "Services", 25, True)
        rows = [
            ("Registration", "Create an account and write your card", self.open_registration, BLACK),
            ("Transaction", "Insert card, enter PIN, then bank", self.open_transaction, BLACK),
            ("Admin", "Display or delete accounts", self.show_admin_login, BLACK),
            ("Exit", "Close the program", self.quit, RED),
        ]
        y = 226
        for title, sub, cmd, color in rows:
            self.list_row(131, y, 809, y + 89, title, sub, cmd, color)
            y += 113

    def open_registration(self):
        if not self.atm.drives():
            self.dialog("No Card Detected",
                        "Please insert a flash drive, then try registering again.", "error")
            return
        self.show_register()

    def show_register(self):
        self.clear("register")
        self.header("Registration", back=self.show_home)
        self.card()
        self.field("name", "Account Name", 113, 220, 715)
        self.field("bday", "Birthday (MM/DD/YYYY)", 112, 319, 344)
        self.field("contact", "Contact number (11 digits)", 483, 319, 344)
        self.field("deposit", "Initial deposit (min. \u20b15000)", 112, 418, 344, prefix="\u20b1")
        self.field("pin", "4-digit PIN", 484, 418, 344, show="*")
        self.button(617, 590, 817, 650, "Register", self.submit_register)
        self.bind_enter(self.submit_register)

    def submit_register(self):
        if self.modal:
            return
        deposit = parse_amount(self.val("deposit"))
        if deposit is None:
            self.dialog("Invalid deposit", "Please enter a valid number for the initial deposit.", "error")
            return
        ok, msg, acc_no = self.atm.create_account(self.val("name"), self.val("bday"),
                                                  self.val("contact"), deposit, self.val("pin"))
        if not ok:
            self.dialog("Registration failed", msg, "error")
            return
        self.dialog("Registration successful",
                    f"Account number: {acc_no}\nYour card has been written.",
                    "success", [("Done", self.show_home)])

    def open_transaction(self):
        acc_no, err = self.atm.load_card_account()
        if err:
            self.dialog("Card error" if self.atm.drives() else "No Card Detected", err, "error")
            return
        self.pin_acc, self.pin_buf, self.attempts = acc_no, "", 0
        self.show_pin()

    def show_pin(self):
        self.clear("pin")
        self.cv.focus_set()
        self.header("Enter PIN", back=self.show_home)
        self.card()
        self.t(480, 157, "Enter your PIN", 16, True, anchor="n")
        self.t(480, 181, "", 12, True, GRAY, anchor="n", tags="attempt_text")
        self.update_attempt_text()
        self.cv.inset(290, 202, 670, 282, r=15)
        self.draw_dots()

        keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "C", "0", "OK"]
        xs, ys = (230, 402, 575), (335, 414, 493, 572)
        for i in range(len(keys)):
            x, y = xs[i % 3], ys[i // 3]
            self.cv.neu_shadow(x, y, x + 155, y + 63, 20, "m")
        for i, k in enumerate(keys):
            x, y = xs[i % 3], ys[i // 3]
            color = "#FF4B4B" if k == "C" else (BLUE if k == "OK" else KEY_TXT)
            self.button(x, y, x + 155, y + 63, k, lambda k=k: self.pin_key(k),
                        size=32, fg=color, style="flat")
        self.t(480, 655, f"Account no. {self.pin_acc}", 12, False, GRAY, anchor="n")

    def update_attempt_text(self):
        self.cv.itemconfigure("attempt_text", text=f"Attempt {min(self.attempts + 1, 3)} of 3")

    def draw_dots(self):
        self.cv.delete("dots")
        for i in range(4):
            cx = 396 + i * 56
            filled = i < len(self.pin_buf)
            self.cv.create_oval(cx - 10, 232, cx + 10, 252, outline="",
                                fill="#4A4A4A" if filled else "#D3D3D3", tags="dots")

    def pin_key(self, k):
        if self.modal:
            return
        if k == "C":
            self.pin_buf = ""
        elif k == "OK":
            self.submit_pin()
            return
        elif len(self.pin_buf) < 4:
            self.pin_buf += k
        self.draw_dots()

    def on_key(self, e):
        enter = e.keysym in ("Return", "KP_Enter")
        if self.modal:
            if enter and e.widget is self.cv and len(self.dlg_btns) == 1:
                cmd = self.btns[self.dlg_btns[0]]["cmd"]
                if cmd:
                    cmd()
            return
        if self.page != "pin":
            return
        if e.char and e.char.isdigit():
            self.pin_key(e.char)
        elif e.keysym == "BackSpace":
            self.pin_buf = self.pin_buf[:-1]
            self.draw_dots()
        elif enter:
            self.submit_pin()

    def submit_pin(self):
        if self.modal:
            return
        if len(self.pin_buf) != 4:
            self.dialog("Incomplete PIN", "Please enter all 4 digits of your PIN.", "error")
            return
        self.attempts += 1
        if self.atm.verify_pin(self.pin_acc, self.pin_buf):
            self.session, self.pin_buf = self.pin_acc, ""
            self.show_dashboard()
            return
        left = 3 - self.attempts
        self.pin_buf = ""
        self.draw_dots()
        if left <= 0:
            self.dialog("Access denied", "Too many incorrect attempts.", "error",
                        [("OK", self.show_home)])
        else:
            self.update_attempt_text()
            self.dialog("Incorrect PIN", f"{left} attempt(s) remaining.", "error",
                        [("Try again", None)])

    def end_session(self):
        self.session = None
        self.show_home()

    def show_dashboard(self):
        acc = self.atm.locate(self.session).data
        self.clear("dash")
        self.header("Transaction", back=self.end_session)
        self.card()
        self.t(108, 163, "Hi, " + acc.account_name[:22], 20, True)
        self.t(108, 191, "Choose a Transaction", 12, True, GRAY)
        tiles = [
            ("Balance", "View account", self.show_balance, BLACK),
            ("Withdraw", "Multiples of 100", lambda: self.show_action("withdraw"), BLACK),
            ("Deposit", "Min. 100", lambda: self.show_action("deposit"), BLACK),
            ("Transfer", "To another account", lambda: self.show_action("transfer"), BLACK),
            ("Change PIN", "Updates card too", lambda: self.show_action("pin"), BLACK),
            ("Exit", "End session", self.exit_session, RED),
        ]
        ys = (240, 381, 521)
        for i, (title, sub, cmd, color) in enumerate(tiles):
            self.tile(137 + (i % 2) * 353, ys[i // 2], title, sub, cmd, color)

    def show_balance(self):
        self.balance_card(self.atm.locate(self.session).data)

    def exit_session(self):
        self.dialog("Goodbye", "Please remove your flash drive.", "info", [("OK", self.end_session)])

    ACTIONS = {
        "withdraw": ("Withdraw", "Withdraw", [("amount", "Amount (multiples of 100)", None, "\u20b1")]),
        "deposit": ("Deposit", "Deposit", [("amount", "Amount (min. \u20b1100)", None, "\u20b1")]),
        "transfer": ("Transfer", "Send",
                     [("to", "Recipient account no.", None, None),
                      ("amount", "Amount", None, "\u20b1")]),
        "pin": ("Change PIN", "Update PIN",
                [("new", "New 4-digit PIN", "*", None), ("confirm", "Confirm new PIN", "*", None)]),
    }

    def show_action(self, kind):
        title, btn, fields = self.ACTIONS[kind]
        acc = self.atm.locate(self.session).data
        self.clear("action")
        self.header(title, back=self.show_dashboard)
        self.card()
        self.t(113, 168, "Current balance", 12, True, GRAY)
        self.t(113, 188, f"\u20b1{acc.balance:,.2f}", 32, True)
        y = 300
        for name, label, show, prefix in fields:
            self.field(name, label, 113, y, 715, show=show, prefix=prefix)
            y += 100
        self.button(617, 590, 817, 650, btn, lambda: self.submit_action(kind))
        self.bind_enter(lambda: self.submit_action(kind))

    def submit_action(self, kind):
        if self.modal:
            return
        acc_no = self.session
        if not self.atm.card_matches(acc_no):
            self.dialog("Card removed", "Your card was removed or changed, so the session was ended.",
                        "error", [("OK", self.end_session)])
            return
        if kind == "pin":
            if self.val("new") != self.val("confirm"):
                self.dialog("PINs do not match", "Please enter the same PIN twice.", "error")
                return
            ok, msg = self.atm.change_pin(acc_no, self.val("new"))
        else:
            amount = parse_amount(self.val("amount"))
            if amount is None:
                self.dialog("Invalid amount", "Please enter a valid number.", "error")
                return
            if kind == "withdraw":
                ok, msg = self.atm.withdraw(acc_no, amount)
            elif kind == "deposit":
                ok, msg = self.atm.deposit(acc_no, amount)
            else:
                ok, msg = self.atm.fund_transfer(acc_no, self.val("to"), amount)
        self.dialog("Success" if ok else "Could not complete", msg,
                    "success" if ok else "error",
                    [("OK", self.show_dashboard if ok else None)])

    def show_admin_login(self):
        self.clear("admin_login")
        self.header("Admin", back=self.show_home)
        self.card()
        self.t(119, 169, "Administrator", 25, True)
        self.field("pw", "Admin password", 113, 260, 715, show="*")
        self.button(617, 590, 817, 650, "Log in", self.submit_admin)
        self.bind_enter(self.submit_admin)

    def submit_admin(self):
        if self.modal:
            return
        if self.val("pw") == ADMIN_PASSWORD:
            self.admin_page = 0
            self.show_admin()
        else:
            self.dialog("Access denied", "Incorrect password.", "error")

    def show_admin(self):
        accounts = self.atm.all_accounts()
        pages = max(1, -(-len(accounts) // self.PAGE_SIZE))
        self.admin_page = max(0, min(self.admin_page, pages - 1))
        self.clear("admin")
        cv = self.cv
        self.header("All accounts", back=self.show_home)
        self.card()

        cols = [(122, "ACCOUNT NO."), (208, "NAME"), (356, "BIRTHDAY"),
                (456, "CONTACT"), (572, "BALANCE"), (696, "ENC. PIN")]
        for x, label in cols:
            self.t(x, 166, label, 11, True, GRAY)

        chunk = accounts[self.admin_page * self.PAGE_SIZE:(self.admin_page + 1) * self.PAGE_SIZE]
        if not chunk:
            cv.inset(98, 200, 845, 270, r=15)
            self.t(471, 235, "No account records found.", 15, False, GRAY, "center")
        y = 196
        for a in chunk:
            cv.panel(98, y, 845, y + 52, r=15, lvl="s")
            vals = [a.account_no, a.account_name[:16], a.birthday, a.contact_number,
                    f"{a.balance:,.2f}", a.encrypted_pin]
            for (x, _), v in zip(cols, vals):
                self.t(x, y + 26, v, 14, False, BLACK, "w")
            self.button(796, y + 11, 830, y + 41, cmd=lambda a=a: self.confirm_delete(a),
                        r=10, style="s",
                        decor=lambda dx, dy, tg, cy=y + 26: cv.glyph("close", 813 + dx, cy + dy, tg))
            y += 62

        self.button(98, 606, 238, 654, "Prev", self.admin_prev, style="m", size=15)
        self.button(258, 606, 398, 654, "Next", self.admin_next, style="m", size=15)
        self.t(430, 630, f"Page {self.admin_page + 1} of {pages}", 13, False, GRAY, "w")
        self.t(845, 630, f"{len(accounts)} account(s)", 13, False, GRAY, "e")

    def admin_prev(self):
        if self.admin_page > 0:
            self.admin_page -= 1
            self.show_admin()

    def admin_next(self):
        if (self.admin_page + 1) * self.PAGE_SIZE < len(self.atm.all_accounts()):
            self.admin_page += 1
            self.show_admin()

    def confirm_delete(self, a):
        self.dialog("Delete account?",
                    f"Account {a.account_no} ({a.account_name}) will be permanently deleted.",
                    "error", [("Cancel", None), ("Delete", lambda: self.do_delete(a.account_no))])

    def do_delete(self, acc_no):
        ok, msg = self.atm.delete_account(acc_no)
        self.dialog("Account deleted" if ok else "Delete failed", msg,
                    "success" if ok else "error", [("OK", self.show_admin)])


if __name__ == "__main__":
    App().run()