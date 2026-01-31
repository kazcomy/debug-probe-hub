FROM espressif/idf:release-v5.1

# Add ESP-IDF OpenOCD to PATH
ENV PATH="/opt/esp/tools/openocd-esp32/v0.12.0-esp32-20250707/openocd-esp32/bin:${PATH}"
ENV OPENOCD_SCRIPTS="/opt/esp/tools/openocd-esp32/v0.12.0-esp32-20250707/openocd-esp32/share/openocd/scripts"

# Install OpenOCD for ESP32 (already included in espressif/idf)
# The base image comes with openocd-esp32 pre-installed

# Install additional utilities
RUN apt-get update && apt-get install -y \
    udev \
    usbutils \
    libusb-1.0-0 \
    socat \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work

# Keep container running
CMD ["sleep", "infinity"]
