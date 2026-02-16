rule Sentinel_Suspicious_Shell_Stagers {
  meta:
    author = "Sentinel Stratos Strategies"
    description = "Detects common shell stagers and inline script execution"
  strings:
    $s1 = "curl -fsSL" nocase
    $s2 = "curl http" nocase
    $s3 = "wget http" nocase
    $s4 = "python -c" nocase
    $s5 = "bash -c" nocase
    $s6 = "osascript -e" nocase
  condition:
    2 of ($s*)
}

rule Sentinel_Token_Leakage {
  meta:
    author = "Sentinel Stratos Strategies"
    description = "Detects common API token patterns"
  strings:
    $aws = /\b(AKIA|ASIA)[0-9A-Z]{16}\b/
    $gh = /\bghp_[A-Za-z0-9]{36}\b/
    $gl = /\bglpat-[A-Za-z0-9\-]{20,}\b/
    $sl = /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/
    $oa = /\bsk-[A-Za-z0-9]{20,}\b/
  condition:
    1 of them
}

rule Sentinel_Mac_Persistence_Indicators {
  meta:
    author = "Sentinel Stratos Strategies"
    description = "Detects macOS persistence keywords in plists/logs"
  strings:
    $p1 = "LaunchAgents" nocase
    $p2 = "LaunchDaemons" nocase
    $p3 = "RunAtLoad" nocase
    $p4 = "KeepAlive" nocase
    $p5 = "ProgramArguments" nocase
    $p6 = "LoginItems" nocase
  condition:
    3 of ($p*)
}
