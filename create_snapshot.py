import socket, json, os, subprocess, time

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
FC_BIN = os.path.join(PROJECT_DIR, "bin", "firecracker")
SOCKET_PATH = "/tmp/firecracker.socket"
VSOCK_PATH = "/run/v.sock"
MEM_FILE = os.path.join(PROJECT_DIR, "resources", "vm.mem")
SNAPSHOT_FILE = os.path.join(PROJECT_DIR, "resources", "vm.snap")
RESOURCES_DIR = os.path.join(PROJECT_DIR, "resources")

def send_config(method, endpoint, body=None):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(SOCKET_PATH)
    req = f"{method} {endpoint} HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\n"
    if body:
        req += f"Content-Length: {len(json.dumps(body))}\r\n\r\n{json.dumps(body)}"
    else:
        req += "\r\n"
    s.sendall(req.encode())
    resp = s.recv(4096).decode()
    s.close()
    if "204" not in resp and "200" not in resp:
        raise Exception(f"API 失败 [{endpoint}]:\n{resp}")


def main():
    # ------------------------------------------------------------------
    # 步骤 1: 启动一个全新的虚拟机实例
    # ------------------------------------------------------------------
    # 这个实例只用于制作快照，之后会被销毁。
    print("[1/4] 启动模板虚拟机...")
    os.system(f"rm -f {SOCKET_PATH} {VSOCK_PATH}")
    fc = subprocess.Popen([FC_BIN, "--api-sock", SOCKET_PATH], cwd=RESOURCES_DIR)
    time.sleep(0.5)

    send_config("PUT", "/boot-source", {
        "kernel_image_path": "vmlinux", 
        "boot_args": "console=ttyS0 reboot=k panic=1 pci=off init=/sbin/init"
    })
    send_config("PUT", "/drives/rootfs", {
        "drive_id": "rootfs",
        "path_on_host": "rootfs.ext4",
        "is_root_device": True, "is_read_only": True
    })
    send_config("PUT", "/machine-config", {"vcpu_count": 1, "mem_size_mib": 512})
    
    send_config("PUT", "/vsock", {"vsock_id": "1", "guest_cid": 3, "uds_path": VSOCK_PATH})
    
    send_config("PUT", "/actions", {"action_type": "InstanceStart"})

    # ------------------------------------------------------------------
    # 步骤 2: 等待 VM 启动并运行到就绪状态
    # ------------------------------------------------------------------
    # 这里简单地 Sleep 等待，实际生产中可以通过 VSock 握手来确认 Agent 已就绪。
    # 只有等内部程序完全运行起来并监听端口后，我们制作的快照才是有意义的（Resume 后能立刻响应请求）。
    print("[2/4] 等待虚拟机完全引导，Supervisor 就绪 (等待 3 秒)...")
    time.sleep(3) # 必须等够时间，让内部的 Python 进程启动并监听 8000 端口

    # ------------------------------------------------------------------
    # 步骤 3: 暂停虚拟机 (Pause)
    # ------------------------------------------------------------------
    # 必须先暂停 VM 才能创建一致的内存快照。
    print("[3/4] 冻结虚拟机状态...")
    send_config("PATCH", "/vm/state", {"state": "Paused"})

    # ------------------------------------------------------------------
    # 步骤 4: 创建全量快照 (Snapshot)
    # ------------------------------------------------------------------
    # 导出两部分：
    # 1. vm.mem: 虚拟机的内存内容（RAM dump）
    # 2. vm.snap: 虚拟机的设备状态（CPU 寄存器、设备模型状态等）
    print("[4/4] 导出快照...")
    send_config("PUT", "/snapshot/create", {
        "snapshot_type": "Full",
        "snapshot_path": SNAPSHOT_FILE,
        "mem_file_path": MEM_FILE
    })
    print("✅ 快照制作完成！")
    fc.terminate()

if __name__ == "__main__":
    main()