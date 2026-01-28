FROM alpine:latest

# Install build dependencies and runtime libraries
RUN apk add --no-cache \
    build-base \
    git \
    libusb-dev \
    eudev-dev \
    pkgconfig \
    libusb

# Clone and build minichlink
RUN git clone https://github.com/cnlohr/ch32v003fun.git /tmp/ch32v003fun && \
    cd /tmp/ch32v003fun/minichlink && \
    make && \
    cp minichlink /usr/local/bin/ && \
    chmod +x /usr/local/bin/minichlink && \
    rm -rf /tmp/ch32v003fun

WORKDIR /work

# Keep container running
CMD ["sleep", "infinity"]
