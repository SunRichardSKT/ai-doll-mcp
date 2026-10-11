#!/usr/bin/env bash
# Remote Linux deployment. Run a saved script, never pipe a download to a shell.
set -Eeuo pipefail
APP_VERSION=2.16.2
PACKAGE="AI_Doll_Server_v${APP_VERSION}.tar.gz"
DOWNLOAD_BASE="https://raw.githubusercontent.com/SunRichardSKT/ai-doll-mcp/main/delivery"
INSTALL_DIR=/opt/ai-doll-mcp
BIN_DIR=/usr/local/bin
DOMAIN=''
PROJECT=ai-doll-server
PROJECT_SPECIFIED=false
ACTION=install
DRY_RUN=false
WAIT_SEC=120
TEMP_DIR=''

die() { printf 'AI Doll：%s\n' "$*" >&2; exit 1; }
cleanup() { if [[ -n "$TEMP_DIR" && "$TEMP_DIR" == /tmp/ai-doll-install.* ]]; then rm -rf -- "$TEMP_DIR"; fi; }
trap cleanup EXIT
trap 'printf "安装未完成（第 %s 行）。已有数据保留；修复原因后可再次运行同一入口。\n" "$LINENO" >&2' ERR

usage() {
    cat <<'EOF'
AI Doll 远程服务器安装
  sudo bash Install_Server.sh --domain doll.your-domain.com
  sudo bash Install_Server.sh     # 按提示填写域名，也可粘贴 HTTPS 首页地址
  sudo bash Install_Server.sh --domain doll.your-domain.com --dry-run
  sudo ai-doll-server status | start | stop | restart | link | logs

选项：--install-dir /opt/ai-doll-mcp   --project ai-doll-server
已有手工 Compose 部署可指定原项目名称和部署目录，以复用原数据卷。
Ubuntu / Debian 自动准备 Docker；其他 Linux 需先装好 Docker Compose。
EOF
}

valid_domain() {
    local label
    local -a labels
    [[ ${#1} -le 253 && "$1" == *.* && "$1" =~ ^[a-zA-Z0-9.-]+$ && "$1" =~ \.[a-zA-Z]{2,}$ ]] || return 1
    IFS=. read -r -a labels <<< "$1"
    for label in "${labels[@]}"; do
        [[ ${#label} -ge 1 && ${#label} -le 63 && "$label" != -* && "$label" != *- ]] || return 1
    done
    [[ "$1" != example.com && "$1" != *.example.com && "$1" != *.invalid && "$1" != *.localhost ]]
}

normalize_domain() {
    # Accept a copied HTTPS home URL without silently discarding a different
    # port, credential, path or query. This deployment always serves port 443.
    local value=$1
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    value=${value,,}
    value=${value#https://}
    value=${value%/}
    value=${value%:443}
    valid_domain "$value" || return 1
    printf '%s' "$value"
}

choose_domain() {
    local entered normalized
    if [[ -n "$DOMAIN" ]]; then
        normalized=$(normalize_domain "$DOMAIN") ||
            die '域名无效。可填写 doll.your-domain.com 或 https://doll.your-domain.com/；不要使用 IP、非 443 端口或其他路径。'
        DOMAIN=$normalized
        return
    fi
    [[ "$ACTION" == install ]] || die '未找到保存的域名，请先运行安装入口。'
    printf '\n首次部署只需填写域名。请先将域名解析到此服务器，并在云安全组放行 TCP 80 / 443。\n'
    while true; do
        read -r -p '域名或 HTTPS 首页地址：' entered ||
            die '未读到域名。请运行 sudo bash Install_Server.sh --domain 你的域名。'
        if normalized=$(normalize_domain "$entered"); then
            DOMAIN=$normalized
            return
        fi
        printf '未识别此地址，请重新填写，例如 doll.your-domain.com。不能使用 IP、其他端口、路径或查询参数。\n' >&2
    done
}

load_saved() {
    local key value
    if [[ -f "$INSTALL_DIR/deployment-private.conf" ]]; then
        while IFS='=' read -r key value; do
            case "$key" in
                domain) [[ -n "$DOMAIN" ]] || DOMAIN=$value ;;
                project) [[ "$PROJECT" != ai-doll-server ]] || PROJECT=$value ;;
            esac
        done < "$INSTALL_DIR/deployment-private.conf"
    fi
}

compose() { docker compose --project-name "$PROJECT" --project-directory "$INSTALL_DIR/deploy/direct-server" "$@"; }

docker_ready() {
    if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
        docker info >/dev/null 2>&1 || die 'Docker 已安装但未运行。请启动 Docker 后重试，不会重装已有引擎。'
        return
    fi
    # Do not replace another engine, container runtime or another apt source.
    command -v docker >/dev/null && die '已有 Docker 缺少 Compose 插件。请按 Docker 官方说明安装插件后重试。'
    [[ -f /etc/os-release ]] || die '无法识别系统，请先安装 Docker Engine 与 Compose。'
    . /etc/os-release
    [[ "$ID" == ubuntu || "$ID" == debian ]] || die '此系统请先安装 Docker Engine 与 Compose，再运行安装入口。'
    local suite=${UBUNTU_CODENAME:-${VERSION_CODENAME:-}} arch package
    [[ "$suite" =~ ^[a-z]+$ ]] || die '无法识别系统版本。'
    for package in docker.io podman-docker containerd runc; do
        if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -qx 'install ok installed'; then
            die "检测到已有 $package。安装器不会删除已有运行环境，请先按官方说明准备 Docker。"
        fi
    done
    [[ ! -e /etc/apt/sources.list.d/docker.sources && ! -e /etc/apt/sources.list.d/docker.list ]] ||
        die '检测到已有 Docker apt 源，请修复原安装后重试。'
    printf '准备 Docker 官方安装源与 Compose…\n'
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl
    install -m 0755 -d /etc/apt/keyrings
    curl --proto '=https' --tlsv1.2 -fsSL "https://download.docker.com/linux/$ID/gpg" -o /etc/apt/keyrings/docker.asc
    chmod 0644 /etc/apt/keyrings/docker.asc
    arch=$(dpkg --print-architecture)
    cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/$ID
Suites: $suite
Components: stable
Architectures: $arch
Signed-By: /etc/apt/keyrings/docker.asc
EOF
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
    docker info >/dev/null 2>&1 || die 'Docker 未能启动。请检查 systemctl status docker。'
}

download_source() {
    local expected actual member listing types
    TEMP_DIR=$(mktemp -d /tmp/ai-doll-install.XXXXXXXX)
    curl --proto '=https' --tlsv1.2 -fsSL --retry 2 "$DOWNLOAD_BASE/$PACKAGE" -o "$TEMP_DIR/package.tar.gz"
    curl --proto '=https' --tlsv1.2 -fsSL --retry 2 "$DOWNLOAD_BASE/$PACKAGE.sha256" -o "$TEMP_DIR/package.sha256"
    read -r expected _ < "$TEMP_DIR/package.sha256"
    [[ "$expected" =~ ^[0-9a-f]{64}$ ]] || die '软件包校验文件无效。'
    actual=$(sha256sum "$TEMP_DIR/package.tar.gz"); actual=${actual%% *}
    [[ "$expected" == "$actual" ]] || die '软件包下载校验失败，请重新下载。'
    # Reject traversal, links and special files before extracting as root.
    listing=$(tar -tzf "$TEMP_DIR/package.tar.gz")
    while IFS= read -r member; do
        [[ "$member" != /* && "$member" != *'../'* && "$member" != '..' ]] || die '软件包包含非法路径。'
    done <<< "$listing"
    types=$(tar -tvzf "$TEMP_DIR/package.tar.gz")
    if grep -q '^[^d-]' <<< "$types"; then die '软件包包含链接或特殊文件。'; fi
    mkdir "$TEMP_DIR/source"
    tar --no-same-owner --no-same-permissions -xzf "$TEMP_DIR/package.tar.gz" -C "$TEMP_DIR/source"
    SOURCE_DIR="$TEMP_DIR/source"
}

owner_token() { compose exec -T doll python tools/direct_server.py --data-dir /data --show-token; }

verify_https() {
    local token=$1 body identity
    # No insecure TLS flag, and no credentials placed in curl's command line.
    body=$(printf 'url = "https://%s/api/server"\nheader = "Authorization: Bearer %s"\n' "$DOMAIN" "$token" |
        curl --config - --proto '=https' --tlsv1.2 -fsS --connect-timeout 3 --max-time 5 2>/dev/null) || return 1
    identity=$(printf 'installation:%s' "$token" | sha256sum); identity=${identity%% *}
    [[ "$body" == *"\"installation_id\": \"$identity\""* && "$body" == *"\"server_url\": \"https://$DOMAIN\""* ]]
}

wait_https() {
    local token=$1 deadline=$((SECONDS+WAIT_SEC))
    printf '服务已启动，正在校验证书与域名连接…\n'
    until verify_https "$token"; do
        if (( SECONDS >= deadline )); then
            printf 'HTTPS 尚未通过验证。检查域名 A/AAAA、云安全组 80/443 和证书日志：sudo ai-doll-server logs\n' >&2
            printf '修复后运行 sudo ai-doll-server start 重试；服务和数据已保留。\n' >&2
            return 2
        fi
        sleep 3
    done
}

show_link() {
    local token=$1
    printf 'https://%s/#connect=%s\n' "$DOMAIN" "$token" > "$INSTALL_DIR/connection-private.txt"
    chmod 0600 "$INSTALL_DIR/connection-private.txt"
    printf '\n管理页面（打开后自动连接，无需娃娃账号）：\n'
    cat "$INSTALL_DIR/connection-private.txt"
    printf '\n设备服务器地址：https://%s\n' "$DOMAIN"
}

main() {
    while (( $# )); do
        case "$1" in
            --domain|--install-dir|--bin-dir|--project|--action|--wait-sec)
                (( $# >= 2 )) || die "$1 缺少参数。"
                case "$1" in
                    --domain) DOMAIN=$2 ;; --install-dir) INSTALL_DIR=$2 ;; --bin-dir) BIN_DIR=$2 ;;
                    --project) PROJECT=$2; PROJECT_SPECIFIED=true ;; --action) ACTION=$2 ;; --wait-sec) WAIT_SEC=$2 ;;
                esac; shift 2 ;;
            --dry-run) DRY_RUN=true; shift ;; -h|--help) usage; return ;;
            *) die "未知选项：$1" ;;
        esac
    done
    [[ "$INSTALL_DIR" == /* && "$INSTALL_DIR" != / && "$INSTALL_DIR" != *'/../'* && "$INSTALL_DIR" != */.. ]] || die '安装目录必须为明确的绝对子目录。'
    [[ "$BIN_DIR" == /* ]] || die '命令目录必须为绝对路径。'
    [[ "$WAIT_SEC" =~ ^[0-9]+$ && "$WAIT_SEC" -ge 1 && "$WAIT_SEC" -le 600 ]] || die '等待时间需为 1～600 秒。'
    case "$ACTION" in install|start|stop|restart|status|link|logs) ;; *) die '不支持的操作。' ;; esac
    load_saved
    choose_domain
    [[ "$PROJECT" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || die 'Compose 项目名无效。'
    if $DRY_RUN; then
        printf '预览：安装目录 %s；项目 %s；HTTPS https://%s。\n' "$INSTALL_DIR" "$PROJECT" "$DOMAIN"
        printf '缺少 Docker 时使用官方 apt 源；校验下载包；生成配置；启动应用与 Caddy；验证 HTTPS。不会执行系统修改。\n'
        return
    fi
    [[ "$(uname -s)" == Linux ]] || die '此入口在远程 Linux 服务器上运行。Windows 本机使用 AI_Doll.cmd。'
    [[ "$(id -u)" == 0 ]] || die '请使用 sudo bash Install_Server.sh 运行。'
    if [[ "$ACTION" != install ]]; then
        [[ -f "$INSTALL_DIR/deployment-private.conf" ]] || die '未找到此项目的安装记录。'
        case "$ACTION" in
            stop) compose stop ;;
            logs) compose logs --tail 60 doll https ;;
            link)
                if [[ -f "$INSTALL_DIR/connection-private.txt" ]]; then cat "$INSTALL_DIR/connection-private.txt"
                else
                    local link_token
                    link_token=$(owner_token) || die '服务未运行，先执行 start。'
                    [[ "$link_token" =~ ^[0-9a-f]{64}$ ]] || die '未读取到管理连接。'
                    show_link "$link_token"
                fi ;;
            status)
                compose ps
                if verify_https "$(owner_token)"; then printf 'HTTPS 与本安装的服务验证通过。\n'; else die 'HTTPS 或服务尚不可用。'; fi ;;
            start|restart)
                if [[ "$ACTION" == restart ]]; then compose restart; else compose up -d --wait --wait-timeout 120; fi
                wait_https "$(owner_token)"
                show_link "$(owner_token)" ;;
        esac
        return
    fi
    if [[ -d "$INSTALL_DIR" && ! -f "$INSTALL_DIR/deployment-private.conf" && -n "$(ls -A "$INSTALL_DIR" | grep -v '^\.install.lock$')" ]]; then
        die '目标目录已有其他文件。请使用空目录，或原安装目录；不会覆盖未知工程。'
    fi
    printf '\n[1/4] 检查域名与服务器环境…\n'
    command -v curl >/dev/null || { apt-get update; DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl; }
    getent ahosts "$DOMAIN" >/dev/null || die '域名尚未解析。请先设置 A/AAAA 指向服务器，再重试。'
    docker_ready
    if [[ ! -f "$INSTALL_DIR/deployment-private.conf" && -n "$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT")" ]]; then
        $PROJECT_SPECIFIED || die '此 Compose 项目已存在，未接管。请核对原项目与数据卷后显式指定 --project。'
        local service
        while IFS= read -r service; do
            [[ "$service" == doll || "$service" == https ]] || die '该项目包含其他服务，不会接管。'
        done < <(docker ps -a --filter "label=com.docker.compose.project=$PROJECT" --format '{{.Label "com.docker.compose.service"}}')
    fi
    # A lock protects two simultaneous installations of this directory.
    mkdir -p "$INSTALL_DIR"
    exec 9> "$INSTALL_DIR/.install.lock"
    flock -n 9 || die '同一目录的安装正在进行，请稍后重试。'
    SOURCE_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
    printf '[2/4] 准备服务代码与配置…\n'
    if [[ ! -f "$SOURCE_DIR/deploy/direct-server/compose.yml" ]]; then download_source; fi
    [[ -f "$SOURCE_DIR/tools/direct_server.py" && -f "$SOURCE_DIR/requirements-server.txt" ]] || die '代码包不完整。'
    umask 077
    # Persist ownership before copying, so an interrupted first install can retry.
    printf 'domain=%s\nproject=%s\nversion=%s\n' "$DOMAIN" "$PROJECT" "$APP_VERSION" > "$INSTALL_DIR/deployment-private.conf"
    if [[ "$SOURCE_DIR" != "$INSTALL_DIR" ]]; then
        umask 022
        mkdir -p "$INSTALL_DIR/tools" "$INSTALL_DIR/deploy/direct-server"
        cp -- "$SOURCE_DIR"/tools/*.{py,js,html} "$INSTALL_DIR/tools/"
        cp -- "$SOURCE_DIR/requirements-server.txt" "$SOURCE_DIR/Install_Server.sh" "$INSTALL_DIR/"
        cp -- "$SOURCE_DIR/deploy/direct-server/compose.yml" "$SOURCE_DIR/deploy/direct-server/Caddyfile" \
            "$SOURCE_DIR/deploy/direct-server/Dockerfile" "$SOURCE_DIR/deploy/direct-server/Dockerfile.dockerignore" "$INSTALL_DIR/deploy/direct-server/"
    fi
    umask 077
    printf 'DOLL_DOMAIN=%s\n' "$DOMAIN" > "$INSTALL_DIR/deploy/direct-server/.env"
    printf 'domain=%s\nproject=%s\nversion=%s\n' "$DOMAIN" "$PROJECT" "$APP_VERSION" > "$INSTALL_DIR/deployment-private.conf"
    mkdir -p "$BIN_DIR"
    {
        printf '#!/usr/bin/env bash\nset -e\n'
        printf 'exec bash %q --install-dir %q --action "${1:-status}"\n' "$INSTALL_DIR/Install_Server.sh" "$INSTALL_DIR"
    } > "$BIN_DIR/ai-doll-server"
    chmod 0755 "$BIN_DIR/ai-doll-server"
    compose config --quiet
    printf '[3/4] 构建并启动接收服务和 HTTPS…\n'
    compose up -d --build --wait --wait-timeout 120
    local token
    token=$(owner_token)
    [[ "$token" =~ ^[0-9a-f]{64}$ ]] || die '服务未能生成管理连接，请检查服务日志。'
    printf '[4/4] 检查 HTTPS 证书与服务…\n'
    wait_https "$token"
    printf '\n远程部署与 HTTPS 验证通过。\n'
    show_link "$token"
    printf '在管理页点击“生成设备连接配置”，用手机将其粘贴到设备“直连服务器”设置并保存。收到实际上传后才显示在线。\n'
    printf '常用操作：sudo ai-doll-server status / stop / start / restart / link / logs\n'
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then main "$@"; fi
