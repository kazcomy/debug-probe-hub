FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install runtime and build dependencies (including Rust for wlink)
RUN apt-get update && apt-get install -y \
    git \
    git-lfs \
    bash \
    libusb-1.0-0 \
    libusb-1.0-0-dev \
    libhidapi-hidraw0 \
    libhidapi-dev \
    libjaylink0 \
    libudev-dev \
    pkg-config \
    curl \
    build-essential \
    socat \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (needed for wlink)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Build argument for REQUIRED private WCH toolchain repository
ARG WCH_TOOLCHAIN_URL=""
ARG WCH_TOOLCHAIN_REF=""

# Fail fast with helpful error message if WCH_TOOLCHAIN_URL not provided
RUN if [ -z "$WCH_TOOLCHAIN_URL" ]; then \
      echo ""; \
      echo "========================================"; \
      echo "ERROR: WCH_TOOLCHAIN_URL is required"; \
      echo "========================================"; \
      echo ""; \
      echo "WCH OpenOCD binaries cannot be redistributed publicly due to license restrictions."; \
      echo "You MUST provide your own private WCH toolchain repository access."; \
      echo ""; \
      echo "Setup instructions:"; \
      echo "  1. Copy template:"; \
      echo "     cp docker-compose.override.yml.template docker-compose.override.yml"; \
      echo ""; \
      echo "  2. Edit docker-compose.override.yml and set your repository URL with token:"; \
      echo "     WCH_TOOLCHAIN_URL: \"https://YOUR_TOKEN@github.com/YOUR_ORG/wch-toolchain-mirror.git\""; \
      echo ""; \
      echo "  3. Build:"; \
      echo "     docker-compose build debug-box-wch"; \
      echo ""; \
      echo "See README.md for more details."; \
      echo ""; \
      exit 1; \
    fi

ENV WCH_TOOLCHAIN=/opt/wch-toolchain
# Add all possible toolchain paths to PATH
ENV PATH="${WCH_TOOLCHAIN}/OpenOCD/OpenOCD/bin:${WCH_TOOLCHAIN}/OpenOCD/bin:${WCH_TOOLCHAIN}/Toolchain/RISC-V Embedded GCC12/bin:${WCH_TOOLCHAIN}/RISC-V Embedded GCC12/bin:${WCH_TOOLCHAIN}/bin:${PATH}"

# Copy WCH toolchain setup script
COPY setup_wch_toolchain.sh /tmp/
RUN chmod +x /tmp/setup_wch_toolchain.sh

# Install WCH OpenOCD toolchain from private repository
RUN /tmp/setup_wch_toolchain.sh

# Verify OpenOCD installation (check multiple possible paths)
RUN if [ ! -f "${WCH_TOOLCHAIN}/OpenOCD/OpenOCD/bin/openocd" ] && \
       [ ! -f "${WCH_TOOLCHAIN}/OpenOCD/bin/openocd" ] && \
       [ ! -f "${WCH_TOOLCHAIN}/bin/openocd" ] && \
       [ ! -f "/usr/local/bin/openocd" ]; then \
      echo "ERROR: OpenOCD not found after toolchain installation"; \
      echo "Checked paths:"; \
      echo "  - ${WCH_TOOLCHAIN}/OpenOCD/OpenOCD/bin/openocd"; \
      echo "  - ${WCH_TOOLCHAIN}/OpenOCD/bin/openocd"; \
      echo "  - ${WCH_TOOLCHAIN}/bin/openocd"; \
      echo "  - /usr/local/bin/openocd"; \
      exit 1; \
    fi

# Build and install wlink from source for SWDIO debug printing
RUN cargo install wlink --root /usr/local && \
    wlink --version || (echo "ERROR: wlink installation failed" && exit 1)

# Verify wlink installation
RUN which wlink || (echo "ERROR: wlink not in PATH" && exit 1)

WORKDIR /work

# Keep container running
CMD ["sleep", "infinity"]
