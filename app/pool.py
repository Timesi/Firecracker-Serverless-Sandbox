import uuid
from app.vmm import Sandbox

class SandboxPool:
    """
    简单的沙盒池管理器。
    在生产环境中，这里应该是一个更复杂的资源调度器，负责：
    1. 限制并发虚拟机数量。
    2. 自动回收超时或空闲的虚拟机。
    3. 管理 IP 地址分配 (如果使用了网络)。
    """
    def __init__(self):
        self.active_sandboxes = {}
    
    def create_sandbox(self):
        """分配一个新沙盒"""
        # 生成一个随机的短 ID
        vm_id = f"vm-{uuid.uuid4().hex[:8]}"
        sandbox = Sandbox(vm_id)
        sandbox.start()

        self.active_sandboxes[vm_id] = sandbox
        return vm_id
    
    def get_sandbox(self, vm_id):
        return self.active_sandboxes.get(vm_id)

    def destroy_sandbox(self, vm_id):
        if vm_id in self.active_sandboxes:
            self.active_sandboxes[vm_id].stop()
            del self.active_sandboxes[vm_id]

    def destroy_all(self):
        for vm_id in list(self.active_sandboxes.keys()):
            self.destroy_sandbox(vm_id)