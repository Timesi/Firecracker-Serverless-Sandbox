# Firecracker Serverless Sandbox (Demo)

一个基于 [AWS Firecracker](https://firecracker-microvm.github.io/) 构建的高性能、安全的代码执行沙盒Demo项目。

本项目演示了如何利用 Firecracker 的 **Snapshot（快照）** 技术实现毫秒级的虚拟机启动，并通过 **Jailer** 进行严格的安全隔离，提供类似 AWS Lambda 的 Serverless 计算环境。

## ✨ 特性

- **毫秒级启动**: 利用快照恢复机制，从预热状态瞬间唤醒虚拟机。
- **高安全性**: 使用 Firecracker + Jailer 进行硬隔离，配合只读 Rootfs。
- **轻量级**: 极低的内存占用和资源消耗。
- **简单 API**: 提供 RESTful API 接口管理沙盒生命周期。
- **Host-Guest 通信**: 使用 VSock 实现宿主机与虚拟机的高效通信。

## 🔒 安全机制

1. **Jailer**: 所有虚拟机都在 `chroot` 环境中运行，限制了文件系统访问。
2. **Cgroups**: 限制 CPU 和 内存使用。
3. **Seccomp**: 限制系统调用。
4. **Read-Only Rootfs**: 根文件系统以只读模式挂载，防止恶意修改。
5. **Ephemeral Storage**: `/tmp` 和 `/workspace` 挂载为 `tmpfs` (内存盘)，重启即丢失。

## 🛠️ 环境要求

- **操作系统**: Linux 或 Windows (WSL2)。
- **虚拟化支持**: 必须支持 KVM (`/dev/kvm` 必须存在且可访问)。
- **依赖工具**:
  - Docker (用于构建 Rootfs)
  - Python 3.8+
  - `curl` (用于测试)

## 📂 目录结构

```text
.
├── app/                 # Python 后端源码
│   ├── api.py           # FastAPI 入口
│   ├── vmm.py           # 虚拟机管理器 (Firecracker 封装)
│   ├── client.py        # VSock 客户端 (与 VM 内部通信)
│   └── pool.py          # 沙盒池管理
├── bin/                 # 二进制文件存放 (需自行下载)
│   ├── firecracker
│   └── jailer
├── builder/             # Rootfs 构建工具
│   ├── Dockerfile       # 虚拟机内部环境定义
│   └── build_disk.sh    # 构建脚本
├── resources/           # 运行时资源 (自动生成)
│   ├── vmlinux          # Linux 内核
│   ├── rootfs.ext4      # 根文件系统
│   ├── vm.mem           # 内存快照
│   └── vm.snap          # 虚拟机状态快照
├── create_snapshot.py   # 快照制作脚本
├── requirements.txt     # Python 依赖包
└── README.md            # 项目说明文档
```

## 🚀 快速开始

### 1. 准备环境

确保你的用户有权限访问 KVM，并且安装了必要的 Python 库：

```bash
pip install fastapi uvicorn requests
```

下载 Firecracker 和 Jailer 二进制文件到 `bin/` 目录，并赋予执行权限。
下载 Linux Kernel (`vmlinux`) 到 `resources/` 目录。
```
# 下载firecracker
mkdir -p bin
cd bin
curl -L https://github.com/firecracker-microvm/firecracker/releases/download/v1.6.0/firecracker-v1.6.0-x86_64.tgz | tar -xz

# 提取 firecracker
mv release-v1.6.0-x86_64/firecracker-v1.6.0-x86_64 ./bin/firecracker

# 提取 jailer
mv release-v1.6.0-x86_64/jailer-v1.6.0-x86_64 ./bin/jailer

# 下载内核
mkdir -p resources
curl -fsSL https://s3.amazonaws.com/spec.ccfc.min/img/quickstart_guide/x86_64/kernels/vmlinux.bin -o resources/vmlinux
```

### 2. 构建 Rootfs 磁盘镜像

制作基础的文件系统镜像，包含 Python 环境和 Supervisor：

```bash
cd builder
./build_disk.sh
```

这将生成 `resources/rootfs.ext4`。

### 3. 制作启动快照

启动一个模板虚拟机，等待其初始化完毕后冻结状态并导出快照：

```bash
# 需要 root 权限运行，因为涉及 firecracker 进程操作
sudo python3 create_snapshot.py
```

成功后会在 `resources/` 下生成 `vm.mem` 和 `vm.snap`。

### 4. 启动 API 服务

```bash
# 必须使用 sudo，因为 Jailer 需要 root 权限来设置 cgroup 和 chroot
sudo uvicorn app.api:app --host 0.0.0.0 --port 8080
```

### 5. 测试沙盒

**创建一个新沙盒:**

```bash
curl -X POST http://localhost:8080/sandbox
# 返回: {"vm_id": "vm-xxxxxxxx", "status": "running"}
```

**在沙盒中执行代码:**

```bash
curl -X POST http://localhost:8080/sandbox/{vm_id}/execute \
  -H "Content-Type: application/json" \
  -d '{"code": "print(1 + 1)"}'
# over VSock -> VM Python Agent -> Supervisor -> Result
```

**销毁沙盒:**

```bash
curl -X DELETE http://localhost:8080/sandbox/{vm_id}
```
