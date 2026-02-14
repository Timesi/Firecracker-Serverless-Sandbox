#!/bin/bash
set -e

WORK_DIR="/tmp/firecracker-build-$(date +%s)"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FINAL_RESOURCES_DIR="$PROJECT_DIR/resources"

RESOURCES_DIR="$WORK_DIR/resources"
MOUNT_POINT="$WORK_DIR/mount"

echo "=========================================="
echo "Firecracker 磁盘镜像构建脚本"
echo "=========================================="

# 准备工作目录
rm -rf "$WORK_DIR"
mkdir -p "$RESOURCES_DIR" "$MOUNT_POINT"

# 创建磁盘
echo "- 创建 512MB 磁盘镜像..."
dd if=/dev/zero of="$RESOURCES_DIR/rootfs.ext4" bs=1M count=512
mkfs.ext4 -q "$RESOURCES_DIR/rootfs.ext4"

# 挂载并填充
echo "- 挂载磁盘..."
sudo mount "$RESOURCES_DIR/rootfs.ext4" "$MOUNT_POINT"

echo "- 构建并导出 Docker 镜像..."
cd "$PROJECT_DIR"
docker build -t my-vm-image -f builder/Dockerfile .

id=$(docker create my-vm-image)
docker export "$id" | sudo tar -x -C "$MOUNT_POINT"
docker rm -v "$id"

# 清理卸载
echo "- 卸载磁盘..."
sudo umount "$MOUNT_POINT"

# 复制到项目目录
echo "- 保存到项目目录..."
mkdir -p "$FINAL_RESOURCES_DIR"
cp "$RESOURCES_DIR/rootfs.ext4" "$FINAL_RESOURCES_DIR/"

# 清理
rm -rf "$WORK_DIR"

echo "✅ 完成: $FINAL_RESOURCES_DIR/rootfs.ext4"
