from textwrap import indent

def tool_NET_INFO(description: str, system_tool, log):
    out_ip = system_tool("ip a")
    out_r = system_tool("ip r")
    if log:
        log(f"[NET_INFO ip a] {out_ip[:2000]}", "net.log")
        log(f"[NET_INFO ip r] {out_r[:2000]}", "net.log")
    return out_ip + "\n" + out_r


def tool_NET_DIAG(description: str, system_tool, log):
    rep = []
    rep.append("=== NET_DIAG – pełna diagnostyka internetu ===")
    if description:
        rep.append(f"Opis / kontekst: {description}")
    rep.append("")

    def add_section(title, cmd):
        rep.append(f"## {title}")
        out = system_tool(cmd)
        rep.append(f"$ {cmd}")
        rep.append(indent(out or "(brak danych)", "    "))
        rep.append("")
        if log:
            log(f"[NET_DIAG {cmd}] {out[:2000]}", "net_diag.log")

    add_section("Interfejsy (ip a)", "ip a")
    add_section("Trasy (ip r)", "ip r")
    add_section("DNS (/etc/resolv.conf)", "cat /etc/resolv.conf || echo '(brak /etc/resolv.conf)'")
    add_section("Ping bramy (192.168.1.1)", "ping -c 4 192.168.1.1 || echo 'PING_FAIL'")
    add_section("Ping 1.1.1.1", "ping -c 4 1.1.1.1 || echo 'PING_FAIL'")
    add_section("Ping 8.8.8.8", "ping -c 4 8.8.8.8 || echo 'PING_FAIL'")
    add_section("DNS lookup google.com", "dig google.com +short || nslookup google.com || host google.com || echo 'DNS_FAIL'")
    add_section("Traceroute 8.8.8.8", "traceroute 8.8.8.8 || tracepath 8.8.8.8 || echo 'TRACE_FAIL'")

    rep.append("=== KONIEC NET_DIAG ===")
    rep.append("")
    rep.append('Jeśli chcesz, mogę spróbować naprawić typowe problemy (tryb 3):')
    rep.append('  ./agent.sh "Lyra napraw internet"  (użyje NET_FIX)')
    return "\n".join(rep)


def tool_NET_FIX(description: str, system_tool, log):
    rep = []
    rep.append("=== NET_FIX – automatyczne naprawy sieci (tryb 3) ===")
    if description:
        rep.append(f"Opis / kontekst: {description}")
    rep.append("")

    cmds = [
        "nmcli networking off || true",
        "nmcli networking on || true",
        "systemctl restart NetworkManager.service || systemctl restart network-manager.service || true",
    ]
    for c in cmds:
        out = system_tool(c)
        rep.append(f"$ {c}\n{indent(out, '    ')}\n")
        if log:
            log(f"[NET_FIX] {c} -> {out[:1000]}", "net_fix.log")

    rep.append("=== KONIEC NET_FIX ===")
    rep.append("Jeśli nadal są problemy – użyj NET_DIAG i pokaż raport Lyrze w czacie.")
    return "\n".join(rep)
