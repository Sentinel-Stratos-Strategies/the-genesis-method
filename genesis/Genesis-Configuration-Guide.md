# Genesis Method - Configuration Reference

**File:** `genesis_config.json`  
**Version:** 2.0  
**Purpose:** Central configuration for Genesis monitoring and forensic capture

---

## Complete Configuration Schema

```json
{
  "version": "2.0",
  "system": {
    "name": "Genesis Forensic Preservation System",
    "description": "Active defense + forensic evidence preservation for macOS",
    "author": "Joe Athan Ellis (The Sentinel)",
    "enabled": true,
    "debug_mode": false
  },
  
  "authorized_user": {
    "whitelist_path": "/Library/Application Support/Genesis/authorized_user.enc",
    "auto_register_on_first_run": false,
    "require_keychain_auth": true,
    "require_admin_password": true,
    "behavioral_monitoring": true,
    "behavioral_tolerance": 0.15,
    "multi_user_support": false,
    "reregistration_required_days": 90
  },
  
  "device_fingerprinting": {
    "capture_hardware_uuid": true,
    "capture_serial_number": true,
    "capture_mac_address": true,
    "capture_ecid": true,
    "capture_model_identifier": true,
    "capture_firmware_version": true,
    "fingerprint_cache_duration_hours": 24
  },
  
  "evidence_storage": {
    "volume_name": "Genesis-Evidence",
    "volume_path": "/Volumes/Genesis-Evidence",
    "auto_create_volume": true,
    "volume_size_gb": 50,
    "auto_create_snapshots": true,
    "snapshot_retention_days": 365,
    "encryption_enabled": true,
    "encryption_method": "FileVault",
    "compression": "lz4",
    "read_only_after_capture": true,
    "evidence_retention_policy": "permanent"
  },
  
  "monitoring": {
    "enabled": true,
    "mode": "active_defense",
    "log_authorized_user": false,
    "log_authorized_user_detail_level": "none",
    "log_unauthorized_access": true,
    "log_unauthorized_detail_level": "full",
    "monitor_login_events": true,
    "monitor_keychain_access": true,
    "monitor_sudo_commands": true,
    "monitor_ssh_connections": true,
    "monitor_network_changes": true,
    "check_interval_seconds": 30,
    "alert_on_intrusion": true,
    "alert_methods": ["log", "email", "notification", "sms"],
    "capture_on_unauthorized": true,
    "auto_lockout_on_threshold": true
  },
  
  "forensic_capture": {
    "auto_capture_on_unauthorized": true,
    "capture_network_interfaces": true,
    "capture_tunnels_and_vpns": true,
    "capture_mac_addresses": true,
    "capture_routing_tables": true,
    "capture_arp_cache": true,
    "capture_dns_cache": true,
    "capture_running_processes": true,
    "capture_process_tree": true,
    "capture_network_connections": true,
    "capture_open_files": true,
    "capture_keychains": true,
    "capture_keychain_passwords": false,
    "capture_certificates": true,
    "capture_launch_daemons": true,
    "capture_launch_agents": true,
    "capture_cron_jobs": true,
    "capture_system_info": true,
    "capture_user_accounts": true,
    "capture_recent_commands": true,
    "capture_bash_history": true,
    "capture_system_logs": true,
    "capture_screenshots": false,
    "capture_clipboard": false,
    "hash_verification": "sha256",
    "timestamp_source": "time.apple.com",
    "capture_timeout_seconds": 300
  },
  
  "intrusion_detection": {
    "enabled": true,
    "detection_mode": "aggressive",
    "threshold_failed_attempts": 3,
    "threshold_time_window_minutes": 15,
    "lockout_enabled": true,
    "lockout_duration_minutes": 30,
    "permanent_lockout_after_attempts": 10,
    "device_fingerprint_mismatch": "ALERT_AND_CAPTURE",
    "credential_mismatch": "ALERT_AND_CAPTURE",
    "new_device_detected": "CAPTURE_AND_CHALLENGE",
    "unusual_time_access": "ALERT",
    "unusual_location_access": "ALERT_AND_CAPTURE",
    "vpn_usage_detected": "LOG",
    "tor_usage_detected": "ALERT_AND_CAPTURE",
    "behavioral_anomaly_threshold": 0.25,
    "geo_fencing_enabled": false,
    "allowed_ip_ranges": [],
    "blocked_countries": []
  },
  
  "alerting": {
    "enabled": true,
    "alert_levels": ["warning", "critical"],
    "email_alerts": {
      "enabled": true,
      "smtp_server": "smtp.gmail.com",
      "smtp_port": 587,
      "smtp_username": "",
      "smtp_password_keychain_item": "genesis_smtp_password",
      "from_address": "genesis@sentinel.local",
      "to_addresses": ["sentinel@example.com"],
      "alert_on_unauthorized": true,
      "alert_on_capture": true,
      "alert_on_system_error": true
    },
    "notification_center": {
      "enabled": true,
      "show_on_unauthorized": true,
      "show_on_capture": true,
      "persistent_notifications": true
    },
    "sms_alerts": {
      "enabled": false,
      "provider": "twilio",
      "api_key_keychain_item": "genesis_sms_api",
      "phone_numbers": []
    },
    "webhook": {
      "enabled": false,
      "url": "",
      "auth_token_keychain_item": "genesis_webhook_token",
      "send_on_unauthorized": true,
      "send_on_capture": true
    }
  },
  
  "legal_compliance": {
    "enabled": true,
    "chain_of_custody_logging": true,
    "custody_log_path": "/Volumes/Genesis-Evidence/chain_of_custody.log",
    "timestamp_server": "time.apple.com",
    "timestamp_verification": "ntp",
    "evidence_tamper_protection": true,
    "audit_trail_enabled": true,
    "audit_log_path": "/var/log/genesis_audit.log",
    "legal_hold_enabled": false,
    "retention_policy_days": 2555,
    "export_format": "forensic_container",
    "include_metadata": true,
    "include_hash_chain": true,
    "gdpr_compliance_mode": false,
    "ccpa_compliance_mode": false,
    "monitoring_notice_required": true,
    "monitoring_notice_text": "This system is monitored. Unauthorized access will be logged and may result in legal action."
  },
  
  "performance": {
    "max_cpu_usage_percent": 10,
    "max_memory_usage_mb": 512,
    "max_disk_io_mbps": 50,
    "capture_priority": "normal",
    "background_mode": true,
    "throttle_when_battery_low": true,
    "pause_during_presentation_mode": false
  },
  
  "logging": {
    "enabled": true,
    "log_level": "INFO",
    "log_path": "/var/log/genesis_monitor.log",
    "log_rotation": true,
    "max_log_size_mb": 100,
    "log_retention_days": 365,
    "log_format": "json",
    "log_timestamps": "utc",
    "log_to_syslog": true,
    "syslog_facility": "local0"
  },
  
  "integration": {
    "splunk_enabled": false,
    "elk_enabled": false,
    "siem_enabled": false,
    "api_enabled": false,
    "api_port": 8443,
    "api_auth_required": true,
    "api_key_keychain_item": "genesis_api_key"
  },
  
  "advanced": {
    "kernel_extension_monitoring": false,
    "network_packet_capture": false,
    "memory_forensics": false,
    "firmware_integrity_check": false,
    "secure_boot_verification": false,
    "system_integrity_protection_check": true
  }
}
```

---

## Configuration Sections Explained

### 1. System

Basic system identification and global enable/disable.

**Key Settings:**
- `enabled`: Master switch for entire Genesis system
- `debug_mode`: Verbose logging for troubleshooting

### 2. Authorized User

Controls how authorized users are registered and recognized.

**Key Settings:**
- `require_keychain_auth`: Force keychain password verification during registration
- `behavioral_monitoring`: Track normal usage patterns for anomaly detection
- `behavioral_tolerance`: How much deviation from normal is acceptable (0.15 = 15%)

### 3. Device Fingerprinting

Defines which device characteristics to capture for identification.

**All should be `true` for maximum security.**

### 4. Evidence Storage

Configure the APFS volume used for forensic evidence.

**Key Settings:**
- `volume_size_gb`: How much space to allocate (minimum 10GB, recommended 50GB+)
- `encryption_enabled`: Always use `true` for sensitive evidence
- `read_only_after_capture`: Prevents tampering after evidence written

### 5. Monitoring

Core monitoring behavior - what to watch and how to respond.

**Key Settings:**
- `log_authorized_user`: Set to `false` for zero-logging of legitimate user
- `log_unauthorized_access`: Always `true` to capture intrusions
- `check_interval_seconds`: How often to verify authentication (30 = every 30 seconds)

### 6. Forensic Capture

Exactly what data to collect when unauthorized access detected.

**Recommended:**
- Enable all capture options except:
  - `capture_keychain_passwords`: Security risk if Genesis compromised
  - `capture_screenshots`: Privacy concern + large file sizes
  - `capture_clipboard`: Privacy concern

### 7. Intrusion Detection

Define what constitutes unauthorized access and how to respond.

**Key Settings:**
- `threshold_failed_attempts`: How many failed logins before triggering (3 recommended)
- `device_fingerprint_mismatch`: **Most important** - responds to wrong device
- `behavioral_anomaly_threshold`: Sensitivity of behavioral detection (0.25 = 25% deviation)

**Response Options:**
- `LOG`: Write to log only
- `ALERT`: Write to log + send alert
- `CAPTURE`: Trigger full forensic capture
- `ALERT_AND_CAPTURE`: Send alert + trigger capture (recommended)
- `CAPTURE_AND_CHALLENGE`: Trigger capture + require re-authentication

### 8. Alerting

How to notify authorized user when intrusion detected.

**Recommended Configuration:**
```json
"alerting": {
  "email_alerts": {"enabled": true},
  "notification_center": {"enabled": true},
  "sms_alerts": {"enabled": true}  // For critical alerts
}
```

### 9. Legal Compliance

Settings to ensure evidence admissibility in court.

**Must enable:**
- `chain_of_custody_logging`: Required for legal proceedings
- `evidence_tamper_protection`: Prevents post-capture modification
- `audit_trail_enabled`: Documents all access to evidence

**Privacy compliance:**
- `gdpr_compliance_mode`: If monitoring EU citizens
- `ccpa_compliance_mode`: If monitoring California residents
- `monitoring_notice_required`: **Always use** - display warning to users

### 10. Performance

Resource limits to prevent Genesis from impacting system performance.

**Defaults are conservative** - Genesis should use <1% CPU during normal monitoring.

### 11. Logging

Genesis internal logging configuration.

**Key Settings:**
- `log_level`: Use `INFO` for production, `DEBUG` for troubleshooting
- `log_format`: `json` recommended for SIEM integration

### 12. Integration

Connect Genesis to enterprise security infrastructure.

**Available integrations:**
- Splunk
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Generic SIEM via syslog
- REST API for custom integrations

### 13. Advanced

Experimental and resource-intensive features.

**Most require kernel extensions or significant overhead** - leave disabled unless specifically needed.

---

## Configuration Best Practices

### For Personal Device Protection

```json
{
  "monitoring": {
    "log_authorized_user": false,  // Zero overhead
    "check_interval_seconds": 60   // Check every minute
  },
  "intrusion_detection": {
    "detection_mode": "aggressive",
    "threshold_failed_attempts": 2,  // Very sensitive
    "device_fingerprint_mismatch": "ALERT_AND_CAPTURE"
  },
  "alerting": {
    "notification_center": {"enabled": true},
    "sms_alerts": {"enabled": true}  // Immediate notification
  }
}
```

### For Corporate Deployment

```json
{
  "monitoring": {
    "log_authorized_user": true,  // Audit requirements
    "log_authorized_user_detail_level": "minimal",
    "check_interval_seconds": 30
  },
  "intrusion_detection": {
    "detection_mode": "balanced",
    "threshold_failed_attempts": 3,
    "geo_fencing_enabled": true,  // Restrict to office IP ranges
    "allowed_ip_ranges": ["10.0.0.0/8", "192.168.1.0/24"]
  },
  "integration": {
    "splunk_enabled": true,  // Feed to SIEM
    "api_enabled": true      // Central management
  },
  "legal_compliance": {
    "gdpr_compliance_mode": true,  // If EU operations
    "monitoring_notice_required": true  // Legal requirement
  }
}
```

### For Legal Evidence Collection

```json
{
  "evidence_storage": {
    "encryption_enabled": true,
    "snapshot_retention_days": 2555,  // 7 years
    "read_only_after_capture": true
  },
  "forensic_capture": {
    "capture_system_logs": true,
    "capture_bash_history": true,
    "capture_network_connections": true,
    "hash_verification": "sha256"
  },
  "legal_compliance": {
    "chain_of_custody_logging": true,
    "audit_trail_enabled": true,
    "timestamp_verification": "ntp",
    "include_metadata": true,
    "include_hash_chain": true
  }
}
```

---

## Configuration Validation

Genesis validates configuration on startup. Common errors:

### Error: Invalid whitelist path
```
ERROR: Whitelist file not found at /Library/Application Support/Genesis/authorized_user.enc
SOLUTION: Run genesis_register.py to create whitelist
```

### Error: Evidence volume not mounted
```
ERROR: Evidence volume not found at /Volumes/Genesis-Evidence
SOLUTION: Check volume_path in config or run volume setup
```

### Error: Insufficient permissions
```
ERROR: Genesis monitor must run as root
SOLUTION: Use launchctl to run as daemon with root privileges
```

---

## Environment-Specific Overrides

Genesis supports environment variables to override config:

```bash
# Override evidence volume path
export GENESIS_EVIDENCE_PATH="/Volumes/Backup/Genesis-Evidence"

# Enable debug mode
export GENESIS_DEBUG=1

# Disable monitoring temporarily
export GENESIS_ENABLED=0

# Override check interval
export GENESIS_CHECK_INTERVAL=60
```

---

## Security Recommendations

### DO:
✓ Store `genesis_config.json` with restrictive permissions: `chmod 600`  
✓ Use Keychain for all sensitive credentials (SMTP passwords, API keys)  
✓ Enable encryption on evidence volume  
✓ Set `log_authorized_user: false` to minimize privacy impact  
✓ Use `read_only_after_capture: true` to prevent tampering  
✓ Enable `chain_of_custody_logging` if evidence may be used legally  

### DON'T:
✗ Store passwords in plaintext in config file  
✗ Disable `evidence_tamper_protection`  
✗ Set `threshold_failed_attempts` too high (defeats purpose)  
✗ Disable `hash_verification`  
✗ Use `debug_mode` in production (logs sensitive data)  
✗ Allow unauthorized users to read config file  

---

## Configuration Change Log

Maintain a change log when modifying configuration:

```
# /Library/Application Support/Genesis/config_changelog.txt

2026-02-15 21:00 UTC - Initial Genesis 2.0 configuration created
2026-02-15 21:30 UTC - Enabled email alerts, configured SMTP
2026-02-16 09:00 UTC - Lowered threshold_failed_attempts from 5 to 3
2026-02-17 14:00 UTC - Added geo-fencing for office IP range
```

This provides audit trail of security posture changes.

---

## Testing Configuration

Before production deployment, test configuration:

```bash
# Validate config syntax
python3 -c "import json; json.load(open('genesis_config.json'))"

# Test with Genesis in dry-run mode
sudo GENESIS_DRY_RUN=1 python3 genesis_monitor.py

# Simulate unauthorized access
sudo su - testuser  # Should trigger capture in test mode

# Check logs
tail -f /var/log/genesis_monitor.log
```

---

## Configuration Templates

Genesis includes templates for common scenarios:

- `config_personal.json` - Personal device protection
- `config_corporate.json` - Enterprise deployment
- `config_legal.json` - Evidence collection for litigation
- `config_minimal.json` - Minimal resource usage
- `config_paranoid.json` - Maximum security, aggressive detection

Copy template and customize:
```bash
cp config_templates/config_personal.json genesis_config.json
nano genesis_config.json  # Customize for your environment
```

---

**Configuration Version:** 2.0  
**Last Updated:** February 15, 2026  
**Status:** Production-Ready
