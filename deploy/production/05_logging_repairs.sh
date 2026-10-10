#!/usr/bin/env bash
# ==============================================================================
# 05_logging_repairs.sh — Centralized Noisy Logging, Automated Repairs & CLI
# Target: Fresh production VPS (Debian 12 / Ubuntu 24.04)
# ==============================================================================
set -euo pipefail

ROOT_DIR="/srv/shadenet"
BIN_DIR="${ROOT_DIR}/bin"
LOGS_DIR="${ROOT_DIR}/logs"
REPAIRS_LOG="${LOGS_DIR}/repairs/repair.log"

echo "===> [1/4] Installing Logrotate and monitoring utilities..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq logrotate jq curl sqlite3

mkdir -p "${BIN_DIR}" "${LOGS_DIR}/repairs"

echo "===> [2/4] Setting up Logrotate policy for noisy logs..."
cat > /etc/logrotate.d/shadenet <<EOF
${LOGS_DIR}/*/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 root root
    sharedscripts
}
EOF

echo "===> [3/4] Writing Automated Repair & Watchdog Engine (${BIN_DIR}/repair.sh)..."
cat > "${BIN_DIR}/repair.sh" <<'EOF'
#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="/srv/shadenet"
LOG_FILE="${ROOT_DIR}/logs/repairs/repair.log"
TIMESTAMP="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

log_repair() {
    echo "[$TIMESTAMP] $1" | tee -a "${LOG_FILE}"
}

# 1. Disk Space Sentinel (Auto-prune if > 80%)
DISK_USAGE=$(df -P "${ROOT_DIR}/data" | awk 'NR==2 {print $5}' | tr -d '%')
if [ "${DISK_USAGE}" -ge 80 ]; then
    log_repair "WARNING: Disk usage at ${DISK_USAGE}%. Running aggressive Docker prune..."
    docker image prune -af --filter "until=48h" >> "${LOG_FILE}" 2>&1 || true
    docker builder prune -af --filter "until=24h" >> "${LOG_FILE}" 2>&1 || true
    log_repair "SUCCESS: Docker system pruned. New disk usage: $(df -P "${ROOT_DIR}/data" | awk 'NR==2 {print $5}')"
fi

# 2. Container Health Sentinel
UNHEALTHY=$(docker ps -q --filter "health=unhealthy")
if [ -n "${UNHEALTHY}" ]; then
    for cid in ${UNHEALTHY}; do
        cname=$(docker inspect --format '{{.Name}}' "$cid" | tr -d '/')
        log_repair "ALERT: Container $cname is UNHEALTHY. Triggering automated repair restart..."
        docker restart "$cid" >> "${LOG_FILE}" 2>&1
        log_repair "SUCCESS: Container $cname restarted."
    done
fi

# 3. SQLite Database WAL & Integrity Sentinel
DB_FILE="${ROOT_DIR}/data/shadenet/shadenet.db"
if [ -f "${DB_FILE}" ]; then
    INTEGRITY=$(sqlite3 "${DB_FILE}" "PRAGMA integrity_check;" 2>&1 || echo "error")
    if [ "${INTEGRITY}" != "ok" ]; then
        log_repair "CRITICAL: ShadeNet DB integrity error: ${INTEGRITY}. Attempting WAL vacuum checkpoint..."
        sqlite3 "${DB_FILE}" "PRAGMA wal_checkpoint(TRUNCATE);" >> "${LOG_FILE}" 2>&1 || true
    else
        # Routine lean checkpoint
        sqlite3 "${DB_FILE}" "PRAGMA wal_checkpoint(PASSIVE);" >/dev/null 2>&1 || true
    fi
fi

# 4. WireGuard Interface Sentinel
if ! ip link show wg0 up >/dev/null 2>&1; then
    log_repair "ALERT: WireGuard interface wg0 is DOWN. Restarting wg-quick@wg0..."
    systemctl restart wg-quick@wg0 >> "${LOG_FILE}" 2>&1 || true
fi

# 5. Caddy Ingress Sentinel
if ! curl -s -f http://127.0.0.1 >/dev/null 2>&1; then
    # If Caddy container stopped or unresponsive
    if [ "$(docker inspect -f '{{.State.Running}}' shadenet_ingress 2>/dev/null)" != "true" ]; then
        log_repair "ALERT: Caddy Ingress container is stopped. Starting shadenet_ingress..."
        docker start shadenet_ingress >> "${LOG_FILE}" 2>&1 || true
    fi
fi

# Clean exit
exit 0
EOF
chmod +x "${BIN_DIR}/repair.sh"

# Install Systemd Timer for Repair Sentinel (every 3 minutes)
cat > /etc/systemd/system/shadenet-repair.service <<EOF
[Unit]
Description=ShadeNet Automated Self-Healing & Repair Sentinel
After=network.target

[Service]
Type=oneshot
ExecStart=${BIN_DIR}/repair.sh
EOF

cat > /etc/systemd/system/shadenet-repair.timer <<EOF
[Unit]
Description=Run ShadeNet Repair Sentinel every 3 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=3min
AccuracySec=10s

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable shadenet-repair.timer
systemctl restart shadenet-repair.timer

echo "===> [4/4] Writing Master Control CLI (${BIN_DIR}/shadenet-ctl)..."
cat > "${BIN_DIR}/shadenet-ctl" <<'EOF'
#!/usr/bin/env bash
# ShadeNet Infrastructure Master Controller CLI
set -uo pipefail

ROOT_DIR="/srv/shadenet"
cd "${ROOT_DIR}" || exit 1

usage() {
    echo "============================================================"
    echo " ShadeNet Production Infrastructure Controller (shadenet-ctl)"
    echo "============================================================"
    echo "Usage: shadenet-ctl <command> [args]"
    echo ""
    echo "Commands:"
    echo "  status            - Show status of all containers, VPN, and disk"
    echo "  up                - Build and start all services in background"
    echo "  down              - Stop all services gracefully"
    echo "  restart [service] - Restart all or specific service"
    echo "  logs [service]    - Follow live noisy logs for a container"
    echo "  repairs           - View automated repair & watchdog log"
    echo "  repair-now        - Run an immediate self-healing repair drill"
    echo "  vpn-qr            - Display mobile WireGuard QR code for operator"
    echo "  monero-status     - Query pruned Monero node height & sync"
    echo "  matrix-create-admin <user> <pass> - Register new Matrix admin user"
    echo "============================================================"
    exit 1
}

CMD="${1:-help}"

case "$CMD" in
    status)
        echo "=== [1/4] Docker Containers ==="
        docker compose ps
        echo ""
        echo "=== [2/4] WireGuard VPN Status ==="
        wg show wg0 || echo "WireGuard wg0 not active"
        echo ""
        echo "=== [3/4] LUKS Encrypted Storage ==="
        df -h "${ROOT_DIR}/data"
        echo ""
        echo "=== [4/4] Automated Repair Timer ==="
        systemctl status shadenet-repair.timer --no-pager | head -n 5
        ;;
    up)
        docker compose up -d --remove-orphans
        ;;
    down)
        docker compose down
        ;;
    restart)
        TARGET="${2:-}"
        if [ -n "$TARGET" ]; then
            docker compose restart "$TARGET"
        else
            docker compose restart
        fi
        ;;
    logs)
        TARGET="${2:-}"
        if [ -n "$TARGET" ]; then
            docker compose logs -f --tail=100 "$TARGET"
        else
            docker compose logs -f --tail=50
        fi
        ;;
    repairs)
        tail -n 100 -f "${ROOT_DIR}/logs/repairs/repair.log"
        ;;
    repair-now)
        echo "Running immediate automated self-healing drill..."
        "${ROOT_DIR}/bin/repair.sh"
        tail -n 20 "${ROOT_DIR}/logs/repairs/repair.log"
        ;;
    vpn-qr)
        if [ -f "${ROOT_DIR}/config/wireguard/clients/operator-phone-qr.txt" ]; then
            cat "${ROOT_DIR}/config/wireguard/clients/operator-phone-qr.txt"
        else
            echo "Phone QR code not found."
        fi
        ;;
    monero-status)
        curl -s -X POST http://203.0.113.1:18081/json_rpc \
            -d '{"jsonrpc":"2.0","id":"0","method":"get_info"}' \
            -H 'Content-Type: application/json' | jq '.result | {height, target_height, synchronized, connections_in, connections_out}'
        ;;
    matrix-create-admin)
        USER="${2:-}"
        PASS="${3:-}"
        if [ -z "$USER" ] || [ -z "$PASS" ]; then
            echo "Usage: shadenet-ctl matrix-create-admin <username> <password>"
            exit 1
        fi
        docker exec -it matrix_synapse register_new_matrix_user \
            -c /data/homeserver.yaml \
            -u "$USER" -p "$PASS" --admin "http://localhost:8008"
        ;;
    *)
        usage
        ;;
esac
EOF
chmod +x "${BIN_DIR}/shadenet-ctl"
ln -sf "${BIN_DIR}/shadenet-ctl" /usr/local/bin/shadenet-ctl

echo "✓ Centralized noisy logging, repair daemon, and 'shadenet-ctl' installed!"
