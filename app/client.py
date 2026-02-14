import socket, struct, json

def send_code_to_vm(vm_id, code):
    """
    通过 VSock 与虚拟机内部的 Agent 进行通信。
    Firecracker 在宿主机暴露出一个 Unix Socket 文件，对应虚拟机内部的 VSock 设备。
    """
    # 动态拼接这个特定虚拟机的 VSock 路径
    # 路径结构：Jailer Root (/srv/jailer/firecracker) -> VM ID -> root -> run -> v.sock
    uds_path = f"/srv/jailer/firecracker/{vm_id}/root/run/v.sock"
    vm_port = 8000 # 虚拟机内部监听的 VSock 端口

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(uds_path)
    except Exception as e:
        return {"status": "error", "output": f"无法连接到沙盒: {e}"}

    # Firecracker 的 VSock 是多路复用的。
    # 协议规定：连接建立后，必须先发送 "CONNECT <port>\n" 
    # 告诉 Firecracker 我们想要连接到 Guest OS 里的哪个端口。
    s.sendall(f"CONNECT {vm_port}\n".encode())
    
    response = s.recv(1024).decode()
    if not response.startswith("OK"):
        s.close()
        return {"status": "error", "output": "沙盒内部 Agent 未就绪"}

    payload = json.dumps({"code": code}).encode()
    s.sendall(struct.pack('>I', len(payload)))
    s.sendall(payload)

    raw_len = s.recv(4)
    if not raw_len:
        return {"status": "error", "output": "沙盒连接异常断开"}
        
    msg_len = struct.unpack('>I', raw_len)[0]
    
    chunks = []
    bytes_recd = 0
    while bytes_recd < msg_len:
        chunk = s.recv(min(msg_len - bytes_recd, 4096))
        if not chunk: break
        chunks.append(chunk)
        bytes_recd += len(chunk)
        
    s.close()
    return json.loads(b''.join(chunks).decode())