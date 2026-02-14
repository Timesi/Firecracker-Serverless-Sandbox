FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive

# 安装基础工具：Python3，以及必要的系统工具
RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    util-linux \
    && rm -rf /var/lib/apt/lists/*

# 设置主机名
RUN echo "my-microvm" > /etc/hostname

# 设置 root 密码
RUN echo "root:root" | chpasswd

# 允许串口登录
RUN echo "ttyS0" >> /etc/securetty

# 创建必要挂载点目录
RUN mkdir -p /proc /sys /dev /tmp /sbin /etc/init.d

# 注入代码执行文件
COPY guest/supervisor.py /usr/bin/supervisor.py
COPY guest/kernel.py /usr/bin/kernel.py

# 先把内容写到一个临时文件里
# ----------------------------------------------------------------------
# 手动编写极简 Init 脚本 (/sbin/init)
#
# 为了极速启动，我们不使用 Systemd 或 SysVinit，而是直接通过 Shell 脚本初始化系统。
# 这使得启动过程仅需几毫秒。
# ----------------------------------------------------------------------
RUN cat > /sbin/init.tmp <<'EOF'
#!/bin/sh
# 挂载必要的虚拟文件系统
mount -t proc proc /proc
mount -t sysfs sys /sys
mount -t devtmpfs none /dev

# 关键安全配置：
# 因为 Rootfs 是以只读 (Read-Only) 模式挂载的，我们必须把需要写入的目录挂载为 tmpfs (内存盘)。
# 这样不仅保护了镜像，还保证了每次重启后产生的垃圾文件都会自动消失 (Ephemeral Storage)。
# 挂载 /tmp 为纯内存盘
mount -t tmpfs tmpfs /tmp
# 创建一个专用的纯内存工作区，分配 256MB
mkdir -p /workspace
mount -t tmpfs -o size=256m tmpfs /workspace

hostname my-microvm

[ -c /dev/null ] || mknod -m 666 /dev/null c 1 3
[ -c /dev/random ] || mknod -m 666 /dev/random c 1 8
[ -c /dev/urandom ] || mknod -m 666 /dev/urandom c 1 9
[ -c /dev/zero ] || mknod -m 666 /dev/zero c 1 5
[ -c /dev/console ] || mknod -m 600 /dev/console c 5 1
[ -c /dev/tty ] || mknod -m 666 /dev/tty c 5 0
[ -c /dev/ttyS0 ] || mknod -m 660 /dev/ttyS0 c 4 64

# 因为根目录只读，日志必须写到 /tmp 下
echo "启动 Supervisor 守护进程..."
nohup python3 /usr/bin/supervisor.py > /tmp/supervisor.log 2>&1 &

echo ""
echo "========================================"
echo "🎉 Serverless Sandbox 启动成功! (Read-Only Mode)"
echo "========================================"
echo ""

exec /bin/bash --login
EOF

# 删除所有 \r 字符，写入最终的 /sbin/init，并赋予执行权限
RUN tr -d '\r' < /sbin/init.tmp > /sbin/init && \
    rm /sbin/init.tmp && \
    chmod +x /sbin/init