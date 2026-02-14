import socket, json, os, subprocess, time, shutil

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JAILER_BIN = os.path.join(PROJECT_DIR, "bin", "jailer")
FC_BIN = os.path.join(PROJECT_DIR, "bin", "firecracker")

# 主要依赖快照文件和硬盘
SNAP_SRC = os.path.join(PROJECT_DIR, "resources", "vm.snap")
MEM_SRC = os.path.join(PROJECT_DIR, "resources", "vm.mem")
ROOTFS_SRC = os.path.join(PROJECT_DIR, "resources", "rootfs.ext4")
JAILER_ROOT_DIR = os.environ.get("JAILER_ROOT_DIR", "/srv/jailer/firecracker")
UID = 1000
GID = 1000


class Sandbox:
    """
    Sandbox 类用于封装 Firecracker MicroVM 的生命周期管理。
    它负责：
    1. 准备 Jailer 隔离环境（chroot, cgroups, netns）。
    2. 启动 Firecracker 进程。
    3. 加载预先制作好的 Snapshot（快照）实现毫秒级启动。
    4. 管理 VM 的生命周期（Start/Stop）。
    """
    def __init__(self, vm_id):
        self.vm_id = vm_id
        # 因为在jailer里，所以统一用 3
        self.guest_cid = 3 
        self.jail_dir = os.path.join(JAILER_ROOT_DIR, self.vm_id)
        self.jail_root = f"{self.jail_dir}/root"
        self.api_socket = f"{self.jail_root}/run/firecracker.socket"
        self.process = None

    def _send_config(self, method, endpoint, body=None):
        """
        通过 Unix Domain Socket 向 Firecracker API 发送 HTTP 请求。
        Firecracker 使用无状态的 HTTP API 来控制虚拟机配置。
        """
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        for _ in range(10): # 给 Jailer 多一点点准备时间
            try:
                s.connect(self.api_socket)
                break
            except:
                time.sleep(0.05)
        
        req = f"{method} {endpoint} HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\n"
        if body:
            req += f"Content-Length: {len(json.dumps(body))}\r\n\r\n{json.dumps(body)}"
        else:
            req += "\r\n"
            
        s.sendall(req.encode())
        resp = s.recv(4096).decode()
        s.close()
        if "204" not in resp and "200" not in resp:
            raise Exception(f"VM {self.vm_id} API 失败 [{endpoint}]: {resp}")
        
    def start(self):
        """
        基于快照启动虚拟机。
        流程：
        1. 清理并重建 Jailer 目录。
        2. 硬链接资源文件到 Jailer 目录（避免复制大文件）。
        3. 启动 Jailer (它会 chroot 并 exec Firecracker)。
        4. 发送 API 命令加载快照 (Load Snapshot)。
        5. 修正块设备路径 (因为在 Chroot 环境下路径变了)。
        6. 唤醒虚拟机 (Resume)。
        """
        print(f"[Sandbox {self.vm_id}] 正在启动...")
        start_time = time.perf_counter()

        if os.path.exists(self.jail_dir):
            shutil.rmtree(self.jail_dir)
            
        os.makedirs(f"{self.jail_root}/run", exist_ok=True)

        # 1. 资源准备
        # 使用硬链接
        # 优势：
        # 1. 速度极快（毫秒级），不消耗额外磁盘空间。
        # 2. 安全性：因为快照和 Rootfs 本来就是 Read-Only 的，多个 VM 共享同一个文件 inode 没问题。
        #    哪怕 VM 试图写入，也因为文件系统挂载为 ro 而失败，或者因为 overlayfs (如果有) 隔离。
        #    在这里我们依靠 Firecracker 的只读挂载配置。
        if not os.path.exists(f"{self.jail_root}/vm.snap"):
            os.link(SNAP_SRC, f"{self.jail_root}/vm.snap")
        if not os.path.exists(f"{self.jail_root}/vm.mem"):
            os.link(MEM_SRC, f"{self.jail_root}/vm.mem")
        if not os.path.exists(f"{self.jail_root}/rootfs.ext4"):
            os.link(ROOTFS_SRC, f"{self.jail_root}/rootfs.ext4")
        
        # 确保 Jailer 有权限访问这些文件
        os.system(f"chown -R {UID}:{GID} {self.jail_dir}")

        # 2. 启动jailer
        cmd = [
            JAILER_BIN, "--id", self.vm_id, "--exec-file", FC_BIN,
            "--uid", str(UID), "--gid", str(GID),
            "--", "--api-sock", "/run/firecracker.socket"
        ]
        self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. 加载内存快照
        self._send_config("PUT", "/snapshot/load", {
            "snapshot_path": "vm.snap",
            "mem_backend": {"backend_path": "vm.mem", "backend_type": "File"},
            "enable_diff_snapshots": False
        })

        # 4. 重新挂载硬盘和网络（Firecracker 恢复快照时的硬性要求）
        self._send_config("PATCH", "/drives/rootfs", {
            "drive_id": "rootfs", 
            "path_on_host": "/rootfs.ext4"
        })

        # 5. 唤醒快照
        self._send_config("PATCH", "/vm/state", {"state": "Resumed"})
        
        end_time = time.perf_counter()
        print(f"[Sandbox {self.vm_id}] ✅ 就绪！耗时: {(end_time - start_time)*1000:.1f} ms")

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
        shutil.rmtree(self.jail_dir, ignore_errors=True)
        print(f"[Sandbox {self.vm_id}] 🛑 已销毁")