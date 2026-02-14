import socket
import json
import struct
import subprocess

PORT = 8000
KERNEL_CMD = ["python3", "/usr/bin/kernel.py"]

class KernelManager:
    def __init__(self):
        self.process = None

    def start_kernel(self):
        """如果 Kernel 不存在或已崩溃，就拉起一个新的"""
        if self.process is None or self.process.poll() is not None:
            print("(Re)starting Kernel Process...")
            # 启动子进程，并将输入输出管道化
            self.process = subprocess.Popen(
                KERNEL_CMD,                 # ["python3", "/usr/bin/kernel.py"]
                stdin=subprocess.PIPE,      # 标准输入重定向为管道
                stdout=subprocess.PIPE,     # 标准输出重定向为管道
                text=True,                  # 文本模式（自动编解码）
                bufsize=1                   # 行缓冲
            )
    
    def execute_code(self, code):
        """派发代码给 Kernel"""
        self.start_kernel() # 确保 Kernel 活着
        
        try:
            # 1. 把代码塞进管道发给 Kernel
            req_str = json.dumps({"code": code}) + "\n"
            self.process.stdin.write(req_str)
            self.process.stdin.flush()

            # 2. 在管道另一头等 Kernel 的结果
            resp_str = self.process.stdout.readline()
            
            if not resp_str:
                # 如果没读到数据，说明 Kernel 进程被底层杀死了 (比如内存溢出或 os._exit)
                return {"status": "error", "output": "Kernel 核心进程崩溃死亡！Supervisor 将在下次请求时自动重启它。"}
                
            return json.loads(resp_str)
        except Exception as e:
            return {"status": "error", "output": f"Supervisor 通信错误: {e}"}
    
def main():
    s = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    s.bind((socket.VMADDR_CID_ANY, PORT))
    s.listen()
    print(f"Supervisor 守护进程启动，监听 VSock:{PORT}...")

    km = KernelManager()
    km.start_kernel()

    while True:
        try:
            conn, addr = s.accept()
            raw_len = conn.recv(4)
            if not raw_len:
                conn.close()
                continue
                
            msg_len = struct.unpack('>I', raw_len)[0]
            data = conn.recv(msg_len).decode()

            req = json.loads(data)
            code = req.get("code", "")

            # 交给 Manager 处理，Supervisor 本身不执行代码
            resp = km.execute_code(code)

            resp_bytes = json.dumps(resp).encode()
            conn.sendall(struct.pack('>I', len(resp_bytes)))
            conn.sendall(resp_bytes)
            conn.close()
        except Exception as e:
            print(f"VSock Loop Error: {e}")

if __name__ == "__main__":
    main()