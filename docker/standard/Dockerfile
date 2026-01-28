FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install basic dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    udev \
    usbutils \
    libusb-1.0-0 \
    libusb-1.0-0-dev \
    libudev-dev \
    build-essential \
    git \
    pkg-config \
    autoconf \
    automake \
    libtool \
    libhidapi-dev \
    libftdi1-dev \
    && rm -rf /var/lib/apt/lists/*

# Install OpenOCD
RUN apt-get update && apt-get install -y openocd && rm -rf /var/lib/apt/lists/*

# Install J-Link Software
# Note: You need to download J-Link software manually from SEGGER website
# due to licensing. Place JLink_Linux_*.deb in the build context if needed.
# For now, we'll just document the installation steps:
# wget --post-data 'accept_license_agreement=accepted' https://www.segger.com/downloads/jlink/JLink_Linux_V794e_x86_64.deb
# dpkg -i JLink_Linux_V*.deb

WORKDIR /work

# Keep container running
CMD ["sleep", "infinity"]
