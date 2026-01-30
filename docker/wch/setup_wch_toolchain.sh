#!/bin/bash
# WCH Toolchain Setup Script
# Downloads and installs WCH official RISC-V toolchain from wch-toolchain-mirror
# Replaces PlatformIO-based toolchain with official WCH MounRiverStudio components

set -e  # Exit on error

# Configuration
DEFAULT_INSTALL_DIR="/opt/wch-toolchain"
DEFAULT_GIT_URL="https://github.com/kazcomy/wch-toolchain-mirror.git"
INSTALL_DIR="${WCH_TOOLCHAIN:-$DEFAULT_INSTALL_DIR}"
TOOLCHAIN_GIT_URL="${WCH_TOOLCHAIN_URL:-$DEFAULT_GIT_URL}"  # Set via environment variable (git repo URL)
TOOLCHAIN_GIT_REF="${WCH_TOOLCHAIN_REF:-}"  # Optional git ref (branch/tag/commit)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    log_info "Checking dependencies..."

    local missing_deps=()

    for cmd in git git-lfs tar sudo; do
        if ! command -v $cmd &> /dev/null; then
            missing_deps+=($cmd)
        fi
    done

    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        log_info "Install with: sudo apt install ${missing_deps[*]}"
        exit 1
    fi

    log_info "All dependencies satisfied"
}

download_toolchain() {
    if [ -z "$TOOLCHAIN_GIT_URL" ]; then
        log_error "WCH_TOOLCHAIN_URL environment variable not set" >&2
        log_info "Please set it to your wch-toolchain-mirror git URL:" >&2
        log_info "  export WCH_TOOLCHAIN_URL=https://github.com/your-private-repo/wch-toolchain-mirror.git" >&2
        exit 1
    fi

    local tmp_dir="/tmp/wch-toolchain-src"
    rm -rf "$tmp_dir"
    mkdir -p "$tmp_dir"

    log_info "Cloning WCH toolchain repo from $TOOLCHAIN_GIT_URL..." >&2
    git clone --depth 1 "$TOOLCHAIN_GIT_URL" "$tmp_dir" 1>&2

    log_info "Fetching Git LFS objects..." >&2
    git -C "$tmp_dir" lfs install --local 1>&2
    git -C "$tmp_dir" lfs pull 1>&2

    if [ -n "$TOOLCHAIN_GIT_REF" ]; then
        log_info "Checking out ref: $TOOLCHAIN_GIT_REF" >&2
        git -C "$tmp_dir" fetch --depth 1 origin "$TOOLCHAIN_GIT_REF" 1>&2
        git -C "$tmp_dir" checkout --detach "$TOOLCHAIN_GIT_REF" 1>&2
        git -C "$tmp_dir" lfs pull 1>&2
    fi

    if [ ! -d "$tmp_dir" ]; then
        log_error "Clone failed"
        exit 1
    fi

    log_info "Clone complete: $tmp_dir" >&2
    printf '%s\n' "$tmp_dir"
}

extract_toolchain() {
    local src_dir="$1"
    local archive_path=""
    local archives=()

    log_info "Creating installation directory: $INSTALL_DIR"
    sudo mkdir -p "$INSTALL_DIR"

    while IFS= read -r -d '' file; do
        archives+=("$file")
    done < <(find "$src_dir" -maxdepth 2 -type f \( -name "*.tar.gz" -o -name "*.tgz" -o -name "*.tar.xz" -o -name "*.txz" \) -print0)

    if [ ${#archives[@]} -eq 0 ]; then
        log_error "No toolchain archive found in cloned repo"
        exit 1
    elif [ ${#archives[@]} -gt 1 ]; then
        log_error "Multiple toolchain archives found. Please keep only one:"
        for file in "${archives[@]}"; do
            log_error "  - $file"
        done
        exit 1
    fi

    archive_path="${archives[0]}"

    log_info "Extracting toolchain archive: $archive_path"
    sudo tar -xf "$archive_path" -C "$INSTALL_DIR"

    log_info "Extraction complete"
}

verify_toolchain() {
    log_info "Verifying toolchain installation..."

    local gcc_path1="$INSTALL_DIR/Toolchain/RISC-V Embedded GCC12/bin/riscv-wch-elf-gcc"
    local gcc_path2="$INSTALL_DIR/RISC-V Embedded GCC12/bin/riscv-wch-elf-gcc"
    local gcc_path3="$INSTALL_DIR/toolchain/RISC-V-Embedded-GCC12/bin/riscv-wch-elf-gcc"
    local gcc_path4="$INSTALL_DIR/toolchain/RISC-V-Embedded-GCC12/riscv-wch-elf/bin/riscv-wch-elf-gcc"
    local openocd_path1="$INSTALL_DIR/OpenOCD/OpenOCD/bin/openocd"
    local openocd_path2="$INSTALL_DIR/OpenOCD/bin/openocd"
    local openocd_scripts1="$INSTALL_DIR/OpenOCD/OpenOCD/scripts"
    local openocd_scripts2="$INSTALL_DIR/OpenOCD/scripts"

    local errors=0

    # Check for GCC (try both possible locations)
    if [ -f "$gcc_path1" ]; then
        log_info "Found GCC at: $gcc_path1"
        GCC_PATH="$gcc_path1"
    elif [ -f "$gcc_path2" ]; then
        log_info "Found GCC at: $gcc_path2"
        GCC_PATH="$gcc_path2"
    elif [ -f "$gcc_path3" ]; then
        log_info "Found GCC at: $gcc_path3"
        GCC_PATH="$gcc_path3"
    elif [ -f "$gcc_path4" ]; then
        log_info "Found GCC at: $gcc_path4"
        GCC_PATH="$gcc_path4"
    else
        log_error "GCC not found at expected locations:"
        log_error "  - $gcc_path1"
        log_error "  - $gcc_path2"
        log_error "  - $gcc_path3"
        log_error "  - $gcc_path4"
        errors=$((errors + 1))
    fi

    # Check for OpenOCD
    if [ -f "$openocd_path1" ]; then
        log_info "Found OpenOCD at: $openocd_path1"
    elif [ -f "$openocd_path2" ]; then
        log_info "Found OpenOCD at: $openocd_path2"
    else
        log_error "OpenOCD not found at expected locations:"
        log_error "  - $openocd_path1"
        log_error "  - $openocd_path2"
        errors=$((errors + 1))
    fi

    # Check for wch-riscv.cfg
    if [ -f "$openocd_scripts1/wch-riscv.cfg" ] || [ -f "$openocd_scripts2/wch-riscv.cfg" ]; then
        log_info "Found WCH RISC-V configuration"
    else
        log_warn "wch-riscv.cfg not found, may need manual configuration"
    fi

    if [ $errors -gt 0 ]; then
        log_error "Verification failed with $errors error(s)"
        exit 1
    fi

    log_info "Toolchain verification successful"
}

test_toolchain() {
    log_info "Testing toolchain..."

    # Test GCC version
    local gcc_version=$("$GCC_PATH" --version | head -n 1)
    log_info "GCC version: $gcc_version"

    # Test OpenOCD version
    local openocd_cmd="$INSTALL_DIR/OpenOCD/OpenOCD/bin/openocd"
    if [ ! -x "$openocd_cmd" ]; then
        openocd_cmd="$INSTALL_DIR/OpenOCD/bin/openocd"
    fi
    local openocd_version=$("$openocd_cmd" --version 2>&1 | head -n 1 || true)
    log_info "OpenOCD version: $openocd_version"
}

setup_environment() {
    log_info "Setting up environment..."

    local shell_rc=""
    if [ -n "$BASH_VERSION" ]; then
        shell_rc="$HOME/.bashrc"
    elif [ -n "$ZSH_VERSION" ]; then
        shell_rc="$HOME/.zshrc"
    fi

    if [ -n "$shell_rc" ]; then
        log_info "Add the following to your $shell_rc:"
        echo ""
        echo "  export WCH_TOOLCHAIN=$INSTALL_DIR"
        echo "  export PATH=\$WCH_TOOLCHAIN/Toolchain/RISC-V Embedded GCC12/bin:\$PATH"
        echo "  export PATH=\$WCH_TOOLCHAIN/OpenOCD/OpenOCD/bin:\$PATH"
        echo ""
    fi
}

cleanup() {
    log_info "Cleaning up temporary files..."
    rm -rf /tmp/wch-toolchain-src
}

main() {
    log_info "WCH Toolchain Setup"
    log_info "Installation directory: $INSTALL_DIR"
    echo ""

    check_dependencies

    local src_path
    src_path=$(download_toolchain)

    extract_toolchain "$src_path"
    verify_toolchain
    test_toolchain

    cleanup

    echo ""
    log_info "WCH Toolchain installation complete!"
    setup_environment

    log_info "To use the toolchain in this session:"
    echo "  export WCH_TOOLCHAIN=$INSTALL_DIR"
}

# Run main function
main "$@"
